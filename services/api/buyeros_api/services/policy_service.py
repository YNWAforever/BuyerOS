"""Fail-closed, purpose-specific policy and suppression evaluation (BO-009)."""
import re
import uuid
from hashlib import sha256
from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select, update

from ..api.errors import ApiError
from ..db.buyers import Company
from ..db.icp import Project
from ..db.policy import PURPOSES, PolicyDecision, Suppression
from ..db.runs import ContactPoint

_RANK = {"permitted": 0, "requires_review": 1, "blocked": 2}


def effective_decision(decisions: list[dict], purpose: str) -> str:
    """Most restrictive provided status for one purpose; absence is unknown."""
    relevant = [d["status"] for d in decisions if d.get("purpose") == purpose and d.get("status") in _RANK]
    return max(relevant, key=lambda status: _RANK[status]) if relevant else "unknown"


def normalize_domain(value: str) -> str:
    domain = value.strip().rstrip(".").lower()
    try:
        domain = domain.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ApiError(422, "INVALID_REQUEST", "invalid normalized domain") from exc
    if len(domain) > 255 or not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", domain):
        raise ApiError(422, "INVALID_REQUEST", "invalid normalized domain")
    return domain


async def policy_workspace_lock(session, workspace_id: uuid.UUID) -> None:
    """Serialize current-policy decisions with writes through transaction commit."""
    lock_id = int.from_bytes(sha256(f"policy-gate:{workspace_id}".encode()).digest()[:8], "big", signed=True)
    await session.execute(select(func.pg_advisory_xact_lock(lock_id)))


async def validate_subject(session, *, workspace_id: uuid.UUID, subject_type: str, subject_id: uuid.UUID):
    model = {"project": Project, "company": Company, "contact_point": ContactPoint}.get(subject_type)
    if model is None:
        raise ApiError(422, "INVALID_REQUEST", "unsupported subject_type")
    row = (await session.execute(select(model).where(model.workspace_id == workspace_id, model.id == subject_id))).scalar_one_or_none()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "subject not found")
    return row


async def quarantine_contacts_for_suppression(session, *, workspace_id: uuid.UUID,
                                               subject_type: str, subject_id: uuid.UUID | None,
                                               normalized_domain: str | None) -> int:
    """Keep existing contact results, but hide them on a newly active suppression.

    Removal never reverses this quarantine; a separate reviewed revalidation is required.
    """
    if subject_type == "contact_point" and subject_id is not None:
        condition = ContactPoint.id == subject_id
    elif subject_type == "company" and subject_id is not None:
        condition = ContactPoint.company_id == subject_id
    elif subject_type == "domain" and normalized_domain is not None:
        companies = select(Company.id).where(Company.workspace_id == workspace_id,
                                             func.lower(Company.domain) == normalized_domain)
        condition = ContactPoint.company_id.in_(companies)
    else:
        return 0
    result = await session.execute(
        update(ContactPoint).where(ContactPoint.workspace_id == workspace_id,
                                   ContactPoint.quarantined.is_(False), condition)
        .values(quarantined=True)
    )
    return result.rowcount or 0


def policy_data(item: PolicyDecision) -> dict:
    data = {
        "id": str(item.id), "workspace_id": str(item.workspace_id), "version": item.version,
        "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat(),
        "data_mode": "live", "subject_type": item.subject_type, "subject_id": str(item.subject_id),
        "controller_scope_id": str(item.controller_scope_id), "purpose": item.purpose,
        "status": item.status, "policy_version": item.policy_version,
        "basis_reference": item.basis_reference, "provenance": item.provenance,
        "countries": item.countries, "expires_at": item.expires_at.isoformat(),
        "retention_days": item.retention_days, "decision_author_id": str(item.decision_author_id),
    }
    if item.supersedes_id is not None:
        data["supersedes_id"] = str(item.supersedes_id)
    return data


def suppression_data(item: Suppression) -> dict:
    data = {
        "id": str(item.id), "workspace_id": str(item.workspace_id), "version": item.version,
        "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat(),
        "data_mode": "live", "subject_type": item.subject_type,
        "controller_scope_id": str(item.controller_scope_id), "purposes": item.purposes,
        "reason": item.reason, "active": item.active, "actor_id": str(item.actor_id),
    }
    if item.subject_id is not None:data["subject_id"] = str(item.subject_id)
    if item.normalized_domain is not None:data["normalized_domain"] = item.normalized_domain
    if item.source_reference is not None:data["source_reference"] = item.source_reference
    if item.expires_at is not None:data["expires_at"] = item.expires_at.isoformat()
    if item.removed_reason is not None:data["removed_reason"] = item.removed_reason
    if item.removed_at is not None:data["removed_at"] = item.removed_at.isoformat()
    return data


