"""One Python domain executor; no Celery, Redis or worker package imports."""
import asyncio
import uuid
from sqlalchemy import select, update
from buyeros_api.db.outbox import DISPATCHED_STATE, TERMINAL_STATES, OutboxEvent
from buyeros_api.db.session import tenant_session
from . import handlers  # noqa: F401
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
    if row["state"] != DISPATCHED_STATE:
        return "not_dispatched"
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


async def run_domain_intent(engine, workspace_id: uuid.UUID, outbox_id: uuid.UUID,
                            generation: int) -> str:
    """Run one DB-only registered intent atomically on the caller's async loop.

    Unextracted object/provider handlers are explicitly unsupported here until
    their owning tasks land. No synthetic success or terminal write is made.
    """
    async with tenant_session(engine, workspace_id) as session:
        row = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.id == outbox_id
        ).with_for_update())).scalar_one_or_none()
        if row is None:
            return "unknown_intent"
        if row.state in TERMINAL_STATES:
            return "duplicate"
        if row.state != DISPATCHED_STATE:
            return "not_dispatched"
        if not fence_ok(generation, row.fencing_generation):
            return "stale"
        if row.event_type not in {"bulk.mutate", "fetch.evidence", "run.discover", "run.fit", "contact.submit"}:
            return "unsupported_event"
        return await run_intent(session, {"workspace_id": str(workspace_id)}, row.intent_key, generation)
