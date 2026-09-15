"""Manual outcomes, exports and audit events (BO-023/024)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, String, UniqueConstraint
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
    )

    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class ExportJob(Base, TenantMixin):
    __tablename__ = "export_jobs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_export_jobs_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_export_jobs_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_export_jobs_project"
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # buyers|draft
    scope_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="ready")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    redaction_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class AuditEvent(Base, TenantMixin):
    """Append-only; no payload PII, no tokens, no prompts."""

    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_audit_events_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_audit_events_workspace"),
    )

    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail_digest: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(400), nullable=True)
