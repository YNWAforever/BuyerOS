"""Immutable ICP serialization and exact-context approval (BO-007)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.errors import ApiError
from ..db.icp import IcpVersion, Project
from .audit_service import append_audit


class StaleRevision(Exception):
    pass


class AlreadyApproved(Exception):
    pass


def verify_approval_hash(row, expected_hash: str) -> None:
    if row.content_hash != expected_hash:
        raise StaleRevision("content hash changed; reload the profile")


def effective_offer_facts(row: IcpVersion) -> list[dict]:
    """Exact reviewer approval authorizes included sourced/manual facts; saved flags never do."""
    reviewed = row.approved_at is not None and row.approved_by is not None
    return [{**fact, "approved": reviewed and fact.get("provenance") in
             {"user_entered", "document_excerpt"}}
            for fact in (row.content or {}).get("offer_facts", []) if isinstance(fact, dict)]


def icp_data(row: IcpVersion, *, project: Project | None = None) -> dict:
    content = row.content or {}
    data = {
        "id": str(row.id),
        "workspace_id": str(row.workspace_id),
        "project_id": str(row.project_id),
        "version": row.number,
        "number": row.number,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "data_mode": "live",
        "basis_offer_revision": row.basis_offer_revision,
        "basis_status": (
            "unknown" if row.basis_offer_revision is None or project is None
            else "current" if row.basis_offer_revision == project.offer_revision else "stale"
        ),
        "is_current": bool(project is not None and project.active_icp_version_id == row.id),
        "content_hash": row.content_hash,
        "status": "superseded" if row.superseded_at else ("approved" if row.approved_at else "saved"),
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "approved_by": str(row.approved_by) if row.approved_by else None,
        "offer_document_ids": content.get("offer_document_ids", []),
        "requirements": content.get("requirements", []),
        "markets": content.get("markets", []),
        "buyer_types": content.get("buyer_types", []),
        "languages": content.get("languages", []),
        "desired_roles": content.get("desired_roles", []),
        "offer_facts": effective_offer_facts(row),
    }
    if row.parent_id is not None:
        data["parent_icp_version_id"] = str(row.parent_id)
    return data


async def approve_icp(
    session: AsyncSession,
    project_id: uuid.UUID,
    icp_id: uuid.UUID,
    expected_project_version: int,
    content_hash: str,
    actor_id: uuid.UUID,
    *,
    workspace_id: uuid.UUID,
    expected_number: int,
) -> dict:
    """Lock Project then ICP and record approval plus audit in one transaction."""
    project = (
        await session.execute(
            select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id).with_for_update()
        )
    ).scalar_one_or_none()
    if project is None:
        raise ApiError(404, "NOT_FOUND", "project not found")
    row = (
        await session.execute(
            select(IcpVersion).where(
                IcpVersion.workspace_id == workspace_id,
                IcpVersion.project_id == project_id,
                IcpVersion.id == icp_id,
            ).with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "profile version not found")
    if project.version != expected_project_version or row.number != expected_number:
        raise ApiError(412, "STALE_REVISION", "project or profile changed; reload")
    if project.status != "active":
        raise ApiError(409, "INVALID_REQUEST", "archived project cannot approve profiles")
    if row.basis_offer_revision is None or row.basis_offer_revision != project.offer_revision:
        raise ApiError(412, "STALE_REVISION", "offer basis changed; save a new profile")
    try:
        verify_approval_hash(row, content_hash)
    except StaleRevision as exc:
        raise ApiError(412, "STALE_REVISION", str(exc)) from exc
    if row.content.get("offer_document_ids"):
        from ..api.schemas import OfferFact
        from .offer_document_refs import validate_offer_document_refs

        await validate_offer_document_refs(
            session, workspace_id=workspace_id, project_id=project_id,
            document_ids=[uuid.UUID(value) for value in row.content["offer_document_ids"]],
            facts=[OfferFact.model_validate(value) for value in row.content.get("offer_facts", [])],
        )
    if row.approved_at is not None:
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "profile already approved with another key")
    now = datetime.now(timezone.utc)
    row.approved_at = now
    row.approved_by = actor_id
    prior_id = project.active_icp_version_id
    project.active_icp_version_id = row.id
    project.version += 1
    if prior_id is not None and prior_id != row.id:
        prior = (
            await session.execute(
                select(IcpVersion).where(
                    IcpVersion.workspace_id == workspace_id,
                    IcpVersion.project_id == project_id,
                    IcpVersion.id == prior_id,
                ).with_for_update()
            )
        ).scalar_one_or_none()
        if prior is not None:
            prior.superseded_at = now
    append_audit(session, workspace_id=workspace_id, actor_id=actor_id,
        action="icp.approved", entity_type="icp_version", entity_id=row.id,
        detail_digest=row.content_hash)
    await session.flush()
    await session.refresh(row)
    return icp_data(row, project=project)
