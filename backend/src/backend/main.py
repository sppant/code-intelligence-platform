from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.fastapi import GraphQLRouter

from backend.config import settings
from backend.db import get_session
from backend.schema.schema import schema


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    yield
    await app.state.redis.close()


async def get_context(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"session": session, "redis": request.app.state.redis}


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
