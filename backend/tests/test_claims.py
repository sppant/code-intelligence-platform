import asyncio
import uuid

from sqlalchemy import delete

from backend.db import async_session_factory
from backend.jobs.claims import claim_job, claim_outstanding_jobs
from backend.models import AnalysisJob, Repository


async def _make_job(status: str = "pending", started_at=None) -> tuple[uuid.UUID, uuid.UUID]:
    async with async_session_factory() as session:
        repo = Repository(url=f"https://github.com/test/{uuid.uuid4()}", owner="test", name="repo")
        session.add(repo)
        await session.flush()
        job = AnalysisJob(repository_id=repo.id, status=status, started_at=started_at)
        session.add(job)
        await session.flush()
        job_id, repo_id = job.id, repo.id
        await session.commit()
    return job_id, repo_id


async def _cleanup(job_id: uuid.UUID, repo_id: uuid.UUID) -> None:
    async with async_session_factory() as session:
        await session.execute(delete(AnalysisJob).where(AnalysisJob.id == job_id))
        await session.execute(delete(Repository).where(Repository.id == repo_id))
        await session.commit()


async def test_claim_job_is_race_safe_under_concurrent_claimers():
    job_id, repo_id = await _make_job(status="pending")
    try:
        async def claim():
            async with async_session_factory() as session:
                return await claim_job(session, job_id)

        results = await asyncio.gather(claim(), claim())
        assert sorted(results) == [False, True]
    finally:
        await _cleanup(job_id, repo_id)


async def test_claim_job_ignores_a_fresh_running_job():
    from datetime import datetime, timezone

    job_id, repo_id = await _make_job(status="running", started_at=datetime.now(timezone.utc))
    try:
        async with async_session_factory() as session:
            claimed = await claim_job(session, job_id)
        assert claimed is False
    finally:
        await _cleanup(job_id, repo_id)


async def test_claim_outstanding_jobs_picks_up_stale_running_job():
    from datetime import datetime, timedelta, timezone

    stale_started_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    job_id, repo_id = await _make_job(status="running", started_at=stale_started_at)
    try:
        async with async_session_factory() as session:
            claimed_ids = await claim_outstanding_jobs(session)
        assert job_id in claimed_ids
    finally:
        await _cleanup(job_id, repo_id)
