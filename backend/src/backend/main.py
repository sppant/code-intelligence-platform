import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.fastapi import GraphQLRouter

from backend.config import settings
from backend.db import async_session_factory, get_session
from backend.jobs.claims import claim_outstanding_jobs
from backend.jobs.tasks import execute_claimed_job
from backend.schema.schema import schema


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup reconciliation: pick back up any job left pending/stale-running
    # by a previous process (e.g. a Passenger worker recycle) rather than
    # losing it. Tasks are held in a set so asyncio doesn't garbage-collect
    # them mid-flight; add_done_callback discards each once it finishes.
    app.state.background_tasks = set()
    async with async_session_factory() as session:
        stale_job_ids = await claim_outstanding_jobs(session)
    for job_id in stale_job_ids:
        task = asyncio.create_task(execute_claimed_job(str(job_id)))
        app.state.background_tasks.add(task)
        task.add_done_callback(app.state.background_tasks.discard)

    yield


def get_client_ip(request: Request) -> str | None:
    """Best-effort client IP for rate limiting (see backend.rate_limit).

    Trusts X-Forwarded-For's first entry over the raw socket peer when
    present: Plesk/Passenger deployments sit behind Apache/nginx, so
    request.client.host would otherwise always be the local proxy. This is
    an abuse-mitigation signal, not an auth boundary, so a spoofed header on
    a misconfigured deployment just means a shared rate-limit bucket -- not
    a security hole.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


async def get_context(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {
        "session": session,
        "background_tasks": background_tasks,
        "client_ip": get_client_ip(request),
    }


app = FastAPI(title="Code Intelligence Platform API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(GraphQLRouter(schema, context_getter=get_context), prefix="/graphql")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
