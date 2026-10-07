from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings


class Base(DeclarativeBase):
    pass



# The psycopg (v3) SQLAlchemy dialect supports both sync and async over the
# same "postgresql+psycopg://" URL scheme -- create_async_engine selects the
# async codepath, so no separate driver or URL rewrite is needed.
engine = create_async_engine(settings.database_url)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
