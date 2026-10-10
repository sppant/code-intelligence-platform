import uuid

import strawberry
from fastapi import BackgroundTasks
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from analysis_engine.ingestion.clone import validate_github_url
from backend.jobs.tasks import run_analysis_job
from backend.rate_limit import enforce_rate_limit
from backend.models import Analysis as AnalysisModel
from backend.models import AnalysisJob
from backend.models import File as FileModel
from backend.models import Repository as RepositoryModel
from backend.models import Symbol as SymbolModel
from backend.schema.types import Analysis as AnalysisType
from backend.schema.types import AnalysisJob as AnalysisJobType
from backend.schema.types import ImpactAnalysis as ImpactAnalysisType
from backend.schema.types import Repository as RepositoryType
from backend.schema.types import Symbol as SymbolType
from backend.schema.types import _to_job_type, build_analysis_type, build_impact_analysis


def _to_repository_type(repo: RepositoryModel) -> RepositoryType:
    return RepositoryType(
        id=repo.id,
        url=repo.url,
        owner=repo.owner,
        name=repo.name,
        default_branch=repo.default_branch,
    )


@strawberry.type
class Query:
    @strawberry.field
    def health(self) -> str:
        return "ok"

    @strawberry.field
    async def repository(self, info: strawberry.Info, id: uuid.UUID) -> RepositoryType | None:
        session: AsyncSession = info.context["session"]
        repo = await session.get(RepositoryModel, id)
        return _to_repository_type(repo) if repo else None

    @strawberry.field
    async def repositories(self, info: strawberry.Info, limit: int = 20) -> list[RepositoryType]:
        """Previously analyzed repositories, most recently active first.

        "Active" is the most recent analysis_jobs row per repository (not
        Repository.created_at), so a repository re-analyzed later bubbles
        back to the top of the landing-page history list.
        """
        session: AsyncSession = info.context["session"]
        last_activity = (
            select(AnalysisJob.repository_id, func.max(AnalysisJob.created_at).label("last_activity"))
            .group_by(AnalysisJob.repository_id)
            .subquery()
        )
        stmt = (
            select(RepositoryModel)
            .join(last_activity, last_activity.c.repository_id == RepositoryModel.id)
            .order_by(last_activity.c.last_activity.desc())
            .limit(limit)
        )
        rows = (await session.scalars(stmt)).all()
        return [_to_repository_type(r) for r in rows]

    @strawberry.field
    async def analysis_job(self, info: strawberry.Info, id: uuid.UUID) -> AnalysisJobType | None:
        session: AsyncSession = info.context["session"]
        job = await session.get(AnalysisJob, id)
        return _to_job_type(job) if job else None

    @strawberry.field
    async def analysis(self, info: strawberry.Info, id: uuid.UUID) -> AnalysisType | None:
        session: AsyncSession = info.context["session"]
        row = await session.get(AnalysisModel, id)
        return await build_analysis_type(session, row) if row else None

    @strawberry.field
    async def search_symbols(
        self,
        info: strawberry.Info,
        analysis_id: uuid.UUID,
        query: str,
        kind: str | None = None,
    ) -> list[SymbolType]:
        session: AsyncSession = info.context["session"]
        stmt = (
            select(SymbolModel, FileModel.path)
            .join(FileModel, FileModel.id == SymbolModel.file_id)
            .where(SymbolModel.analysis_id == analysis_id, SymbolModel.name.ilike(f"%{query}%"))
        )
        if kind is not None:
            stmt = stmt.where(SymbolModel.kind == kind)
        rows = await session.execute(stmt)
        return [
            SymbolType(
                id=s.id,
                name=s.name,
                kind=s.kind,
                line_start=s.line_start,
                line_end=s.line_end,
                file_path=path,
                parent=s.parent,
            )
            for s, path in rows.all()
        ]

    @strawberry.field
    async def impact_analysis(self, info: strawberry.Info, symbol_id: uuid.UUID) -> ImpactAnalysisType | None:
        session: AsyncSession = info.context["session"]
        symbol_row = await session.get(SymbolModel, symbol_id)
        return await build_impact_analysis(session, symbol_row) if symbol_row else None


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def analyze_repository(self, info: strawberry.Info, repo_url: str) -> AnalysisJobType:
        """Validate the URL, upsert the repository, create a pending job, and
        schedule the clone/detect/parse work as a background task in this
        same process. Kept intentionally thin: the GraphQL layer only
        orchestrates state, the analysis-engine owns all repository-handling
        logic.
        """
        session: AsyncSession = info.context["session"]
        background_tasks: BackgroundTasks = info.context["background_tasks"]
        client_ip: str | None = info.context.get("client_ip")

        ref = validate_github_url(repo_url)
        await enforce_rate_limit(session, client_ip)
        canonical_url = f"https://github.com/{ref.owner}/{ref.name}"

        repository = await session.scalar(
            select(RepositoryModel).where(RepositoryModel.url == canonical_url)
        )
        if repository is None:
            repository = RepositoryModel(url=canonical_url, owner=ref.owner, name=ref.name)
            session.add(repository)
            await session.flush()

        job = AnalysisJob(repository_id=repository.id, status="pending", client_ip=client_ip)
        session.add(job)
        await session.flush()
        await session.commit()
        await session.refresh(job)

        background_tasks.add_task(run_analysis_job, str(job.id))

        return _to_job_type(job)


schema = strawberry.Schema(query=Query, mutation=Mutation)
