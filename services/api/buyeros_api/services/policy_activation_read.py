"""Read-only policy proof projections; no transaction-service imports or writes."""
from datetime import datetime, timezone
import re

from sqlalchemy import select, text, and_, literal_column
from sqlalchemy.orm import load_only, Load, aliased
from pydantic import ValidationError

from ..api.policy_activation_schemas import PolicyTerms
from ..db.icp import canonical_hash
from ..db.models import Membership
from ..db.policy import PolicyDecision
from ..db.policy_activation import PolicyControllerAuthority, PolicyActivationRequest, PolicyActivationResolution

PROOF_COLUMNS = {
    PolicyControllerAuthority: ("id", "workspace_id", "project_id", "approver_user_id", "membership_version",
                                "version", "status", "purposes", "allowed_actions", "valid_from", "expires_at",
                                "execution_receipt"),
    PolicyActivationRequest: ("id", "workspace_id", "project_id", "authority_id", "authority_version", "terms", "terms_hash"),
    PolicyActivationResolution: ("id", "workspace_id", "project_id", "request_id", "actor_id", "outcome",
                                 "decision_id", "terms_hash"),
}


def proof_select(model):
    # Worker has precisely these column SELECT privileges, never full-table read
    # or access to designation text / submitter / decision-reason evidence.
    return select(model).options(load_only(*(getattr(model, name) for name in PROOF_COLUMNS[model]),
                                           raiseload=True)).execution_options(populate_existing=True)


async def latest_head(session, *, workspace_id, project_id=None, purpose, subject_type="project", subject_id=None):
    target = subject_id if subject_id is not None else project_id
    if target is None:
        raise ValueError("exact subject required")
    return (await session.scalars(select(PolicyDecision).where(
        PolicyDecision.workspace_id == workspace_id, PolicyDecision.controller_scope_id == workspace_id,
        PolicyDecision.subject_type == subject_type, PolicyDecision.subject_id == target,
        PolicyDecision.purpose == purpose,
    ).order_by(PolicyDecision.version.desc(), PolicyDecision.created_at.desc(), PolicyDecision.id.desc()).limit(1))).one_or_none()


async def current_authority(session, row):
    return (await session.scalars(proof_select(PolicyControllerAuthority).where(
        PolicyControllerAuthority.workspace_id == row.workspace_id,
        PolicyControllerAuthority.project_id == row.project_id,
        PolicyControllerAuthority.approver_user_id == row.approver_user_id,
    ).order_by(PolicyControllerAuthority.version.desc(), PolicyControllerAuthority.id.desc()).limit(1))).one_or_none()


async def authority_eligible(session, row, now: datetime) -> bool:
    if row is None or row.status != "active" or not row.valid_from <= now < row.expires_at:
        return False
    latest = await current_authority(session, row)
    if latest is None or latest.id != row.id:
        return False
    member = (await session.scalars(select(Membership).where(
        Membership.workspace_id == row.workspace_id, Membership.user_id == row.approver_user_id)
        .execution_options(populate_existing=True))).one_or_none()
    owner = await session.scalar(text(
        "SELECT pg_get_userbyid(c.relowner) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relname='policy_controller_authorities'"))
    return _authority_snapshot_eligible(row, latest.id, member, owner, now)


def _authority_snapshot_eligible(row, latest_id, member, owner, now):
    if (row is None or row.status != "active" or latest_id != row.id
        or not row.valid_from <= now < row.expires_at or not member or not member.active
        or "workspace_admin" not in member.roles or member.version != row.membership_version):
        return False
    receipt = row.execution_receipt
    # Administrative direct and runtime pooled transports can differ. Their
    # runtime/DB binding is the release contract's job; this row's trust root is
    # its owner-only provisioner and exact tenant/project/member relationships.
    return (isinstance(receipt, dict) and receipt.get("service") == "policy-authority-bootstrap"
            and receipt.get("db_role") == owner and owner not in {"buyeros_api", "buyeros_worker"}
            and bool(re.fullmatch(r"[0-9a-f]{40}", str(receipt.get("source_sha", ""))))
            and all(re.fullmatch(r"[0-9a-f]{64}", str(receipt.get(key, "")))
                    for key in ("target_sha256", "authorization_sha256", "approval_reference_sha256")))


