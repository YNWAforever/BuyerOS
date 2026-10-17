"""Immutable controller designation, exact policy request and unique resolution."""
from datetime import datetime
from uuid import UUID as PythonUUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin


class PolicyControllerAuthority(Base, TenantMixin):
    __tablename__ = "policy_controller_authorities"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_policy_authority_tenant"),
        UniqueConstraint("workspace_id", "project_id", "id", "version", name="uq_policy_authority_binding"),
        UniqueConstraint("workspace_id", "project_id", "approver_user_id", "version", name="uq_policy_authority_version"),
        UniqueConstraint("workspace_id", "manifest_sha256", name="uq_policy_authority_manifest"),
        ForeignKeyConstraint(["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_pauthority_project"),
        ForeignKeyConstraint(["workspace_id", "approver_user_id"], ["memberships.workspace_id", "memberships.user_id"], name="fk_pauthority_member"),
        ForeignKeyConstraint(["workspace_id", "supersedes_id"], ["policy_controller_authorities.workspace_id", "policy_controller_authorities.id"], name="fk_pauthority_previous"),
        CheckConstraint("version>=1 AND membership_version>=1", name="policy_authority_versions"),
        CheckConstraint("status IN ('active','revoked') AND valid_from<expires_at", name="policy_authority_state"),
        CheckConstraint("cardinality(purposes) BETWEEN 1 AND 4 AND purposes <@ ARRAY['account_research','contact_research','draft_preparation','outreach']::varchar[]",
                        name="policy_authority_purposes"),
        Index("ix_policy_authority_current", "workspace_id", "project_id", "approver_user_id", "version"),
    )
    project_id: Mapped[PythonUUID] = mapped_column(UUID, nullable=False)
    approver_user_id: Mapped[PythonUUID] = mapped_column(UUID, nullable=False)
    membership_version: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    purposes: Mapped[list[str]] = mapped_column(ARRAY(String(32)), nullable=False)
    allowed_actions: Mapped[list[str]] = mapped_column(ARRAY(String(64)), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    designation_reference: Mapped[str] = mapped_column(String(1000), nullable=False)
    designation_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_receipt: Mapped[dict] = mapped_column(JSONB, nullable=False)
    supersedes_id: Mapped[PythonUUID | None] = mapped_column(UUID, nullable=True)


class PolicyActivationRequest(Base, TenantMixin):
    __tablename__ = "policy_activation_requests"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_policy_request_tenant"),
        UniqueConstraint("workspace_id", "project_id", "id", name="uq_policy_request_project"),
        UniqueConstraint("workspace_id", "requester_id", "client_request_id", name="uq_policy_request_client"),
        ForeignKeyConstraint(["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_prequest_project"),
        ForeignKeyConstraint(["workspace_id", "requester_id"], ["memberships.workspace_id", "memberships.user_id"], name="fk_prequest_member"),
        ForeignKeyConstraint(["workspace_id", "project_id", "authority_id", "authority_version"],
                             ["policy_controller_authorities.workspace_id", "policy_controller_authorities.project_id",
                              "policy_controller_authorities.id", "policy_controller_authorities.version"], name="fk_prequest_authority"),
        ForeignKeyConstraint(["workspace_id", "expected_policy_id"], ["policy_decisions.workspace_id", "policy_decisions.id"], name="fk_prequest_previous"),
        CheckConstraint("(expected_policy_id IS NULL)=(expected_policy_version IS NULL)", name="policy_request_prior_pair"),
        CheckConstraint(
            "jsonb_typeof(terms)='object' AND terms->>'workspace_id'=workspace_id::text "
            "AND terms->>'controller_scope_id'=workspace_id::text AND terms->>'project_id'=project_id::text",
            name="policy_request_terms_scope"),
        Index("ix_policy_request_project", "workspace_id", "project_id", "created_at"),
    )
    project_id: Mapped[PythonUUID] = mapped_column(UUID, nullable=False)
    requester_id: Mapped[PythonUUID] = mapped_column(UUID, nullable=False)
    client_request_id: Mapped[PythonUUID] = mapped_column(UUID, nullable=False)
    authority_id: Mapped[PythonUUID] = mapped_column(UUID, nullable=False)
    authority_version: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_policy_id: Mapped[PythonUUID | None] = mapped_column(UUID, nullable=True)
    expected_policy_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    terms: Mapped[dict] = mapped_column(JSONB, nullable=False)
    terms_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PolicyActivationResolution(Base, TenantMixin):
    __tablename__ = "policy_activation_resolutions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_policy_resolution_tenant"),
        UniqueConstraint("workspace_id", "request_id", name="uq_policy_resolution_once"),
        UniqueConstraint("workspace_id", "decision_id", name="uq_policy_resolution_decision"),
        ForeignKeyConstraint(["workspace_id", "project_id", "request_id"],
                             ["policy_activation_requests.workspace_id", "policy_activation_requests.project_id", "policy_activation_requests.id"], name="fk_presolution_request"),
        ForeignKeyConstraint(["workspace_id", "actor_id"], ["memberships.workspace_id", "memberships.user_id"], name="fk_presolution_actor"),
        ForeignKeyConstraint(["workspace_id", "decision_id"], ["policy_decisions.workspace_id", "policy_decisions.id"], name="fk_presolution_decision"),
        CheckConstraint("outcome IN ('approved','rejected','withdrawn') AND ((outcome='approved')=(decision_id IS NOT NULL))",
                        name="policy_resolution_decision"),
    )
    project_id: Mapped[PythonUUID] = mapped_column(UUID, nullable=False)
    request_id: Mapped[PythonUUID] = mapped_column(UUID, nullable=False)
    actor_id: Mapped[PythonUUID] = mapped_column(UUID, nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    decision_id: Mapped[PythonUUID | None] = mapped_column(UUID, nullable=True)
    terms_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_hash: Mapped[str] = mapped_column(String(64), nullable=False)
