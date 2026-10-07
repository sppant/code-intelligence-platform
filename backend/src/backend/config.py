from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://cip:cip_dev_password@localhost:5432/cip"
    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "info"
    env: str = "development"
    max_repo_size_mb: int = 500
    clone_timeout_seconds: int = 60
    frontend_origin: str = "http://localhost:5173"


settings = Settings()
