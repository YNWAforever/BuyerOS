"""Sensitive payload erasure uses the migration-owned, expiry-checked boundary."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.errors import ApiError
from ..db.runs import Person
from .audit_service import append_audit


async def redact_lead_subject(
    session: AsyncSession, *, workspace_id: UUID, subject_type: str,
    subject_id: UUID, now: datetime,
) -> dict:
    if subject_type not in {"person", "contact_point", "source_document"}:
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
