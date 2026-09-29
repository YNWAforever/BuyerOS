"""Private offer documents and unapproved extraction candidates (T16)."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin


class OfferDocument(Base, TenantMixin):
    __tablename__ = "offer_documents"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_offer_documents_workspace_id"),
        UniqueConstraint("workspace_id", "project_id", "id", name="uq_offer_documents_project_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_offer_documents_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"],
            name="fk_offer_documents_project",
        ),
        CheckConstraint("kind IN ('upload','url')", name="kind"),
        CheckConstraint("status IN ('quarantined','queued','parsing','ready','failed','deleted')", name="status"),
        CheckConstraint("version > 0", name="version_positive"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="quarantined")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fact_candidates: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    source_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
