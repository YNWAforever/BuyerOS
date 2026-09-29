"""Celery task entrypoints: execute one outbox intent, ack only after commit.

The broker message is deliberately **not** the instruction source. It carries
only opaque ids (``intent_key``, ``workspace_id``, ``generation``); the event
type and payload are read from the ``outbox_events`` row inside the
transaction-local tenant context, and the row's fencing generation must still
match before any handler runs.
"""

import asyncio
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from celery import signals
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from buyeros_api.db.outbox import DISPATCHED_STATE, TERMINAL_STATES, OutboxEvent
from buyeros_api.db.worker import WorkerHeartbeat
from buyeros_api.db.session import tenant_session
from buyeros_api.providers.base import ProviderAdapter, ProviderIntent

from . import handlers  # noqa: F401  (import registers handlers)
from .app import celery_app
from .engine import create_engine, dispose_engine, run_async, set_active_engine
from .external_runner import execute_external, reconcile_intent_key
from .handlers.contact_submit import execute_contact_lookup
from .handlers.reconcile import execute_contact_reconcile
from .handlers.retention import execute_source_delete, expire_due_sources, expire_due_contacts
from .document_runner import DOCUMENT_EVENTS, execute_document
from .discovery_runner import execute_discovery, execute_discovery_reconcile
from .fetch_runner import FETCH_EVENTS, execute_offer_fetch
from .fit_execution import execute_fit
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


EXTERNAL_EVENTS = frozenset({"provider.external", "provider.reconcile"})


def resolve_provider_adapter(service: str) -> ProviderAdapter | None:
    """Live activation is empty until one named provider passes T14 evidence."""
    return None


def _provider_command(intent_key: str, event_type: str, payload: object):
    if not isinstance(payload, dict):
        return None
    try:
        operation_id = uuid.UUID(payload["operation_id"])
        original_key = (payload["original_intent_key"] if event_type == "provider.reconcile"
                        else intent_key)
        if (event_type == "provider.reconcile"
                and intent_key != reconcile_intent_key(operation_id)):
            return None
        intent = ProviderIntent(original_key, payload["service"], payload["market"],
                                payload["language"], payload["role"])
        if intent.service not in {"search", "model", "contact"}:
            return None
        return operation_id, intent
    except (KeyError, TypeError, ValueError):
        return None


