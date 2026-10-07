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

    # run_pipeline executes in a worker thread (asyncio.to_thread); its
    # on_progress callback can't directly await an async DB write, so it
    # schedules one onto this coroutine's event loop instead.
    loop = asyncio.get_running_loop()

    def on_progress(stage: str) -> None:
        asyncio.run_coroutine_threadsafe(_update_progress(job_id, stage), loop)

    try:
        result = await asyncio.to_thread(
            run_pipeline,
            repository.url,
            settings.max_repo_size_mb,
            settings.clone_timeout_seconds,
            on_progress,
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

            # Already running on the event loop here (unlike the pipeline's
            # on_progress stages above) -- set directly, no thread hop needed.
            job.progress = "persisting"

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
            # dependency_edges/call_edges below can resolve path -> file_id
            # and (path, name) -> symbol_id without a flush per row.
            path_to_file_id: dict[str, uuid.UUID] = {}
            symbol_id_by_path_name: dict[tuple[str, str], uuid.UUID] = {}
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
                    symbol_id = uuid.uuid4()
                    # first-definition-wins on a duplicate top-level name in
                    # one file (e.g. two functions named the same via
                    # conditional branches) -- the call graph can only ever
                    # point at one of them.
                    symbol_id_by_path_name.setdefault((file_summary.path, sym.name), symbol_id)
                    session.add(
                        Symbol(
                            id=symbol_id,
                            analysis_id=analysis.id,
                            file_id=file_id,
                            name=sym.name,
                            kind=sym.kind,
                            line_start=sym.line_start,
                            line_end=sym.line_end,
                        )
                    )

            # Flush files/symbols before adding dependency_edges/call_edges:
            # relationships has FK columns pointing at both files and
            # symbols, which SQLAlchemy's automatic flush-order dependency
            # sort does not reliably sequence after files/symbols on its
            # own -- an explicit flush boundary guarantees it.
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

            for call in result.call_edges:
                source_symbol_id = (
                    symbol_id_by_path_name.get((call.source_path, call.source_symbol))
                    if call.source_symbol
                    else None
                )
                target_symbol_id = (
                    symbol_id_by_path_name.get((call.target_path, call.target_symbol))
                    if call.target_path and call.target_symbol
                    else None
                )
                session.add(
                    DependencyEdge(
                        analysis_id=analysis.id,
                        source_file_id=path_to_file_id[call.source_path],
                        target_file_id=path_to_file_id.get(call.target_path) if call.target_path else None,
                        source_symbol_id=source_symbol_id,
                        target_symbol_id=target_symbol_id,
                        type=call.type,
                        called_name=call.callee_name,
                    )
                )

            job.status = "completed"
            job.finished_at = datetime.now(timezone.utc)
            await session.commit()
    except Exception as exc:  # persistence bug shouldn't leave a job stuck "running" forever
        await _mark_failed(job_id, f"Failed to persist analysis results: {exc}")


async def _update_progress(job_id: str, stage: str) -> None:
    """Best-effort/informational: never let a write failure (or a lost
    update, if two progress writes race under pathological speed) affect
    the job itself -- status/error_message remain the authoritative
    completion signal, progress is purely a nicer polling experience.
    """
    try:
        async with async_session_factory() as session:
            job = await session.get(AnalysisJob, uuid.UUID(job_id))
            if job is None:
                return
            job.progress = stage
            await session.commit()
    except Exception:
        pass


async def _mark_failed(job_id: str, error_message: str) -> None:
    async with async_session_factory() as session:
        job = await session.get(AnalysisJob, uuid.UUID(job_id))
        if job is None:
            return
        job.status = "failed"
        job.error_message = error_message
        job.finished_at = datetime.now(timezone.utc)
        await session.commit()
