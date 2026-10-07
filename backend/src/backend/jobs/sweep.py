"""Standalone safety-net sweep: claim and process any job stuck pending or
stale-running, then exit. Meant to be invoked periodically by a cron-style
scheduler (e.g. Plesk Scheduled Tasks) as a backstop against a web process
being recycled mid-job -- not a long-running daemon.

Run as: python -m backend.jobs.sweep
"""

import asyncio

from backend.db import async_session_factory
from backend.jobs.claims import claim_outstanding_jobs
from backend.jobs.tasks import execute_claimed_job


async def _main() -> None:
    async with async_session_factory() as session:
        job_ids = await claim_outstanding_jobs(session)

    for job_id in job_ids:
        await execute_claimed_job(str(job_id))  # sequential: a periodic sweep, not a server


if __name__ == "__main__":
    asyncio.run(_main())
