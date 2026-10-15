"""Actor-scoped durable local writes; no provider, worker or sending registry."""
import uuid
from dataclasses import replace
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.deps import permission_for_roles
from ..api.errors import ApiError
from ..api.idempotency import begin_idempotency, complete_idempotency, if_match_version
from ..api.lead_schemas import LeadScope, LeadIntentInput, LeadIntentView, LeadIntentReceipt
from ..db.buyers import ProjectBuyer
from ..db.icp import canonical_hash
from ..db.lead_workflow import LeadActionIntent, LeadObservation, LeadReview
from .audit_service import append_audit
from .lead_evidence_service import (
    append_observation, assert_active_project, observation_data, personal_policy,
    retained_payload, save_private_payload, validate_observation,
)

ACTION_PERMISSIONS = {
    "observation.append": "updateBuyer", "lead.review": "updateBuyer", "case.update": "updateBuyer",
    "preparation.create": "editDraft", "preparation.revise": "editDraft",
    "preparation.review": "approveDraft", "preparation.archive": "editDraft",
    "preparation.request_review": "requestDraftReview",
    "pilot.policy": "updateBudget", "cost.record": "updateBudget",
    "credits.record": "updateBudget", "budget.reconcile": "updateBudget",
}
LOCAL_CONFIGURATION_INTENT_DAYS = 30


def personal_action(action):
    return action in {"observation.append", "lead.review"} or (
        action.startswith("preparation.") and action != "preparation.archive"
    )


def require_action(scope, action):
    operation = ACTION_PERMISSIONS.get(action)
    if operation is None or not permission_for_roles(list(scope.roles), operation):
        raise ApiError(403, "PERMISSION_DENIED", "insufficient permission for original action")


def require_key(key):
    if not isinstance(key, str) or not 8 <= len(key) <= 200:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key must be 8..200 characters")
    return key


async def intent_scope(session, scope, row):
    if row.buyer_id is None:
        return scope
    buyer = await session.scalar(select(ProjectBuyer).where(
        ProjectBuyer.workspace_id == scope.workspace_id, ProjectBuyer.project_id == scope.project_id,
        ProjectBuyer.id == row.buyer_id,
    ))
    if buyer is None:
        raise ApiError(404, "NOT_FOUND", "buyer not found")
    return replace(scope, buyer_id=buyer.id, company_id=buyer.company_id)


async def _intent(session, scope, identity, *, lock=False):
    query = select(LeadActionIntent).where(
        LeadActionIntent.workspace_id == scope.workspace_id,
        LeadActionIntent.project_id == scope.project_id,
        LeadActionIntent.actor_id == scope.actor_id, LeadActionIntent.id == identity,
    )
    if lock:
        query = query.with_for_update()
    row = await session.scalar(query)
    if row is None:
        raise ApiError(404, "NOT_FOUND", "intent not found")
    require_action(scope, row.action)
    return row


async def _receipt(session, scope, row, now):
    if not row.resource_id or not row.resource_type:
        raise ApiError(409, "INVALID_STATE", "original result has no canonical resource")
    redacted = False
    if row.resource_type == "lead_observation":
        observation = await session.scalar(select(LeadObservation).where(
            LeadObservation.workspace_id == scope.workspace_id,
            LeadObservation.project_id == scope.project_id, LeadObservation.id == row.resource_id,
        ))
        if observation is None:
            redacted = True
        else:
            current = await observation_data(session, scope, observation, now)
            redacted = current["redacted"]
    elif row.resource_type == "lead_review":
        from .lead_review_service import review_observations, review_data
        review = await session.scalar(select(LeadReview).where(
            LeadReview.workspace_id == scope.workspace_id, LeadReview.project_id == scope.project_id,
            LeadReview.id == row.resource_id,
        ))
        redacted = review is None
        if review is not None:
            data = await review_data(session, scope, review, await review_observations(session, scope, now), now)
            redacted = data.redacted
    elif row.resource_type == "lead_preparation":
        from .lead_preparation_service import get_preparation
        view = await get_preparation(session, scope=scope, preparation_id=row.resource_id, now=now)
        redacted = view["redacted"]
    elif row.resource_type in {"pilot_cost_event", "pilot_credit_observation", "pilot_reconciliation"}:
        from ..db.lead_workflow import PilotCostEvent, PilotCreditObservation, PilotReconciliation
        model = {"pilot_cost_event": PilotCostEvent, "pilot_credit_observation": PilotCreditObservation,
                 "pilot_reconciliation": PilotReconciliation}[row.resource_type]
        item = await session.scalar(select(model).where(
            model.workspace_id == scope.workspace_id, model.project_id == scope.project_id, model.id == row.resource_id,
        ))
        _, proof = await retained_payload(session, scope, item.payload_id, now) if item else (None, None)
        redacted = proof is None
    return LeadIntentReceipt(intent_id=row.id, resource_type=row.resource_type,
        resource_id=row.resource_id, resource_version=row.resource_version or 1,
        state="applied", redacted=redacted).model_dump(mode="json")


