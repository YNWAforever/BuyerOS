"""Human judgements bind exact retained observations, never a research fit."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.errors import ApiError
from ..api.lead_schemas import LeadScope, LeadReviewInput, LeadCaseUpdate, LeadObservationRecord, LeadReviewRecord
from ..db.icp import canonical_hash
from ..db.lead_workflow import LeadObservation, LeadReview, LeadReviewEvidence, LeadPrivatePayload
from ..db.runs import Person, ContactPoint
from .audit_service import append_audit
from .lead_evidence_service import (
    require_permission, personal_policy, lock_case, save_private_payload, observation_data,
    assert_active_project, retained_payload, authorize_native_policy_use,
)
from .lead_quality import relevant_observations, evaluate_lead_quality


def review_context(observations, person_id, contact_id, policy_hash):
    rows = relevant_observations(observations, person_id, contact_id)
    return canonical_hash({"policy": policy_hash, "observations": [
        {"id": str(row.id), "hash": row.content_hash, "availability": row.availability,
         "person": row.person, "channel": row.channel}
        for row in sorted(rows, key=lambda value: str(value.id))
    ]})


async def review_observations(session, scope, now):
    rows = list((await session.scalars(select(LeadObservation).where(
        LeadObservation.workspace_id == scope.workspace_id, LeadObservation.project_id == scope.project_id,
        LeadObservation.buyer_id == scope.buyer_id,
    ).order_by(LeadObservation.created_at, LeadObservation.id))).all())
    # Materialize only the server-selected subjects/payloads in this invocation.
    # observation_data still checks current policy and retention for every row;
    # this contains no authorization decisions or cross-request cache.
    payload_ids={row.payload_id for row in rows if row.payload_id}
    person_ids={row.person_id for row in rows if row.person_id}
    contact_ids={row.contact_id for row in rows if row.contact_id}
    payloads=list((await session.scalars(select(LeadPrivatePayload).where(
        LeadPrivatePayload.workspace_id==scope.workspace_id,LeadPrivatePayload.project_id==scope.project_id,
        LeadPrivatePayload.id.in_(payload_ids)))).all()) if payload_ids else []
    people=list((await session.scalars(select(Person).where(
        Person.workspace_id==scope.workspace_id,Person.id.in_(person_ids)))).all()) if person_ids else []
    contacts=list((await session.scalars(select(ContactPoint).where(
        ContactPoint.workspace_id==scope.workspace_id,ContactPoint.id.in_(contact_ids)))).all()) if contact_ids else []
    cache={"payloads":{row.id:row for row in payloads},"people":{row.id:row for row in people},
           "contacts":{row.id:row for row in contacts}}
    return [LeadObservationRecord.model_validate(await observation_data(session, scope, row, now,cache=cache)) for row in rows]


async def review_history(session, scope, observations, now):
    rows = list((await session.scalars(select(LeadReview).where(
        LeadReview.workspace_id == scope.workspace_id, LeadReview.project_id == scope.project_id,
        LeadReview.buyer_id == scope.buyer_id,
    ).order_by(LeadReview.case_version))).all())
    return [await review_data(session, scope, row, observations, now) for row in rows]


async def list_lead_reviews(session, scope, *, offset, limit, now, purpose="contact_research"):
    require_permission(scope, "getBuyer")
    filters = (LeadReview.workspace_id == scope.workspace_id, LeadReview.project_id == scope.project_id,
               LeadReview.buyer_id == scope.buyer_id)
    total = await session.scalar(select(func.count()).select_from(LeadReview).where(*filters))
    rows = list((await session.scalars(select(LeadReview).where(*filters)
        .order_by(LeadReview.case_version.desc()).offset(offset).limit(limit))).all())
    observations = await review_observations(session, scope, now) if rows else []
    items = [await review_data(session, scope, row, observations, now) for row in rows]
    if purpose == "draft_preparation":
        for index, item in enumerate(items):
            try:
                await authorize_native_policy_use(
                    session, scope, action="preparation.read", source_ids=(), now=now,
                    contact_id=item.contact_id, observation_ids=item.observation_ids, purposes=("draft_preparation",))
            except ApiError:
                items[index] = item.model_copy(update={
                    "redacted": True, "context_current": False, "rationale": None, "conflict_resolution": None,
                })
    return {"items": [item.model_dump(mode="json") for item in items], "offset": offset, "limit": limit, "total": total}


async def validate_lead_review(session, scope, data, now):
    require_permission(scope, "updateBuyer")
    await assert_active_project(session, scope)
    rows = await review_observations(session, scope, now)
    selected = relevant_observations(rows, data.person_id, data.contact_id)
    by_id = {row.id: row for row in selected}
    if any(identity not in by_id for identity in data.observation_ids):
        raise ApiError(404, "NOT_FOUND", "observation not found in selected subject")
    if set(data.observation_ids) != set(by_id):
        raise ApiError(422, "INVALID_REQUEST", "review must address all current subject observations")
    if not selected or any(row.redacted for row in selected):
        raise ApiError(403, "POLICY_BLOCKED", "current retained sources required")
    deadline = await personal_policy(session, scope, now, data.contact_id, action="lead.review",
                                     sources=[source for row in selected for source in row.sources])
    if any(row.stance == "refutes" for row in selected) and not (data.conflict_resolution or "").strip():
        raise ApiError(422, "INVALID_REQUEST", "source conflict requires an explicit resolution")
    for claim, judgement in (
        ("employment", data.employment), ("procurement_scope", data.procurement_scope),
        ("channel_ownership", data.channel_ownership),
    ):
        if judgement == "accepted" and not any(row.claim == claim and row.stance == "supports" for row in selected):
            raise ApiError(422, "INVALID_REQUEST", "accepted judgement requires supporting evidence")
    return deadline, rows


async def review_data(session, scope, row, observations, now, *, cache=None, references=None, policy_allowed=None):
    _, private = await retained_payload(session, scope, row.payload_id, now, cache=cache)
    if references is None:
        references = list((await session.scalars(select(LeadReviewEvidence.observation_id).where(
            LeadReviewEvidence.workspace_id == scope.workspace_id, LeadReviewEvidence.project_id == scope.project_id,
            LeadReviewEvidence.review_id == row.id,
        ))).all())
    proof = None
    try:
        proof = await authorize_native_policy_use(
            session, scope, action="lead.evidence.read", source_ids=(), now=now,
            contact_id=row.contact_id, observation_ids=references)
    except ApiError:
        pass
    if proof is None or policy_allowed is False:
        private = None
    content = private or {}
    references = sorted(references, key=str)
    return LeadReviewRecord(
        id=row.id, workspace_id=row.workspace_id, project_id=row.project_id, buyer_id=row.buyer_id,
        company_id=row.company_id, person_id=row.person_id, contact_id=row.contact_id,
        employment=row.employment, procurement_scope=row.procurement_scope, channel_ownership=row.channel_ownership,
        case_version=row.case_version, context_hash=row.context_hash,
        context_current=private is not None and row.context_hash == review_context(
            observations, row.person_id, row.contact_id, proof.context_hash if proof else None),
        observation_ids=references, previous_review_id=row.previous_review_id,
        recorded_by_user_id=row.recorded_by_user_id, created_at=row.created_at,
        rationale=content.get("rationale"), conflict_resolution=content.get("conflict_resolution"),
        redacted=private is None,
    )


async def append_lead_review(
    session: AsyncSession, *, scope: LeadScope, data: LeadReviewInput, expected_version: int, now: datetime,
) -> dict:
    deadline, observations = await validate_lead_review(session, scope, data, now)
    case = await lock_case(session, scope)
    if case.version != expected_version:
        raise ApiError(412, "STALE_REVISION", "buyer workflow changed")
    previous = await session.scalar(select(LeadReview).where(
        LeadReview.workspace_id == scope.workspace_id, LeadReview.project_id == scope.project_id,
        LeadReview.buyer_id == scope.buyer_id,
        LeadReview.person_id == data.person_id, LeadReview.contact_id == data.contact_id,
    ).order_by(LeadReview.case_version.desc()).limit(1))
    if data.previous_review_id is not None and (previous is None or previous.id != data.previous_review_id):
        raise ApiError(412, "STALE_REVISION", "previous review changed")
    body = data.model_dump(mode="json")
    payload = await save_private_payload(session, scope, body, deadline, data.person_id, data.contact_id)
    case.version += 1
    proof = await authorize_native_policy_use(
        session, scope, action="lead.review", source_ids=(), now=now,
        contact_id=data.contact_id, observation_ids=data.observation_ids)
    row = LeadReview(id=uuid4(), workspace_id=scope.workspace_id, project_id=scope.project_id,
        buyer_id=scope.buyer_id, company_id=scope.company_id, person_id=data.person_id, contact_id=data.contact_id,
        employment=data.employment, procurement_scope=data.procurement_scope, channel_ownership=data.channel_ownership,
        case_version=case.version, context_hash=review_context(
            observations, data.person_id, data.contact_id, proof.context_hash),
        payload_id=payload.id, previous_review_id=previous.id if previous else None, recorded_by_user_id=scope.actor_id)
    session.add(row)
    await session.flush()
    for identity in data.observation_ids:
        session.add(LeadReviewEvidence(workspace_id=scope.workspace_id, project_id=scope.project_id,
                    buyer_id=scope.buyer_id, company_id=scope.company_id, review_id=row.id, observation_id=identity))
    append_audit(session, workspace_id=scope.workspace_id, actor_id=scope.actor_id, action="lead.review.recorded",
                 entity_type="lead_review", entity_id=row.id, detail_digest=row.context_hash)
    await session.flush()
    return (await review_data(session, scope, row, observations, now)).model_dump(mode="json")


async def update_lead_case(
    session: AsyncSession, *, scope: LeadScope, data: LeadCaseUpdate, expected_version: int,
) -> dict:
    require_permission(scope, "updateBuyer")
    await assert_active_project(session, scope)
    case = await lock_case(session, scope)
    if case.version != expected_version:
        raise ApiError(412, "STALE_REVISION", "buyer workflow changed")
    case.priority, case.priority_reason = data.priority, data.priority_reason
    case.next_action, case.due_on = data.next_action, data.due_on
    case.version += 1
    append_audit(session, workspace_id=scope.workspace_id, actor_id=scope.actor_id, action="lead.case.updated",
                 entity_type="lead_case", entity_id=case.id, detail_digest=canonical_hash(data.model_dump(mode="json")))
    await session.flush()
    return {"id": str(case.id), "version": case.version, "buyer_id": str(case.buyer_id)}
