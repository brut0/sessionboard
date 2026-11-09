"""Application configuration and environment settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="local", alias="APP_ENV")
    app_version: str = Field(default="unknown", alias="APP_VERSION")
    database_url: str = Field(
        default="postgresql+psycopg://sessionboard:sessionboard@localhost:5432/sessionboard",
        alias="DATABASE_URL",
    )
    seed_demo_data: bool = Field(default=False, alias="SEED_DEMO_DATA")

    # Observability
    otel_service_name: str = Field(default="sessionboard", alias="OTEL_SERVICE_NAME")
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    otel_sdk_disabled: bool = Field(default=False, alias="OTEL_SDK_DISABLED")

    @property
    def normalized_database_url(self) -> str:
        """Ensure connection string uses the psycopg dialect."""
        url = self.database_url
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url[len("postgres://") :]
        if url.startswith("postgresql://") and not url.startswith("postgresql+"):
            return "postgresql+psycopg://" + url[len("postgresql://") :]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
