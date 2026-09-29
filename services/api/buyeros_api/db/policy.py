"""Purpose-specific policy history and scoped suppression overlays (BO-009)."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin

PURPOSES = ("offer_research", "account_research", "contact_research", "draft_preparation", "outreach", "export_accounts", "export_contacts")
SUPPRESSIBLE_PURPOSES = ("contact_research", "draft_preparation", "outreach", "export_contacts")


class PolicyDecision(Base, TenantMixin):
    __tablename__ = "policy_decisions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_policy_decisions_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_policy_decisions_workspace"),
    )

    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    controller_scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    basis_reference: Mapped[str] = mapped_column(String(1000), nullable=False)
    provenance: Mapped[str] = mapped_column(String(1000), nullable=False)
    countries: Mapped[list[str]] = mapped_column(ARRAY(String(2)), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    decision_author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class Suppression(Base, TenantMixin):
    """Independent overlay; removal never changes contact validity or approvals."""

    __tablename__ = "suppressions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_suppressions_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_suppressions_workspace"),
    )

    subject_key_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    normalized_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    controller_scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)  # legacy first-purpose index
    purposes: Mapped[list[str]] = mapped_column(ARRAY(String(32)), nullable=False)
    reason: Mapped[str] = mapped_column(String(2000), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    removed_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
