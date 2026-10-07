import asyncio
import uuid
from datetime import datetime, timezone

from analysis_engine.exceptions import AnalysisEngineError
from analysis_engine.pipeline import run_pipeline
from backend.config import settings
from backend.db import async_session_factory
from backend.jobs.claims import claim_job
from backend.models import Analysis, AnalysisJob, DependencyEdge, File, Repository, Symbol


async def run_analysis_job(job_id: str) -> None:
    """Entry point for a freshly-created job: claim it, then run it.

    Called from the analyzeRepository mutation via FastAPI's BackgroundTasks
    -- runs in the same process, after the response has been sent.
    """
    async with async_session_factory() as session:
        claimed = await claim_job(session, uuid.UUID(job_id))
    if not claimed:
        return
    await execute_claimed_job(job_id)


async def execute_claimed_job(job_id: str) -> None:
    """Clone, detect languages, parse, and persist results for a job that
    has ALREADY been marked 'running' by the caller (claim_job or
    claim_outstanding_jobs). The analysis-engine pipeline itself has no DB
    dependency -- this is the only place that touches Postgres.
    """
    async with async_session_factory() as session:
        job = await session.get(AnalysisJob, uuid.UUID(job_id))
        if job is None:
            return
        repository = await session.get(Repository, job.repository_id)

    try:
        result = await asyncio.to_thread(
            run_pipeline,
            repository.url,
            settings.max_repo_size_mb,
            settings.clone_timeout_seconds,
        )
    except AnalysisEngineError as exc:
        await _mark_failed(job_id, str(exc))
        return
    except Exception as exc:  # unexpected failure -- still record it, never crash the worker silently
        await _mark_failed(job_id, f"Unexpected analysis failure: {exc}")
        return

    try:
        async with async_session_factory() as session:
            job = await session.get(AnalysisJob, uuid.UUID(job_id))

            analysis = Analysis(
                analysis_job_id=job.id,
                repository_id=job.repository_id,
                languages=result.languages,
                total_files=result.total_files,
                total_lines=result.total_lines,
            )
            session.add(analysis)
            await session.flush()

            # Explicit ids (rather than relying on the column's Python-side
            # default, which SQLAlchemy only evaluates at flush time) so
            # dependency_edges below can resolve path -> file_id without a
            # flush per file.
            path_to_file_id: dict[str, uuid.UUID] = {}
            for file_summary in result.files:
                file_id = uuid.uuid4()
                path_to_file_id[file_summary.path] = file_id
                session.add(
                    File(
                        id=file_id,
                        analysis_id=analysis.id,
                        path=file_summary.path,
                        language=file_summary.language,
                        line_count=file_summary.line_count,
                        parse_ok=file_summary.parse_ok,
                        size_bytes=file_summary.size_bytes,
                    )
                )
                for sym in file_summary.symbols:
                    session.add(
                        Symbol(
                            analysis_id=analysis.id,
                            file_id=file_id,
                            name=sym.name,
                            kind=sym.kind,
                            line_start=sym.line_start,
                            line_end=sym.line_end,
                        )
                    )

            # Flush files/symbols before adding dependency_edges:
            # relationships has two FK columns pointing at the same files
            # table (source_file_id, target_file_id), which SQLAlchemy's
            # automatic flush-order dependency sort does not reliably
            # sequence after files on its own -- an explicit flush boundary
            # guarantees it.
            await session.flush()

            for edge in result.dependency_edges:
                session.add(
                    DependencyEdge(
                        analysis_id=analysis.id,
                        source_file_id=path_to_file_id[edge.source_path],
                        target_file_id=path_to_file_id.get(edge.target_path) if edge.target_path else None,
                        type=edge.type,
                        external_module=edge.external_module,
                    )
                )

            job.status = "completed"
            job.finished_at = datetime.now(timezone.utc)
            await session.commit()
    except Exception as exc:  # persistence bug shouldn't leave a job stuck "running" forever
        await _mark_failed(job_id, f"Failed to persist analysis results: {exc}")


async def _mark_failed(job_id: str, error_message: str) -> None:
    async with async_session_factory() as session:
        job = await session.get(AnalysisJob, uuid.UUID(job_id))
        if job is None:
            return
        job.status = "failed"
        job.error_message = error_message
        job.finished_at = datetime.now(timezone.utc)
        await session.commit()
