"""Apply a bulk human review against explicit or snapshot buyer versions (BO-008)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from ..api.errors import ApiError
from ..db.buyers import BuyerSnapshot, BuyerSnapshotItem, FitAssessment, HumanReview, ProjectBuyer


async def _resolve_items(session, *, workspace_id, project_id, selection: dict):
    """Return deterministic (buyer_id, expected_version) pairs for the request's selection."""
    if selection["kind"] == "explicit":
        items: list[tuple[uuid.UUID | str, int]] = []
        seen: set[str] = set()
        for item in selection["buyers"]:
            raw_id = item["id"]
            if raw_id in seen:
                continue
            seen.add(raw_id)
            try:
                buyer_id: uuid.UUID | str = uuid.UUID(raw_id)
            except (ValueError, AttributeError, TypeError):
                buyer_id = raw_id  # a malformed id is reported blocked, never a server error
            items.append((buyer_id, item["version"]))
        return sorted(items, key=lambda pair: str(pair[0]))
    try:
        snapshot_id = uuid.UUID(selection["snapshot_id"])
    except (ValueError, AttributeError, TypeError):
        raise ApiError(422, "INVALID_REQUEST", "snapshot_id must be a UUID")
    snapshot = (
        await session.execute(
            select(BuyerSnapshot).where(
                BuyerSnapshot.workspace_id == workspace_id,
                BuyerSnapshot.project_id == project_id,
                BuyerSnapshot.id == snapshot_id,
            )
        )
    ).scalar_one_or_none()
    if snapshot is None:
        raise ApiError(404, "NOT_FOUND", "buyer snapshot not found")
    if snapshot.expires_at is not None and snapshot.expires_at <= datetime.now(timezone.utc):
        raise ApiError(404, "NOT_FOUND", "buyer snapshot expired")
    excluded = {uuid.UUID(value) for value in selection["excluded_ids"]}
    rows = (
        await session.execute(
            select(BuyerSnapshotItem)
            .where(BuyerSnapshotItem.workspace_id == workspace_id, BuyerSnapshotItem.snapshot_id == snapshot_id)
            .order_by(BuyerSnapshotItem.ordinal)
        )
    ).scalars().all()
    items = [(row.buyer_id, row.buyer_version) for row in rows if row.buyer_id not in excluded]
    return sorted(items, key=lambda pair: str(pair[0]))


async def _latest(session, model, workspace_id, buyer_id):
    return (
        await session.execute(
            select(model)
            .where(model.workspace_id == workspace_id, model.project_buyer_id == buyer_id)
            .order_by(model.created_at.desc(), model.id)
        )
    ).scalars().first()


async def apply(session, *, workspace_id, project_id, actor_user_id, selection: dict, status: str, reason: str) -> dict:
    items = await _resolve_items(session, workspace_id=workspace_id, project_id=project_id, selection=selection)
    results: list[dict] = []
    updated = blocked = conflicts = 0
    for buyer_id, expected_version in items:
        if not isinstance(buyer_id, uuid.UUID):
            blocked += 1
            results.append({"id": str(buyer_id), "status": "blocked", "reason_code": "not_found"})
            continue
        buyer = (
            await session.execute(
                select(ProjectBuyer)
                .where(
                    ProjectBuyer.workspace_id == workspace_id,
                    ProjectBuyer.project_id == project_id,
                    ProjectBuyer.id == buyer_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if buyer is None:
            blocked += 1
            results.append({"id": str(buyer_id), "status": "blocked", "reason_code": "not_found"})
            continue
        if buyer.version != expected_version:
            conflicts += 1
            results.append({"id": str(buyer_id), "status": "conflict", "reason_code": "version_conflict", "version": buyer.version})
            continue
        latest = await _latest(session, HumanReview, workspace_id, buyer_id)
        if latest is not None and latest.state == status:
            results.append({"id": str(buyer_id), "status": "unchanged", "version": buyer.version})
            continue
        fit = await _latest(session, FitAssessment, workspace_id, buyer_id)
        session.add(
            HumanReview(
                workspace_id=workspace_id, project_buyer_id=buyer_id, state=status, reason=reason,
                actor_user_id=actor_user_id, fit_assessment_id=fit.id if fit else None,
            )
        )
        buyer.version += 1
        await session.flush()
        updated += 1
        results.append({"id": str(buyer_id), "status": "updated", "reason_code": status, "version": buyer.version})
    return {
        "requested": len(items), "updated": updated, "blocked": blocked, "conflicts": conflicts, "results": results,
    }
