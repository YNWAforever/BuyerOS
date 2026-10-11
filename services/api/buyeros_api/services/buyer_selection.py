"""Filter a project's buyers into an ordered, bounded snapshot selection (BO-008)."""

import uuid
from datetime import datetime

from sqlalchemy import case, func, or_, select

from ..api.errors import ApiError
from ..db.buyers import BuyerList, Company, Evidence, FitAssessment, HumanReview, ListMembership, ProjectBuyer, SourceDocument

# Filters this phase can source. `source_types` is deferred: neither evidence nor source_documents
# carries a source-type column yet (that lands with P3/BO-014 ingestion).
_DEFERRED = ("markets", "buyer_types", "contact", "suppressed", "source_types", "run_id")


def reject_unsupported_filters(filters: dict) -> None:
    for name in _DEFERRED:
        value = filters.get(name)
        if value not in (None, [], "", False):
            raise ApiError(422, "INVALID_REQUEST", f"filter not supported in this phase: {name}")


def filters_hash(filters: dict, sort: str) -> str:
    from ..db.icp import canonical_hash

    normalized = {key: value for key, value in sorted(filters.items()) if value not in (None, [], "")}
    return canonical_hash({"filters": normalized, "sort": sort})


async def selection_query(session, *, workspace_id, project_id, filters: dict, sort: str):
    """Build the same server-side selection for snapshots and manifest cursors."""
    reject_unsupported_filters(filters)
    fit_verdict = (
        select(FitAssessment.verdict)
        .where(FitAssessment.workspace_id == workspace_id,
               FitAssessment.project_buyer_id == ProjectBuyer.id)
        .order_by(FitAssessment.created_at.desc(), FitAssessment.id.desc())
        .limit(1).correlate(ProjectBuyer).scalar_subquery()
    )
    review_state = (
        select(HumanReview.state)
        .where(HumanReview.workspace_id == workspace_id,
               HumanReview.project_buyer_id == ProjectBuyer.id)
        .order_by(HumanReview.created_at.desc(), HumanReview.id.desc())
        .limit(1).correlate(ProjectBuyer).scalar_subquery()
    )
    query = (
        select(ProjectBuyer.id, ProjectBuyer.version)
        .join(Company, (Company.workspace_id == ProjectBuyer.workspace_id)
              & (Company.id == ProjectBuyer.company_id))
        .where(ProjectBuyer.workspace_id == workspace_id,
               ProjectBuyer.project_id == project_id)
    )
    list_id = filters.get("list_id")
    if list_id:
        try:
            parsed_list_id = uuid.UUID(list_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ApiError(422, "INVALID_REQUEST", "list_id must be a UUID") from exc
        owned_list = (await session.execute(select(BuyerList.id).where(
            BuyerList.workspace_id == workspace_id, BuyerList.project_id == project_id,
            BuyerList.id == parsed_list_id,
        ))).scalar_one_or_none()
        if owned_list is None:
            raise ApiError(404, "NOT_FOUND", "buyer list not found")
        member = select(ListMembership.id).where(
            ListMembership.workspace_id == workspace_id,
            ListMembership.project_id == project_id,
            ListMembership.list_id == parsed_list_id,
            ListMembership.buyer_id == ProjectBuyer.id,
        ).correlate(ProjectBuyer).exists()
        query = query.where(member)
    q = filters.get("q")
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(Company.display_name.ilike(f"%{escaped}%", escape="\\"))
    owner_membership_id = filters.get("owner_membership_id")
    if owner_membership_id:
        from ..db.models import Membership
        try:
            parsed_owner_membership_id = uuid.UUID(owner_membership_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ApiError(422, "INVALID_REQUEST", "owner_membership_id must be a UUID") from exc
        owner_user_id = (
            await session.execute(
                select(Membership.user_id).where(
                    Membership.workspace_id == workspace_id,
                    Membership.id == parsed_owner_membership_id,
                    Membership.active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if owner_user_id is None:
            raise ApiError(422, "INVALID_REQUEST", "owner_membership_id is not an active member")
        query = query.where(ProjectBuyer.owner_user_id == owner_user_id)
    if filters.get("owner_unassigned"):
        query = query.where(ProjectBuyer.owner_user_id.is_(None))
    if filters.get("unknown_fit"):
        query = query.where(fit_verdict.is_(None))
    if filters.get("fit"):
        query = query.where(fit_verdict.in_(filters["fit"]))
    if filters.get("review"):
        requested = filters["review"]
        clause = review_state.in_(requested)
        if "awaiting_review" in requested:
            clause = or_(clause, review_state.is_(None))
        query = query.where(clause)
    if filters.get("evidence_retrieved_after"):
        try:
            cutoff = datetime.fromisoformat(filters["evidence_retrieved_after"])
            if cutoff.tzinfo is None:
                raise ValueError("timezone required")
        except (ValueError, TypeError) as exc:
            raise ApiError(422, "INVALID_REQUEST", "evidence_retrieved_after must be a timezone-aware ISO-8601 timestamp") from exc
        evidence_exists = (
            select(Evidence.id)
            .join(SourceDocument,
                  (SourceDocument.workspace_id == Evidence.workspace_id)
                  & (SourceDocument.id == Evidence.source_document_id))
            .where(Evidence.workspace_id == workspace_id,
                   Evidence.project_id == ProjectBuyer.project_id,
                   Evidence.company_id == ProjectBuyer.company_id,
                   SourceDocument.retrieved_at >= cutoff)
            .correlate(ProjectBuyer).exists()
        )
        query = query.where(evidence_exists)
    name_order = func.lower(Company.display_name)
    if sort == "name_asc":
        query = query.order_by(name_order, ProjectBuyer.id)
    else:
        rank = case((fit_verdict == "match", 0),
                    (fit_verdict == "needs_review", 1),
                    (fit_verdict == "not_a_match", 2), else_=3)
        query = query.order_by(rank, name_order, ProjectBuyer.id)
    return query


async def materialize(session, *, workspace_id, project_id, filters: dict, sort: str, limit: int):
    query = await selection_query(session, workspace_id=workspace_id, project_id=project_id, filters=filters, sort=sort)
    rows = (await session.execute(query.limit(limit + 1))).all()
    clipped = len(rows) > limit
    return [(buyer_id, version) for buyer_id, version in rows[:limit]], len(rows), clipped
