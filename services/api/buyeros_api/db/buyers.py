"""Buyers, evidence, reviews, lists and snapshots (BO-008/BO-014).

Key separations: ``company`` identity is distinct from a project buyer; AI fit
(``FitAssessment``) is immutable and separate from append-only ``HumanReview``;
list membership removal keeps the company and its evidence.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin


class Company(Base, TenantMixin):
    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_companies_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_companies_workspace"),
    )

    legal_name: Mapped[str] = mapped_column(String(400), nullable=False)
    display_name: Mapped[str] = mapped_column(String(400), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)  # non-unique identity hint
    registry_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ProjectBuyer(Base, TenantMixin):
    __tablename__ = "project_buyers"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_project_buyers_workspace_id"),
        UniqueConstraint("workspace_id", "project_id", "company_id", name="uq_project_buyers_project_company"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_project_buyers_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_project_buyers_project"
        ),
        ForeignKeyConstraint(
            ["workspace_id", "company_id"], ["companies.workspace_id", "companies.id"], name="fk_project_buyers_company"
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    note: Mapped[str | None] = mapped_column(String(4000), nullable=True)


class SourceDocument(Base, TenantMixin):
    __tablename__ = "source_documents"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_source_documents_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_source_documents_workspace"),
    )

    canonical_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    digest: Mapped[str] = mapped_column(String(80), nullable=False)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    storage_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="excerpt_only")


class Evidence(Base, TenantMixin):
    __tablename__ = "evidence"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_evidence_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_evidence_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_evidence_project"
        ),
        ForeignKeyConstraint(
            ["workspace_id", "company_id"], ["companies.workspace_id", "companies.id"], name="fk_evidence_company"
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    requirement_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stance: Mapped[str] = mapped_column(String(16), nullable=False)  # supports|contradicts|qualifies
    excerpt: Mapped[str] = mapped_column(String(4000), nullable=False)
    translation: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    is_inference: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class FitAssessment(Base, TenantMixin):
    """Immutable; human acceptance is separate (see HumanReview)."""

    __tablename__ = "fit_assessments"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_fit_assessments_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_fit_assessments_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "project_buyer_id"],
            ["project_buyers.workspace_id", "project_buyers.id"],
            name="fk_fit_assessments_buyer",
        ),
    )

    project_buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    icp_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    evidence_set_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)  # match|needs_review|not_a_match
    rationale: Mapped[str] = mapped_column(String(4000), nullable=False)
    evidence_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)


class HumanReview(Base, TenantMixin):
    """Append-only review event; never changes fit or contact validity."""

    __tablename__ = "human_reviews"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_human_reviews_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_human_reviews_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "project_buyer_id"],
            ["project_buyers.workspace_id", "project_buyers.id"],
            name="fk_human_reviews_buyer",
        ),
    )

    project_buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    fit_assessment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)  # awaiting_review|accepted|rejected|needs_information
    reason: Mapped[str | None] = mapped_column(String(400), nullable=True)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class BuyerList(Base, TenantMixin):
    __tablename__ = "buyer_lists"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_buyer_lists_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_buyer_lists_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_buyer_lists_project"
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class ListMembership(Base, TenantMixin):
    __tablename__ = "list_memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_list_memberships_workspace_id"),
        UniqueConstraint("workspace_id", "list_id", "buyer_id", name="uq_list_memberships_list_buyer"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_list_memberships_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "list_id"], ["buyer_lists.workspace_id", "buyer_lists.id"], name="fk_list_memberships_list"
        ),
        ForeignKeyConstraint(
            ["workspace_id", "buyer_id"],
            ["project_buyers.workspace_id", "project_buyers.id"],
            name="fk_list_memberships_buyer",
        ),
    )

    list_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class BuyerSnapshot(Base, TenantMixin):
    __tablename__ = "buyer_snapshots"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_buyer_snapshots_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_buyer_snapshots_workspace"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    filter_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BuyerSnapshotItem(Base, TenantMixin):
    __tablename__ = "buyer_snapshot_items"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_buyer_snapshot_items_workspace_id"),
        UniqueConstraint("workspace_id", "snapshot_id", "ordinal", name="uq_buyer_snapshot_items_ordinal"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_buyer_snapshot_items_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "snapshot_id"],
            ["buyer_snapshots.workspace_id", "buyer_snapshots.id"],
            name="fk_buyer_snapshot_items_snapshot",
        ),
    )

    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    buyer_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
