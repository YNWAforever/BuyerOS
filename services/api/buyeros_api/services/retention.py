"""Tenant-scoped, fail-closed retention lifecycle.

The database tombstone precedes private-object deletion. A worker may retry
the object deletion after a crash without restoring readable source content.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime

from sqlalchemy import null, or_, select, update

from ..api.errors import ApiError
from ..db.buyers import Evidence, FitAssessment, SourceDocument
from ..db.drafts import Approval, DraftRevision, OutreachDraft
from ..db.outbox import OutboxEvent
from ..db.outcomes import ExportJob
from ..db.runs import ContactPoint, Person
from .audit_service import append_audit
from .approval_service import invalidate_approvals_for_subject


async def _ensure_source_delete_intent(session, row: SourceDocument) -> None:
    key = f"source.delete:{row.id}"
    event = (await session.execute(select(OutboxEvent).where(
        OutboxEvent.workspace_id == row.workspace_id,
        OutboxEvent.intent_key == key,
    ).with_for_update())).scalar_one_or_none()
    if event is None:
        session.add(OutboxEvent(
            workspace_id=row.workspace_id, intent_key=key, event_type="source.delete",
            payload={"source_document_id": str(row.id)},
        ))
    elif event.state in {"done", "failed"}:
        event.state = "ready"
        event.lease_owner = None
        event.lease_expires_at = None


def _redacted_draft_content(content: dict, *, subject: str = "source") -> dict:
    label = "Source expired" if subject == "source" else "Contact expired"
    return {
        "subject": label, "body": label,
        "kind": content.get("kind") if content.get("kind") in {"initial", "follow_up"} else "initial",
        "language": content.get("language") if content.get("language") in {"en", "zh-HK"} else "en",
        "icp_version_id": content.get("icp_version_id"),
        "evidence_set_hash": content.get("evidence_set_hash"),
        "value_proposition_fact_ids": [], "policy_decision_ids": [],
        "context_hash": "0" * 64, "grounding_status": f"{subject}_expired",
        "claims": [], "evidence_refs": [],
    }


async def _redact_derived_source_content(session, row: SourceDocument) -> None:
    evidence_ids = list((await session.execute(select(Evidence.id).where(
        Evidence.workspace_id == row.workspace_id,
        Evidence.source_document_id == row.id,
    ))).scalars())
    if not evidence_ids:
        return
    references = [str(value) for value in evidence_ids]
    fit_predicates = [FitAssessment.evidence_ids.contains([value]) for value in references]
    fits = list((await session.execute(select(FitAssessment).where(
        FitAssessment.workspace_id == row.workspace_id,
        or_(*fit_predicates),
    ).with_for_update())).scalars())
    for fit in fits:
        fit.verdict = "needs_review"
        fit.rationale = "Source expired"
        fit.assessment_details = {}

    revision_predicates = [DraftRevision.evidence_ids.contains([value]) for value in references]
    revisions = list((await session.execute(select(DraftRevision).where(
        DraftRevision.workspace_id == row.workspace_id,
        or_(*revision_predicates),
    ).with_for_update())).scalars())
    draft_ids = set()
    for revision in revisions:
        safe = _redacted_draft_content(revision.content)
        revision.content = safe
        revision.content_hash = hashlib.sha256(json.dumps(
            safe, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")).hexdigest()
        draft_ids.add(revision.draft_id)
    if draft_ids:
        await session.execute(update(OutreachDraft).where(
            OutreachDraft.workspace_id == row.workspace_id,
            OutreachDraft.id.in_(draft_ids),
        ).values(
            state="stale", review_context=None, review_context_hash=None,
            review_revision_id=None, state_version=OutreachDraft.state_version + 1,
        ))


async def _expire_contact(session, subject_id: uuid.UUID, policy_version: str, now: datetime) -> dict:
    contact = (await session.execute(select(ContactPoint).where(
        ContactPoint.id == subject_id,
    ).with_for_update())).scalar_one_or_none()
    if contact is None:
        raise ApiError(404, "NOT_FOUND", "retention subject not found")
    if contact.retention_expires_at is None or contact.retention_expires_at > now:
        raise ApiError(409, "POLICY_BLOCKED", "contact retention has not expired")
    if contact.validity == "unavailable" and contact.normalized_value.startswith("expired+"):
        return {"expired": False, "subject_id": str(contact.id)}
    contact.normalized_value = f"expired+{contact.id}@redacted.invalid"
    contact.validity = "unavailable"
    contact.quarantined = True
    contact.version += 1
    if contact.person_id is not None:
        await session.execute(update(Person).where(
            Person.workspace_id == contact.workspace_id,
            Person.id == contact.person_id,
            Person.retention_expires_at.is_not(None),
            Person.retention_expires_at <= now,
        ).values(full_name=None, role=None))
    await session.flush()

    revisions = list((await session.execute(select(DraftRevision).where(
        DraftRevision.workspace_id == contact.workspace_id,
        DraftRevision.content["recipient_contact_id"].as_string() == str(contact.id),
    ).with_for_update())).scalars())
    draft_ids = set()
    for revision in revisions:
        safe = _redacted_draft_content(revision.content, subject="contact")
        revision.content = safe
        revision.content_hash = hashlib.sha256(json.dumps(
            safe, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")).hexdigest()
        draft_ids.add(revision.draft_id)
    if draft_ids:
        await session.execute(update(OutreachDraft).where(
            OutreachDraft.workspace_id == contact.workspace_id,
            OutreachDraft.id.in_(draft_ids),
        ).values(
            state="stale", review_context=None, review_context_hash=None,
            review_revision_id=None, state_version=OutreachDraft.state_version + 1,
        ))
        projects = select(OutreachDraft.project_id).where(
            OutreachDraft.workspace_id == contact.workspace_id,
            OutreachDraft.id.in_(draft_ids),
        )
        await session.execute(update(ExportJob).where(
            ExportJob.workspace_id == contact.workspace_id,
            ExportJob.project_id.in_(projects),
            ExportJob.include_contact_data.is_(True),
            ExportJob.state == "ready",
        ).values(state="revoked", expires_at=now, version=ExportJob.version + 1))
    await invalidate_approvals_for_subject(
        session, workspace_id=contact.workspace_id, subject_type="contact_point",
        subject_id=contact.id, reason="CONTACT_EXPIRED",
    )
    await session.execute(update(Approval).where(
        Approval.workspace_id == contact.workspace_id,
        Approval.recipient_contact_id == contact.id,
        Approval.invalidated_reason.is_not(None),
        Approval.context_snapshot.is_not(None),
    ).values(context_snapshot=null()))
    append_audit(
        session, workspace_id=contact.workspace_id, actor_id=None,
        action="contact.expired", entity_type="contact_point", entity_id=contact.id,
        reason="RETENTION_EXPIRED",
        detail_digest="sha256:" + hashlib.sha256(policy_version.encode()).hexdigest(),
    )
    return {"expired": True, "subject_id": str(contact.id)}


async def expire_subject_data(
    session, subject_id: uuid.UUID, policy_version: str, now: datetime,
    *, subject_type: str,
) -> dict:
    if not policy_version or len(policy_version) > 64:
        raise ApiError(422, "INVALID_REQUEST", "policy version is required")
    if subject_type == "contact_point":
        return await _expire_contact(session, subject_id, policy_version, now)
    if subject_type != "source_document":
        raise ApiError(422, "INVALID_REQUEST", "unsupported retention subject")
    row = (await session.execute(
        select(SourceDocument).where(SourceDocument.id == subject_id).with_for_update()
    )).scalar_one_or_none()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "retention subject not found")
    if row.retention_until is None or row.retention_until > now:
        raise ApiError(409, "POLICY_BLOCKED", "source retention has not expired")
    if row.excerpt is None and row.canonical_url.startswith("https://redacted.invalid/"):
        if row.object_key or row.run_id:
            await _ensure_source_delete_intent(session, row)
        return {"expired": False, "subject_id": str(row.id)}
    row.excerpt = None
    row.canonical_url = f"https://redacted.invalid/{row.id}"
    await session.flush()
    await _redact_derived_source_content(session, row)
    await session.execute(update(Evidence).where(
        Evidence.workspace_id == row.workspace_id,
        Evidence.source_document_id == row.id,
    ).values(excerpt="Source expired", translation=None, version=Evidence.version + 1))
    if row.project_id is not None:
        await invalidate_approvals_for_subject(
            session, workspace_id=row.workspace_id, subject_type="project",
            subject_id=row.project_id, reason="SOURCE_EXPIRED",
        )
        project_drafts = select(OutreachDraft.id).where(
            OutreachDraft.workspace_id == row.workspace_id,
            OutreachDraft.project_id == row.project_id,
        )
        await session.execute(update(Approval).where(
            Approval.workspace_id == row.workspace_id,
            Approval.draft_id.in_(project_drafts),
            Approval.invalidated_reason.is_not(None),
            Approval.context_snapshot.is_not(None),
        ).values(context_snapshot=null()))
        await session.execute(update(ExportJob).where(
            ExportJob.workspace_id == row.workspace_id,
            ExportJob.project_id == row.project_id,
            ExportJob.state == "ready",
        ).values(state="revoked", expires_at=now, version=ExportJob.version + 1))
    if row.object_key or row.run_id:
        await _ensure_source_delete_intent(session, row)
    append_audit(
        session, workspace_id=row.workspace_id, actor_id=None,
        action="source.expired", entity_type="source_document", entity_id=row.id,
        reason="RETENTION_EXPIRED",
        detail_digest="sha256:" + hashlib.sha256(policy_version.encode()).hexdigest(),
    )
    return {"expired": True, "subject_id": str(row.id)}
