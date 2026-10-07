from arq.connections import RedisSettings

from backend.config import settings
from backend.jobs.tasks import analyze_repository_task


class WorkerSettings:
    functions = [analyze_repository_task]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
