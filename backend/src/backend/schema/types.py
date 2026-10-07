import uuid
from datetime import datetime

import strawberry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from analysis_engine.graph.impact import affected_files, compute_risk_indicators, is_test_file
from analysis_engine.graph.insights import compute_architecture_insights
from backend.models import Analysis as AnalysisModel
from backend.models import DependencyEdge as DependencyEdgeModel
from backend.models import File as FileModel
from backend.models import Symbol as SymbolModel


@strawberry.type
class Repository:
    id: uuid.UUID
    url: str
    owner: str
    name: str
    default_branch: str | None

    @strawberry.field
    async def latest_analysis(self, info: strawberry.Info) -> "Analysis | None":
        session: AsyncSession = info.context["session"]
        row = await session.scalar(
            select(AnalysisModel)
            .where(AnalysisModel.repository_id == self.id)
            .order_by(AnalysisModel.created_at.desc())
            .limit(1)
        )
        return await build_analysis_type(session, row) if row else None


@strawberry.type
class AnalysisJob:
    id: uuid.UUID
    repository_id: uuid.UUID
    status: str
    error_message: str | None
    progress: str | None
    created_at: datetime

    @strawberry.field
    async def analysis(self, info: strawberry.Info) -> "Analysis | None":
        session: AsyncSession = info.context["session"]
        row = await session.scalar(select(AnalysisModel).where(AnalysisModel.analysis_job_id == self.id))
        return await build_analysis_type(session, row) if row else None


@strawberry.type
class CallReference:
    file_path: str
    symbol_name: str | None


@strawberry.type
class Symbol:
    id: uuid.UUID
    name: str
    kind: str
    line_start: int
    line_end: int
    file_path: str

    @strawberry.field
    async def callers(self, info: strawberry.Info) -> list[CallReference]:
        """Symbols with a resolved call edge targeting this symbol."""
        session: AsyncSession = info.context["session"]
        return await _call_references(session, DependencyEdgeModel.target_symbol_id == self.id, source_side=True)

    @strawberry.field
    async def calls(self, info: strawberry.Info) -> list[CallReference]:
        """Symbols this symbol has a resolved call edge to."""
        session: AsyncSession = info.context["session"]
        return await _call_references(session, DependencyEdgeModel.source_symbol_id == self.id, source_side=False)


async def _call_references(session: AsyncSession, where_clause, *, source_side: bool) -> list[CallReference]:
    rows = (
        await session.scalars(
            select(DependencyEdgeModel).where(DependencyEdgeModel.type == "calls", where_clause)
        )
    ).all()
    # For .calls (source_side=False), `rows` can include unresolved call
    # edges (target_file_id/target_symbol_id both None) -- filter those out
    # here rather than in SQL, since .callers' matching side (target_*) is
    # never null by construction (it's exactly what where_clause filtered
    # on), but .calls' matching side (target_*) needs this explicit check.
    rows = [e for e in rows if (e.source_file_id if source_side else e.target_file_id) is not None]

    file_ids = {(e.source_file_id if source_side else e.target_file_id) for e in rows}
    file_ids.discard(None)
    path_by_file_id = {
        f.id: f.path for f in (await session.scalars(select(FileModel).where(FileModel.id.in_(file_ids)))).all()
    }
    symbol_ids = {(e.source_symbol_id if source_side else e.target_symbol_id) for e in rows}
    symbol_ids.discard(None)
    name_by_symbol_id = {
        s.id: s.name for s in (await session.scalars(select(SymbolModel).where(SymbolModel.id.in_(symbol_ids)))).all()
    }
    return [
        CallReference(
            file_path=path_by_file_id[e.source_file_id if source_side else e.target_file_id],
            symbol_name=name_by_symbol_id.get(e.source_symbol_id if source_side else e.target_symbol_id),
        )
        for e in rows
    ]


@strawberry.type
class DependencyEdge:
    source_path: str
    target_path: str | None
    external_module: str | None
    type: str


@strawberry.type
class RepositoryStatistics:
    total_files: int
    total_lines: int
    languages: strawberry.scalars.JSON
    total_symbols: int
    total_dependency_edges: int


