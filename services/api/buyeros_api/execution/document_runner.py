"""Private document I/O outside database transactions; fenced finalization."""
from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select, update

from buyeros_api.db.ingestion import OfferDocument
from buyeros_api.db.buyers import SourceDocument
from buyeros_api.db.outbox import OutboxEvent
from buyeros_api.db.models import Membership
from buyeros_api.api.deps import permission_for_roles
from buyeros_api.db.session import tenant_session
from buyeros_api.services.ingestion_service import parse_candidate_facts, validate_upload
from buyeros_api.services.object_store import StoreUnavailable, get_private_store

from .leases import fence_ok
from .pdf_parser import PdfParserTimeout, parse_pdf_candidates

DOCUMENT_EVENTS = frozenset({"offer.parse", "offer.delete"})


async def execute_document(engine, workspace_id: uuid.UUID, intent_key: str,
                           generation: int, *, private_store=None, execution=None) -> str:
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
        if event.event_type not in DOCUMENT_EVENTS:
            return "unknown_handler"
        try:
            document_id = uuid.UUID(event.payload["document_id"])
        except (KeyError, TypeError, ValueError):
            return "invalid_document_intent"
        row = (await session.execute(select(OfferDocument).where(
            OfferDocument.workspace_id == workspace_id, OfferDocument.id == document_id,
        ))).scalar_one_or_none()
        if row is None:
            return "document_missing"
        kind, filename, media_type, digest = row.kind, row.filename, row.media_type, row.sha256
        status, object_key = row.status, row.object_key
        event_type = event.event_type
        actor_id = event.payload.get("actor_user_id")
        if event_type == "offer.parse" and (execution is not None or actor_id is not None):
            if not await _parse_actor_current(session, workspace_id, actor_id):
                return "actor_changed"

    # Storage egress can block. No tenant transaction or row lock crosses this boundary.
    if event_type == "offer.parse" and status == "deleted":
        result, facts = "deleted", []
    elif event_type == "offer.parse" and status != "quarantined":
        result, facts = "already_processed", []
    elif event_type == "offer.parse" and (kind != "upload" or not object_key or not digest):
        result, facts = "invalid_document", []
    elif event_type == "offer.delete" and not object_key:
        result, facts = "deleted", []
    else:
        try:
            store = private_store if private_store is not None else get_private_store(workspace_id)
            if event_type == "offer.delete":
                await asyncio.wait_for(store.delete_private(object_key), timeout=45)
                result, facts = "deleted", []
            else:
                body = await asyncio.wait_for(store.get_private(object_key), timeout=45)
                upload = validate_upload(filename, media_type, body, digest)
                result = "parsed"
                facts = (await asyncio.to_thread(parse_pdf_candidates, upload)
                         if upload.kind == "pdf" else parse_candidate_facts(upload))
        except PdfParserTimeout:
            result, facts = "parser_timeout", []
        except StoreUnavailable:
            return "storage_unavailable"
        except ValueError:
            if event_type == "offer.delete":
                return "storage_unavailable"
            result, facts = "invalid_document", []
        except Exception:
            return "storage_unavailable"

    async with tenant_session(engine, workspace_id) as session:
        if execution is not None and not await execution.guard(session):
            return "stale"
        event = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id, OutboxEvent.intent_key == intent_key,
        ).with_for_update())).scalar_one_or_none()
        if event is None or event.state != "dispatched" or not fence_ok(generation, event.fencing_generation):
            return "stale"
        row = (await session.execute(select(OfferDocument).where(
            OfferDocument.workspace_id == workspace_id, OfferDocument.id == document_id,
        ).with_for_update())).scalar_one_or_none()
        if row is None:
            return "document_missing"
        if event_type == "offer.parse" and (execution is not None or actor_id is not None):
            if not await _parse_actor_current(session, workspace_id, actor_id):
                return "actor_changed"
        if event_type == "offer.delete":
            if row.status != "deleted":
                return "stale"
            row.object_key = None
            source = (await session.execute(select(SourceDocument).where(
                SourceDocument.workspace_id == workspace_id, SourceDocument.id == document_id,
            ).with_for_update())).scalar_one_or_none()
            if source is not None:
                source.object_key = None
                source.excerpt = None
        elif row.status == "quarantined":
            if result == "parsed":
                row.fact_candidates = [
                    {
                        "id": str(uuid.uuid5(document_id, f"{index}:{fact['field']}:{fact['value']}")),
                        "field": fact["field"], "value": fact["value"],
                        "provenance": "document_excerpt", "source_document_id": str(document_id),
                        "excerpt": fact["value"], "approved": False,
                    }
                    for index, fact in enumerate(facts)
                ]
                row.status = "ready"
            elif result == "parser_timeout":
                row.status, row.failure_code = "failed", "PARSER_TIMEOUT"
            elif result == "invalid_document":
                row.status, row.failure_code = "failed", "INVALID_DOCUMENT"
            row.version += 1
        event.state = "done"
        event.lease_owner = None
        event.lease_expires_at = None
        if execution is not None:
            execution.finish_done()
    return "done"


async def _parse_actor_current(session, workspace_id, raw_actor):
    try:
        actor = uuid.UUID(raw_actor)
    except (ValueError, TypeError, AttributeError):
        return False
    membership = (await session.execute(select(Membership).where(
        Membership.workspace_id == workspace_id, Membership.user_id == actor,
        Membership.active.is_(True)).with_for_update())).scalar_one_or_none()
    return membership is not None and permission_for_roles(membership.roles, "uploadOfferDocument")
