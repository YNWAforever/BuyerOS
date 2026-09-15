from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Fails closed: no Auth0 values means live auth is off."""

    model_config = SettingsConfigDict(env_prefix="BUYEROS_", extra="ignore")

    database_url: str = "postgresql://buyeros:buyeros@localhost:5432/buyeros"
    database_migration_url: str | None = None
    auth0_issuer: str | None = None
    auth0_audience: str | None = None
    jwks_cache_seconds: int = 300
    environment: str = "local"

    @field_validator("database_url")
    @classmethod
    def _postgres_only(cls, value: str) -> str:
        if not value.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be PostgreSQL (sqlite is not supported)")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
