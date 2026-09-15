"""Purpose-specific policy decisions and scoped suppression (BO-009).

Fail-closed: with no supplied decision the effective state is ``unknown`` and
the relevant personal-data operation stays blocked. Values (market/entity/
purpose/basis) are owner-supplied and are not invented here.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin

PURPOSES = ("research", "contact_lookup", "export", "outreach")


class PolicyDecision(Base, TenantMixin):
    __tablename__ = "policy_decisions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_policy_decisions_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_policy_decisions_workspace"),
    )

    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    basis: Mapped[str | None] = mapped_column(String(400), nullable=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1")
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    review_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Suppression(Base, TenantMixin):
    """Independent overlay; never changes contact validity."""

    __tablename__ = "suppressions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_suppressions_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_suppressions_workspace"),
    )

    subject_key_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(400), nullable=False)
    active: Mapped[bool] = mapped_column(nullable=False, default=True)
    removed_reason: Mapped[str | None] = mapped_column(String(400), nullable=True)
