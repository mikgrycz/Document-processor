"""Application settings, loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the service.

    Values can be overridden via environment variables (e.g. APP_LOG_LEVEL=DEBUG)
    or a local .env file during development.
    """

    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    log_level: str = "INFO"
    worker_concurrency: int = 2


settings = Settings()
