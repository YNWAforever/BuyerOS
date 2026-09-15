from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BUYEROS_", extra="ignore")

    broker_url: str = "redis://localhost:6379/0"
    eager: bool = False
    lease_seconds: int = 120
    batch_size: int = 10
    sweep_seconds: int = 60


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()
