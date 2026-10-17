"""Native immutable policy applications; permissions are always server-resolved."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from uuid import UUID

from sqlalchemy import select, text, func

from ..api.errors import ApiError
from ..api.idempotency import begin_idempotency, complete_idempotency
from ..api.policy_activation_schemas import (
    ActivationSubmit, ActivationReceipt, ActivationView, ActivationPage, PolicyTerms,
    ActivationDecision, ActivationWithdrawal, AuthoritySummary, AuthorityPage,
)
from ..db.models import Membership
from ..db.icp import Project, canonical_hash
from ..db.ingestion import OfferDocument
from ..db.policy import PolicyDecision
from ..db.policy_activation import PolicyActivationRequest, PolicyActivationResolution, PolicyControllerAuthority
from .audit_service import append_audit
from .membership_admin import lock_membership_admin
from .policy_service import policy_workspace_lock
from .policy_activation_terms import canonicalize_terms
from .policy_activation_read import latest_head, authority_eligible, effective_project_status


@dataclass(frozen=True)
class PolicyActor:
    workspace_id: UUID
    user_id: UUID
    roles: frozenset[str]
    membership_version: int


def server_time(now):
    if now.tzinfo is None:
        raise ValueError("aware server time required")
    return max(now, datetime.now(timezone.utc))


async def refresh_actor_membership(session, actor: PolicyActor) -> PolicyActor:
    if await session.scalar(text("SELECT current_setting('app.workspace_id',true)")) != str(actor.workspace_id):
        raise ApiError(404, "NOT_FOUND", "workspace not found")
    row = (await session.scalars(select(Membership).where(
        Membership.workspace_id == actor.workspace_id, Membership.user_id == actor.user_id)
        .execution_options(populate_existing=True))).one_or_none()
    if row is None or not row.active:
        raise ApiError(404, "NOT_FOUND", "workspace not found")
    if "workspace_admin" not in row.roles:
        raise ApiError(403, "PERMISSION_DENIED", "current workspace administrator required")
    return PolicyActor(actor.workspace_id, row.user_id, frozenset(row.roles), row.version)


async def _admin(session, actor, *, mutation=False):
    # Validate scope before acquiring any foreign workspace lock.
    actor = await refresh_actor_membership(session, actor)
    if mutation:
        await lock_membership_admin(session, actor.workspace_id)
        actor = await refresh_actor_membership(session, actor)
    return actor


async def _project(session, actor, project_id):
    if await session.scalar(select(Project.id).where(
            Project.workspace_id == actor.workspace_id, Project.id == project_id)) is None:
        raise ApiError(404, "NOT_FOUND", "project not found")


async def _request(session, actor, request_id):
    row = (await session.scalars(select(PolicyActivationRequest).where(
        PolicyActivationRequest.workspace_id == actor.workspace_id,
        PolicyActivationRequest.id == request_id))).one_or_none()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "policy application not found")
    return row


def _stored_submit(row):
    return ActivationSubmit(
        client_request_id=row.client_request_id, authority_id=row.authority_id,
        authority_version=row.authority_version, expected_policy_id=row.expected_policy_id,
        expected_policy_version=row.expected_policy_version, terms=row.terms,
        request_deadline=row.request_deadline)


async def build_activation_view(session, request, now) -> ActivationView:
    now = server_time(now)
    terms = PolicyTerms.model_validate(request.terms)
    resolution = (await session.scalars(select(PolicyActivationResolution).where(
        PolicyActivationResolution.workspace_id == request.workspace_id,
        PolicyActivationResolution.request_id == request.id))).one_or_none()
    state = resolution.outcome if resolution else "submitted"
    if resolution is None:
        if request.request_deadline <= now:
            state = "expired"
        else:
            authority = (await session.scalars(select(PolicyControllerAuthority).where(
                PolicyControllerAuthority.workspace_id == request.workspace_id,
                PolicyControllerAuthority.id == request.authority_id))).one_or_none()
            head = await latest_head(session, workspace_id=request.workspace_id,
                                     project_id=request.project_id, purpose=terms.purpose)
            if (not await authority_eligible(session, authority, now)
                or (head.id if head else None) != request.expected_policy_id
                or (head.version if head else None) != request.expected_policy_version):
                state = "stale"
    decision_version = await session.scalar(select(PolicyDecision.version).where(
        PolicyDecision.workspace_id == request.workspace_id, PolicyDecision.id == resolution.decision_id
    )) if resolution and resolution.decision_id else None
    receipt = ActivationReceipt(
        request_id=request.id, resolution_id=resolution.id if resolution else None,
        decision_id=resolution.decision_id if resolution else None, terms_hash=request.terms_hash,
        outcome=resolution.outcome if resolution else "submitted",
        policy_version=decision_version)
    return ActivationView(
        id=request.id, project_id=request.project_id, client_request_id=request.client_request_id,
        requester_id=request.requester_id, authority_id=request.authority_id,
        authority_version=request.authority_version, terms=terms, terms_hash=request.terms_hash,
        request_deadline=request.request_deadline, request_state=state,
        effective_status=await effective_project_status(session, workspace_id=request.workspace_id,
            project_id=request.project_id, purpose=terms.purpose, now=now), receipt=receipt)


async def get_activation(session, *, actor: PolicyActor, request_id: UUID, now: datetime) -> ActivationView:
    actor = await _admin(session, actor)
    return await build_activation_view(session, await _request(session, actor, request_id), now)


async def find_activation(session, *, actor: PolicyActor, project_id: UUID,
                          client_request_id: UUID, now: datetime) -> ActivationView | None:
    actor = await _admin(session, actor)
    await _project(session, actor, project_id)
    row = (await session.scalars(select(PolicyActivationRequest).where(
        PolicyActivationRequest.workspace_id == actor.workspace_id,
        PolicyActivationRequest.project_id == project_id,
        PolicyActivationRequest.requester_id == actor.user_id,
        PolicyActivationRequest.client_request_id == client_request_id))).one_or_none()
    return await build_activation_view(session, row, now) if row else None


async def list_activations(session, *, actor: PolicyActor, project_id: UUID,
                           offset: int, limit: int, now: datetime) -> ActivationPage:
    actor = await _admin(session, actor)
    await _project(session, actor, project_id)
    if offset < 0 or not 1 <= limit <= 100:
        raise ApiError(422, "INVALID_REQUEST", "bounded policy pagination required")
    conditions = (PolicyActivationRequest.workspace_id == actor.workspace_id,
                  PolicyActivationRequest.project_id == project_id)
    total = await session.scalar(select(func.count()).select_from(PolicyActivationRequest).where(*conditions))
    rows = (await session.scalars(select(PolicyActivationRequest).where(*conditions).order_by(
        PolicyActivationRequest.created_at.desc(), PolicyActivationRequest.id.desc()).offset(offset).limit(limit))).all()
    return ActivationPage(items=tuple([await build_activation_view(session, row, now) for row in rows]),
                          offset=offset, limit=limit, total=total)


async def list_authorities(session, *, actor: PolicyActor, project_id: UUID,
                           offset: int, limit: int, now: datetime) -> AuthorityPage:
    actor = await _admin(session, actor)
    await _project(session, actor, project_id)
    if offset < 0 or not 1 <= limit <= 100:
        raise ApiError(422, "INVALID_REQUEST", "bounded authority pagination required")
    rows = (await session.scalars(select(PolicyControllerAuthority).where(
        PolicyControllerAuthority.workspace_id == actor.workspace_id,
        PolicyControllerAuthority.project_id == project_id,
    ).distinct(PolicyControllerAuthority.approver_user_id).order_by(
        PolicyControllerAuthority.approver_user_id, PolicyControllerAuthority.version.desc()))).all()
    items = tuple([AuthoritySummary(
        id=row.id, version=row.version, project_id=row.project_id, approver_user_id=row.approver_user_id,
        purposes=tuple(row.purposes), allowed_actions=tuple(row.allowed_actions),
        valid_from=row.valid_from, expires_at=row.expires_at,
        eligible=await authority_eligible(session, row, server_time(now)),
    ) for row in rows[offset:offset + limit]])
    return AuthorityPage(items=items, offset=offset, limit=limit, total=len(rows))


async def submit_activation(session, *, actor: PolicyActor, data: ActivationSubmit,
                            key: str, now: datetime) -> ActivationView:
    actor = await _admin(session, actor, mutation=True)
    data = ActivationSubmit.model_validate(data.model_dump(mode="json"))
    if data.terms.workspace_id != actor.workspace_id:
        raise ApiError(404, "NOT_FOUND", "project not found")
    await _project(session, actor, data.terms.project_id)
    if not isinstance(key, str):
        raise ApiError(400, "INVALID_REQUEST", "original idempotency key required")
    outcome = await begin_idempotency(
        session, workspace_id=actor.workspace_id, actor_id=actor.user_id,
        operation_id="submitPolicyActivationRequest", key=key, body=data.model_dump(mode="json"),
        target={"project_id": str(data.terms.project_id), "client_request_id": str(data.client_request_id)})
    if outcome.replay and outcome.response is not None:
        view = await get_activation(session, actor=actor, request_id=UUID(outcome.response["request_id"]), now=now)
        return view.model_copy(update={"receipt": ActivationReceipt.model_validate(outcome.response)})
    await policy_workspace_lock(session, actor.workspace_id)
    existing = (await session.scalars(select(PolicyActivationRequest).where(
        PolicyActivationRequest.workspace_id == actor.workspace_id,
        PolicyActivationRequest.requester_id == actor.user_id,
        PolicyActivationRequest.client_request_id == data.client_request_id))).one_or_none()
    if existing:
        if canonical_hash(_stored_submit(existing).model_dump(mode="json")) != canonical_hash(data.model_dump(mode="json")):
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "original client reference payload required")
        view = await build_activation_view(session, existing, now)
        complete_idempotency(outcome, str(existing.id), response=view.receipt.model_dump(mode="json"))
        return view
    now = server_time(now)
    authority = (await session.scalars(select(PolicyControllerAuthority).where(
        PolicyControllerAuthority.workspace_id == actor.workspace_id,
        PolicyControllerAuthority.project_id == data.terms.project_id,
        PolicyControllerAuthority.id == data.authority_id,
        PolicyControllerAuthority.version == data.authority_version))).one_or_none()
    if (not await authority_eligible(session, authority, now)
        or data.terms.purpose not in authority.purposes
        or not set(data.terms.allowed_actions) <= set(authority.allowed_actions)
        or data.terms.valid_from < authority.valid_from or data.terms.expires_at > authority.expires_at):
        raise ApiError(403, "POLICY_APPROVAL_REQUIRED", "current bounded controller designation required")
    if data.request_deadline <= now or data.terms.expires_at <= now:
        raise ApiError(422, "INVALID_REQUEST", "future application deadline and policy expiry required")
    head = await latest_head(session, workspace_id=actor.workspace_id, project_id=data.terms.project_id,
                             purpose=data.terms.purpose)
    if ((head.id if head else None) != data.expected_policy_id
        or (head.version if head else None) != data.expected_policy_version):
        raise ApiError(412, "STALE_REVISION", "policy head changed before application")
    for document_id in data.terms.allowed_sources.document_ids:
        document = (await session.scalars(select(OfferDocument).where(
            OfferDocument.workspace_id == actor.workspace_id, OfferDocument.project_id == data.terms.project_id,
            OfferDocument.id == document_id))).one_or_none()
        if (not document or document.status != "ready" or document.deleted_at is not None
            or (document.retention_until is not None and document.retention_until <= now)):
            raise ApiError(404, "NOT_FOUND", "provided source document unavailable")
    from .provider_policy_context import validate_provider_resources
    await validate_provider_resources(session, data.terms, now)
    terms, digest = canonicalize_terms(data.terms)
    row = PolicyActivationRequest(
        workspace_id=actor.workspace_id, project_id=terms.project_id, requester_id=actor.user_id,
        client_request_id=data.client_request_id, authority_id=data.authority_id,
        authority_version=data.authority_version, expected_policy_id=data.expected_policy_id,
        expected_policy_version=data.expected_policy_version, terms=terms.model_dump(mode="json"),
        terms_hash=digest, request_deadline=data.request_deadline)
    session.add(row)
    await session.flush()
    append_audit(session, workspace_id=actor.workspace_id, actor_id=actor.user_id,
                 action="policy.activation.submitted", entity_type="policy_activation_request", entity_id=row.id,
                 detail_digest=canonical_hash({"terms_hash": digest, "authority_id": str(row.authority_id),
                                               "authority_version": row.authority_version}))
    view = await build_activation_view(session, row, now)
    complete_idempotency(outcome, str(row.id), response=view.receipt.model_dump(mode="json"))
    await session.flush()
    return view


async def _resolution(session, row):
    return (await session.scalars(select(PolicyActivationResolution).where(
        PolicyActivationResolution.workspace_id == row.workspace_id,
        PolicyActivationResolution.request_id == row.id))).one_or_none()


async def _finish_resolution(session, actor, row, *, outcome, reason, idempotency, now, decision_id=None):
    resolution = PolicyActivationResolution(
        workspace_id=row.workspace_id, project_id=row.project_id, request_id=row.id,
        actor_id=actor.user_id, outcome=outcome, decision_id=decision_id,
        terms_hash=row.terms_hash, reason_code="POLICY_" + outcome.upper(),
        reason_hash=hashlib.sha256(reason.encode()).hexdigest())
    session.add(resolution)
    await session.flush()
    if decision_id is not None:
        from . import approval_service
        await approval_service.invalidate_approvals_for_subject(
            session, workspace_id=row.workspace_id, subject_type="project",
            subject_id=row.project_id, reason="policy_changed")
    append_audit(session, workspace_id=row.workspace_id, actor_id=actor.user_id,
                 action="policy.activation." + outcome, entity_type="policy_activation_resolution",
                 entity_id=resolution.id, detail_digest=canonical_hash({
                     "request_id": str(row.id), "decision_id": str(decision_id),
                     "terms_hash": row.terms_hash, "authority_id": str(row.authority_id),
                     "authority_version": row.authority_version, "reason_sha256": resolution.reason_hash}))
    view = await build_activation_view(session, row, now)
    complete_idempotency(idempotency, str(resolution.id), response=view.receipt.model_dump(mode="json"))
    await session.flush()
    return view


async def decide_activation(session, *, actor: PolicyActor, request_id: UUID,
                            data: ActivationDecision, key: str, now: datetime) -> ActivationView:
    actor = await _admin(session, actor, mutation=True)
    data = ActivationDecision.model_validate(data.model_dump(mode="json"))
    row = await _request(session, actor, request_id)
    now = server_time(now)
    authority = (await session.scalars(select(PolicyControllerAuthority).where(
        PolicyControllerAuthority.workspace_id == row.workspace_id,
        PolicyControllerAuthority.project_id == row.project_id,
        PolicyControllerAuthority.id == row.authority_id,
        PolicyControllerAuthority.version == row.authority_version))).one_or_none()
    if (not await authority_eligible(session, authority, now)
        or authority.approver_user_id != actor.user_id):
        raise ApiError(403, "PERMISSION_DENIED", "current designated controller reviewer required")
    if data.terms_hash != row.terms_hash:
        raise ApiError(412, "STALE_REVISION", "exact application content hash required")
    if (data.expected_policy_id != row.expected_policy_id
        or data.expected_policy_version != row.expected_policy_version):
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "original policy precondition required")
    if not isinstance(key, str):
        raise ApiError(400, "INVALID_REQUEST", "original idempotency key required")
    idempotency = await begin_idempotency(
        session, workspace_id=actor.workspace_id, actor_id=actor.user_id,
        operation_id="decidePolicyActivationRequest", key=key, body=data.model_dump(mode="json"),
        target={"request_id": str(row.id)})
    if idempotency.replay and idempotency.response is not None:
        view = await build_activation_view(session, row, now)
        return view.model_copy(update={"receipt": ActivationReceipt.model_validate(idempotency.response)})
    await policy_workspace_lock(session, actor.workspace_id)
    now = server_time(now)
    prior_resolution = await _resolution(session, row)
    target_outcome = "approved" if data.action == "approve" else "rejected"
    if prior_resolution:
        if (prior_resolution.outcome != target_outcome or prior_resolution.actor_id != actor.user_id
            or prior_resolution.reason_hash != hashlib.sha256(data.reason.encode()).hexdigest()):
            raise ApiError(409, "INVALID_STATE", "application already has a different recorded decision")
        view = await build_activation_view(session, row, now)
        complete_idempotency(idempotency, str(prior_resolution.id), response=view.receipt.model_dump(mode="json"))
        return view
    if row.request_deadline <= now:
        raise ApiError(409, "INVALID_STATE", "application deadline expired")
    # Immutable rows cannot use SELECT FOR UPDATE under the reviewed append-only
    # ACL. The shared workspace transaction lock serializes legitimate writers.
    terms = PolicyTerms.model_validate(row.terms)
    if canonicalize_terms(terms)[1] != row.terms_hash:
        raise ApiError(409, "INVALID_STATE", "application content integrity check failed")
    if (not await authority_eligible(session, authority, now)
        or terms.purpose not in authority.purposes
        or not set(terms.allowed_actions) <= set(authority.allowed_actions)
        or terms.valid_from < authority.valid_from or terms.expires_at > authority.expires_at
        or terms.expires_at <= now):
        raise ApiError(403, "POLICY_APPROVAL_REQUIRED", "current bounded designation required")
    head = await latest_head(session, workspace_id=row.workspace_id, project_id=row.project_id, purpose=terms.purpose)
    if ((head.id if head else None) != row.expected_policy_id
        or (head.version if head else None) != row.expected_policy_version):
        raise ApiError(412, "STALE_REVISION", "policy changed after application")
    for document_id in terms.allowed_sources.document_ids:
        document = (await session.scalars(select(OfferDocument).where(
            OfferDocument.workspace_id == row.workspace_id, OfferDocument.project_id == row.project_id,
            OfferDocument.id == document_id))).one_or_none()
        if (not document or document.status != "ready" or document.deleted_at is not None
            or (document.retention_until is not None and document.retention_until <= now)):
            raise ApiError(412, "STALE_REVISION", "provided evidence changed or expired")
    from .provider_policy_context import validate_provider_resources
    await validate_provider_resources(session, terms, now)
    decision_id = None
    if data.action == "approve":
        decision = PolicyDecision(
            workspace_id=row.workspace_id, subject_type="project", subject_id=row.project_id,
            controller_scope_id=row.workspace_id, purpose=terms.purpose, status="permitted",
            policy_version=terms.policy_version, basis_reference=terms.basis_reference,
            provenance=terms.provenance, countries=list(terms.countries),
            expires_at=terms.expires_at, retention_days=terms.retention_days,
            decision_author_id=actor.user_id, supersedes_id=head.id if head else None,
            version=head.version + 1 if head else 1)
        session.add(decision)
        await session.flush()
        decision_id = decision.id
    return await _finish_resolution(session, actor, row, outcome=target_outcome, reason=data.reason,
                                     idempotency=idempotency, now=now, decision_id=decision_id)


async def withdraw_activation(session, *, actor: PolicyActor, request_id: UUID,
                              data: ActivationWithdrawal, key: str, now: datetime) -> ActivationView:
    actor = await _admin(session, actor, mutation=True)
    data = ActivationWithdrawal.model_validate(data.model_dump(mode="json"))
    row = await _request(session, actor, request_id)
    if row.requester_id != actor.user_id:
        raise ApiError(403, "PERMISSION_DENIED", "original requester required")
    if data.terms_hash != row.terms_hash or not data.reason.strip():
        raise ApiError(412, "STALE_REVISION", "exact original application and reason required")
    if not isinstance(key, str):
        raise ApiError(400, "INVALID_REQUEST", "original idempotency key required")
    idempotency = await begin_idempotency(
        session, workspace_id=actor.workspace_id, actor_id=actor.user_id,
        operation_id="withdrawPolicyActivationRequest", key=key, body=data.model_dump(mode="json"),
        target={"request_id": str(row.id)})
    if idempotency.replay and idempotency.response is not None:
        view = await build_activation_view(session, row, now)
        return view.model_copy(update={"receipt": ActivationReceipt.model_validate(idempotency.response)})
    await policy_workspace_lock(session, actor.workspace_id)
    now = server_time(now)
    prior_resolution = await _resolution(session, row)
    if prior_resolution:
        if (prior_resolution.outcome != "withdrawn" or prior_resolution.actor_id != actor.user_id
            or prior_resolution.reason_hash != hashlib.sha256(data.reason.encode()).hexdigest()):
            raise ApiError(409, "INVALID_STATE", "application already decided")
        view = await build_activation_view(session, row, now)
        complete_idempotency(idempotency, str(prior_resolution.id), response=view.receipt.model_dump(mode="json"))
        return view
    if row.request_deadline <= now:
        raise ApiError(409, "INVALID_STATE", "application expired")
    return await _finish_resolution(session, actor, row, outcome="withdrawn", reason=data.reason,
                                     idempotency=idempotency, now=now)
