"""Durable, actor-scoped request admission for API reads and writes."""
from __future__ import annotations

import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert

from ..api.errors import ApiError
from ..db.rate import ApiRateWindow
from ..db.session import tenant_session
from ..settings import get_settings

request_rate_bucket: ContextVar[str | None] = ContextVar("buyer_request_rate_bucket", default=None)
_EXPENSIVE = frozenset({
    "projects", "buyers", "snapshots", "runs", "quotes", "exports",
    "drafts", "outcomes", "usage", "audit-events", "jobs", "evidence",
    "documents", "bulk", "enrichment",
})


def classify_request(method: str, path: str) -> str | None:
    if not path.startswith("/v1/") or method == "OPTIONS":
        return None
    parts = frozenset(path.split("/"))
    expensive = bool(parts.intersection(_EXPENSIVE))
    if method in {"GET", "HEAD"}:
        return "expensive_read" if expensive else "read"
    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        return "expensive_write" if expensive else "write"
    return None


async def enforce_rate_limit(engine, workspace_id: uuid.UUID, actor_id: uuid.UUID) -> None:
    bucket = request_rate_bucket.get()
    if bucket is None:
        return
    settings = get_settings()
    limit = {
        "read": settings.read_per_minute,
        "write": settings.write_per_minute,
        "expensive_read": settings.expensive_read_per_minute,
        "expensive_write": settings.expensive_write_per_minute,
    }[bucket]
    window_start = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    statement = insert(ApiRateWindow).values(
        workspace_id=workspace_id, actor_id=actor_id, bucket=bucket,
        window_start=window_start, hits=1,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[ApiRateWindow.workspace_id, ApiRateWindow.actor_id,
                        ApiRateWindow.bucket, ApiRateWindow.window_start],
        set_={"hits": ApiRateWindow.hits + 1},
        where=ApiRateWindow.hits < limit,
    ).returning(ApiRateWindow.hits)
    # Separate transaction: a rejected/failed business request still consumes
    # its admission slot and cannot roll back the limiter counter.
    async with tenant_session(engine, workspace_id) as session:
        accepted = (await session.execute(statement)).scalar_one_or_none()
    if accepted is None:
        raise ApiError(429, "RATE_LIMITED", "request rate limit reached", retryable=True)
