from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BUYEROS_", extra="ignore")

    broker_url: str = Field(default="redis://localhost:6379/0", repr=False, exclude=True)
    checkpoint_database_url: str | None = Field(default=None, repr=False, exclude=True)
    eager: bool = False
    lease_seconds: int = 120
    batch_size: int = 10
    sweep_seconds: int = 60
    paid_dispatch_enabled: bool = False
    reconciliation_enabled: bool = True
    retention_policy_version: str | None = None
    cloudflare_execution_enabled: bool = False


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()