@strawberry.type
class FileNode:
    path: str
    language: str | None
    line_count: int
    symbols: list[Symbol]


@strawberry.type
class FileFanInOut:
    path: str
    fan_in: int
    fan_out: int


@strawberry.type
class ArchitectureInsights:
    cycles: list[list[str]]
    fan_in_out: list[FileFanInOut]
    large_files: list[str]
    isolated_files: list[str]


@strawberry.type
class Analysis:
    id: uuid.UUID
    commit_sha: str | None
    created_at: datetime
    statistics: RepositoryStatistics
    files: list[FileNode]
    dependency_edges: list[DependencyEdge]
    architecture_insights: ArchitectureInsights


async def build_analysis_type(session: AsyncSession, analysis_row: AnalysisModel) -> Analysis:
    """Load files/symbols/relationships for one Analysis row and assemble
    the full nested GraphQL shape. Lives here (not schema.py) specifically
    so Repository.latest_analysis and AnalysisJob.analysis above can call it
    without schema.py importing back from this module.
    """
    file_rows = (
        await session.scalars(select(FileModel).where(FileModel.analysis_id == analysis_row.id))
    ).all()
    symbol_rows = (
        await session.scalars(select(SymbolModel).where(SymbolModel.analysis_id == analysis_row.id))
    ).all()
    edge_rows = (
        await session.scalars(select(DependencyEdgeModel).where(DependencyEdgeModel.analysis_id == analysis_row.id))
    ).all()

    path_by_file_id = {f.id: f.path for f in file_rows}

    symbols_by_file_id: dict[uuid.UUID, list[Symbol]] = {}
    for s in symbol_rows:
        symbols_by_file_id.setdefault(s.file_id, []).append(
            Symbol(id=s.id, name=s.name, kind=s.kind, line_start=s.line_start, line_end=s.line_end, file_path=path_by_file_id[s.file_id])
        )

    files = [
        FileNode(
            path=f.path,
            language=f.language,
            line_count=f.line_count,
            symbols=symbols_by_file_id.get(f.id, []),
        )
        for f in file_rows
    ]

    # edge_rows holds both "imports" (module-level) and "calls" (symbol-
    # level, Day 3) rows -- the GraphQL `dependency_edges` field is
    # specifically the module dependency graph the frontend renders, so it
    # must only ever contain "imports" rows. Call edges are reached via
    # Symbol.callers/Symbol.calls instead.
    import_edge_rows = [e for e in edge_rows if e.type == "imports"]

    dependency_edges = [
        DependencyEdge(
            source_path=path_by_file_id[e.source_file_id],
            target_path=path_by_file_id.get(e.target_file_id) if e.target_file_id else None,
            external_module=e.external_module,
            type=e.type,
        )
        for e in import_edge_rows
    ]

    statistics = RepositoryStatistics(
        total_files=analysis_row.total_files,
        total_lines=analysis_row.total_lines,
        languages=analysis_row.languages,
        total_symbols=len(symbol_rows),
        total_dependency_edges=len(import_edge_rows),
    )

    # Computed eagerly (not as a lazy @strawberry.field like latest_analysis)
    # since file_rows/import_edge_rows are already loaded here -- costs no
    # extra round trip, unlike latest_analysis which is genuinely optional.
    file_tuples = [(f.path, f.line_count) for f in file_rows]
    import_edge_tuples = [
        (path_by_file_id[e.source_file_id], path_by_file_id[e.target_file_id])
        for e in import_edge_rows
        if e.target_file_id is not None
    ]
    raw_insights = compute_architecture_insights(file_tuples, import_edge_tuples)
    architecture_insights = ArchitectureInsights(
        cycles=raw_insights.cycles,
        fan_in_out=[FileFanInOut(path=f.path, fan_in=f.fan_in, fan_out=f.fan_out) for f in raw_insights.fan_in_out],
        large_files=raw_insights.large_files,
        isolated_files=raw_insights.isolated_files,
    )

    return Analysis(
        id=analysis_row.id,
        commit_sha=analysis_row.commit_sha,
        created_at=analysis_row.created_at,
        statistics=statistics,
        files=files,
        dependency_edges=dependency_edges,
        architecture_insights=architecture_insights,
    )