async def _view(session, scope, row, now):
    scope = await intent_scope(session, scope, row)
    payload, content = await retained_payload(session, scope, row.payload_id, now)
    allowed = (await personal_policy(session, scope, now, payload.contact_id if payload else None,
                                     required=False) is not None) if personal_action(row.action) else True
    if not allowed:
        content = None
    receipt = await _receipt(session, scope, row, now) if row.state == "applied" else None
    return LeadIntentView(
        id=row.id, workspace_id=row.workspace_id, project_id=row.project_id,
        buyer_id=row.buyer_id, action=row.action, target_id=row.target_id,
        expected_version=row.expected_version, submission_key=row.submission_key,
        prepare_key=row.prepare_key,
        payload_hash=payload.content_hash if payload else row.fingerprint,
        payload=content.get("payload") if content and row.state == "prepared" else None,
        state=row.state, receipt=receipt, acknowledged_at=row.acknowledged_at,
        redacted=content is None or bool(receipt and receipt["redacted"]), created_at=row.created_at,
    ).model_dump(mode="json")


async def prepare_intent(
    session: AsyncSession, *, scope: LeadScope, data: LeadIntentInput, key: str,
) -> dict:
    from datetime import timezone
    now = datetime.now(timezone.utc)
    require_key(key)
    require_action(scope, data.action)
    await assert_active_project(session, scope)
    deadline = (await personal_policy(session, scope, now)) if personal_action(data.action) else now + timedelta(days=LOCAL_CONFIGURATION_INTENT_DAYS)
    body = data.model_dump(mode="json")
    fingerprint = canonical_hash({"scope": [str(scope.workspace_id), str(scope.project_id),
                                          str(scope.buyer_id), str(scope.company_id)], "body": body})
    outcome = await begin_idempotency(session, workspace_id=scope.workspace_id, actor_id=scope.actor_id,
        operation_id="prepareLeadIntent", key=key, body=body,
        target={"project_id": str(scope.project_id), "buyer_id": str(scope.buyer_id)})
    if outcome.replay:
        if not outcome.response:
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "original intent needs reconciliation")
        return await read_intent(session, scope=scope, intent_id=uuid.UUID(outcome.response["intent_id"]), now=now)
    active_query = select(LeadActionIntent).where(
        LeadActionIntent.workspace_id == scope.workspace_id, LeadActionIntent.project_id == scope.project_id,
        LeadActionIntent.actor_id == scope.actor_id, LeadActionIntent.fingerprint == fingerprint,
        LeadActionIntent.state != "cancelled", LeadActionIntent.acknowledged_at.is_(None),
    )
    row = await session.scalar(active_query)
    if row is None:
        person_id, contact_id = None, None
        offer_document_ids = []
        if data.action == "observation.append":
            deadline = await validate_observation(session, scope, data.payload, now)
            person_id = data.payload.person.person_id if data.payload.person else None
            contact_id = data.payload.channel.contact_id if data.payload.channel else None
        elif data.action == "lead.review":
            from .lead_review_service import validate_lead_review
            deadline, _ = await validate_lead_review(session, scope, data.payload, now)
            person_id, contact_id = data.payload.person_id, data.payload.contact_id
        elif data.action in {"preparation.create", "preparation.revise"}:
            from .lead_preparation_service import validate_preparation_input, _row
            if data.target_id is not None:
                await _row(session, scope, data.target_id)
            context = await validate_preparation_input(session, scope, data.payload, now)
            deadline = context["deadline"]
            offer_document_ids = [item["id"] for item in context["documents"]]
            person_id, contact_id = data.payload.person_id, data.payload.contact_id
        elif data.action.startswith("preparation."):
            from .lead_preparation_service import _row, _revision
            target, _ = await _row(session, scope, data.target_id)
            revision = await _revision(session, scope, target)
            person_id, contact_id = revision.person_id, revision.contact_id
        elif data.action in {"pilot.policy", "cost.record", "credits.record", "budget.reconcile"}:
            from .pilot_budget_service import validate_pilot_input
            await validate_pilot_input(session, scope, data.action, data.payload, now)
            if hasattr(data.payload, "source_refs"):
                offer_document_ids = [str(source.document_id) for source in data.payload.source_refs if source.document_id]
        try:
            async with session.begin_nested():
                private = await save_private_payload(session, scope, {
                    "payload": body["payload"], "offer_document_ids": offer_document_ids,
                },
                                                      deadline, person_id, contact_id)
                row = LeadActionIntent(id=uuid.uuid4(), workspace_id=scope.workspace_id,
                    project_id=scope.project_id, buyer_id=scope.buyer_id, actor_id=scope.actor_id,
                    action=data.action, target_id=data.target_id, expected_version=data.expected_version,
                    prepare_key=key, submission_key=str(uuid.uuid4()), fingerprint=fingerprint, payload_id=private.id)
                session.add(row)
                await session.flush()
        except IntegrityError:
            row = await session.scalar(active_query)
            if row is None:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "original prepare is still being reconciled")
    complete_idempotency(outcome, str(row.id), response={"intent_id": str(row.id)})
    append_audit(session, workspace_id=scope.workspace_id, actor_id=scope.actor_id,
        action="lead.intent.prepared", entity_type="lead_action_intent", entity_id=row.id,
        detail_digest=row.fingerprint)
    return await _view(session, scope, row, now)


