"""Fenced, retryable private-object cleanup after a committed source tombstone."""
from __future__ import annotations

import uuid
import asyncio
from datetime import datetime, timezone

import psycopg
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import async_sessionmaker

from buyeros_api.db.buyers import SourceDocument
from buyeros_api.db.models import Workspace
from buyeros_api.db.runs import ContactPoint
from buyeros_api.db.outbox import OutboxEvent
from ..provider_context import execution_session as tenant_session
from buyeros_api.services.object_store import get_private_store
from buyeros_api.services.retention import expire_subject_data

from ..config import get_settings
from ..leases import fence_ok


async def _delete_run_checkpoints(dsn: str, workspace_id: uuid.UUID, run_id: uuid.UUID) -> None:
    """Use the existing worker-only graph role under transaction-local RLS."""
    prefix = f"{workspace_id}:{run_id}:%"
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as connection:
        async with connection.transaction():
            role = await connection.execute(
                "SELECT NOT rolsuper AND NOT rolbypassrls "
                "AND pg_has_role(current_user,'buyeros_worker','MEMBER') "
                "FROM pg_roles WHERE rolname=current_user"
            )
            if (await role.fetchone())[0] is not True:
                raise ValueError("checkpoint cleanup requires the dedicated worker role")
            await connection.execute("SELECT set_config('app.workspace_id', %s, true)",
                                     (str(workspace_id),))
            for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                await connection.execute(
                    f"DELETE FROM buyeros_graph.{table} WHERE thread_id LIKE %s", (prefix,)
                )


async def execute_source_delete(
    engine, workspace_id: uuid.UUID, intent_key: str, generation: int, *, private_store=None, execution=None,
) -> str:
    async with tenant_session(engine, workspace_id) as session:
        if execution is not None and not await execution.guard(session):
            return "stale"
        event = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id, OutboxEvent.intent_key == intent_key,
        ))).scalar_one_or_none()
        if event is None:
            return "unknown_intent"
        if event.state in {"done", "failed"}:
            return "duplicate"
        if event.state != "dispatched":
            return "not_dispatched"
        if not fence_ok(generation, event.fencing_generation):
            return "stale"
        if event.event_type != "source.delete":
            return "unknown_handler"
        try:
            source_id = uuid.UUID(event.payload["source_document_id"])
        except (KeyError, TypeError, ValueError):
            return "invalid_retention_intent"
        source = (await session.execute(select(SourceDocument).where(
            SourceDocument.workspace_id == workspace_id, SourceDocument.id == source_id,
        ))).scalar_one_or_none()
        if source is None:
            return "source_missing"
        if (source.excerpt is not None or source.retention_until is None
                or source.retention_until > datetime.now(timezone.utc)
                or not source.canonical_url.startswith("https://redacted.invalid/")):
            return "source_not_tombstoned"
        object_key = source.object_key

    if object_key:
        try:
            store = private_store if private_store is not None else get_private_store(workspace_id)
            await asyncio.wait_for(store.delete_private(object_key), timeout=45)
        except Exception:
            return "storage_unavailable"

    if source.run_id is not None:
        checkpoint_dsn = get_settings().checkpoint_database_url
        if not checkpoint_dsn:
            return "checkpoint_unavailable"
        try:
            await asyncio.wait_for(_delete_run_checkpoints(checkpoint_dsn, workspace_id, source.run_id), timeout=45)
        except Exception:
            return "checkpoint_unavailable"

    async with tenant_session(engine, workspace_id) as session:
        if execution is not None and not await execution.guard(session):
            return "stale"
        event = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id, OutboxEvent.intent_key == intent_key,
        ).with_for_update())).scalar_one_or_none()
        if event is None or event.state != "dispatched" or not fence_ok(generation, event.fencing_generation):
            return "stale"
        source = (await session.execute(select(SourceDocument).where(
            SourceDocument.workspace_id == workspace_id, SourceDocument.id == source_id,
        ).with_for_update())).scalar_one_or_none()
        if source is None or source.object_key != object_key or source.excerpt is not None:
            return "stale"
        source.object_key = None
        event.state = "done"
        event.lease_owner = None
        event.lease_expires_at = None
        if execution is not None:
            execution.finish_done()
    return "done"


async def expire_due_sources(engine, now, *, policy_version: str, limit: int = 100) -> list[str]:
    """Tombstone only elapsed sources under the configured retention policy.

    The sweep creates deletion intents; private-object IO runs through the
    fenced outbox handler after this transaction commits. Replaying a
    tombstoned row repairs an outbox intent lost during a restore.
    """
    if not policy_version or not 1 <= limit <= 100:
        raise ValueError("explicit retention policy version and bounded limit required")
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as root_session:
        workspace_ids = list((await root_session.execute(
            select(Workspace.id).order_by(Workspace.id)
        )).scalars())

    expired: list[str] = []
    for workspace_id in workspace_ids:
        remaining = limit - len(expired)
        if remaining <= 0:
            break
        async with tenant_session(engine, workspace_id) as session:
            source_ids = list((await session.execute(
                select(SourceDocument.id).where(
                    SourceDocument.workspace_id == workspace_id,
                    SourceDocument.retention_until.is_not(None),
                    SourceDocument.retention_until <= now,
                    or_(
                        SourceDocument.canonical_url.not_like("https://redacted.invalid/%"),
                        SourceDocument.excerpt.is_not(None),
                        SourceDocument.object_key.is_not(None),
                    ),
                ).order_by(SourceDocument.retention_until, SourceDocument.id)
                .limit(remaining).with_for_update(skip_locked=True)
            )).scalars())
            for source_id in source_ids:
                await expire_subject_data(
                    session, source_id, policy_version, now, subject_type="source_document"
                )
                expired.append(str(source_id))
    return expired


async def expire_due_contacts(engine, now, *, policy_version: str, limit: int = 100) -> list[str]:
    """Expire explicit contact deadlines under tenant RLS; never infer a legal default."""
    if not policy_version or not 1 <= limit <= 100:
        raise ValueError("explicit retention policy version and bounded limit required")
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as root_session:
        workspace_ids = list((await root_session.execute(
            select(Workspace.id).order_by(Workspace.id)
        )).scalars())
    expired: list[str] = []
    for workspace_id in workspace_ids:
        remaining = limit - len(expired)
        if remaining <= 0:
            break
        async with tenant_session(engine, workspace_id) as session:
            contact_ids = list((await session.execute(
                select(ContactPoint.id).where(
                    ContactPoint.workspace_id == workspace_id,
                    ContactPoint.retention_expires_at.is_not(None),
                    ContactPoint.retention_expires_at <= now,
                    ContactPoint.normalized_value.not_like("expired+%@redacted.invalid"),
                ).order_by(ContactPoint.retention_expires_at, ContactPoint.id)
                .limit(remaining).with_for_update(skip_locked=True)
            )).scalars())
            for contact_id in contact_ids:
                await expire_subject_data(
                    session, contact_id, policy_version, now, subject_type="contact_point"
                )
                expired.append(str(contact_id))
    return expired