@strawberry.type
class ImpactAnalysis:
    symbol: Symbol
    direct_callers: list[CallReference]
    affected_files: list[str]
    affected_symbols: list[Symbol]
    affected_tests: list[str]
    risk_indicators: list[str]


async def build_impact_analysis(session: AsyncSession, symbol_row: SymbolModel) -> ImpactAnalysis:
    """Given one Symbol row, compute direct callers (reverse "calls" edges),
    affected files (transitive dependents via the file-level "imports"
    graph), affected symbols (a bounded union of callers' symbols and
    symbols defined in affected files -- NOT an unbounded transitive
    closure), affected tests (affected files filtered through the stated
    is_test_file heuristic), and risk indicators.
    """
    analysis_id = symbol_row.analysis_id

    file_rows = (await session.scalars(select(FileModel).where(FileModel.analysis_id == analysis_id))).all()
    path_by_file_id = {f.id: f.path for f in file_rows}
    file_id_by_path = {f.path: f.id for f in file_rows}

    symbol_rows = (await session.scalars(select(SymbolModel).where(SymbolModel.analysis_id == analysis_id))).all()
    symbol_by_id = {s.id: s for s in symbol_rows}
    symbols_by_file_id: dict[uuid.UUID, list[SymbolModel]] = {}
    for s in symbol_rows:
        symbols_by_file_id.setdefault(s.file_id, []).append(s)

    edge_rows = (
        await session.scalars(select(DependencyEdgeModel).where(DependencyEdgeModel.analysis_id == analysis_id))
    ).all()

    symbol_file_path = path_by_file_id[symbol_row.file_id]

    import_edges = [
        (path_by_file_id[e.source_file_id], path_by_file_id[e.target_file_id])
        for e in edge_rows
        if e.type == "imports" and e.target_file_id is not None
    ]
    affected_file_paths = affected_files(symbol_file_path, import_edges)

    caller_edges = [e for e in edge_rows if e.type == "calls" and e.target_symbol_id == symbol_row.id]
    direct_callers = [
        CallReference(
            file_path=path_by_file_id[e.source_file_id],
            symbol_name=symbol_by_id[e.source_symbol_id].name if e.source_symbol_id else None,
        )
        for e in caller_edges
    ]

    caller_symbols = [symbol_by_id[e.source_symbol_id] for e in caller_edges if e.source_symbol_id]
    affected_file_symbols = [
        s for path in affected_file_paths for s in symbols_by_file_id.get(file_id_by_path.get(path), [])
    ]
    affected_symbols_by_id = {s.id: s for s in caller_symbols + affected_file_symbols}  # dedup, bounded
    affected_symbols = [
        Symbol(
            id=s.id,
            name=s.name,
            kind=s.kind,
            line_start=s.line_start,
            line_end=s.line_end,
            file_path=path_by_file_id[s.file_id],
        )
        for s in affected_symbols_by_id.values()
    ]

    affected_tests = sorted(p for p in affected_file_paths if is_test_file(p))

    fan_in = sum(1 for _source, target in import_edges if target == symbol_file_path)
    risk_indicators = compute_risk_indicators(
        fan_in=fan_in,
        affected_files_count=len(affected_file_paths),
        affected_tests_count=len(affected_tests),
        direct_callers_count=len(direct_callers),
        symbol_kind=symbol_row.kind,
    )

    return ImpactAnalysis(
        symbol=Symbol(
            id=symbol_row.id,
            name=symbol_row.name,
            kind=symbol_row.kind,
            line_start=symbol_row.line_start,
            line_end=symbol_row.line_end,
            file_path=symbol_file_path,
        ),
        direct_callers=direct_callers,
        affected_files=sorted(affected_file_paths),
        affected_symbols=affected_symbols,
        affected_tests=affected_tests,
        risk_indicators=risk_indicators,
    )
