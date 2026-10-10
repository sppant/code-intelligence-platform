from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the repo-root .env by path rather than relying on cwd: without
# Docker injecting real process env vars, this file is the only source of
# config, and the backend can reasonably be started from either the repo
# root or backend/ (see README).
_REPO_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_REPO_ROOT_ENV, extra="ignore")

    database_url: str = "postgresql+psycopg://cip:cip_dev_password@localhost:5432/cip"
    log_level: str = "info"
    env: str = "development"
    max_repo_size_mb: int = 500
    max_file_size_mb: int = 5
    clone_timeout_seconds: int = 60
    frontend_origin: str = "http://localhost:5173"
    stale_job_threshold_minutes: int = 10
    rate_limit_max_analyses: int = 5
    rate_limit_window_minutes: int = 10


settings = Settings()
