"""Retention enforcement for derived conversation data (Phase 3.4).

Two append-only structures grow with every turn and are safe to drop once they
are older than the configured window:

* ``conversation_turn_events`` — derived SSE replay source. Pruning an event
  never changes ``conversation_turns.parts``/``status`` and never changes the
  thread version, so a pruned replay degrades to the persisted transcript.
* ``api_rate_windows`` and ``conversation_turn_rate_windows`` — transient
  per-minute counters whose only purpose is the current window.

User content (turns, parts, proposals, decisions, reconciliations) is never
touched here. Sweeps are bounded and tenant-scoped: the workspace directory is
read once, then every delete runs inside ``tenant_session`` so forced RLS on
each table applies even to a mistake in this module.

Values of ``0`` disable the corresponding sweep (production default is set by
the worker settings, reviewed in the release packet).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from ..db.session import tenant_session
from ..db.conversation_turn_events import ConversationTurnEvent
from ..db.models import Workspace
from ..db.rate import ApiRateWindow, ConversationTurnRateWindow

# One sweep is bounded so a large backlog is drained by repeated, short
# transactions instead of one long lock-taking delete.
MAX_SWEEP = 5000
MAX_RETENTION_DAYS = 3650


def _validate(retention: int, limit: int, *, label: str) -> None:
    if not isinstance(retention, int) or isinstance(retention, bool) or retention < 0:
        raise ValueError(f"{label} retention must be a non-negative integer")
    if label == "event" and retention > MAX_RETENTION_DAYS:
        raise ValueError("event retention must not exceed ten years")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 0 < limit <= MAX_SWEEP:
        raise ValueError(f"sweep limit must be between 1 and {MAX_SWEEP}")


async def _workspace_ids(engine: AsyncEngine) -> list[uuid.UUID]:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        return list((await session.execute(
            select(Workspace.id).order_by(Workspace.id)
        )).scalars())


async def prune_turn_events(engine: AsyncEngine, now: datetime, *,
                            retention_days: int, limit: int = MAX_SWEEP) -> int:
    """Delete turn events older than ``retention_days``; turns are untouched."""
    _validate(retention_days, limit, label="event")
    if retention_days == 0:
        return 0
    cutoff = now - timedelta(days=retention_days)
    pruned = 0
    for workspace_id in await _workspace_ids(engine):
        remaining = limit - pruned
        if remaining <= 0:
            break
        async with tenant_session(engine, workspace_id) as session:
            event_ids = list((await session.execute(
                select(ConversationTurnEvent.id).where(
                    ConversationTurnEvent.workspace_id == workspace_id,
                    ConversationTurnEvent.created_at < cutoff,
                ).order_by(ConversationTurnEvent.created_at, ConversationTurnEvent.id)
                .limit(remaining)
            )).scalars())
            if event_ids:
                await session.execute(delete(ConversationTurnEvent).where(
                    ConversationTurnEvent.workspace_id == workspace_id,
                    ConversationTurnEvent.id.in_(event_ids),
                ))
            pruned += len(event_ids)
    return pruned


async def prune_rate_windows(engine: AsyncEngine, now: datetime, *,
                             retention_minutes: int, limit: int = MAX_SWEEP) -> int:
    """Delete per-minute counters older than ``retention_minutes``.

    Rate windows are keyed by minute, so a day of history is at most 1440 rows
    per actor/bucket/workspace; the sweep count only bounds how many workspaces
    a single call visits.
    """
    _validate(retention_minutes, limit, label="rate-window")
    if retention_minutes == 0:
        return 0
    cutoff = now - timedelta(minutes=retention_minutes)
    pruned = 0
    for workspace_id in await _workspace_ids(engine):
        remaining = limit - pruned
        if remaining <= 0:
            break
        async with tenant_session(engine, workspace_id) as session:
            for model in (ApiRateWindow, ConversationTurnRateWindow):
                result = await session.execute(delete(model).where(
                    model.workspace_id == workspace_id,
                    model.window_start < cutoff,
                ))
                pruned += int(result.rowcount or 0)
    return pruned
