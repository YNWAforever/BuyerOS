"""Sensitive payload erasure uses the migration-owned, expiry-checked boundary."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, text, update, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.errors import ApiError
from ..db.runs import Person
from .audit_service import append_audit


async def expire_due_lead_subjects(session, *, now, policy_version, limit):
    """Bounded normal discovery; workers never SELECT private payload contents."""
    if not policy_version or not 1 <= len(policy_version) <= 64 or not 1 <= limit <= 100:
        raise ValueError("configured policy and bounded lead retention required")
    from .lead_schema import lead_schema_available
    if not await lead_schema_available(session):
        return []
    workspace = await session.scalar(text("SELECT NULLIF(current_setting('app.workspace_id',true),'')::uuid"))
    if workspace is None:
        raise ValueError("tenant scope required")
    people = list((await session.scalars(select(Person.id).where(
        Person.workspace_id == workspace, Person.retention_expires_at <= now,
        or_(Person.full_name.is_not(None), Person.role.is_not(None)),
    ).order_by(Person.retention_expires_at, Person.id).limit(limit)
        .with_for_update(skip_locked=True))).all())
    expired = []
    for identity in people:
        await redact_lead_subject(session, workspace_id=workspace, subject_type="person",
                                  subject_id=identity, now=now)
        expired.append(str(identity))
    remaining = limit - len(expired)
    if remaining:
        rows = (await session.execute(text(
            "SELECT subject_id,erased FROM public.buyeros_expire_due_lead_payloads(:workspace,:bound)"
        ), {"workspace": workspace, "bound": remaining})).all()
        for identity, erased in rows:
            if erased:
                append_audit(session, workspace_id=workspace, actor_id=None,
                    action="lead.payloads.expired", entity_type="lead_payload", entity_id=identity,
                    reason="RETENTION_EXPIRED")
                expired.append(str(identity))
    return expired


async def redact_lead_subject(
    session: AsyncSession, *, workspace_id: UUID, subject_type: str,
    subject_id: UUID, now: datetime,
) -> dict:
    if subject_type not in {"person", "contact_point", "source_document", "lead_payload", "offer_document"}:
        raise ApiError(422, "INVALID_REQUEST", "unsupported lead retention subject")
    if subject_type == "person":
        person = await session.scalar(select(Person).where(
            Person.workspace_id == workspace_id, Person.id == subject_id,
        ).with_for_update())
        if person is None:
            raise ApiError(404, "NOT_FOUND", "retention subject not found")
        if person.retention_expires_at is None or person.retention_expires_at > now:
            raise ApiError(409, "POLICY_BLOCKED", "person retention has not expired")
        person.full_name, person.role = None, None
        await session.flush()
    count = await session.scalar(text(
        "SELECT public.buyeros_redact_lead_subject(:workspace,:kind,:identity)"
    ), {"workspace": workspace_id, "kind": subject_type, "identity": subject_id})
    if count:
        append_audit(session, workspace_id=workspace_id, actor_id=None,
                     action="lead.payloads.expired", entity_type=subject_type, entity_id=subject_id,
                     reason="RETENTION_EXPIRED")
    return {"redacted": count, "subject_id": str(subject_id)}