def execute_intent_sync(intent_key: str, workspace_id: str, generation: int, *,
                        adapter: ProviderAdapter | None = None, search_adapter=None,
                        environment: str = "production", private_store=None, fetch_transport=None,
                        checkpoint_dsn: str | None = None) -> str:
    async def body(engine):
        async with tenant_session(engine, workspace_id) as session:
            row = await load_intent(session, intent_key)
            if row is None:
                return "unknown_intent"
            if row["state"] in TERMINAL_STATES:
                return "duplicate"
            if row["state"] != DISPATCHED_STATE:
                return "not_dispatched"
            if not fence_ok(generation, row["fencing_generation"]):
                return "stale"
            if row["event_type"] in {"provider.reconcile", "research.reconcile", "contact.reconcile"}:
                from .config import get_settings
                if not get_settings().reconciliation_enabled:
                    return "reconciliation_disabled"
            if row["event_type"] in DOCUMENT_EVENTS:
                document_event = True
            else:
                document_event = False
            source_delete_event = row["event_type"] == "source.delete"
            fetch_event = row["event_type"] in FETCH_EVENTS
            discovery_event = (row["event_type"] == "run.discover" and
                               search_adapter is not None and environment == "test")
            discovery_reconcile_event = (row["event_type"] == "research.reconcile" and
                                         search_adapter is not None and environment == "test")
            fit_event = row["event_type"] == "run.fit" and checkpoint_dsn is not None
            contact_event = row["event_type"] == "contact.lookup"
            contact_reconcile_event = row["event_type"] == "contact.reconcile"
            try:
                contact_job_id = uuid.UUID(row["payload"]["job_id"]) if (contact_event or contact_reconcile_event) else None
                contact_operation_id = uuid.UUID(row["payload"]["operation_id"]) if contact_reconcile_event else None
                if (contact_event or contact_reconcile_event) and row["payload"].get("workspace_id") != workspace_id:
                    return "invalid_provider_intent"
            except (KeyError, TypeError, ValueError, AttributeError):
                return "invalid_provider_intent"
            if (row["event_type"] not in EXTERNAL_EVENTS and not document_event
                    and not fetch_event and not discovery_event and not discovery_reconcile_event
                    and not fit_event and not contact_event and not contact_reconcile_event
                    and not source_delete_event):
                return await run_intent(session, {"workspace_id": workspace_id},
                                        intent_key, generation)
            command = _provider_command(intent_key, row["event_type"], row["payload"])
        # The tenant transaction has committed before any object or provider network call.
        if discovery_event:
            return await execute_discovery(
                engine, uuid.UUID(workspace_id), intent_key, generation,
                adapter=search_adapter, environment=environment,
            )
        if discovery_reconcile_event:
            return await execute_discovery_reconcile(
                engine, uuid.UUID(workspace_id), intent_key, generation,
                adapter=search_adapter, environment=environment,
            )
        if fit_event:
            return await execute_fit(engine, uuid.UUID(workspace_id), intent_key,
                                     generation, checkpoint_dsn=checkpoint_dsn)
        if fetch_event:
            return await execute_offer_fetch(
                engine, uuid.UUID(workspace_id), intent_key, generation,
                private_store=private_store, transport=fetch_transport,
            )
        if document_event:
            return await execute_document(
                engine, uuid.UUID(workspace_id), intent_key, generation,
                private_store=private_store,
            )
        if source_delete_event:
            return await execute_source_delete(
                engine, uuid.UUID(workspace_id), intent_key, generation,
                private_store=private_store,
            )
        if contact_event:
            chosen_adapter = adapter or resolve_provider_adapter("contact")
            if chosen_adapter is None:
                return "provider_unavailable"
            if environment != "test":
                from .config import get_settings
                if not get_settings().paid_dispatch_enabled:
                    return "dispatch_disabled"
            return await execute_contact_lookup(
                engine, uuid.UUID(workspace_id), contact_job_id, generation,
                chosen_adapter, environment=environment,
            )
        if contact_reconcile_event:
            chosen_adapter = adapter or resolve_provider_adapter("contact")
            if chosen_adapter is None:
                return "provider_unavailable"
            return await execute_contact_reconcile(
                engine, uuid.UUID(workspace_id), contact_job_id, contact_operation_id,
                intent_key, generation, chosen_adapter, environment=environment,
            )
        if command is None:
            return "invalid_provider_intent"
        operation_id, intent = command
        chosen_adapter = adapter or resolve_provider_adapter(intent.service)
        if chosen_adapter is None:
            return "provider_unavailable"
        if row["event_type"] == "provider.external" and environment != "test":
            from .config import get_settings
            if not get_settings().paid_dispatch_enabled:
                return "dispatch_disabled"
        return await execute_external(
            engine, uuid.UUID(workspace_id), operation_id, generation,
            chosen_adapter, intent, environment=environment,
            outbox_intent_key=intent_key,
        )

    try:
        return run_async(_with_engine(body))
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
        if settings.retention_policy_version:
            await expire_due_sources(
                engine, now, policy_version=settings.retention_policy_version,
                limit=settings.batch_size,
            )
            await expire_due_contacts(
                engine, now, policy_version=settings.retention_policy_version,
                limit=settings.batch_size,
            )
        return await sweep_once(
            engine, publish_message, "buyeros-sweeper", now, settings.batch_size, settings.lease_seconds
        )

    return run_async(_with_engine(body))


def record_worker_heartbeat_sync() -> None:
    """Record that a broker-delivered sweep reached a committed worker transaction."""
    async def body(engine):
        async with engine.begin() as connection:
            at = datetime.now(timezone.utc)
            statement = insert(WorkerHeartbeat).values(
                worker_id="celery-sweeper", observed_at=at, broker_state="ready"
            ).on_conflict_do_update(
                index_elements=[WorkerHeartbeat.worker_id],
                set_={"observed_at": at, "broker_state": "ready"},
            )
            await connection.execute(statement)
    run_async(_with_engine(body))


@celery_app.task(name="buyeros.execute_intent", acks_late=True, bind=True)
def execute_intent(self, intent_key: str, workspace_id: str, generation: int) -> str:
    try:
        return execute_intent_sync(intent_key, workspace_id, generation)
    except RetryRequested:
        raise self.retry(countdown=30, max_retries=3)


@celery_app.task(name="buyeros.sweep")
def sweep() -> int:
    """Periodic recovery task (see ``beat_schedule`` in ``app.build_app``)."""
    count = len(sweep_sync())
    # Eager/disposable calls are not evidence that the broker delivered a task.
    from .config import get_settings
    if not get_settings().eager:
        record_worker_heartbeat_sync()
    return count


signals.worker_shutdown.connect(dispose_engine, weak=False)
