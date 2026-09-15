"""Celery task entrypoints: execute one outbox intent, ack only after commit.

The broker message is deliberately **not** the instruction source. It carries
only opaque ids (``intent_key``, ``workspace_id``, ``generation``); the event
type and payload are read from the ``outbox_events`` row inside the
transaction-local tenant context, and the row's fencing generation must still
match before any handler runs.
"""

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone

from celery import signals
from sqlalchemy import select, update

from buyeros_api.db.outbox import DISPATCHED_STATE, TERMINAL_STATES, OutboxEvent
from buyeros_api.db.session import tenant_session

from . import handlers  # noqa: F401  (import registers handlers)
from .app import celery_app
from .engine import create_engine, dispose_engine, set_active_engine
from .leases import fence_ok
from .registry import UnknownHandler, get_handler

# Handler result state -> terminal outbox state. ``retry`` is absent: it leaves
# the row non-terminal and asks Celery for a bounded retry.
TERMINAL_FOR_RESULT = {"done": "done", "blocked": "failed"}


class RetryRequested(Exception):
    """The handler asked for a bounded Celery retry; the transaction rolls back."""


class StaleFenced(Exception):
    """A superseded worker lost the fencing race; nothing may be committed."""


async def load_intent(session, intent_key: str) -> dict | None:
    """Lock and read the intent from the database (never from the message)."""
    row = (
        await session.execute(select(OutboxEvent).where(OutboxEvent.intent_key == intent_key).with_for_update())
    ).scalar_one_or_none()
    if row is None:
        return None
    return {
        "state": row.state,
        "event_type": row.event_type,
        "payload": row.payload,
        "fencing_generation": row.fencing_generation,
    }


async def mark_outbox_terminal(session, intent_key: str, generation: int, state: str) -> int:
    """Terminal write guarded by the fencing generation; returns rows updated."""
    result = await session.execute(
        update(OutboxEvent)
        .where(
            OutboxEvent.intent_key == intent_key,
            OutboxEvent.fencing_generation == generation,
            OutboxEvent.state == DISPATCHED_STATE,
        )
        .values(state=state, lease_owner=None, lease_expires_at=None)
    )
    return result.rowcount or 0


async def run_intent(session, context, intent_key: str, generation: int) -> str:
    """Resolve the intent from the DB, enforce fencing, then run one handler.

    Everything happens on one tenant-scoped transaction: the handler's writes
    and the terminal outbox write commit together, or neither does.
    """
    row = await load_intent(session, intent_key)
    if row is None:
        return "unknown_intent"
    if row["state"] in TERMINAL_STATES:
        return "duplicate"
    if not fence_ok(generation, row["fencing_generation"]):
        return "stale"

    try:
        handler = get_handler(row["event_type"])
    except UnknownHandler:
        await mark_outbox_terminal(session, intent_key, generation, "failed")
        return "unknown_handler"

    handler_context = dict(context or {})
    handler_context["event_type"] = row["event_type"]
    result = handler(session, handler_context, row["payload"])
    if asyncio.iscoroutine(result):
        result = await result

    if result.state == "retry":
        raise RetryRequested()

    terminal = TERMINAL_FOR_RESULT.get(result.state)
    if terminal is not None and await mark_outbox_terminal(session, intent_key, generation, terminal) == 0:
        raise StaleFenced()
    return result.state


async def _with_engine(body: Callable):
    """Create an engine, run ``body`` on a fresh loop, always dispose it."""
    engine = create_engine()
    set_active_engine(engine)
    try:
        return await body(engine)
    finally:
        try:
            await engine.dispose()
        finally:
            set_active_engine(None)


def execute_intent_sync(intent_key: str, workspace_id: str, generation: int) -> str:
    async def body(engine):
        async with tenant_session(engine, workspace_id) as session:
            return await run_intent(session, {"workspace_id": workspace_id}, intent_key, generation)

    try:
        return asyncio.run(_with_engine(body))
    except StaleFenced:
        return "stale"


def publish_message(message: dict) -> None:
    celery_app.send_task(
        "buyeros.execute_intent",
        args=[message["intent_key"], message["workspace_id"], message["generation"]],
    )


def sweep_sync() -> list[str]:
    from .config import get_settings
    from .dispatcher import sweep_once

    settings = get_settings()
    now = datetime.now(timezone.utc)

    async def body(engine):
        return await sweep_once(
            engine, publish_message, "buyeros-sweeper", now, settings.batch_size, settings.lease_seconds
        )

    return asyncio.run(_with_engine(body))


@celery_app.task(name="buyeros.execute_intent", acks_late=True, bind=True)
def execute_intent(self, intent_key: str, workspace_id: str, generation: int) -> str:
    try:
        return execute_intent_sync(intent_key, workspace_id, generation)
    except RetryRequested:
        raise self.retry(countdown=30, max_retries=3)


@celery_app.task(name="buyeros.sweep")
def sweep() -> int:
    """Periodic recovery task (see ``beat_schedule`` in ``app.build_app``)."""
    return len(sweep_sync())


signals.worker_shutdown.connect(dispose_engine, weak=False)
