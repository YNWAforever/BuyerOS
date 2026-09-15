"""Search runs, durable run events, candidates, aliases and contacts (BO-013..BO-016)."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin


class SearchRun(Base, TenantMixin):
    __tablename__ = "search_runs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_search_runs_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_search_runs_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_search_runs_project"
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    icp_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    limits: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    target_companies: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    raw_result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    terminal_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)


class RunEvent(Base, TenantMixin):
    """Monotonic per-run sequence; committed atomically with state changes."""

    __tablename__ = "run_events"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_run_events_workspace_id"),
        UniqueConstraint("workspace_id", "run_id", "sequence", name="uq_run_events_sequence"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_run_events_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "run_id"], ["search_runs.workspace_id", "search_runs.id"], name="fk_run_events_run"
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class RawCandidate(Base, TenantMixin):
    """Raw observation before canonicalization; keeps source provenance."""

    __tablename__ = "raw_candidates"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_raw_candidates_workspace_id"),
        UniqueConstraint("workspace_id", "run_id", "normalized_url", name="uq_raw_candidates_run_url"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_raw_candidates_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "run_id"], ["search_runs.workspace_id", "search_runs.id"], name="fk_raw_candidates_run"
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_digest: Mapped[str | None] = mapped_column(String(80), nullable=True)
    canonical_company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    merge_state: Mapped[str] = mapped_column(String(16), nullable=False, default="unmapped")


class CompanyAlias(Base, TenantMixin):
    """Non-unique canonicalization hints; disambiguation is a human review."""

    __tablename__ = "company_aliases"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_company_aliases_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_company_aliases_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "company_id"], ["companies.workspace_id", "companies.id"], name="fk_company_aliases_company"
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    alias_type: Mapped[str] = mapped_column(String(32), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(400), nullable=False)
    provenance: Mapped[str | None] = mapped_column(String(400), nullable=True)
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Person(Base, TenantMixin):
    __tablename__ = "people"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_people_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_people_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "company_id"], ["companies.workspace_id", "companies.id"], name="fk_people_company"
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    role: Mapped[str | None] = mapped_column(String(200), nullable=True)
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ContactPoint(Base, TenantMixin):
    """Validity is independent of suppression and purpose permission."""

    __tablename__ = "contact_points"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_contact_points_workspace_id"),
        UniqueConstraint("workspace_id", "company_id", "type", "normalized_value", name="uq_contact_points_value"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_contact_points_workspace"),
        ForeignKeyConstraint(
            ["workspace_id", "company_id"], ["companies.workspace_id", "companies.id"], name="fk_contact_points_company"
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, default="business_email")
    normalized_value: Mapped[str] = mapped_column(String(400), nullable=False)
    validity: Mapped[str] = mapped_column(String(32), nullable=False, default="unverified_public")
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quarantined: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
