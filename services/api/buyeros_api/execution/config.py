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
    delivery_dispatch_enabled: bool = False
    reconciliation_enabled: bool = True
    retention_policy_version: str | None = None
    # Derived conversation data retention (Phase 3.4); 0 disables each sweep.
    conversation_event_retention_days: int = Field(default=30, ge=0, le=3650)
    turn_rate_window_retention_minutes: int = Field(default=1440, ge=0, le=525600)
    cloudflare_execution_enabled: bool = False
    celery_execution_enabled: bool = False


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()
