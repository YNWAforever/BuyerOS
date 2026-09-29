"""Projects and immutable ICP versions (BO-007)."""

import hashlib
import json
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin


def canonical_hash(content: dict) -> str:
    """Deterministic content fingerprint (UTF-8, sorted keys, compact)."""
    payload = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Project(Base, TenantMixin):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_projects_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_projects_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "id", "active_icp_version_id"],
            ["icp_versions.workspace_id", "icp_versions.project_id", "icp_versions.id"],
            name="fk_projects_active_icp_same_project",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "id", "active_sender_identity_version_id"],
            ["sender_identity_versions.workspace_id", "sender_identity_versions.project_id",
             "sender_identity_versions.id"],
            name="fk_projects_active_sender_same_project",
        ),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    offer: Mapped[str] = mapped_column(Text, nullable=False)
    website: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    markets: Mapped[list[str]] = mapped_column(ARRAY(String(2)), nullable=False, default=list)
    language_preferences: Mapped[list[str]] = mapped_column(ARRAY(String(16)), nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    offer_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    active_icp_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    active_sender_identity_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    sender_identity_epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class IcpVersion(Base, TenantMixin):
    """Immutable once saved; approval binds the exact number + content hash."""

    __tablename__ = "icp_versions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_icp_versions_workspace_id"),
        UniqueConstraint("workspace_id", "project_id", "number", name="uq_icp_versions_project_number"),
        UniqueConstraint("workspace_id", "project_id", "id", name="uq_icp_versions_project_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_icp_versions_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_icp_versions_project"
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "parent_id"],
            ["icp_versions.workspace_id", "icp_versions.project_id", "icp_versions.id"],
            name="fk_icp_versions_parent_same_project",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    basis_offer_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
