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
            is_incremental=True,
            files_reused=1,
            files_reprocessed=1,
        )
        session.add(analysis)
        await session.flush()

        file_a = File(analysis_id=analysis.id, path="a.py", language="python", line_count=5)
        file_b = File(analysis_id=analysis.id, path="b.py", language="python", line_count=5)
        session.add_all([file_a, file_b])
        await session.flush()

        symbol_a = Symbol(analysis_id=analysis.id, file_id=file_a.id, name="do_thing", kind="function", line_start=1, line_end=2)
        symbol_b = Symbol(analysis_id=analysis.id, file_id=file_b.id, name="do_other", kind="function", line_start=1, line_end=2)
        session.add_all([symbol_a, symbol_b])
        await session.flush()

        session.add(
            DependencyEdge(analysis_id=analysis.id, source_file_id=file_a.id, target_file_id=file_b.id, type="imports")
        )
        session.add(
            DependencyEdge(
                analysis_id=analysis.id,
                source_file_id=file_a.id,
                target_file_id=file_b.id,
                source_symbol_id=symbol_a.id,
                target_symbol_id=symbol_b.id,
                type="calls",
                called_name="do_other",
            )
        )
        await session.commit()

        return {
            "repo_id": repo.id,
            "job_id": job.id,
            "analysis_id": analysis.id,
            "symbol_a_id": symbol_a.id,
            "symbol_b_id": symbol_b.id,
        }


async def _cleanup(ids: dict) -> None:
    async with async_session_factory() as session:
        # relationships rows can reference symbols (source/target_symbol_id)
        # -- must be deleted before Symbol to satisfy the FK constraint.
        await session.execute(delete(DependencyEdge).where(DependencyEdge.analysis_id == ids["analysis_id"]))
        await session.execute(delete(Symbol).where(Symbol.analysis_id == ids["analysis_id"]))
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
            "totalSymbols": 2,
            "totalDependencyEdges": 1,  # the "calls" edge must NOT be counted here
        }
        assert analysis["dependencyEdges"] == [{"sourcePath": "a.py", "targetPath": "b.py"}]
    finally:
        await _cleanup(ids)


async def test_symbol_callers_and_calls_resolve_only_calls_type_edges():
    ids = await _make_analysis()
    try:
        async with async_session_factory() as session:
            result = await schema.execute(
                """
                query($aid: UUID!) {
                  searchSymbols(analysisId: $aid, query: "do_other") { calls { filePath symbolName } callers { filePath symbolName } }
                }
                """,
                variable_values={"aid": str(ids["analysis_id"])},
                context_value={"session": session, "background_tasks": None},
            )
        assert result.errors is None
        [do_other] = result.data["searchSymbols"]
        assert do_other["calls"] == []
        assert do_other["callers"] == [{"filePath": "a.py", "symbolName": "do_thing"}]
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


async def test_architecture_insights_fan_in_out():
    ids = await _make_analysis()
    try:
        async with async_session_factory() as session:
            result = await schema.execute(
                """
                query($aid: UUID!) {
                  analysis(id: $aid) {
                    architectureInsights { cycles fanInOut { path fanIn fanOut } largeFiles isolatedFiles }
                  }
                }
                """,
                variable_values={"aid": str(ids["analysis_id"])},
                context_value={"session": session, "background_tasks": None},
            )
        assert result.errors is None
        insights = result.data["analysis"]["architectureInsights"]
        assert insights["cycles"] == []
        assert insights["largeFiles"] == []
        assert insights["isolatedFiles"] == []  # both files are connected via the imports edge
        fan_by_path = {f["path"]: (f["fanIn"], f["fanOut"]) for f in insights["fanInOut"]}
        assert fan_by_path == {"a.py": (0, 1), "b.py": (1, 0)}
    finally:
        await _cleanup(ids)


