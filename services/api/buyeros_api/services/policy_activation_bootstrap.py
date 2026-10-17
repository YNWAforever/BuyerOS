"""Reviewed DB-owner designation bootstrap. Never writes a permitted policy.

The DB owner is a trust root, not a second user impersonated by this service.
Authorization evidence must be verified by that operator outside the client API.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, StrictInt, StrictStr, field_validator, model_validator
from sqlalchemy import select, text

from ..api.errors import ApiError
from ..api.policy_activation_schemas import ActivationStrict, ActivationPurpose, SUPPORTED_ACTIONS
from ..db.models import Membership
from ..db.icp import Project, canonical_hash
from ..db.policy_activation import PolicyControllerAuthority
from .audit_service import append_audit
from .membership_admin import lock_membership_admin
from .policy_service import policy_workspace_lock
from .release_binding import database_target_sha256


class AuthorityManifest(ActivationStrict):
    schema_version: Literal["buyeros.policy-authority.v1"]
    operation: Literal["provision", "revoke"] = "provision"
    workspace_id: UUID
    project_id: UUID
    approver_user_id: UUID
    membership_version: StrictInt = Field(ge=1)
    purposes: tuple[ActivationPurpose, ...] = Field(min_length=1, max_length=4)
    allowed_actions: tuple[StrictStr, ...] = Field(min_length=1, max_length=20)
    valid_from: AwareDatetime
    expires_at: AwareDatetime
    designation_reference: StrictStr = Field(min_length=3, max_length=1000)
    designation_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    source_sha: StrictStr = Field(pattern=r"^[0-9a-f]{40}$")
    target_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    expected_authority_id: UUID | None
    expected_authority_version: StrictInt | None = Field(ge=1)
    revocation_reason_sha256: StrictStr | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @field_validator("valid_from", "expires_at")
    @classmethod
    def utc(cls, value):
        return value.astimezone(timezone.utc)

    @field_validator("purposes", "allowed_actions")
    @classmethod
    def unique_scope(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("duplicate authority scope")
        return tuple(sorted(values))

    @model_validator(mode="after")
    def supported(self):
        if (not set(self.allowed_actions) <= SUPPORTED_ACTIONS or self.valid_from >= self.expires_at
            or not self.designation_reference.strip()
            or (self.expected_authority_id is None) != (self.expected_authority_version is None)
            or (self.operation == "revoke" and (self.expected_authority_id is None or not self.revocation_reason_sha256))
            or (self.operation == "provision" and self.revocation_reason_sha256 is not None)):
            raise ValueError("bounded manual authority binding required")
        return self


class BootstrapAuthorization(ActivationStrict):
    manifest_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    target_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    source_sha: StrictStr = Field(pattern=r"^[0-9a-f]{40}$")
    approval_reference: StrictStr = Field(min_length=3, max_length=1000)
    approval_evidence_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")


_EXECUTION_SEAL = object()


@dataclass(frozen=True)
class VerifiedBootstrapExecution:
    manifest: AuthorityManifest
    manifest_sha256: str
    target_sha256: str
    db_role: str
    authorization_sha256: str
    approval_reference_sha256: str
    _seal: object = field(repr=False, compare=False)


def manifest_digest(manifest: AuthorityManifest) -> str:
    return canonical_hash(manifest.model_dump(mode="json")).removeprefix("sha256:")


async def _owner(session) -> str:
    row = (await session.execute(text(
        "SELECT current_user,pg_get_userbyid(c.relowner) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relname='policy_controller_authorities'"
    ))).one_or_none()
    if not row or row[0] != row[1] or row[0] in {"buyeros_api", "buyeros_worker"}:
        raise ApiError(403, "PERMISSION_DENIED", "verified existing migration-owner role required")
    return row[0]


async def verify_bootstrap_execution(session, manifest: AuthorityManifest,
                                     authorization: BootstrapAuthorization) -> VerifiedBootstrapExecution:
    actual_target = database_target_sha256(session.get_bind().url)
    digest = manifest_digest(manifest)
    if (not authorization.approval_reference.strip()
        or actual_target != manifest.target_sha256 or authorization.target_sha256 != actual_target
        or authorization.manifest_sha256 != digest or authorization.source_sha != manifest.source_sha):
        raise ValueError("authorization manifest/source/target binding mismatch")
    role = await _owner(session)
    return VerifiedBootstrapExecution(
        manifest, digest, actual_target, role,
        canonical_hash(authorization.model_dump(mode="json")).removeprefix("sha256:"),
        hashlib.sha256(authorization.approval_reference.encode()).hexdigest(), _EXECUTION_SEAL,
    )


async def _verified(session, manifest, execution):
    if (execution._seal is not _EXECUTION_SEAL or execution.manifest_sha256 != manifest_digest(manifest)
        or execution.target_sha256 != database_target_sha256(session.get_bind().url)
        or execution.manifest != manifest or await _owner(session) != execution.db_role):
        raise ValueError("verified execution manifest binding mismatch")


async def latest_authority(session, workspace_id, project_id, user_id):
    return (await session.scalars(select(PolicyControllerAuthority).where(
        PolicyControllerAuthority.workspace_id == workspace_id,
        PolicyControllerAuthority.project_id == project_id,
        PolicyControllerAuthority.approver_user_id == user_id,
    ).order_by(PolicyControllerAuthority.version.desc(), PolicyControllerAuthority.id.desc()).limit(1))).one_or_none()


def _receipt(row):
    return {"authority_id": str(row.id), "workspace_id": str(row.workspace_id),
            "project_id": str(row.project_id), "version": row.version, "status": row.status,
            "manifest_sha256": row.manifest_sha256, "execution_receipt": row.execution_receipt}


async def reconcile_authority_manifest(session, manifest_hash: str, *, workspace_id: UUID):
    row = (await session.scalars(select(PolicyControllerAuthority).where(
        PolicyControllerAuthority.workspace_id == workspace_id,
        PolicyControllerAuthority.manifest_sha256 == manifest_hash))).one_or_none()
    return _receipt(row) if row else None


async def inspect_authority_manifest(session, manifest: AuthorityManifest, now: datetime) -> dict:
    if now.tzinfo is None:
        raise ValueError("aware server time required")
    project = await session.scalar(select(Project.id).where(
        Project.workspace_id == manifest.workspace_id, Project.id == manifest.project_id))
    if project is None:
        raise ApiError(404, "NOT_FOUND", "project not found")
    prior = await latest_authority(session, manifest.workspace_id, manifest.project_id, manifest.approver_user_id)
    if ((prior.id if prior else None) != manifest.expected_authority_id
        or (prior.version if prior else None) != manifest.expected_authority_version):
        raise ApiError(412, "STALE_REVISION", "controller authority head changed")
    if manifest.operation == "provision":
        member = (await session.scalars(select(Membership).where(
            Membership.workspace_id == manifest.workspace_id,
            Membership.user_id == manifest.approver_user_id))).one_or_none()
        if (not member or not member.active or "workspace_admin" not in member.roles
            or member.version != manifest.membership_version or manifest.expires_at <= now):
            raise ApiError(403, "PERMISSION_DENIED", "current designated admin membership and future expiry required")
    return {"manifest_sha256": manifest_digest(manifest), "target_sha256": manifest.target_sha256,
            "would_create_version": prior.version + 1 if prior else 1, "operation": manifest.operation}


def _execution_receipt(execution):
    return {"service": "policy-authority-bootstrap", "db_role": execution.db_role,
            "target_sha256": execution.target_sha256, "source_sha": execution.manifest.source_sha,
            "authorization_sha256": execution.authorization_sha256,
            "approval_reference_sha256": execution.approval_reference_sha256}


async def apply_authority_manifest(session, manifest: AuthorityManifest,
                                   execution: VerifiedBootstrapExecution, now: datetime):
    await _verified(session, manifest, execution)
    if manifest.operation != "provision":
        raise ValueError("provision operation binding required")
    await lock_membership_admin(session, manifest.workspace_id)
    await policy_workspace_lock(session, manifest.workspace_id)
    prior_receipt = await reconcile_authority_manifest(session, manifest_digest(manifest), workspace_id=manifest.workspace_id)
    if prior_receipt is not None:
        return prior_receipt
    plan = await inspect_authority_manifest(session, manifest, now)
    row = PolicyControllerAuthority(
        workspace_id=manifest.workspace_id, project_id=manifest.project_id,
        approver_user_id=manifest.approver_user_id, membership_version=manifest.membership_version,
        version=plan["would_create_version"], status="active", purposes=list(manifest.purposes),
        allowed_actions=list(manifest.allowed_actions), valid_from=manifest.valid_from,
        expires_at=manifest.expires_at, designation_reference=manifest.designation_reference,
        designation_sha256=manifest.designation_sha256, manifest_sha256=manifest_digest(manifest),
        supersedes_id=manifest.expected_authority_id, execution_receipt=_execution_receipt(execution))
    session.add(row)
    await session.flush()
    append_audit(session, workspace_id=row.workspace_id, actor_id=None, action="policy.authority.provisioned",
                 entity_type="policy_authority", entity_id=row.id,
                 detail_digest=canonical_hash({"manifest": row.manifest_sha256, **row.execution_receipt,
                                               "previous": str(row.supersedes_id), "version": row.version}))
    await session.flush()
    return _receipt(row)


async def revoke_authority(session, authority_id, expected_version: int, reason: str,
                           execution: VerifiedBootstrapExecution, now: datetime):
    manifest = execution.manifest
    await _verified(session, manifest, execution)
    authority_id = UUID(str(authority_id))
    if (manifest.operation != "revoke" or manifest.expected_authority_id != authority_id
        or manifest.expected_authority_version != expected_version or not reason.strip()
        or manifest.revocation_reason_sha256 != hashlib.sha256(reason.encode()).hexdigest()):
        raise ValueError("revoke operation/authority binding mismatch")
    await lock_membership_admin(session, manifest.workspace_id)
    await policy_workspace_lock(session, manifest.workspace_id)
    replay = await reconcile_authority_manifest(session, manifest_digest(manifest), workspace_id=manifest.workspace_id)
    if replay is not None:
        return replay
    await inspect_authority_manifest(session, manifest, now)
    prior = await latest_authority(session, manifest.workspace_id, manifest.project_id, manifest.approver_user_id)
    row = PolicyControllerAuthority(
        workspace_id=prior.workspace_id, project_id=prior.project_id, approver_user_id=prior.approver_user_id,
        membership_version=prior.membership_version, version=prior.version + 1, status="revoked",
        purposes=prior.purposes, allowed_actions=prior.allowed_actions, valid_from=prior.valid_from,
        expires_at=prior.expires_at, designation_reference=prior.designation_reference,
        designation_sha256=prior.designation_sha256, manifest_sha256=manifest_digest(manifest),
        supersedes_id=prior.id, execution_receipt=_execution_receipt(execution))
    session.add(row)
    await session.flush()
    from .approval_service import invalidate_approvals_for_subject
    await invalidate_approvals_for_subject(session, workspace_id=row.workspace_id, subject_type="project",
                                           subject_id=row.project_id, reason="controller_authority_revoked")
    append_audit(session, workspace_id=row.workspace_id, actor_id=None, action="policy.authority.revoked",
                 entity_type="policy_authority", entity_id=row.id,
                 detail_digest=canonical_hash({"manifest": row.manifest_sha256, **row.execution_receipt,
                                               "previous": str(prior.id), "version": row.version,
                                               "reason_sha256": hashlib.sha256(reason.encode()).hexdigest()}))
    await session.flush()
    return _receipt(row)
