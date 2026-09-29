"""Manual outcomes, exports and audit events (BO-023/024)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin


class OutcomeEvent(Base, TenantMixin):
    """Append-only, manual provenance; corrections supersede, never edit."""

    __tablename__ = "outcome_events"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_outcome_events_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_outcome_events_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "buyer_id"], ["project_buyers.workspace_id", "project_buyers.id"], name="fk_outcome_events_buyer"
        ),
        ForeignKeyConstraint(["workspace_id", "project_id", "buyer_id"],
                             ["project_buyers.workspace_id", "project_buyers.project_id", "project_buyers.id"],
                             name="fk_outcomes_project_buyer"),
        UniqueConstraint("workspace_id", "buyer_id", "id", name="uq_outcomes_buyer_id"),
        ForeignKeyConstraint(["workspace_id", "buyer_id", "supersedes_id"],
                             ["outcome_events.workspace_id", "outcome_events.buyer_id", "outcome_events.id"],
                             name="fk_outcomes_supersedes_same_buyer"),
        Index("uq_outcomes_one_successor", "workspace_id", "supersedes_id", unique=True,
              postgresql_where=text("supersedes_id IS NOT NULL")),
        Index("ix_outcomes_project_page", "workspace_id", "project_id", "created_at", "id"),
    )

    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    provenance_reference: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    correction_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class ExportJob(Base, TenantMixin):
    __tablename__ = "export_jobs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_export_jobs_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_export_jobs_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_export_jobs_project"
        ),
        ForeignKeyConstraint(["actor_user_id"], ["users.id"], name="fk_export_jobs_actor"),
        ForeignKeyConstraint(["workspace_id", "draft_id"],
                             ["outreach_drafts.workspace_id", "outreach_drafts.id"], name="fk_export_jobs_draft"),
        ForeignKeyConstraint(["workspace_id", "draft_revision_id"],
                             ["draft_revisions.workspace_id", "draft_revisions.id"], name="fk_export_jobs_revision"),
        ForeignKeyConstraint(["workspace_id", "approval_id"],
                             ["approvals.workspace_id", "approvals.id"], name="fk_export_jobs_approval"),
        Index("ix_export_jobs_actor_expiry", "workspace_id", "actor_user_id", "expires_at"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # buyers|draft
    scope_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="ready")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    redaction_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    selection_manifest: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    format: Mapped[str | None] = mapped_column(String(16), nullable=True)
    include_contact_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    policy_purpose: Mapped[str | None] = mapped_column(String(32), nullable=True)
    draft_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    draft_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    approval_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    requested_record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class AuditEvent(Base, TenantMixin):
    """Append-only; no payload PII, no tokens, no prompts."""

    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_audit_events_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_audit_events_workspace"),
    )

    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail_digest: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(400), nullable=True)
