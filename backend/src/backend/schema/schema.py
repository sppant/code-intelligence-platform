import uuid

import strawberry
from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from analysis_engine.ingestion.clone import validate_github_url
from backend.jobs.tasks import run_analysis_job
from backend.models import AnalysisJob
from backend.models import Repository as RepositoryModel
from backend.schema.types import AnalysisJob as AnalysisJobType
from backend.schema.types import Repository as RepositoryType


def _to_repository_type(repo: RepositoryModel) -> RepositoryType:
    return RepositoryType(
        id=repo.id,
        url=repo.url,
        owner=repo.owner,
        name=repo.name,
        default_branch=repo.default_branch,
    )


def _to_job_type(job: AnalysisJob) -> AnalysisJobType:
    return AnalysisJobType(
        id=job.id,
        repository_id=job.repository_id,
        status=job.status,
        error_message=job.error_message,
        created_at=job.created_at,
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
    async def analysis_job(self, info: strawberry.Info, id: uuid.UUID) -> AnalysisJobType | None:
        session: AsyncSession = info.context["session"]
        job = await session.get(AnalysisJob, id)
        return _to_job_type(job) if job else None


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

        ref = validate_github_url(repo_url)
        canonical_url = f"https://github.com/{ref.owner}/{ref.name}"

        repository = await session.scalar(
            select(RepositoryModel).where(RepositoryModel.url == canonical_url)
        )
        if repository is None:
            repository = RepositoryModel(url=canonical_url, owner=ref.owner, name=ref.name)
            session.add(repository)
            await session.flush()

        job = AnalysisJob(repository_id=repository.id, status="pending")
        session.add(job)
        await session.flush()
        await session.commit()
        await session.refresh(job)

        background_tasks.add_task(run_analysis_job, str(job.id))

        return _to_job_type(job)


schema = strawberry.Schema(query=Query, mutation=Mutation)
