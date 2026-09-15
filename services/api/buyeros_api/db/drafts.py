"""Drafts, immutable revisions, sender identity and exact-context approvals (BO-021/022)."""

import uuid

from sqlalchemy import Boolean, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin


class SenderIdentityVersion(Base, TenantMixin):
    """Immutable; the project points at the active version."""

    __tablename__ = "sender_identity_versions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_sender_identity_versions_workspace_id"),
        UniqueConstraint("workspace_id", "project_id", "version_key", name="uq_sender_identity_versions_key"),
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
    retired: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class OutreachDraft(Base, TenantMixin):
    __tablename__ = "outreach_drafts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_outreach_drafts_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_outreach_drafts_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_outreach_drafts_project"
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")


class DraftRevision(Base, TenantMixin):
    """Immutable once written; edits create a successor revision."""

    __tablename__ = "draft_revisions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_draft_revisions_workspace_id"),
        UniqueConstraint("workspace_id", "draft_id", "revision_number", name="uq_draft_revisions_number"),
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
    )

    draft_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    context_fingerprint: Mapped[str] = mapped_column(String(80), nullable=False)
    serializer_version: Mapped[str] = mapped_column(String(32), nullable=False, default="approval-cjson-v1")
    approver_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    invalidated_reason: Mapped[str | None] = mapped_column(String(400), nullable=True)
