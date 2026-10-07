"""Performance benchmark: GraphQL query latency against a real persisted
analysis in the real local Postgres (no HTTP server -- reuses
schema.execute(...) directly, the same pattern backend/tests already use).

Not pytest-discovered -- run manually (requires local Postgres up and
migrated, same as running the app normally):

    uv run --project backend python backend/benchmarks/bench_graphql_query.py

Prints avg/median/p95 latency (ms) for two queries: the Repository
Overview's statistics query (a straightforward row/aggregate read) and the
Architecture Insights query (which runs real cycle-detection/fan-in-out
computation over the persisted graph, not just a row dump). Paste the real
output into the README -- numbers here are never fabricated, this script is
the thing that produces them.
"""

import asyncio
import statistics
import time
import uuid

from sqlalchemy import delete

from analysis_engine.pipeline import run_pipeline
from backend.db import async_session_factory
from backend.jobs.tasks import persist_analysis
from backend.models import Analysis, AnalysisJob, DependencyEdge, File, Repository, Symbol
from backend.schema.schema import schema

BENCHMARK_REPO_URL = "https://github.com/psf/requests"
REPETITIONS = 20

OVERVIEW_QUERY = """
query($id: UUID!) {
  repository(id: $id) {
    latestAnalysis {
      statistics { totalFiles totalLines languages totalSymbols totalDependencyEdges }
    }
  }
}
"""

INSIGHTS_QUERY = """
query($aid: UUID!) {
  analysis(id: $aid) {
    architectureInsights { cycles fanInOut { path fanIn fanOut } largeFiles isolatedFiles }
  }
}
"""


async def _seed() -> dict:
    print(f"Cloning and analyzing {BENCHMARK_REPO_URL} ...", flush=True)
    result = run_pipeline(BENCHMARK_REPO_URL, max_size_mb=2000, clone_timeout_seconds=120)
    print(f"  {result.total_files} files, {result.total_lines} lines -- persisting...", flush=True)

    async with async_session_factory() as session:
        repo = Repository(url=f"https://github.com/bench/{uuid.uuid4()}", owner="bench", name="repo")
        session.add(repo)
        await session.flush()
        job = AnalysisJob(repository_id=repo.id, status="running")
        session.add(job)
        await session.flush()
        analysis = await persist_analysis(session, job, result)
        return {"repo_id": repo.id, "job_id": job.id, "analysis_id": analysis.id}


async def _cleanup(ids: dict) -> None:
    async with async_session_factory() as session:
        await session.execute(delete(DependencyEdge).where(DependencyEdge.analysis_id == ids["analysis_id"]))
        await session.execute(delete(Symbol).where(Symbol.analysis_id == ids["analysis_id"]))
        await session.execute(delete(File).where(File.analysis_id == ids["analysis_id"]))
        await session.execute(delete(Analysis).where(Analysis.id == ids["analysis_id"]))
        await session.execute(delete(AnalysisJob).where(AnalysisJob.id == ids["job_id"]))
        await session.execute(delete(Repository).where(Repository.id == ids["repo_id"]))
        await session.commit()


async def _time_query(query: str, variables: dict, repetitions: int) -> list[float]:
    latencies_ms = []
    for _ in range(repetitions):
        async with async_session_factory() as session:
            t0 = time.perf_counter()
            result = await schema.execute(query, variable_values=variables, context_value={"session": session, "background_tasks": None})
            latencies_ms.append((time.perf_counter() - t0) * 1000)
        if result.errors:
            raise RuntimeError(f"query failed: {result.errors}")
    return latencies_ms


def _percentile(values: list[float], pct: float) -> float:
    sorted_values = sorted(values)
    index = min(len(sorted_values) - 1, int(len(sorted_values) * pct))
    return sorted_values[index]


def _print_row(label: str, latencies_ms: list[float]) -> None:
    print(
        f"| {label} | {statistics.mean(latencies_ms):.2f} | {statistics.median(latencies_ms):.2f} | "
        f"{_percentile(latencies_ms, 0.95):.2f} |"
    )


async def main() -> None:
    ids = await _seed()
    try:
        overview_latencies = await _time_query(OVERVIEW_QUERY, {"id": str(ids["repo_id"])}, REPETITIONS)
        insights_latencies = await _time_query(INSIGHTS_QUERY, {"aid": str(ids["analysis_id"])}, REPETITIONS)

        print(f"\n{REPETITIONS} repetitions each, against {BENCHMARK_REPO_URL}\n")
        print("| Query | Avg (ms) | Median (ms) | p95 (ms) |")
        print("|---|---|---|---|")
        _print_row("Repository Overview (statistics)", overview_latencies)
        _print_row("Architecture Insights (cycles/fan-in-out)", insights_latencies)
    finally:
        await _cleanup(ids)


if __name__ == "__main__":
    asyncio.run(main())
