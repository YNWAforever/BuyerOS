"""Async engine lifecycle for the worker.

A Celery task is synchronous and drives its own ``asyncio.run`` loop, and an
async engine is bound to the loop that created it. Reusing one engine across
per-task loops is invalid, so every invocation creates an engine, uses it, and
disposes it on that same loop.

The module also tracks the in-flight engine so Celery's ``worker_shutdown``
signal can dispose it if the process is asked to stop mid-run. In normal
operation there is nothing left to dispose by then (each invocation already
disposed its own engine); the hook is the safety net.
"""

import asyncio
from threading import Lock

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def async_database_url(url: str) -> str:
    """Force the psycopg (v3) async driver for SQLAlchemy async engines."""
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def create_engine() -> AsyncEngine:
    from buyeros_api.settings import get_settings

    return create_async_engine(async_database_url(get_settings().database_url))


_active_engine: AsyncEngine | None = None
_active_lock = Lock()


def set_active_engine(engine: AsyncEngine | None) -> None:
    global _active_engine
    with _active_lock:
        _active_engine = engine


def dispose_engine(**_: object) -> None:
    """Dispose the in-flight engine. Wired to Celery's ``worker_shutdown``."""
    global _active_engine
    with _active_lock:
        engine = _active_engine
        _active_engine = None
    if engine is not None:
        asyncio.run(engine.dispose())