async def evaluate_current_policy(session, subject: dict, purpose: str, now: datetime) -> dict:
    """Synchronous current gate. Caller supplies server-resolved IDs in a tenant-scoped transaction."""
    if purpose not in PURPOSES or now.tzinfo is None:
        raise ValueError("purpose and timezone-aware now are required")
    workspace_id = uuid.UUID(str(subject["workspace_id"]))
    controller_id = uuid.UUID(str(subject.get("controller_scope_id") or workspace_id))
    if controller_id != workspace_id:
        return {"status": "unknown", "allowed": False, "reason_codes": ["controller_scope_unverified"]}
    await policy_workspace_lock(session, workspace_id)
    domain = None
    if subject.get("company_id"):
        company = (await session.execute(select(Company).where(
            Company.workspace_id == workspace_id,
            Company.id == uuid.UUID(str(subject["company_id"]))
        ))).scalar_one_or_none()
        if company is None:
            return {"status": "unknown", "allowed": False, "reason_codes": ["subject_unresolved"]}
        if company.domain:
            try:
                domain = normalize_domain(company.domain)
            except ApiError:
                return {"status": "unknown", "allowed": False, "reason_codes": ["domain_unverified"]}
        if subject.get("normalized_domain") and normalize_domain(subject["normalized_domain"]) != domain:
            return {"status": "unknown", "allowed": False, "reason_codes": ["domain_mismatch"]}
    scopes = []
    for kind, key in (("project", "project_id"), ("company", "company_id"), ("contact_point", "contact_point_id")):
        if subject.get(key):scopes.append((kind, uuid.UUID(str(subject[key]))))
    if not scopes:
        return {"status": "unknown", "allowed": False, "reason_codes": ["subject_unresolved"]}
    conditions = [and_(PolicyDecision.subject_type == kind, PolicyDecision.subject_id == value) for kind, value in scopes]
    rows = (await session.execute(
        select(PolicyDecision).where(PolicyDecision.workspace_id == workspace_id,
                                     PolicyDecision.controller_scope_id == controller_id,
                                     PolicyDecision.purpose == purpose, or_(*conditions))
        .distinct(PolicyDecision.subject_type, PolicyDecision.subject_id)
        .order_by(PolicyDecision.subject_type, PolicyDecision.subject_id, PolicyDecision.created_at.desc(), PolicyDecision.id.desc())
    )).scalars().all()
    active = [row.status for row in rows if row.expires_at > now]
    expired = any(row.expires_at <= now for row in rows)
    status = effective_decision([{"purpose": purpose, "status": value} for value in active], purpose)
    if expired and status == "permitted":status = "unknown"
    suppressions = []
    if purpose in {"contact_research", "draft_preparation", "outreach", "export_contacts"}:
        suppress_conditions = []
        if subject.get("company_id"):
            suppress_conditions.append(and_(Suppression.subject_type == "company", Suppression.subject_id == uuid.UUID(str(subject["company_id"]))))
        if subject.get("contact_point_id"):
            suppress_conditions.append(and_(Suppression.subject_type == "contact_point", Suppression.subject_id == uuid.UUID(str(subject["contact_point_id"]))))
        if domain:suppress_conditions.append(and_(Suppression.subject_type == "domain", Suppression.normalized_domain == domain))
        if suppress_conditions:
            suppressions = (await session.execute(
                select(Suppression.id).where(Suppression.workspace_id == workspace_id,
                    Suppression.controller_scope_id == controller_id, Suppression.active.is_(True),
                    or_(Suppression.expires_at.is_(None), Suppression.expires_at > now),
                    Suppression.purposes.any(purpose), or_(*suppress_conditions)).limit(1)
            )).scalars().all()
    if suppressions:
        return {"status": "suppressed", "allowed": False, "reason_codes": ["suppression_active"]}
    reasons = {"permitted": [], "blocked": ["policy_blocked"], "requires_review": ["policy_review_required"], "unknown": ["policy_unknown"]}
    return {"status": status, "allowed": status == "permitted", "reason_codes": reasons[status]}


__all__ = ["PURPOSES", "effective_decision", "evaluate_current_policy", "normalize_domain", "policy_workspace_lock", "quarantine_contacts_for_suppression", "policy_data", "suppression_data", "validate_subject"]
