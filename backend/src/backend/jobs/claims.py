import uuid
from datetime import timedelta

from sqlalchemy import and_, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models import AnalysisJob


def _claimable_where():
    """A job is claimable if it's pending, or if it's running but its
    started_at is older than the staleness threshold -- computed inside the
    SQL (not pre-computed in Python) so two processes racing to claim near
    the same instant can't both see a job as "stale enough" based on a value
    frozen before either transaction started.
    """
    stale_before = func.now() - timedelta(minutes=settings.stale_job_threshold_minutes)
    return or_(
        AnalysisJob.status == "pending",
        and_(AnalysisJob.status == "running", AnalysisJob.started_at < stale_before),
    )


async def claim_job(session: AsyncSession, job_id: uuid.UUID) -> bool:
    """Atomically claim exactly one job. Returns False if it's already
    running (and not stale) or doesn't exist.

    Safe against concurrent claimers: Postgres serializes the UPDATEs on
    this row, and the loser's WHERE clause is re-evaluated against the
    post-commit row, which no longer matches.
    """
    result = await session.execute(
        update(AnalysisJob)
        .where(AnalysisJob.id == job_id, _claimable_where())
        .values(status="running", started_at=func.now())
    )
    await session.commit()
    return result.rowcount == 1


async def claim_outstanding_jobs(session: AsyncSession) -> list[uuid.UUID]:
    """Atomically claim every pending job and every stale running job in one
    statement. Used by startup reconciliation and the cron sweep script.
    """
    result = await session.execute(
        update(AnalysisJob)
        .where(_claimable_where())
        .values(status="running", started_at=func.now())
        .returning(AnalysisJob.id)
    )
    await session.commit()
    return [row[0] for row in result.fetchall()]
