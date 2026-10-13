"""Private, tenant-owned import manifests and buyer provenance links."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin


class BuyerImport(Base, TenantMixin):
    __tablename__ = "buyer_imports"
    __table_args__ = (
        UniqueConstraint("workspace_id", "project_id", "id", name="uq_buyer_imports_project_id"),
        ForeignKeyConstraint(["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], ondelete="CASCADE"),
        Index("ix_buyer_imports_scope_actor", "workspace_id", "project_id", "actor_user_id", "created_at"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="previewed")
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    preview_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class BuyerImportRow(Base, TenantMixin):
    __tablename__ = "buyer_import_rows"
    __table_args__ = (
        UniqueConstraint("workspace_id", "project_buyer_id", name="uq_buyer_import_rows_buyer"),
        UniqueConstraint("workspace_id", "import_id", "row_index", name="uq_buyer_import_rows_source"),
        ForeignKeyConstraint(["workspace_id", "project_id", "import_id"], ["buyer_imports.workspace_id", "buyer_imports.project_id", "buyer_imports.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["workspace_id", "project_id", "project_buyer_id"], ["project_buyers.workspace_id", "project_buyers.project_id", "project_buyers.id"], ondelete="CASCADE"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    import_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
