"""One durable buyer-list/preset service sharing T08 selection and tenant tables."""
import uuid

from sqlalchemy import func, select

from ..api.errors import ApiError
from ..db.buyers import BuyerList, FilterPreset, ListMembership, ProjectBuyer
from ..db.icp import canonical_hash
from ..db.models import Membership
from .audit_service import append_audit
from .buyer_review import _resolve_items
from .buyer_selection import reject_unsupported_filters


async def buyer_list_data(session, item: BuyerList) -> dict:
    count = (await session.execute(
        select(func.count()).select_from(ListMembership).where(
            ListMembership.workspace_id == item.workspace_id, ListMembership.list_id == item.id,
        )
    )).scalar_one()
    return {
        "id": str(item.id), "workspace_id": str(item.workspace_id), "project_id": str(item.project_id),
        "version": item.version, "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(), "data_mode": "live", "name": item.name,
        "member_count": count,
    }


async def get_list(session, *, workspace_id, list_id, lock=False):
    query = select(BuyerList).where(BuyerList.workspace_id == workspace_id, BuyerList.id == list_id)
    if lock:
        query = query.with_for_update()
    item = (await session.execute(query)).scalar_one_or_none()
    if item is None:
        raise ApiError(404, "NOT_FOUND", "buyer list not found")
    return item


async def change_memberships(session, *, item, actor_user_id, selection: dict, operation: str) -> dict:
    pairs = await _resolve_items(
        session, workspace_id=item.workspace_id, project_id=item.project_id,
        actor_user_id=actor_user_id, selection=selection,
    )
    results = []
    updated = unchanged = blocked = conflicts = 0
    for buyer_id, expected_version in pairs:
        buyer = (await session.execute(
            select(ProjectBuyer).where(
                ProjectBuyer.workspace_id == item.workspace_id,
                ProjectBuyer.project_id == item.project_id, ProjectBuyer.id == buyer_id,
            ).with_for_update()
        )).scalar_one_or_none()
        if buyer is None:
            blocked += 1
            results.append({"id": str(buyer_id), "status": "blocked", "reason_code": "not_found"})
            continue
        if buyer.version != expected_version:
            conflicts += 1
            results.append({"id": str(buyer_id), "status": "conflict", "reason_code": "version_conflict", "version": buyer.version})
            continue
        membership = (await session.execute(
            select(ListMembership).where(
                ListMembership.workspace_id == item.workspace_id,
                ListMembership.list_id == item.id, ListMembership.buyer_id == buyer_id,
            )
        )).scalar_one_or_none()
        if operation == "add" and membership is None:
            session.add(ListMembership(
                workspace_id=item.workspace_id, project_id=item.project_id,
                list_id=item.id, buyer_id=buyer_id,
            ))
        elif operation == "remove" and membership is not None:
            await session.delete(membership)
        else:
            unchanged += 1
            results.append({"id": str(buyer_id), "status": "unchanged", "version": buyer.version})
            continue
        updated += 1
        results.append({"id": str(buyer_id), "status": "updated", "version": buyer.version})
        append_audit(session, workspace_id=item.workspace_id, actor_id=actor_user_id,
            action="buyer_list.membership_changed", entity_type="buyer_list", entity_id=item.id,
            detail_digest=canonical_hash({"buyer_id": str(buyer_id), "operation": operation}))
    if updated:
        item.version += 1
        await session.flush()
    return {"requested": len(pairs), "updated": updated, "unchanged": unchanged,
            "blocked": blocked, "conflicts": conflicts, "results": results}


async def assign_owners(session, *, workspace_id, project_id, actor_user_id,
                        selection: dict, owner_membership_id, reason: str) -> dict:
    pairs = await _resolve_items(session, workspace_id=workspace_id, project_id=project_id,
                                 actor_user_id=actor_user_id, selection=selection)
    if len(pairs) > 1000:
        raise ApiError(422, "INVALID_REQUEST", "bulk selection exceeds 1000 buyers")
    owner_user_id = None
    if owner_membership_id is not None:
        member = (await session.execute(select(Membership).where(
            Membership.workspace_id == workspace_id, Membership.id == owner_membership_id,
            Membership.active.is_(True)).with_for_update())).scalar_one_or_none()
        if member is None:
            raise ApiError(422, "INVALID_REQUEST", "owner membership is not active in this workspace")
        owner_user_id = member.user_id
    results = []
    updated = unchanged = blocked = conflicts = 0
    for buyer_id, expected_version in pairs:
        buyer = (await session.execute(select(ProjectBuyer).where(
            ProjectBuyer.workspace_id == workspace_id, ProjectBuyer.project_id == project_id,
            ProjectBuyer.id == buyer_id).with_for_update())).scalar_one_or_none()
        if buyer is None:
            blocked += 1
            results.append({"id": str(buyer_id), "status": "blocked", "reason_code": "not_found"})
        elif buyer.version != expected_version:
            conflicts += 1
            results.append({"id": str(buyer_id), "status": "conflict",
                            "reason_code": "version_conflict", "version": buyer.version})
        elif buyer.owner_user_id == owner_user_id:
            unchanged += 1
            results.append({"id": str(buyer_id), "status": "unchanged", "version": buyer.version})
        else:
            buyer.owner_user_id = owner_user_id
            buyer.version += 1
            updated += 1
            append_audit(session, workspace_id=workspace_id, actor_id=actor_user_id,
                action="buyer.owner_assigned", entity_type="project_buyer", entity_id=buyer_id,
                detail_digest=canonical_hash({"owner_membership_id": str(owner_membership_id) if owner_membership_id else None,
                                              "reason": reason}))
            results.append({"id": str(buyer_id), "status": "updated", "version": buyer.version})
    await session.flush()
    return {"requested": len(pairs), "updated": updated, "unchanged": unchanged,
            "blocked": blocked, "conflicts": conflicts, "results": results}


def preset_data(item: FilterPreset) -> dict:
    return {
        "id": str(item.id), "workspace_id": str(item.workspace_id),
        "project_id": str(item.project_id), "actor_id": str(item.actor_user_id),
        "version": item.version, "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(), "data_mode": "live",
        "name": item.name, "filters": item.filters, "sort": item.sort,
    }


def validate_preset_filters(filters: dict) -> None:
    reject_unsupported_filters(filters)
    if filters.get("fit") and set(filters["fit"]) - {"match", "needs_review", "not_a_match"}:
        raise ApiError(422, "INVALID_REQUEST", "invalid fit filter")
    if filters.get("review") and set(filters["review"]) - {"awaiting_review", "accepted", "rejected", "needs_information"}:
        raise ApiError(422, "INVALID_REQUEST", "invalid review filter")
    if filters.get("owner_membership_id"):
        try:
            uuid.UUID(filters["owner_membership_id"])
        except (ValueError, TypeError):
            raise ApiError(422, "INVALID_REQUEST", "invalid owner_membership_id")
    if filters.get("evidence_retrieved_after"):
        from datetime import datetime
        try:
            value = datetime.fromisoformat(filters["evidence_retrieved_after"])
            if value.tzinfo is None:
                raise ValueError("timezone required")
        except (ValueError, TypeError):
            raise ApiError(422, "INVALID_REQUEST", "invalid evidence_retrieved_after")
