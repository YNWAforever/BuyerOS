from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Fails closed: no Auth0 values means live auth is off."""

    model_config = SettingsConfigDict(env_prefix="BUYEROS_", extra="ignore")

    database_url: str = Field(default="postgresql://buyeros:buyeros@localhost:5432/buyeros",
                              repr=False, exclude=True)
    database_migration_url: str | None = Field(default=None, repr=False, exclude=True)
    auth0_issuer: str | None = None
    auth0_audience: str | None = None
    jwks_cache_seconds: int = Field(default=300, ge=1)
    jwks_max_stale_seconds: int = Field(default=3600, ge=1)
    worker_heartbeat_max_age_seconds: int = Field(default=180, ge=30, le=3600)
    environment: str = "local"
    paid_admission_enabled: bool = False
    live_read_enabled: bool = True
    reconciliation_enabled: bool = True
    read_per_minute: int = Field(default=600, ge=1, le=10000)
    write_per_minute: int = Field(default=300, ge=1, le=10000)
    expensive_read_per_minute: int = Field(default=120, ge=1, le=10000)
    expensive_write_per_minute: int = Field(default=60, ge=1, le=10000)
    cors_origins: list[str] = Field(default_factory=list)
    r2_enabled: bool = False
    r2_account_id: str | None = None
    r2_bucket: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = Field(default=None, repr=False, exclude=True)
    r2_jurisdiction: str | None = None
    execution_database_url: str | None = Field(default=None, repr=False, exclude=True)
    cloudflare_execution_enabled: bool = False
    worker_current_key_id: str | None = None
    worker_current_secret: SecretStr | None = Field(default=None, repr=False, exclude=True)
    worker_previous_key_id: str | None = None
    worker_previous_secret: SecretStr | None = Field(default=None, repr=False, exclude=True)

    @field_validator("execution_database_url")
    @classmethod
    def _execution_postgres_only(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("postgresql://"):
            raise ValueError("EXECUTION_DATABASE_URL must be a PostgreSQL worker DSN")
        return value

    @field_validator("database_url")
    @classmethod
    def _postgres_only(cls, value: str) -> str:
        if not value.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be PostgreSQL (sqlite is not supported)")
        return value

    @field_validator("cors_origins")
    @classmethod
    def _explicit_browser_origins(cls, values: list[str]) -> list[str]:
        origins: list[str] = []
        for value in values:
            parsed = urlsplit(value)
            if (
                parsed.scheme not in {"https", "http"}
                or not parsed.hostname
                or parsed.username or parsed.password
                or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
                or "*" in value
                or (parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"})
            ):
                raise ValueError("CORS_ORIGINS must list explicit HTTPS or loopback origins")
            origin = f"{parsed.scheme}://{parsed.netloc}"
            if origin not in origins:
                origins.append(origin)
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
