import uuid
from datetime import datetime

import strawberry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    created_at: datetime

    @strawberry.field
    async def analysis(self, info: strawberry.Info) -> "Analysis | None":
        session: AsyncSession = info.context["session"]
        row = await session.scalar(select(AnalysisModel).where(AnalysisModel.analysis_job_id == self.id))
        return await build_analysis_type(session, row) if row else None


@strawberry.type
class Symbol:
    id: uuid.UUID
    name: str
    kind: str
    line_start: int
    line_end: int
    file_path: str


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
class Analysis:
    id: uuid.UUID
    commit_sha: str | None
    created_at: datetime
    statistics: RepositoryStatistics
    files: list[FileNode]
    dependency_edges: list[DependencyEdge]


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

    dependency_edges = [
        DependencyEdge(
            source_path=path_by_file_id[e.source_file_id],
            target_path=path_by_file_id.get(e.target_file_id) if e.target_file_id else None,
            external_module=e.external_module,
            type=e.type,
        )
        for e in edge_rows
    ]

    statistics = RepositoryStatistics(
        total_files=analysis_row.total_files,
        total_lines=analysis_row.total_lines,
        languages=analysis_row.languages,
        total_symbols=len(symbol_rows),
        total_dependency_edges=len(edge_rows),
    )

    return Analysis(
        id=analysis_row.id,
        commit_sha=analysis_row.commit_sha,
        created_at=analysis_row.created_at,
        statistics=statistics,
        files=files,
        dependency_edges=dependency_edges,
    )
