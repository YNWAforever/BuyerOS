"""Buyers, evidence, reviews, lists and snapshots (BO-008/BO-014).

Key separations: ``company`` identity is distinct from a project buyer; AI fit
(``FitAssessment``) is immutable and separate from append-only ``HumanReview``;
list membership removal keeps the company and its evidence.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin


class Company(Base, TenantMixin):
    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_companies_workspace_id"),
        Index("uq_companies_workspace_registry", "workspace_id", "registry_id",
              unique=True, postgresql_where=text("registry_id IS NOT NULL")),
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
        UniqueConstraint("workspace_id", "project_id", "id", name="uq_project_buyers_project_id"),
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
    note: Mapped[str | None] = mapped_column(String(20000), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class SourceDocument(Base, TenantMixin):
    __tablename__ = "source_documents"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_source_documents_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_source_documents_workspace"),
        ForeignKeyConstraint(["workspace_id", "project_id"],
                             ["projects.workspace_id", "projects.id"],
                             name="fk_source_documents_project"),
        ForeignKeyConstraint(["workspace_id", "project_id", "run_id"],
                             ["search_runs.workspace_id", "search_runs.project_id", "search_runs.id"],
                             name="fk_source_documents_project_run"),
    )

    canonical_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    digest: Mapped[str] = mapped_column(String(80), nullable=False)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    storage_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="excerpt_only")
    object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    excerpt: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    permission_purpose: Mapped[str | None] = mapped_column(String(32), nullable=True)


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
        ForeignKeyConstraint(
            ["workspace_id", "source_document_id"], ["source_documents.workspace_id", "source_documents.id"],
            name="fk_evidence_source_document",
        ),
        ForeignKeyConstraint(["workspace_id", "project_id", "run_id"],
                             ["search_runs.workspace_id", "search_runs.project_id", "search_runs.id"],
                             name="fk_evidence_project_run"),
        ForeignKeyConstraint(["workspace_id", "raw_candidate_id"],
                             ["raw_candidates.workspace_id", "raw_candidates.id"],
                             name="fk_evidence_raw_candidate"),
        ForeignKeyConstraint(["workspace_id", "provider_operation_id"],
                             ["provider_operations.workspace_id", "provider_operations.id"],
                             name="fk_evidence_provider_operation"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    requirement_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stance: Mapped[str] = mapped_column(String(16), nullable=False)  # supports|contradicts|qualifies
    excerpt: Mapped[str] = mapped_column(String(4000), nullable=False)
    translation: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    is_inference: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    raw_candidate_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    provider_operation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class FitAssessment(Base, TenantMixin):
    """Immutable; human acceptance is separate (see HumanReview)."""

    __tablename__ = "fit_assessments"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_fit_assessments_workspace_id"),
        UniqueConstraint("workspace_id", "project_buyer_id", "id", name="uq_fit_assessments_buyer_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_fit_assessments_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "project_buyer_id"],
            ["project_buyers.workspace_id", "project_buyers.id"],
            name="fk_fit_assessments_buyer",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "project_buyer_id"],
            ["project_buyers.workspace_id", "project_buyers.project_id", "project_buyers.id"],
            name="fk_fit_assessments_buyer_project",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "icp_version_id"],
            ["icp_versions.workspace_id", "icp_versions.project_id", "icp_versions.id"],
            name="fk_fit_assessments_icp_project",
        ),
        ForeignKeyConstraint(["workspace_id", "project_id", "run_id"],
                             ["search_runs.workspace_id", "search_runs.project_id", "search_runs.id"],
                             name="fk_fit_assessments_project_run"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    icp_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    evidence_set_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)  # match|needs_review|not_a_match
    rationale: Mapped[str] = mapped_column(String(4000), nullable=False)
    evidence_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    fit_algorithm_version: Mapped[str] = mapped_column(String(30), nullable=False, default="legacy", server_default="legacy")
    assessment_details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


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
        ForeignKeyConstraint(
            ["workspace_id", "project_buyer_id", "fit_assessment_id"],
            ["fit_assessments.workspace_id", "fit_assessments.project_buyer_id", "fit_assessments.id"],
            name="fk_human_reviews_fit_buyer",
        ),
    )

    project_buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    fit_assessment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)  # awaiting_review|accepted|rejected|needs_information
    reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class BuyerList(Base, TenantMixin):
    __tablename__ = "buyer_lists"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_buyer_lists_workspace_id"),
        UniqueConstraint("workspace_id", "project_id", "id", name="uq_buyer_lists_project_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_buyer_lists_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_buyer_lists_project"
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


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
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "list_id"],
            ["buyer_lists.workspace_id", "buyer_lists.project_id", "buyer_lists.id"],
            name="fk_list_memberships_list_project",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "buyer_id"],
            ["project_buyers.workspace_id", "project_buyers.project_id", "project_buyers.id"],
            name="fk_list_memberships_buyer_project",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    list_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class BuyerSnapshot(Base, TenantMixin):
    __tablename__ = "buyer_snapshots"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_buyer_snapshots_workspace_id"),
        UniqueConstraint("workspace_id", "project_id", "id", name="uq_buyer_snapshots_project_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_buyer_snapshots_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"],
            name="fk_buyer_snapshots_project",
        ),
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
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "snapshot_id"],
            ["buyer_snapshots.workspace_id", "buyer_snapshots.project_id", "buyer_snapshots.id"],
            name="fk_buyer_snapshot_items_snapshot_project",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "buyer_id"],
            ["project_buyers.workspace_id", "project_buyers.project_id", "project_buyers.id"],
            name="fk_buyer_snapshot_items_buyer_project",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    buyer_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class FilterPreset(Base, TenantMixin):
    __tablename__ = "filter_presets"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_filter_presets_workspace_id"),
        UniqueConstraint("workspace_id", "project_id", "actor_user_id", "name", name="uq_filter_presets_actor_name"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_filter_presets_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"],
            name="fk_filter_presets_project",
        ),
        ForeignKeyConstraint(["actor_user_id"], ["users.id"], name="fk_filter_presets_actor"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    filters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    sort: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
