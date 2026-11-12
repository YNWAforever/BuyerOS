"""Dedicated per-workspace conversation-turn admission.

The generic API limiter is actor-scoped and treats ``/conversation-turns`` as a
plain write. Starting a turn is the expensive conversation path, so it also has a
workspace-wide ceiling shared by every member.

Admission is one atomic upsert in its own transaction on the independent rate
engine: a later business failure (or the caller's rollback) cannot undo a
consumed slot, and a rejected request writes nothing into the turn transaction.
A completed idempotency replay never reaches this function.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert

from ..api.errors import ApiError
from ..db.rate import ConversationTurnRateWindow
from ..db.session import tenant_session
from ..settings import get_settings


def current_window() -> datetime:
    """Current UTC minute; tests monkeypatch this instead of sleeping."""
    return datetime.now(timezone.utc).replace(second=0, microsecond=0)


async def enforce_turn_rate_limit(engine, workspace_id: uuid.UUID) -> None:
    limit = get_settings().turn_per_minute
    if limit <= 0:
        return
    window_start = current_window()
    statement = insert(ConversationTurnRateWindow).values(
        workspace_id=workspace_id, window_start=window_start, hits=1,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[ConversationTurnRateWindow.workspace_id,
                        ConversationTurnRateWindow.window_start],
        set_={"hits": ConversationTurnRateWindow.hits + 1},
        where=ConversationTurnRateWindow.hits < limit,
    ).returning(ConversationTurnRateWindow.hits)
    # Separate transaction and independent engine: a rejected turn cannot roll
    # the counter back, and this admission write cannot be part of the caller's
    # turn/task/budget transaction.
    async with tenant_session(engine, workspace_id) as session:
        accepted = (await session.execute(statement)).scalar_one_or_none()
    if accepted is None:
        raise ApiError(429, 'TURN_RATE_LIMITED', 'turn rate limit reached', retryable=True)
