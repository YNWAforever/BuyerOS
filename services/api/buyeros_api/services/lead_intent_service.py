"""Actor-scoped durable local writes; no provider, worker or sending registry."""
import uuid
from dataclasses import replace
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.deps import permission_for_roles
from ..api.errors import ApiError
from ..api.idempotency import begin_idempotency, complete_idempotency, if_match_version
from ..api.lead_schemas import LeadScope, LeadIntentInput, LeadIntentView, LeadIntentReceipt
from ..db.buyers import ProjectBuyer
from ..db.icp import canonical_hash
from ..db.lead_workflow import LeadActionIntent, LeadObservation
from .audit_service import append_audit
from .lead_evidence_service import (
    append_observation, assert_active_project, observation_data, personal_policy,
    retained_payload, save_private_payload, validate_observation,
)

ACTION_PERMISSIONS = {"observation.append": "updateBuyer"}


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
    return LeadIntentReceipt(intent_id=row.id, resource_type=row.resource_type,
        resource_id=row.resource_id, resource_version=row.resource_version or 1,
        state="applied", redacted=redacted).model_dump(mode="json")


async def _view(session, scope, row, now):
    scope = await intent_scope(session, scope, row)
    payload, content = await retained_payload(session, scope, row.payload_id, now)
    allowed = await personal_policy(session, scope, now, required=False) is not None
    if not allowed:
        content = None
    receipt = await _receipt(session, scope, row, now) if row.state == "applied" else None
    return LeadIntentView(
        id=row.id, workspace_id=row.workspace_id, project_id=row.project_id,
        buyer_id=row.buyer_id, action=row.action, target_id=row.target_id,
        expected_version=row.expected_version, submission_key=row.submission_key,
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
    deadline = await personal_policy(session, scope, now)
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
        deadline = await validate_observation(session, scope, data.payload, now)
        person_id = data.payload.person.person_id if data.payload.person else None
        contact_id = data.payload.channel.contact_id if data.payload.channel else None
        try:
            async with session.begin_nested():
                private = await save_private_payload(session, scope, {"payload": body["payload"]},
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
    from ..api.lead_schemas import LeadObservationInput
    result = await append_observation(session, scope=scope,
                                      data=LeadObservationInput.model_validate(content["payload"]), now=now)
    row.state, row.resource_type = "applied", "lead_observation"
    row.resource_id, row.resource_version = uuid.UUID(result["id"]), 1
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
