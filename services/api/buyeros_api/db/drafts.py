"""Drafts, immutable revisions, sender identity and exact-context approvals (BO-021/022)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin


class SenderIdentityVersion(Base, TenantMixin):
    """Immutable; the project points at the active version."""

    __tablename__ = "sender_identity_versions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_sender_identity_versions_workspace_id"),
        UniqueConstraint("workspace_id", "project_id", "version_key", name="uq_sender_identity_versions_key"),
        UniqueConstraint("workspace_id", "project_id", "id", name="uq_sender_versions_project_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_sender_identity_versions_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_sender_versions_project"
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_key: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str | None] = mapped_column(String(200), nullable=True)
    organization: Mapped[str | None] = mapped_column(String(200), nullable=True)
    business_email: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_reason: Mapped[str | None] = mapped_column(String(400), nullable=True)
    retired: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class OutreachDraft(Base, TenantMixin):
    __tablename__ = "outreach_drafts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_outreach_drafts_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_outreach_drafts_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_outreach_drafts_project"
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "buyer_id"],
            ["project_buyers.workspace_id", "project_buyers.project_id", "project_buyers.id"],
            name="fk_outreach_drafts_buyer_project",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    review_context_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    review_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class DraftRevision(Base, TenantMixin):
    """Immutable once written; edits create a successor revision."""

    __tablename__ = "draft_revisions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_draft_revisions_workspace_id"),
        UniqueConstraint("workspace_id", "draft_id", "revision_number", name="uq_draft_revisions_number"),
        UniqueConstraint("workspace_id", "draft_id", "revision_number", "id",
                         name="uq_draft_revision_exact_binding"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_draft_revisions_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "draft_id"], ["outreach_drafts.workspace_id", "outreach_drafts.id"], name="fk_draft_revisions_draft"
        ),
    )

    draft_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    offer_fact_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)


class Approval(Base, TenantMixin):
    """Binds the exact revision + context fingerprint; never implies delivery."""

    __tablename__ = "approvals"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_approvals_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_approvals_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "draft_id"], ["outreach_drafts.workspace_id", "outreach_drafts.id"], name="fk_approvals_draft"
        ),
        ForeignKeyConstraint(
            ["workspace_id", "draft_id", "revision_number", "draft_revision_id"],
            ["draft_revisions.workspace_id", "draft_revisions.draft_id",
             "draft_revisions.revision_number", "draft_revisions.id"],
            name="fk_approvals_exact_revision",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "recipient_contact_id"], ["contact_points.workspace_id", "contact_points.id"],
            name="fk_approvals_contact_workspace",
        ),
        Index("uq_approvals_current_draft", "workspace_id", "draft_id", unique=True,
              postgresql_where=text("invalidated_reason IS NULL")),
    )

    draft_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    context_fingerprint: Mapped[str] = mapped_column(String(80), nullable=False)
    serializer_version: Mapped[str] = mapped_column(String(32), nullable=False, default="approval-cjson-v1")
    approver_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    invalidated_reason: Mapped[str | None] = mapped_column(String(400), nullable=True)
    draft_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    recipient_contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    recipient_contact_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_set_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    icp_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    policy_decision_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    sender_identity_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    context_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
