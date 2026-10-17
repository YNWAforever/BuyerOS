"""T10 purpose-policy and suppression lifecycle; server owns every permission gate."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import func, select

from ..auth import Principal, get_principal
from ..deps import load_membership, permission_for_roles, tenant_scoped
from ..errors import ApiError, envelope
from ..idempotency import begin_idempotency, complete_idempotency, if_match_version
from ..schemas import PolicyWrite, SuppressionCreate, SuppressionRemove
from ..policy_activation_schemas import ActivationSubmit, ActivationDecision, ActivationWithdrawal, ActivationPage
from ...services import policy_activation_service as activation
from ...db.buyers import Company
from ...db.icp import canonical_hash
from ...services.audit_service import append_audit
from ...db.policy import PolicyDecision, Suppression
from ...db.runs import ContactPoint
from ...services.policy_service import normalize_domain, policy_data, policy_workspace_lock, quarantine_contacts_for_suppression, suppression_data, validate_subject

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["policy"])


async def _member(session, principal, workspace_id, operation):
    member = await load_membership(session, principal=principal, workspace_id=workspace_id)
    if not permission_for_roles(member["roles"], operation):
        raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
    return member


def _key(value):
    if not value:raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    return value


def _controller(workspace_id, controller_scope_id):
    if controller_scope_id != workspace_id:
        raise ApiError(422, "INVALID_REQUEST", "controller scope is not verified for this workspace")


async def _activation_actor(session, principal, workspace_id, operation):
    member = await _member(session, principal, workspace_id, operation)
    # The service refreshes membership/version under its mutation lock.
    return activation.PolicyActor(workspace_id, member["user_id"], frozenset(member["roles"]), 0)


@router.get("/policy-controller-authorities")
async def list_policy_controller_authorities(
    workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request,
    offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100),
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        actor = await _activation_actor(session, principal, workspace_id, "listPolicyControllerAuthorities")
        result = await activation.list_authorities(
            session, actor=actor, project_id=project_id, offset=offset, limit=limit, now=datetime.now(timezone.utc))
    return envelope(result.model_dump(mode="json"), request.state.request_id)


@router.post("/policy-activation-requests", status_code=201)
async def submit_policy_activation_request(
    workspace_id: uuid.UUID, payload: ActivationSubmit, request: Request,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    async with tenant_scoped(workspace_id) as session:
        actor = await _activation_actor(session, principal, workspace_id, "submitPolicyActivationRequest")
        result = await activation.submit_activation(
            session, actor=actor, data=payload, key=_key(idempotency_key), now=datetime.now(timezone.utc))
    return envelope(result.model_dump(mode="json"), request.state.request_id)


@router.get("/policy-activation-requests")
async def list_policy_activation_requests(
    workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request,
    client_request_id: uuid.UUID | None = None,
    offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100),
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        actor = await _activation_actor(session, principal, workspace_id, "listPolicyActivationRequests")
        now = datetime.now(timezone.utc)
        if client_request_id is not None:
            item = await activation.find_activation(session, actor=actor, project_id=project_id,
                                                    client_request_id=client_request_id, now=now)
            result = ActivationPage(items=(item,) if item else (), offset=0, limit=limit, total=1 if item else 0)
        else:
            result = await activation.list_activations(
                session, actor=actor, project_id=project_id, offset=offset, limit=limit, now=now)
    return envelope(result.model_dump(mode="json"), request.state.request_id)


@router.get("/policy-activation-requests/{request_id}")
async def get_policy_activation_request(
    workspace_id: uuid.UUID, request_id: uuid.UUID, request: Request,
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        actor = await _activation_actor(session, principal, workspace_id, "getPolicyActivationRequest")
        result = await activation.get_activation(
            session, actor=actor, request_id=request_id, now=datetime.now(timezone.utc))
    return envelope(result.model_dump(mode="json"), request.state.request_id)


@router.post("/policy-activation-requests/{request_id}/decisions")
async def decide_policy_activation_request(
    workspace_id: uuid.UUID, request_id: uuid.UUID, payload: ActivationDecision, request: Request,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    async with tenant_scoped(workspace_id) as session:
        actor = await _activation_actor(session, principal, workspace_id, "decidePolicyActivationRequest")
        result = await activation.decide_activation(
            session, actor=actor, request_id=request_id, data=payload, key=_key(idempotency_key),
            now=datetime.now(timezone.utc))
    return envelope(result.model_dump(mode="json"), request.state.request_id)


@router.post("/policy-activation-requests/{request_id}/withdrawals")
async def withdraw_policy_activation_request(
    workspace_id: uuid.UUID, request_id: uuid.UUID, payload: ActivationWithdrawal, request: Request,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    async with tenant_scoped(workspace_id) as session:
        actor = await _activation_actor(session, principal, workspace_id, "withdrawPolicyActivationRequest")
        result = await activation.withdraw_activation(
            session, actor=actor, request_id=request_id, data=payload, key=_key(idempotency_key),
            now=datetime.now(timezone.utc))
    return envelope(result.model_dump(mode="json"), request.state.request_id)


@router.get("/policy-decisions")
async def list_policy_decisions(workspace_id: uuid.UUID, request: Request,
    offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100),
    subject_id: uuid.UUID | None = None, principal: Principal = Depends(get_principal)):
    async with tenant_scoped(workspace_id) as session:
        await _member(session, principal, workspace_id, "listPolicyDecisions")
        conditions = [PolicyDecision.workspace_id == workspace_id]
        if subject_id:conditions.append(PolicyDecision.subject_id == subject_id)
        total = (await session.execute(select(func.count()).select_from(PolicyDecision).where(*conditions))).scalar_one()
        rows = (await session.execute(select(PolicyDecision).where(*conditions)
            .order_by(PolicyDecision.created_at.desc(), PolicyDecision.id.desc()).offset(offset).limit(limit))).scalars().all()
        items = [policy_data(row) for row in rows]
    return envelope({"items": items, "offset": offset, "limit": limit, "total": total}, request.state.request_id)


@router.post("/policy-decisions", status_code=201)
async def record_policy_decision(workspace_id: uuid.UUID, payload: PolicyWrite, request: Request,
    principal: Principal = Depends(get_principal), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    body = payload.model_dump(mode="json")
    async with tenant_scoped(workspace_id) as session:
        member = await _member(session, principal, workspace_id, "recordPolicyDecision")
        _controller(workspace_id, payload.controller_scope_id)
        if payload.status == "permitted":
            raise ApiError(403, "POLICY_APPROVAL_REQUIRED", "a reviewed controller policy activation is required")
        if payload.expires_at <= datetime.now(timezone.utc):
            raise ApiError(422, "INVALID_REQUEST", "policy expiry must be in the future")
        await validate_subject(session, workspace_id=workspace_id, subject_type=payload.subject_type, subject_id=payload.subject_id)
        outcome = await begin_idempotency(session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id="recordPolicyDecision", key=_key(idempotency_key), body=body,
            target={"subject_type": payload.subject_type, "subject_id": str(payload.subject_id), "purpose": payload.purpose})
        if outcome.replay and outcome.response is not None:return envelope(outcome.response, request.state.request_id)
        await policy_workspace_lock(session, workspace_id)
        prior = (await session.execute(select(PolicyDecision).where(PolicyDecision.workspace_id == workspace_id,
            PolicyDecision.controller_scope_id == workspace_id, PolicyDecision.subject_type == payload.subject_type,
            PolicyDecision.subject_id == payload.subject_id, PolicyDecision.purpose == payload.purpose)
            .order_by(PolicyDecision.version.desc(), PolicyDecision.created_at.desc(), PolicyDecision.id.desc()).limit(1))).scalar_one_or_none()
        item = PolicyDecision(workspace_id=workspace_id, subject_type=payload.subject_type, subject_id=payload.subject_id,
            controller_scope_id=workspace_id, purpose=payload.purpose, status=payload.status,
            policy_version=payload.policy_version, basis_reference=payload.basis_reference, provenance=payload.provenance,
            countries=payload.countries, expires_at=payload.expires_at, retention_days=payload.retention_days,
            decision_author_id=member["user_id"], supersedes_id=prior.id if prior else None,
            version=prior.version + 1 if prior else 1)
        session.add(item);await session.flush();await session.refresh(item)
        from ...services.approval_service import invalidate_approvals_for_subject
        await invalidate_approvals_for_subject(session, workspace_id=workspace_id, subject_type=payload.subject_type, subject_id=payload.subject_id, reason="policy_changed")
        append_audit(session, workspace_id=workspace_id, actor_id=member["user_id"], action="policy.recorded",
            entity_type="policy_decision", entity_id=item.id, request_id=request.state.request_id,
            detail_digest=canonical_hash({"status": item.status, "purpose": item.purpose, "subject_id": str(item.subject_id)}))
        data = policy_data(item);complete_idempotency(outcome, str(item.id), response=data)
    return envelope(data, request.state.request_id)


@router.get("/suppressions")
async def list_suppressions(workspace_id: uuid.UUID, request: Request,
    offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100),
    principal: Principal = Depends(get_principal)):
    async with tenant_scoped(workspace_id) as session:
        await _member(session, principal, workspace_id, "listSuppressions")
        total = (await session.execute(select(func.count()).select_from(Suppression).where(Suppression.workspace_id == workspace_id))).scalar_one()
        rows = (await session.execute(select(Suppression).where(Suppression.workspace_id == workspace_id)
            .order_by(Suppression.created_at.desc(), Suppression.id.desc()).offset(offset).limit(limit))).scalars().all()
        items = [suppression_data(row) for row in rows]
    return envelope({"items": items, "offset": offset, "limit": limit, "total": total}, request.state.request_id)


@router.post("/suppressions", status_code=201)
async def create_suppression(workspace_id: uuid.UUID, payload: SuppressionCreate, request: Request,
    principal: Principal = Depends(get_principal), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    body = payload.model_dump(mode="json")
    async with tenant_scoped(workspace_id) as session:
        member = await _member(session, principal, workspace_id, "createSuppression")
        _controller(workspace_id, payload.controller_scope_id)
        if payload.expires_at is not None and payload.expires_at <= datetime.now(timezone.utc):
            raise ApiError(422, "INVALID_REQUEST", "suppression expiry must be in the future")
        normalized_domain = normalize_domain(payload.normalized_domain) if payload.normalized_domain else None
        if payload.subject_id is not None:
            await validate_subject(session, workspace_id=workspace_id, subject_type=payload.subject_type, subject_id=payload.subject_id)
        outcome = await begin_idempotency(session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id="createSuppression", key=_key(idempotency_key), body=body,
            target={"subject_type": payload.subject_type, "subject_id": str(payload.subject_id) if payload.subject_id else normalized_domain})
        if outcome.replay and outcome.response is not None:return envelope(outcome.response, request.state.request_id)
        await policy_workspace_lock(session, workspace_id)
        item = Suppression(workspace_id=workspace_id, subject_key_hash=canonical_hash({"type": payload.subject_type, "id": str(payload.subject_id) if payload.subject_id else normalized_domain}),
            subject_type=payload.subject_type, subject_id=payload.subject_id, normalized_domain=normalized_domain,
            controller_scope_id=workspace_id, purpose=payload.purposes[0], purposes=list(payload.purposes),
            reason=payload.reason, source_reference=payload.source_reference, expires_at=payload.expires_at,
            active=True, actor_id=member["user_id"], version=1)
        session.add(item);await session.flush();await session.refresh(item)
        from ...services.approval_service import invalidate_approvals_for_subject
        await invalidate_approvals_for_subject(session, workspace_id=workspace_id, subject_type=payload.subject_type,
            subject_id=payload.subject_id, normalized_domain=normalized_domain, reason="suppression_added")
        await quarantine_contacts_for_suppression(session, workspace_id=workspace_id, subject_type=payload.subject_type,
            subject_id=payload.subject_id, normalized_domain=normalized_domain)
        append_audit(session, workspace_id=workspace_id, actor_id=member["user_id"], action="suppression.created",
            entity_type="suppression", entity_id=item.id, request_id=request.state.request_id,
            detail_digest=canonical_hash({"purposes": sorted(item.purposes), "subject_hash": item.subject_key_hash}))
        data = suppression_data(item);complete_idempotency(outcome, str(item.id), response=data)
    return envelope(data, request.state.request_id)


@router.post("/suppressions/{suppression_id}/remove")
async def remove_suppression(workspace_id: uuid.UUID, suppression_id: uuid.UUID, payload: SuppressionRemove,
    request: Request, response: Response, principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match")):
    expected = if_match_version(if_match);body = payload.model_dump(mode="json")
    async with tenant_scoped(workspace_id) as session:
        member = await _member(session, principal, workspace_id, "removeSuppression")
        outcome = await begin_idempotency(session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id="removeSuppression", key=_key(idempotency_key), body=body,
            target={"suppression_id": str(suppression_id)}, precondition=if_match)
        if outcome.replay and outcome.response is not None:
            response.headers["ETag"] = f'"{outcome.response["version"]}"'
            return envelope(outcome.response, request.state.request_id)
        await policy_workspace_lock(session, workspace_id)
        item = (await session.execute(select(Suppression).where(Suppression.workspace_id == workspace_id,
            Suppression.id == suppression_id).with_for_update())).scalar_one_or_none()
        if item is None:raise ApiError(404, "NOT_FOUND", "suppression not found")
        if item.version != expected:raise ApiError(412, "STALE_REVISION", "suppression changed; reload it")
        if not item.active:raise ApiError(409, "ALREADY_REMOVED", "suppression already removed")
        item.active = False;item.removed_reason = payload.reason;item.removed_at = datetime.now(timezone.utc);item.version += 1
        await session.flush();await session.refresh(item)
        append_audit(session, workspace_id=workspace_id, actor_id=member["user_id"], action="suppression.removed",
            entity_type="suppression", entity_id=item.id, request_id=request.state.request_id,
            detail_digest=canonical_hash({"reason": "reviewed-removal", "version": item.version}))
        data = suppression_data(item);complete_idempotency(outcome, str(item.id), response=data)
        response.headers["ETag"] = f'"{item.version}"'
    return envelope(data, request.state.request_id)
