"""Filter a project's buyers into an ordered, bounded snapshot selection (BO-008)."""

import uuid
from datetime import datetime

from sqlalchemy import select

from ..api.errors import ApiError
from ..db.buyers import Company, Evidence, FitAssessment, HumanReview, ProjectBuyer, SourceDocument

# Filters this phase can source. `source_types` is deferred: neither evidence nor source_documents
# carries a source-type column yet (that lands with P3/BO-014 ingestion).
_SUPPORTED = frozenset({"q", "fit", "review", "owner_membership_id", "evidence_retrieved_after"})
_DEFERRED = ("markets", "buyer_types", "contact", "suppressed", "source_types", "run_id", "list_id")
_FIT_RANK = {"match": 0, "needs_review": 1, "not_a_match": 2}


def reject_unsupported_filters(filters: dict) -> None:
    for name in _DEFERRED:
        value = filters.get(name)
        if value not in (None, [], "", False):
            raise ApiError(422, "INVALID_REQUEST", f"filter not supported in this phase: {name}")


def filters_hash(filters: dict, sort: str) -> str:
    from ..db.icp import canonical_hash

    normalized = {key: value for key, value in sorted(filters.items()) if value not in (None, [], "")}
    return canonical_hash({"filters": normalized, "sort": sort})


async def _latest(session, model, workspace_id, buyer_ids):
    if not buyer_ids:
        return {}
    rows = (
        await session.execute(
            select(model)
            .where(model.workspace_id == workspace_id, model.project_buyer_id.in_(buyer_ids))
            .order_by(model.project_buyer_id, model.created_at.desc(), model.id)
        )
    ).scalars().all()
    latest: dict = {}
    for row in rows:
        latest.setdefault(row.project_buyer_id, row)
    return latest


async def _buyers_with_evidence_after(session, workspace_id, project_id, buyer_ids, retrieved_after):
    if not buyer_ids:
        return set()
    try:
        cutoff = datetime.fromisoformat(retrieved_after)
    except ValueError as exc:
        raise ApiError(422, "INVALID_REQUEST", "evidence_retrieved_after must be an ISO-8601 timestamp") from exc
    rows = (
        await session.execute(
            select(ProjectBuyer.id)
            .join(
                Evidence,
                (Evidence.workspace_id == ProjectBuyer.workspace_id) & (Evidence.company_id == ProjectBuyer.company_id),
            )
            .join(
                SourceDocument,
                (SourceDocument.workspace_id == Evidence.workspace_id)
                & (SourceDocument.id == Evidence.source_document_id),
            )
            .where(
                ProjectBuyer.workspace_id == workspace_id,
                ProjectBuyer.project_id == project_id,
                ProjectBuyer.id.in_(buyer_ids),
                SourceDocument.retrieved_at.is_not(None),
                SourceDocument.retrieved_at >= cutoff,
            )
        )
    ).scalars().all()
    return set(rows)


async def materialize(session, *, workspace_id, project_id, filters: dict, sort: str, limit: int):
    """Return ordered (buyer_id, version) pairs, the matched total, and whether the limit clipped it."""
    reject_unsupported_filters(filters)
    query = (
        select(ProjectBuyer, Company)
        .join(Company, (Company.workspace_id == ProjectBuyer.workspace_id) & (Company.id == ProjectBuyer.company_id))
        .where(ProjectBuyer.workspace_id == workspace_id, ProjectBuyer.project_id == project_id)
    )
    q = filters.get("q")
    if q:
        query = query.where(Company.display_name.ilike(f"%{q}%"))
    owner_membership_id = filters.get("owner_membership_id")
    if owner_membership_id:
        from ..db.models import Membership

        owner_user_id = (
            await session.execute(
                select(Membership.user_id).where(
                    Membership.workspace_id == workspace_id,
                    Membership.id == uuid.UUID(owner_membership_id),
                    Membership.active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if owner_user_id is None:
            raise ApiError(422, "INVALID_REQUEST", "owner_membership_id is not an active member")
        query = query.where(ProjectBuyer.owner_user_id == owner_user_id)

    rows = (await session.execute(query)).all()
    buyer_ids = [buyer.id for buyer, _ in rows]
    fits = await _latest(session, FitAssessment, workspace_id, buyer_ids)
    reviews = await _latest(session, HumanReview, workspace_id, buyer_ids)
    wanted_fit = set(filters.get("fit") or [])
    wanted_review = set(filters.get("review") or [])
    retrieved_after = filters.get("evidence_retrieved_after")
    evidence_ok = (
        await _buyers_with_evidence_after(session, workspace_id, project_id, buyer_ids, retrieved_after)
        if retrieved_after
        else set(buyer_ids)
    )

    selected = []
    for buyer, company in rows:
        fit = fits.get(buyer.id)
        review = reviews.get(buyer.id)
        if wanted_fit and (fit.verdict if fit else None) not in wanted_fit:
            continue
        if wanted_review and (review.state if review else None) not in wanted_review:
            continue
        if buyer.id not in evidence_ok:
            continue
        selected.append((buyer, company, fit))

    if sort == "name_asc":
        selected.sort(key=lambda item: (item[1].display_name, str(item[0].id)))
    else:
        selected.sort(key=lambda item: (_FIT_RANK.get(item[2].verdict if item[2] else None, 3), item[1].display_name, str(item[0].id)))
    matched = len(selected)
    return [(buyer.id, buyer.version) for buyer, _, _ in selected[:limit]], matched, matched > limit
