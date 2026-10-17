"""Shared, distinct-company projection for overview, dossier and manual work queue."""
from collections import defaultdict
from dataclasses import replace
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.errors import ApiError
from ..api.lead_schemas import (
    LeadScope, LeadFilters, LeadCaseView, LeadMetrics, LeadProgressPage, LeadObservationRecord,
)
from ..db.buyers import Company, ProjectBuyer, BuyerSourceCheck
from ..db.icp import canonical_hash
from ..db.lead_workflow import (
    LeadCaseState, LeadObservation, LeadReview, LeadReviewEvidence, LeadPrivatePayload,
)
from ..db.runs import Person, ContactPoint
from .lead_evidence_service import require_permission, observation_data, personal_policy
from .lead_review_service import review_data
from .lead_quality import evaluate_lead_quality, reviewed_subjects


async def _case_views(session, scope, now, *, detail=False, include_preparations=True):
    require_permission(scope, "getBuyer")
    query = select(ProjectBuyer, Company).join(Company, (Company.id == ProjectBuyer.company_id)
        & (Company.workspace_id == ProjectBuyer.workspace_id)).where(
        ProjectBuyer.workspace_id == scope.workspace_id, ProjectBuyer.project_id == scope.project_id,
    )
    if scope.buyer_id:
        query = query.where(ProjectBuyer.id == scope.buyer_id)
    buyers = (await session.execute(query.order_by(Company.display_name, ProjectBuyer.id))).all()
    ids = [buyer.id for buyer, _ in buyers]
    if not ids:
        return []
    base = lambda model: (
        model.workspace_id == scope.workspace_id, model.project_id == scope.project_id,
        model.buyer_id.in_(ids),
    )
    cases = {row.buyer_id: row for row in (await session.scalars(select(LeadCaseState).where(*base(LeadCaseState)))).all()}
    observations = list((await session.scalars(select(LeadObservation).where(*base(LeadObservation))
        .order_by(LeadObservation.created_at, LeadObservation.id))).all())
    reviews = list((await session.scalars(select(LeadReview).where(*base(LeadReview))
        .order_by(LeadReview.case_version))).all())
    payload_ids = {row.payload_id for row in observations + reviews if row.payload_id}
    payloads = list((await session.scalars(select(LeadPrivatePayload).where(
        LeadPrivatePayload.workspace_id == scope.workspace_id,
        LeadPrivatePayload.project_id == scope.project_id, LeadPrivatePayload.id.in_(payload_ids),
    ))).all()) if payload_ids else []
    person_ids = {row.person_id for row in observations + reviews if row.person_id}
    contact_ids = {row.contact_id for row in observations + reviews if row.contact_id}
    people = list((await session.scalars(select(Person).where(
        Person.workspace_id == scope.workspace_id, Person.id.in_(person_ids),
    ))).all()) if person_ids else []
    contacts = list((await session.scalars(select(ContactPoint).where(
        ContactPoint.workspace_id == scope.workspace_id, ContactPoint.id.in_(contact_ids),
    ))).all()) if contact_ids else []
    refs = list((await session.scalars(select(LeadReviewEvidence).where(*base(LeadReviewEvidence)))).all())
    checks = list((await session.scalars(select(BuyerSourceCheck).where(*base(BuyerSourceCheck)))).all())
    cache = {"payloads": {row.id: row for row in payloads},
             "people": {row.id: row for row in people}, "contacts": {row.id: row for row in contacts}}
    by_buyer, review_by_buyer, check_by_buyer, refs_by_review = (defaultdict(list) for _ in range(4))
    for row in observations:
        by_buyer[row.buyer_id].append(row)
    for row in reviews:
        review_by_buyer[row.buyer_id].append(row)
    for row in checks:
        check_by_buyer[row.buyer_id].append(row.id)
    for row in refs:
        refs_by_review[row.review_id].append(row.observation_id)
    results = []
    for buyer, company in buyers:
        current_scope = replace(scope, buyer_id=buyer.id, company_id=company.id)
        materialized = [
            LeadObservationRecord.model_validate(await observation_data(
                session, current_scope, row, now, cache=cache,
            )) for row in by_buyer[buyer.id]
        ]
        history = [
            await review_data(session, current_scope, row, materialized, now, cache=cache,
                              references=refs_by_review[row.id])
            for row in review_by_buyer[buyer.id]
        ]
        subjects = reviewed_subjects(materialized, history, now)
        selected = max(subjects, key=lambda item: (
            item.quality.direct_channel, item.quality.qualified_person,
            item.quality.employment_current, item.review.case_version,
        )) if subjects else None
        latest = selected.review if selected else None
        quality = selected.quality if selected else evaluate_lead_quality(observations=materialized, review=None, now=now)
        selected_history = [item for item in history if latest and
            item.person_id == latest.person_id and item.contact_id == latest.contact_id]
        person_id = latest.person_id if latest else next((row.person_id for row in reversed(materialized) if row.person_id), None)
        contact_id = latest.contact_id if latest else None
        if quality.needs_review:
            stage = "refresh_evidence"
        elif person_id is None:
            stage = "find_person"
        elif not quality.employment_current:
            stage = "verify_employment"
        elif not quality.procurement_current or not quality.qualified_person:
            stage = "verify_procurement"
        elif not quality.direct_channel:
            stage = "verify_channel"
        else:
            stage = "review_preparation"
        case = cases.get(buyer.id)
        view = LeadCaseView(
            workspace_id=scope.workspace_id, project_id=scope.project_id, buyer_id=buyer.id,
            company_id=company.id, company_name=company.display_name,
            version=case.version if case else 1, state_exists=case is not None,
            priority=case.priority if case else False, priority_reason=case.priority_reason if case else "",
            owner_user_id=buyer.owner_user_id, next_action=case.next_action if case else "",
            due_on=case.due_on if case else None, selected_person_id=person_id, selected_contact_id=contact_id,
            quality=quality, observations=materialized[-20:] if detail else None,
            observations_total=len(materialized), reviews=selected_history[-3:] if detail else [],
            reviews_total=len(history), source_check_ids=check_by_buyer[buyer.id], stage=stage, as_of=now,
        )
        if include_preparations and view.quality.direct_channel:
            from .lead_preparation_service import has_current_reviewed_preparation
            review_view = view.model_copy(update={"reviews": selected_history[-3:]})
            view.reviewed_preparation = await has_current_reviewed_preparation(
                session, current_scope, review_view, now, subject_states=subjects)
            if view.reviewed_preparation:
                view.stage = "complete"
        results.append(view)
    return results


