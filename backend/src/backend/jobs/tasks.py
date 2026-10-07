import asyncio
import uuid
from datetime import datetime, timezone

from analysis_engine.exceptions import AnalysisEngineError
from analysis_engine.pipeline import run_pipeline
from backend.config import settings
from backend.db import async_session_factory
from backend.models import AnalysisJob, Repository


async def analyze_repository_task(ctx: dict, job_id: str) -> None:
    """arq task: clone and validate one AnalysisJob's repository.

    Persisting the analysis result (languages, files) is added once
    detection/parsing land in subsequent commits.
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
        await asyncio.to_thread(
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
