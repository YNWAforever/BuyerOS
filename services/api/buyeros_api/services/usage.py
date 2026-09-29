"""Usage projections and manual outcome chains (BO-024)."""

from decimal import ROUND_HALF_UP, Decimal


def safe_ratio(numerator: str, denominator: int) -> str | None:
    """Zero denominator returns None (rendered as an em dash), never 0."""
    if denominator == 0:
        return None
    value = (Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return f"{value:.6f}"


def outcome_chain(events: list[dict]) -> dict:
    """Latest non-superseded manual stage per buyer."""
    latest: dict[str, str] = {}
    for event in events:
        if not event.get("superseded", False):
            latest[event["buyer_id"]] = event["stage"]
    return latest


# Database projection below keeps metered cost, current holds and denominators separate.
from datetime import datetime, timezone

from sqlalchemy import and_, func, select, text

from ..api.errors import ApiError
from ..db.budget import BudgetAccount, BudgetReservation, BudgetReservationAllocation, CostEvent
from ..db.icp import Project
from ..db.runs import ContactPoint
from .budget_service import CATEGORIES, ZERO, UNIT
from .policy_service import evaluate_current_policy, policy_workspace_lock

DENOMINATOR = ("Distinct project companies first accepted in the UTC half-open period "
    "and still accepted against the current ICP and fit at as_of; contactable subset "
    "has a current provider-marked-valid, research-permitted, unsuppressed business email. "
    "Numerator is all attributed metered cost events recorded in the period, including "
    "failed and partial runs and signed refunds; "
    "ratios are blended period costs, not causal acquisition costs.")


def _signed(value: Decimal) -> dict:
    return {"amount": format(value.quantize(UNIT), ".6f"), "currency": "USD"}


def _unsigned(value: Decimal) -> dict:
    return _signed(max(ZERO, value))


async def _accepted_companies(session, *, workspace_id, project_id, start, end, as_of):
    # Both first acceptance and latest review are derived from immutable events.
    rows = (await session.execute(text("""
        WITH first_accepted AS (
          SELECT project_buyer_id, min(created_at) AS first_at
          FROM human_reviews WHERE workspace_id=:workspace_id AND state='accepted'
            AND created_at<=:as_of GROUP BY project_buyer_id
        ), latest_review AS (
          SELECT DISTINCT ON (r.project_buyer_id) r.project_buyer_id, r.state, r.fit_assessment_id
          FROM human_reviews r JOIN project_buyers b
            ON b.workspace_id=r.workspace_id AND b.id=r.project_buyer_id
          WHERE r.workspace_id=:workspace_id AND b.project_id=:project_id
            AND r.created_at<=:as_of
          ORDER BY r.project_buyer_id, r.created_at DESC, r.id DESC
        ), latest_fit AS (
          SELECT DISTINCT ON (f.project_buyer_id) f.project_buyer_id, f.id, f.icp_version_id
          FROM fit_assessments f WHERE f.workspace_id=:workspace_id AND f.project_id=:project_id
            AND f.created_at<=:as_of
          ORDER BY f.project_buyer_id, f.created_at DESC, f.id DESC
        )
        SELECT DISTINCT b.company_id FROM project_buyers b
        JOIN projects p ON p.workspace_id=b.workspace_id AND p.id=b.project_id
        JOIN first_accepted first ON first.project_buyer_id=b.id
        JOIN latest_review review ON review.project_buyer_id=b.id AND review.state='accepted'
        JOIN latest_fit fit ON fit.project_buyer_id=b.id
          AND fit.id=review.fit_assessment_id AND fit.icp_version_id=p.active_icp_version_id
        WHERE b.workspace_id=:workspace_id AND b.project_id=:project_id
          AND first.first_at>=:start AND first.first_at<:end
        LIMIT 10001
    """), {"workspace_id": workspace_id, "project_id": project_id,
           "start": start, "end": end, "as_of": as_of})).scalars().all()
    if len(rows)>10000:
        raise ApiError(503, "METRIC_UNAVAILABLE", "accepted company set exceeds bounded projection")
    return rows


async def _contactable_count(session, *, workspace_id, project_id, company_ids, as_of):
    if not company_ids:
        return 0
    points = (await session.execute(select(ContactPoint).where(
        ContactPoint.workspace_id == workspace_id,
        ContactPoint.company_id.in_(company_ids),
        ContactPoint.type == "business_email",
        ContactPoint.validity == "provider_marked_valid",
        ContactPoint.quarantined.is_(False),
        ContactPoint.checked_at <= as_of,
    ).order_by(ContactPoint.company_id, ContactPoint.id).limit(10001))).scalars().all()
    if len(points)>10000:
        raise ApiError(503, "METRIC_UNAVAILABLE", "contactable set exceeds bounded projection")
    allowed=set()
    for point in points:
        if point.company_id in allowed:
            continue
        gate=await evaluate_current_policy(session, {"workspace_id": workspace_id,
            "project_id": project_id, "company_id": point.company_id,
            "contact_point_id": point.id}, "contact_research", as_of)
        if gate["allowed"]:
            allowed.add(point.company_id)
    return len(allowed)


async def get_usage(session, *, workspace_id, project_id, from_utc, to_utc, as_of):
    if (from_utc.tzinfo is None or to_utc.tzinfo is None or
            from_utc >= to_utc):
        raise ApiError(422, "INVALID_REQUEST", "usage requires a valid UTC half-open period")
    start=from_utc.astimezone(timezone.utc)
    end=to_utc.astimezone(timezone.utc)
    await policy_workspace_lock(session, workspace_id)
    project=(await session.execute(select(Project).where(
        Project.workspace_id == workspace_id, Project.id == project_id,
    ))).scalar_one_or_none()
    if project is None:
        raise ApiError(404, "NOT_FOUND", "project not found")
    scope=(BudgetAccount.workspace_id == workspace_id,
           BudgetAccount.scope == "category", BudgetAccount.scope_id == project_id,
           BudgetAccount.currency == "USD")
    settled_rows=(await session.execute(select(BudgetAccount.category,func.sum(CostEvent.amount))
        .select_from(CostEvent)
        .join(BudgetReservation, and_(BudgetReservation.workspace_id==CostEvent.workspace_id,
                                     BudgetReservation.operation_id==CostEvent.operation_id))
        .join(BudgetReservationAllocation, and_(
            BudgetReservationAllocation.workspace_id==BudgetReservation.workspace_id,
            BudgetReservationAllocation.reservation_id==BudgetReservation.id))
        .join(BudgetAccount, and_(BudgetAccount.workspace_id==BudgetReservationAllocation.workspace_id,
                                 BudgetAccount.id==BudgetReservationAllocation.account_id))
        .where(*scope,CostEvent.recorded_at>=start,CostEvent.recorded_at<end,
               CostEvent.recorded_at<=as_of,CostEvent.kind.in_(("commit","reversal")))
        .group_by(BudgetAccount.category))).all()
    held_rows=(await session.execute(select(BudgetAccount.category,func.sum(BudgetReservation.remaining_hold))
        .select_from(BudgetReservation)
        .join(BudgetReservationAllocation, and_(
            BudgetReservationAllocation.workspace_id==BudgetReservation.workspace_id,
            BudgetReservationAllocation.reservation_id==BudgetReservation.id))
        .join(BudgetAccount, and_(BudgetAccount.workspace_id==BudgetReservationAllocation.workspace_id,
                                 BudgetAccount.id==BudgetReservationAllocation.account_id))
        .where(*scope,BudgetReservation.remaining_hold>ZERO,
               BudgetReservation.created_at<=as_of)
        .group_by(BudgetAccount.category))).all()
    settled_by={name:Decimal(value) for name,value in settled_rows}
    held_by={name:Decimal(value) for name,value in held_rows}
    categories=[{"category": name, "settled": _signed(settled_by.get(name,ZERO)),
                 "reserved": _unsigned(held_by.get(name,ZERO))}
                for name in sorted(CATEGORIES)]
    total_settled=sum(settled_by.values(),ZERO)
    total_reserved=sum(held_by.values(),ZERO)
    account=(await session.execute(select(BudgetAccount).where(
        BudgetAccount.workspace_id==workspace_id,BudgetAccount.scope=="project",
        BudgetAccount.scope_id==project_id,BudgetAccount.category=="all",
        BudgetAccount.currency=="USD",BudgetAccount.period_start<=as_of,
        BudgetAccount.period_end>as_of))).scalar_one_or_none()
    remaining=max(ZERO,(account.approved_limit-account.settled_spend-total_reserved) if account else ZERO)
    company_ids=await _accepted_companies(session,workspace_id=workspace_id,
        project_id=project_id,start=start,end=end,as_of=as_of)
    contactable=await _contactable_count(session,workspace_id=workspace_id,
        project_id=project_id,company_ids=company_ids,as_of=as_of)
    ratio_accepted=safe_ratio(str(total_settled),len(company_ids))
    ratio_contact=safe_ratio(str(total_settled),contactable)
    return {"workspace_id":str(workspace_id),"project_id":str(project_id),
            "from":start.isoformat(),"to":end.isoformat(),"as_of":as_of.isoformat(),
            "categories":categories,"total_settled":_signed(total_settled),
            "total_reserved":_unsigned(total_reserved),"remaining":_unsigned(remaining),
            "accepted_company_count":len(company_ids),
            "eligible_contactable_company_count":contactable,
            "cost_per_accepted_company":_signed(Decimal(ratio_accepted)) if ratio_accepted else None,
            "cost_per_contactable_accepted_company":_signed(Decimal(ratio_contact)) if ratio_contact else None,
            "denominator_definition":DENOMINATOR,"includes_partial_runs":True}