async def read_intent(
    session: AsyncSession, *, scope: LeadScope, intent_id: uuid.UUID, now: datetime,
) -> dict:
    return await _view(session, scope, await _intent(session, scope, intent_id), now)


async def list_intents(
    session: AsyncSession, *, scope: LeadScope, offset: int, limit: int, now: datetime,
) -> dict:
    actions = [action for action, permission in ACTION_PERMISSIONS.items()
               if permission_for_roles(list(scope.roles), permission)]
    conditions = (
        LeadActionIntent.workspace_id == scope.workspace_id, LeadActionIntent.project_id == scope.project_id,
        LeadActionIntent.actor_id == scope.actor_id, LeadActionIntent.action.in_(actions),
        LeadActionIntent.state != "cancelled", LeadActionIntent.acknowledged_at.is_(None),
    )
    total = await session.scalar(select(func.count()).select_from(LeadActionIntent).where(*conditions))
    rows = list((await session.scalars(select(LeadActionIntent).where(*conditions)
        .order_by(LeadActionIntent.created_at, LeadActionIntent.id).offset(offset).limit(limit))).all())
    return {"items": [await _view(session, scope, row, now) for row in rows],
            "offset": offset, "limit": limit, "total": total}


async def apply_intent(
    session: AsyncSession, *, scope: LeadScope, intent_id: uuid.UUID, key: str,
    if_match: str | None, now: datetime,
) -> dict:
    require_key(key)
    row = await _intent(session, scope, intent_id, lock=True)
    scope = await intent_scope(session, scope, row)
    if row.submission_key != key:
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "original submission key required")
    if row.expected_version is not None:
        if if_match_version(if_match) != row.expected_version:
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "original precondition required")
    elif if_match is not None:
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "original request had no precondition")
    if row.state == "cancelled":
        raise ApiError(409, "INVALID_STATE", "intent was cancelled")
    if row.state == "applied":
        return await _receipt(session, scope, row, now)
    _, content = await retained_payload(session, scope, row.payload_id, now)
    if content is None:
        raise ApiError(409, "INVALID_STATE", "original payload is no longer retained")
    from ..api.lead_schemas import LeadObservationInput, LeadReviewInput, LeadCaseUpdate
    if row.action == "observation.append":
        result = await append_observation(session, scope=scope,
            data=LeadObservationInput.model_validate(content["payload"]), now=now)
        resource_type, resource_version = "lead_observation", 1
    elif row.action == "lead.review":
        from .lead_review_service import append_lead_review
        result = await append_lead_review(session, scope=scope,
            data=LeadReviewInput.model_validate(content["payload"]), expected_version=row.expected_version, now=now)
        resource_type, resource_version = "lead_review", result["case_version"]
    elif row.action == "case.update":
        from .lead_review_service import update_lead_case
        result = await update_lead_case(session, scope=scope,
            data=LeadCaseUpdate.model_validate(content["payload"]), expected_version=row.expected_version)
        resource_type, resource_version = "lead_case", result["version"]
    elif row.action.startswith("preparation."):
        from ..api.lead_schemas import LeadPreparationInput, LeadPreparationReviewInput, LeadPreparationStateInput
        from .lead_preparation_service import (
            create_preparation, revise_preparation, review_preparation, change_preparation_state,
        )
        if row.action == "preparation.create":
            result = await create_preparation(session, scope=scope,
                data=LeadPreparationInput.model_validate(content["payload"]), now=now)
        elif row.action == "preparation.revise":
            result = await revise_preparation(session, scope=scope, preparation_id=row.target_id,
                data=LeadPreparationInput.model_validate(content["payload"]), expected_version=row.expected_version, now=now)
        elif row.action == "preparation.review":
            data = LeadPreparationReviewInput.model_validate(content["payload"])
            result = await review_preparation(session, scope=scope, preparation_id=row.target_id,
                expected_version=row.expected_version, revision_id=data.revision_id,
                context_hash=data.context_hash, reason=data.reason, now=now)
        else:
            data = LeadPreparationStateInput.model_validate(content["payload"])
            result = await change_preparation_state(session, scope=scope, preparation_id=row.target_id,
                expected_version=row.expected_version, reason=data.reason, now=now,
                archive=row.action == "preparation.archive")
        resource_type, resource_version = "lead_preparation", result["version"]
    elif row.action in {"pilot.policy", "cost.record", "credits.record", "budget.reconcile"}:
        from ..api.lead_schemas import PilotPolicyInput, PilotCostInput, PilotCreditInput, PilotReconcileInput
        from .pilot_budget_service import (
            set_pilot_policy, record_pilot_cost, record_credit_observation, reconcile_pilot_budget,
        )
        if row.action == "pilot.policy":
            result = await set_pilot_policy(session, scope=scope,
                data=PilotPolicyInput.model_validate(content["payload"]), expected_version=row.expected_version, now=now)
            resource_type, resource_version = "pilot_budget", result["version"]
        elif row.action == "cost.record":
            result = await record_pilot_cost(session, scope=scope,
                data=PilotCostInput.model_validate(content["payload"]), expected_version=row.expected_version, now=now)
            resource_type, resource_version = "pilot_cost_event", result["version"]
        elif row.action == "credits.record":
            result = await record_credit_observation(session, scope=scope,
                data=PilotCreditInput.model_validate(content["payload"]), expected_version=row.expected_version, now=now)
            resource_type, resource_version = "pilot_credit_observation", result["version"]
        else:
            result = await reconcile_pilot_budget(session, scope=scope,
                data=PilotReconcileInput.model_validate(content["payload"]), expected_version=row.expected_version, now=now)
            result = {**result, "id": result["last_reconciliation_id"]}
            resource_type, resource_version = "pilot_reconciliation", 1
    else:
        raise ApiError(403, "POLICY_BLOCKED", "action handler unavailable")
    row.state, row.resource_type = "applied", resource_type
    row.resource_id, row.resource_version = uuid.UUID(result["id"]), resource_version
    append_audit(session, workspace_id=scope.workspace_id, actor_id=scope.actor_id,
        action="lead.intent.applied", entity_type=row.resource_type, entity_id=row.resource_id,
        detail_digest=row.fingerprint)
    await session.flush()
    return await _receipt(session, scope, row, now)


async def acknowledge_intent(
    session: AsyncSession, *, scope: LeadScope, intent_id: uuid.UUID, key: str, now: datetime,
) -> dict:
    require_key(key)
    row = await _intent(session, scope, intent_id, lock=True)
    if row.state == "prepared":
        raise ApiError(409, "INVALID_STATE", "unresolved intent cannot be acknowledged")
    if row.acknowledged_at is None:
        row.acknowledged_at = now
        append_audit(session, workspace_id=scope.workspace_id, actor_id=scope.actor_id,
            action="lead.intent.acknowledged", entity_type="lead_action_intent", entity_id=row.id)
    return await _view(session, scope, row, now)


async def cancel_intent(
    session: AsyncSession, *, scope: LeadScope, intent_id: uuid.UUID, key: str, now: datetime,
) -> dict:
    require_key(key)
    row = await _intent(session, scope, intent_id, lock=True)
    if row.state == "prepared":
        row.state = "cancelled"
        append_audit(session, workspace_id=scope.workspace_id, actor_id=scope.actor_id,
            action="lead.intent.cancelled", entity_type="lead_action_intent", entity_id=row.id)
    return await _view(session, scope, row, now)
