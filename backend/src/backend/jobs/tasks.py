import asyncio
import uuid
from datetime import datetime, timezone

from analysis_engine.exceptions import AnalysisEngineError
from analysis_engine.pipeline import run_pipeline
from backend.config import settings
from backend.db import async_session_factory
from backend.models import Analysis, AnalysisJob, File, Repository


async def analyze_repository_task(ctx: dict, job_id: str) -> None:
    """arq task: clone, detect languages, parse, and persist results for one
    AnalysisJob. The analysis-engine pipeline itself has no DB dependency --
    this task is the only place that touches Postgres.
    """
    async with async_session_factory() as session:
        job = await session.get(AnalysisJob, uuid.UUID(job_id))
        if job is None:
            return

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        await session.commit()

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

        for file_summary in result.files:
            session.add(
                File(
                    analysis_id=analysis.id,
                    path=file_summary.path,
                    language=file_summary.language,
                    line_count=file_summary.line_count,
                    parse_ok=file_summary.parse_ok,
                    size_bytes=file_summary.size_bytes,
                )
            )

        job.status = "completed"
        job.finished_at = datetime.now(timezone.utc)
        await session.commit()


async def _mark_failed(job_id: str, error_message: str) -> None:
    async with async_session_factory() as session:
        job = await session.get(AnalysisJob, uuid.UUID(job_id))
        if job is None:
            return
        job.status = "failed"
        job.error_message = error_message
        job.finished_at = datetime.now(timezone.utc)
        await session.commit()