def qualifies(row, criterion):
    priority = row.priority and bool(row.source_check_ids)
    return {
        "company_card": bool(row.source_check_ids),
        "priority_company": priority,
        "qualified_person": priority and row.quality.qualified_person,
        "direct_channel": priority and row.quality.direct_channel,
        "reviewed_preparation": priority and row.quality.direct_channel and row.reviewed_preparation,
    }[criterion]


def metrics(rows):
    count = lambda criterion: len({row.company_id for row in rows if qualifies(row, criterion)})
    return LeadMetrics(company_cards=count("company_card"), priority_companies=count("priority_company"),
        qualified_people_companies=count("qualified_person"), direct_channel_companies=count("direct_channel"),
        reviewed_preparation_companies=count("reviewed_preparation"))


async def get_lead_case(session: AsyncSession, *, scope: LeadScope, now: datetime, include_preparations=True) -> dict:
    rows = await _case_views(session, scope, now, detail=True, include_preparations=include_preparations)
    if len(rows) != 1:
        raise ApiError(404, "NOT_FOUND", "buyer not found")
    return rows[0].model_dump(mode="json")


async def get_lead_progress(
    session: AsyncSession, *, scope: LeadScope, filters: LeadFilters, offset: int, limit: int, now: datetime,
) -> dict:
    rows = await _case_views(session, scope, now)
    selected = [row for row in rows if (
        (filters.priority is None or row.priority == filters.priority)
        and (filters.stage is None or row.stage == filters.stage)
        and (filters.owner_user_id is None or row.owner_user_id == filters.owner_user_id)
        and (filters.due_before is None or (row.due_on is not None and row.due_on <= filters.due_before))
        and (filters.qualifies_for is None or qualifies(row, filters.qualifies_for))
    )]
    totals = metrics(selected)
    context = canonical_hash([{"buyer_id": str(row.buyer_id), "version": row.version,
                                "quality": row.quality.model_dump(mode="json")} for row in selected])
    return LeadProgressPage(items=selected[offset:offset+limit], offset=offset, limit=limit,
        total=len(selected), metrics=totals, as_of=now, context_hash=context).model_dump(mode="json")
