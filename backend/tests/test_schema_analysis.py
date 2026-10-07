import uuid

from sqlalchemy import delete

from backend.db import async_session_factory
from backend.models import Analysis, AnalysisJob, DependencyEdge, File, Repository, Symbol
from backend.schema.schema import schema


async def _make_analysis() -> dict:
    async with async_session_factory() as session:
        repo = Repository(url=f"https://github.com/test/{uuid.uuid4()}", owner="test", name="repo")
        session.add(repo)
        await session.flush()

        job = AnalysisJob(repository_id=repo.id, status="completed")
        session.add(job)
        await session.flush()

        analysis = Analysis(
            analysis_job_id=job.id,
            repository_id=repo.id,
            languages={"python": 1},
            total_files=2,
            total_lines=10,
        )
        session.add(analysis)
        await session.flush()

        file_a = File(analysis_id=analysis.id, path="a.py", language="python", line_count=5)
        file_b = File(analysis_id=analysis.id, path="b.py", language="python", line_count=5)
        session.add_all([file_a, file_b])
        await session.flush()

        session.add(
            Symbol(analysis_id=analysis.id, file_id=file_a.id, name="do_thing", kind="function", line_start=1, line_end=2)
        )
        session.add(
            DependencyEdge(analysis_id=analysis.id, source_file_id=file_a.id, target_file_id=file_b.id, type="imports")
        )
        await session.commit()

        return {
            "repo_id": repo.id,
            "job_id": job.id,
            "analysis_id": analysis.id,
        }


async def _cleanup(ids: dict) -> None:
    async with async_session_factory() as session:
        await session.execute(delete(Symbol).where(Symbol.analysis_id == ids["analysis_id"]))
        await session.execute(delete(DependencyEdge).where(DependencyEdge.analysis_id == ids["analysis_id"]))
        await session.execute(delete(File).where(File.analysis_id == ids["analysis_id"]))
        await session.execute(delete(Analysis).where(Analysis.id == ids["analysis_id"]))
        await session.execute(delete(AnalysisJob).where(AnalysisJob.id == ids["job_id"]))
        await session.execute(delete(Repository).where(Repository.id == ids["repo_id"]))
        await session.commit()


async def test_repository_latest_analysis_resolves_nested_shape():
    ids = await _make_analysis()
    try:
        async with async_session_factory() as session:
            result = await schema.execute(
                """
                query($id: UUID!) {
                  repository(id: $id) {
                    latestAnalysis {
                      statistics { totalFiles totalSymbols totalDependencyEdges }
                      dependencyEdges { sourcePath targetPath }
                    }
                  }
                }
                """,
                variable_values={"id": str(ids["repo_id"])},
                context_value={"session": session, "background_tasks": None},
            )
        assert result.errors is None
        analysis = result.data["repository"]["latestAnalysis"]
        assert analysis["statistics"] == {
            "totalFiles": 2,
            "totalSymbols": 1,
            "totalDependencyEdges": 1,
        }
        assert analysis["dependencyEdges"] == [{"sourcePath": "a.py", "targetPath": "b.py"}]
    finally:
        await _cleanup(ids)


async def test_search_symbols_filters_by_name_and_kind():
    ids = await _make_analysis()
    try:
        async with async_session_factory() as session:
            result = await schema.execute(
                """
                query($aid: UUID!) {
                  searchSymbols(analysisId: $aid, query: "thing", kind: "function") { name filePath }
                }
                """,
                variable_values={"aid": str(ids["analysis_id"])},
                context_value={"session": session, "background_tasks": None},
            )
        assert result.errors is None
        assert result.data["searchSymbols"] == [{"name": "do_thing", "filePath": "a.py"}]
    finally:
        await _cleanup(ids)
