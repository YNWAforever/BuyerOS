"""Permitted offer URL retrieval with short tenant transactions around egress."""
from __future__ import annotations

import uuid
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from buyeros_api.api.deps import permission_for_roles
from buyeros_api.db.ingestion import OfferDocument
from buyeros_api.db.buyers import SourceDocument
from buyeros_api.db.models import Membership
from buyeros_api.db.outbox import AsyncJob, OutboxEvent
from .provider_context import execution_session as tenant_session
from buyeros_api.services.object_store import StoreUnavailable, get_private_store
from buyeros_api.services.offer_source_policy import current_offer_source_permission
from buyeros_api.services.pinned_transport import PinnedHttpsTransport
from buyeros_api.services.safe_fetch import fetch_permitted_document

from .leases import fence_ok

FETCH_EVENTS = frozenset({"offer.fetch"})


async def execute_offer_fetch(engine, workspace_id: uuid.UUID, intent_key: str,
                              generation: int, *, private_store=None, transport=None, execution=None) -> str:
    async with tenant_session(engine, workspace_id) as session:
        if execution is not None and not await execution.guard(session):
            return "stale"
        event = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id,
            OutboxEvent.intent_key == intent_key,
        ))).scalar_one_or_none()
        if event is None:
            return "unknown_intent"
        if event.state in {"done", "failed"}:
            return "duplicate"
        if event.state != "dispatched" or not fence_ok(generation, event.fencing_generation):
            return "stale"
        if event.event_type != "offer.fetch":
            return "unknown_handler"
        try:
            document_id = uuid.UUID(event.payload["document_id"])
            job_id = uuid.UUID(event.payload["job_id"])
        except (KeyError, TypeError, ValueError):
            return "invalid_fetch_intent"
        document = (await session.execute(select(OfferDocument).where(
            OfferDocument.workspace_id == workspace_id, OfferDocument.id == document_id,
        ))).scalar_one_or_none()
        job = (await session.execute(select(AsyncJob).where(
            AsyncJob.workspace_id == workspace_id, AsyncJob.id == job_id,
        ))).scalar_one_or_none()
        if (document is None or job is None or document.kind != "url"
                or document.project_id != job.project_id or job.kind != "offer_ingestion"
                or not isinstance(job.command, dict)
                or job.command.get("document_id") != str(document_id)
                or document.status != "queued"):
            return "invalid_fetch_intent"
        membership = (await session.execute(select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == job.actor_user_id, Membership.active.is_(True),
        ))).scalar_one_or_none()
        if membership is None or not permission_for_roles(membership.roles, "ingestOfferUrl"):
            return "policy_blocked"
        source_url = document.source_url
        if not source_url or job.command.get("source_url") != source_url:
            return "invalid_fetch_intent"
        decision = await current_offer_source_permission(
            session, workspace_id=workspace_id,
            project_id=document.project_id, source_url=source_url,
        )
        if decision is None:
            return "policy_blocked"
        if document.retention_until is None:
            return "invalid_fetch_intent"
        remaining = min(decision.expires_at, document.retention_until) - datetime.now(timezone.utc)
        retention_seconds = int(remaining.total_seconds())
        if retention_seconds < 1:
            return "policy_blocked"

    try:
        store = private_store if private_store is not None else get_private_store(workspace_id)
        checked_transport = transport if transport is not None else PinnedHttpsTransport()
        result = await asyncio.wait_for(fetch_permitted_document(
            {"url": source_url, "permitted": True, "retention_seconds": retention_seconds},
            checked_transport, store,
        ), timeout=45)
    except (StoreUnavailable, OSError, ValueError):
        return "storage_unavailable"
    except Exception:
        return "retrieval_unavailable"

    object_key = result.get("object_key") if result.get("status") == "retrieved" else None
    async with tenant_session(engine, workspace_id) as session:
        # The finalizer below deletes a private orphan on a stale fence.
        fence_current = execution is None or await execution.guard(session)
        event = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id,
            OutboxEvent.intent_key == intent_key,
        ).with_for_update())).scalar_one_or_none() if fence_current else None
        if event is None or event.state != "dispatched" or not fence_ok(generation, event.fencing_generation):
            terminal = "stale"
        else:
            document = (await session.execute(select(OfferDocument).where(
                OfferDocument.workspace_id == workspace_id, OfferDocument.id == document_id,
            ).with_for_update())).scalar_one_or_none()
            job = (await session.execute(select(AsyncJob).where(
                AsyncJob.workspace_id == workspace_id, AsyncJob.id == job_id,
            ).with_for_update())).scalar_one_or_none()
            decision = await current_offer_source_permission(
                session, workspace_id=workspace_id,
                project_id=job.project_id, source_url=source_url,
            ) if job is not None else None
            actor_membership = (await session.execute(select(Membership).where(
                Membership.workspace_id == workspace_id,
                Membership.user_id == job.actor_user_id, Membership.active.is_(True),
            ))).scalar_one_or_none() if job is not None else None
            retention_valid = (document is not None and document.retention_until is not None
                               and document.retention_until > datetime.now(timezone.utc))
            if (document is None or job is None or document.status != "queued"
                    or decision is None or actor_membership is None
                    or not permission_for_roles(actor_membership.roles, "ingestOfferUrl")
                    or not retention_valid):
                terminal = "stale"
            else:
                if object_key:
                    document.object_key = object_key
                    document.sha256 = result["digest"]
                    document.media_type = "text/plain"
                    document.filename = "web-source.txt"
                    document.source_url = result["source_url"]
                    document.status = "ready"
                    session.add(SourceDocument(
                        id=document_id, workspace_id=workspace_id,
                        project_id=document.project_id, permission_purpose="offer_research",
                        canonical_url=result["source_url"], digest=result["source_digest"],
                        retrieved_at=datetime.now(timezone.utc),
                        language=result.get("language", "und"), storage_mode="private_object",
                        object_key=object_key, excerpt=result["excerpt"],
                        retention_until=document.retention_until,
                    ))
                    job.status = "completed"
                    job.updated = 1
                else:
                    document.status = "failed"
                    document.failure_code = str(result.get("reason", "RETRIEVAL_FAILED")).upper()[:64]
                    job.status = "failed"
                    job.blocked = 1
                document.version += 1
                job.processed = 1
                event.state = "done"
                event.lease_owner = None
                event.lease_expires_at = None
                terminal = "done"
                if execution is not None:
                    execution.finish_done()
    if object_key and terminal != "done":
        try:
            await asyncio.wait_for(store.delete_private(object_key), timeout=10)
        except Exception:
            pass  # The private bucket lifecycle rule remains an activation gate.
    return terminal