async def test_impact_analysis_for_called_symbol():
    ids = await _make_analysis()
    try:
        async with async_session_factory() as session:
            result = await schema.execute(
                """
                query($id: UUID!) {
                  impactAnalysis(symbolId: $id) {
                    symbol { name }
                    directCallers { filePath symbolName }
                    affectedFiles
                    affectedSymbols { name }
                    affectedTests
                    riskIndicators
                  }
                }
                """,
                variable_values={"id": str(ids["symbol_b_id"])},  # do_other, called by do_thing in a.py
                context_value={"session": session, "background_tasks": None},
            )
        assert result.errors is None
        impact = result.data["impactAnalysis"]
        assert impact["symbol"]["name"] == "do_other"
        assert impact["directCallers"] == [{"filePath": "a.py", "symbolName": "do_thing"}]
        assert impact["affectedFiles"] == ["a.py"]  # a.py imports b.py, so it's affected by a change to do_other
        assert {s["name"] for s in impact["affectedSymbols"]} == {"do_thing"}
        assert impact["affectedTests"] == []
        assert "Missing test coverage" in impact["riskIndicators"]
    finally:
        await _cleanup(ids)


async def test_analysis_exposes_incremental_fields():
    ids = await _make_analysis()
    try:
        async with async_session_factory() as session:
            result = await schema.execute(
                """
                query($aid: UUID!) {
                  analysis(id: $aid) { isIncremental filesReused filesReprocessed }
                }
                """,
                variable_values={"aid": str(ids["analysis_id"])},
                context_value={"session": session, "background_tasks": None},
            )
        assert result.errors is None
        assert result.data["analysis"] == {
            "isIncremental": True,
            "filesReused": 1,
            "filesReprocessed": 1,
        }
    finally:
        await _cleanup(ids)


async def test_repository_latest_job_reflects_most_recent_job_regardless_of_status():
    ids = await _make_analysis()
    newer_job_id = None
    try:
        async with async_session_factory() as session:
            newer_job = AnalysisJob(repository_id=ids["repo_id"], status="running", progress="cloning")
            session.add(newer_job)
            await session.commit()
            newer_job_id = newer_job.id

        async with async_session_factory() as session:
            result = await schema.execute(
                """
                query($id: UUID!) {
                  repository(id: $id) { latestJob { id status progress } }
                }
                """,
                variable_values={"id": str(ids["repo_id"])},
                context_value={"session": session, "background_tasks": None},
            )
        assert result.errors is None
        latest_job = result.data["repository"]["latestJob"]
        assert latest_job == {"id": str(newer_job_id), "status": "running", "progress": "cloning"}
    finally:
        if newer_job_id is not None:
            async with async_session_factory() as session:
                await session.execute(delete(AnalysisJob).where(AnalysisJob.id == newer_job_id))
                await session.commit()
        await _cleanup(ids)


async def test_repositories_query_orders_by_most_recent_activity():
    first = await _make_analysis()
    second = await _make_analysis()
    extra_job_id = None
    try:
        # Re-activity first by adding a newer job to it after second was created.
        async with async_session_factory() as session:
            extra_job = AnalysisJob(repository_id=first["repo_id"], status="completed")
            session.add(extra_job)
            await session.commit()
            extra_job_id = extra_job.id

        async with async_session_factory() as session:
            result = await schema.execute(
                """
                query { repositories(limit: 50) { id } }
                """,
                context_value={"session": session, "background_tasks": None},
            )
        assert result.errors is None
        ids_in_order = [r["id"] for r in result.data["repositories"]]
        assert ids_in_order.index(str(first["repo_id"])) < ids_in_order.index(str(second["repo_id"]))
    finally:
        if extra_job_id is not None:
            async with async_session_factory() as session:
                await session.execute(delete(AnalysisJob).where(AnalysisJob.id == extra_job_id))
                await session.commit()
        await _cleanup(first)
        await _cleanup(second)


async def test_impact_analysis_flags_no_direct_callers():
    ids = await _make_analysis()
    try:
        async with async_session_factory() as session:
            result = await schema.execute(
                """
                query($id: UUID!) { impactAnalysis(symbolId: $id) { riskIndicators } }
                """,
                variable_values={"id": str(ids["symbol_a_id"])},  # do_thing has no callers in this fixture
                context_value={"session": session, "background_tasks": None},
            )
        assert result.errors is None
        indicators = result.data["impactAnalysis"]["riskIndicators"]
        assert any("No direct callers" in i for i in indicators)
    finally:
        await _cleanup(ids)
