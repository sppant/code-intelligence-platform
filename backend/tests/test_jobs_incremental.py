import uuid
from pathlib import Path

from sqlalchemy import delete, select

from analysis_engine.ingestion.clone import RepositoryRef
from analysis_engine.pipeline import AnalysisResult, WorkspaceAnalysis, analyze_workspace
from backend.db import async_session_factory
from backend.jobs.incremental import load_previous_files
from backend.jobs.tasks import persist_analysis
from backend.models import Analysis, AnalysisJob, DependencyEdge, File, Repository, Symbol

_FAKE_REF = RepositoryRef(owner="test", name="repo", clone_url="https://github.com/test/repo.git")


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _as_analysis_result(ws: WorkspaceAnalysis) -> AnalysisResult:
    """Wrap a clone-free WorkspaceAnalysis (from analyze_workspace) as the
    AnalysisResult persist_analysis expects, with a fake repository/commit --
    these tests never clone anything real."""
    return AnalysisResult(
        repository=_FAKE_REF,
        commit_sha=None,
        languages=ws.languages,
        files=ws.files,
        dependency_edges=ws.dependency_edges,
        call_edges=ws.call_edges,
        total_files=ws.total_files,
        total_lines=ws.total_lines,
        is_incremental=ws.is_incremental,
        files_reused=ws.files_reused,
        files_reprocessed=ws.files_reprocessed,
    )


async def _make_repo_and_job() -> tuple[uuid.UUID, uuid.UUID]:
    async with async_session_factory() as session:
        repo = Repository(url=f"https://github.com/test/{uuid.uuid4()}", owner="test", name="repo")
        session.add(repo)
        await session.flush()
        job = AnalysisJob(repository_id=repo.id, status="running")
        session.add(job)
        await session.flush()
        repo_id, job_id = repo.id, job.id
        await session.commit()
    return repo_id, job_id


async def _cleanup(repo_id: uuid.UUID) -> None:
    async with async_session_factory() as session:
        analysis_ids = (await session.scalars(select(Analysis.id).where(Analysis.repository_id == repo_id))).all()
        for analysis_id in analysis_ids:
            await session.execute(delete(DependencyEdge).where(DependencyEdge.analysis_id == analysis_id))
            await session.execute(delete(Symbol).where(Symbol.analysis_id == analysis_id))
            await session.execute(delete(File).where(File.analysis_id == analysis_id))
        await session.execute(delete(Analysis).where(Analysis.repository_id == repo_id))
        await session.execute(delete(AnalysisJob).where(AnalysisJob.repository_id == repo_id))
        await session.execute(delete(Repository).where(Repository.id == repo_id))
        await session.commit()


async def test_load_previous_files_returns_empty_when_no_completed_analysis():
    repo_id, _job_id = await _make_repo_and_job()
    try:
        async with async_session_factory() as session:
            previous = await load_previous_files(session, repo_id)
        assert previous == {}
    finally:
        await _cleanup(repo_id)


async def test_load_previous_files_round_trips_a_persisted_analysis(tmp_path: Path):
    _write(tmp_path, "a.py", "def helper():\n    pass\n")
    _write(tmp_path, "b.py", "from a import helper\nhelper()\n")
    cold = analyze_workspace(tmp_path)

    repo_id, job_id = await _make_repo_and_job()
    try:
        async with async_session_factory() as session:
            job = await session.get(AnalysisJob, job_id)
            await persist_analysis(session, job, _as_analysis_result(cold))

        async with async_session_factory() as session:
            previous = await load_previous_files(session, repo_id)

        assert set(previous.keys()) == {"a.py", "b.py"}
        assert previous["a.py"].symbols[0].name == "helper"
        assert previous["b.py"].imports[0].local_name == "helper"
        assert previous["b.py"].calls[0].callee_name == "helper"
    finally:
        await _cleanup(repo_id)


async def test_incremental_reuse_after_db_roundtrip_has_no_dangling_edge(tmp_path: Path):
    """Full round trip of the core correctness guarantee: persist a cold
    analysis, reload it as `previous_files`, delete a dependency's target
    file (while the importing file stays byte-identical), re-analyze -- the
    importing file must be reused (cache hit) AND its edge must no longer
    point at the deleted file.
    """
    _write(tmp_path, "a.py", "def helper():\n    pass\n")
    _write(tmp_path, "b.py", "from a import helper\nhelper()\n")
    cold = analyze_workspace(tmp_path)

    repo_id, job_id = await _make_repo_and_job()
    try:
        async with async_session_factory() as session:
            job = await session.get(AnalysisJob, job_id)
            await persist_analysis(session, job, _as_analysis_result(cold))

        async with async_session_factory() as session:
            previous_files = await load_previous_files(session, repo_id)

        (tmp_path / "a.py").unlink()
        warm = analyze_workspace(tmp_path, previous_files=previous_files)

        assert warm.files_reused == 1  # b.py's content is unchanged
        edges_by_source = {e.source_path: e for e in warm.dependency_edges}
        assert edges_by_source["b.py"].target_path is None  # not dangling
        assert edges_by_source["b.py"].external_module == "a"
    finally:
        await _cleanup(repo_id)