async def resolve_approved_policy_terms(session, decision: PolicyDecision, now: datetime) -> PolicyTerms | None:
    if decision.status != "permitted" or decision.subject_type != "project":
        return None
    # One fresh SQL snapshot, not a permission cache. Retain column-only worker
    # projection and refresh pinned ORM instances on every authorization.
    newest = aliased(PolicyControllerAuthority)
    newest_id = select(newest.id).where(
        newest.workspace_id == PolicyControllerAuthority.workspace_id,
        newest.project_id == PolicyControllerAuthority.project_id,
        newest.approver_user_id == PolicyControllerAuthority.approver_user_id,
    ).order_by(newest.version.desc(), newest.id.desc()).limit(1).correlate(
        PolicyControllerAuthority).scalar_subquery()
    owner = literal_column(
        "(SELECT pg_get_userbyid(c.relowner) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relname='policy_controller_authorities')").label("proof_owner")
    statement = select(PolicyActivationResolution, PolicyActivationRequest,
        PolicyControllerAuthority, Membership, newest_id, owner).select_from(
        PolicyActivationResolution).join(PolicyActivationRequest, and_(
            PolicyActivationRequest.workspace_id == PolicyActivationResolution.workspace_id,
            PolicyActivationRequest.project_id == PolicyActivationResolution.project_id,
            PolicyActivationRequest.id == PolicyActivationResolution.request_id,
        )).join(PolicyControllerAuthority, and_(
            PolicyControllerAuthority.workspace_id == PolicyActivationRequest.workspace_id,
            PolicyControllerAuthority.project_id == PolicyActivationRequest.project_id,
            PolicyControllerAuthority.id == PolicyActivationRequest.authority_id,
            PolicyControllerAuthority.version == PolicyActivationRequest.authority_version,
        )).outerjoin(Membership, and_(
            Membership.workspace_id == PolicyControllerAuthority.workspace_id,
            Membership.user_id == PolicyControllerAuthority.approver_user_id,
        )).where(
        PolicyActivationResolution.workspace_id == decision.workspace_id,
        PolicyActivationResolution.decision_id == decision.id,
        PolicyActivationResolution.outcome == "approved",
        PolicyActivationRequest.project_id == decision.subject_id,
    ).options(*(Load(model).load_only(*(getattr(model, name) for name in names), raiseload=True)
                for model, names in PROOF_COLUMNS.items())).execution_options(populate_existing=True)
    snapshot = (await session.execute(statement)).one_or_none()
    if snapshot is None:
        return None
    resolution, request, authority, member, latest_id, owner = snapshot
    now = max(now, datetime.now(timezone.utc))
    if (not _authority_snapshot_eligible(authority, latest_id, member, owner, now)
            or authority.approver_user_id != resolution.actor_id):
        return None
    try:
        terms = PolicyTerms.model_validate(request.terms)
    except ValidationError:
        return None
    digest = canonical_hash(terms.model_dump(mode="json")).removeprefix("sha256:")
    if (digest != request.terms_hash or digest != resolution.terms_hash
        or terms.workspace_id != request.workspace_id or terms.project_id != request.project_id
        or decision.controller_scope_id != request.workspace_id or terms.purpose != decision.purpose
        or decision.decision_author_id != resolution.actor_id
        or decision.expires_at != terms.expires_at or decision.retention_days != terms.retention_days
        or decision.policy_version != terms.policy_version or decision.basis_reference != terms.basis_reference
        or decision.provenance != terms.provenance or set(decision.countries) != set(terms.countries)
        or terms.purpose not in authority.purposes
        or not set(terms.allowed_actions) <= set(authority.allowed_actions)
        or terms.valid_from < authority.valid_from or terms.expires_at > authority.expires_at):
        return None
    return terms


async def effective_project_status(session, *, workspace_id, project_id, purpose, now):
    head = await latest_head(session, workspace_id=workspace_id, project_id=project_id, purpose=purpose)
    if head is None:
        return "unknown"
    if head.expires_at <= now:
        return "expired"
    if head.status != "permitted":
        return head.status
    terms = await resolve_approved_policy_terms(session, head, now)
    if terms is None:
        linked = await session.scalar(select(PolicyActivationResolution.id).where(
            PolicyActivationResolution.workspace_id == workspace_id,
            PolicyActivationResolution.decision_id == head.id))
        return "revoked" if linked else "unknown"
    return "not_yet_valid" if now < terms.valid_from else "permitted"
