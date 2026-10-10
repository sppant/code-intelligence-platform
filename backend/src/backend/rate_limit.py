from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models import AnalysisJob


class RateLimitExceededError(Exception):
    """Raised by enforce_rate_limit when a client has exceeded the
    per-IP analysis quota. Propagates as the analyzeRepository mutation's
    GraphQL error (see schema.schema.Mutation.analyze_repository) -- not
    caught/translated anywhere, same as InvalidRepositoryUrlError already
    is.
    """


async def enforce_rate_limit(session: AsyncSession, client_ip: str | None) -> None:
    """Reject analyzeRepository calls past settings.rate_limit_max_analyses
    per settings.rate_limit_window_minutes, counted per client IP.

    Counted against analysis_jobs.client_ip (Postgres), not an in-memory
    counter -- the same reasoning as the job-claiming logic in
    jobs/claims.py: a plain in-process counter wouldn't hold across
    Passenger worker-process recycles or multiple processes.

    client_ip is None when the caller can't be identified (e.g. a direct
    schema.execute call with no underlying HTTP request, as in tests) --
    there's no identity to rate-limit, so this is a no-op rather than a
    blanket block.
    """
    if client_ip is None:
        return

    window_start = datetime.now(timezone.utc) - timedelta(minutes=settings.rate_limit_window_minutes)
    count = await session.scalar(
        select(func.count())
        .select_from(AnalysisJob)
        .where(AnalysisJob.client_ip == client_ip, AnalysisJob.created_at >= window_start)
    )
    if count is not None and count >= settings.rate_limit_max_analyses:
        raise RateLimitExceededError(
            f"Rate limit exceeded: at most {settings.rate_limit_max_analyses} repository "
            f"analyses per {settings.rate_limit_window_minutes} minutes. Try again later."
        )
