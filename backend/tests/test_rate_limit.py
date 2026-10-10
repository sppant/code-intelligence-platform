import uuid

from fastapi import BackgroundTasks
from sqlalchemy import delete, select

from backend.config import settings
from backend.db import async_session_factory
from backend.models import AnalysisJob, Repository
from backend.schema.schema import schema

_MUTATION = """
mutation($url: String!) {
  analyzeRepository(repoUrl: $url) { id status }
}
"""


def _unique_repo_url() -> str:
    return f"https://github.com/test-{uuid.uuid4().hex}/repo"


async def _analyze(repo_url: str, client_ip: str | None):
    async with async_session_factory() as session:
        return await schema.execute(
            _MUTATION,
            variable_values={"url": repo_url},
            # A real BackgroundTasks() instance (never actually run here --
            # nothing in this test awaits it) rather than None, because the
            # mutation resolver calls background_tasks.add_task(...)
            # unconditionally once rate limiting passes.
            context_value={
                "session": session,
                "background_tasks": BackgroundTasks(),
                "client_ip": client_ip,
            },
        )


async def _cleanup(repo_url: str) -> None:
    async with async_session_factory() as session:
        repo = await session.scalar(select(Repository).where(Repository.url == repo_url))
        if repo is None:
            return
        await session.execute(delete(AnalysisJob).where(AnalysisJob.repository_id == repo.id))
        await session.execute(delete(Repository).where(Repository.id == repo.id))
        await session.commit()


async def test_rate_limit_blocks_after_max_within_window():
    repo_url = _unique_repo_url()
    client_ip = f"10.0.0.{uuid.uuid4().int % 255}"
    try:
        for _ in range(settings.rate_limit_max_analyses):
            result = await _analyze(repo_url, client_ip)
            assert result.errors is None

        blocked = await _analyze(repo_url, client_ip)
        assert blocked.errors is not None
        assert "Rate limit exceeded" in blocked.errors[0].message
    finally:
        await _cleanup(repo_url)


async def test_rate_limit_is_scoped_per_client_ip():
    repo_url = _unique_repo_url()
    ip_a = f"10.0.1.{uuid.uuid4().int % 255}"
    ip_b = f"10.0.2.{uuid.uuid4().int % 255}"
    try:
        for _ in range(settings.rate_limit_max_analyses):
            assert (await _analyze(repo_url, ip_a)).errors is None
        assert (await _analyze(repo_url, ip_a)).errors is not None

        # A different client IP has its own quota against the same repo.
        assert (await _analyze(repo_url, ip_b)).errors is None
    finally:
        await _cleanup(repo_url)


async def test_rate_limit_skipped_when_client_ip_unidentifiable():
    repo_url = _unique_repo_url()
    try:
        for _ in range(settings.rate_limit_max_analyses + 1):
            assert (await _analyze(repo_url, None)).errors is None
    finally:
        await _cleanup(repo_url)
