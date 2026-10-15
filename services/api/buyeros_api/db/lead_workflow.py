"""Manual lead evidence and preparation, deliberately separate from research/delivery."""
import uuid
from hashlib import sha256
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKeyConstraint, Index,
    Integer, Numeric, String, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin


def _project_keys(table: str):
    return (
        UniqueConstraint("workspace_id", "id", name=f"uq_{table}_tenant"),
        UniqueConstraint("workspace_id", "project_id", "id", name=f"uq_{table}_project"),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"],
            name=f"fk_{table}_project",
        ),
    )


def _buyer_keys(table: str):
    return (
        *_project_keys(table),
        UniqueConstraint("workspace_id", "project_id", "buyer_id", "id", name=f"uq_{table}_buyer"),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "buyer_id", "company_id"],
            ["project_buyers.workspace_id", "project_buyers.project_id",
             "project_buyers.id", "project_buyers.company_id"],
            name=f"fk_{table}_buyer",
        ),
    )


def _person_keys(table: str):
    return (
        ForeignKeyConstraint(
            ["workspace_id", "company_id", "person_id"],
            ["people.workspace_id", "people.company_id", "people.id"],
            name=f"fk_{table}_person",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "company_id", "contact_id"],
            ["contact_points.workspace_id", "contact_points.company_id", "contact_points.id"],
            name=f"fk_{table}_contact",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "company_id", "person_id", "contact_id"],
            ["contact_points.workspace_id", "contact_points.company_id",
             "contact_points.person_id", "contact_points.id"],
            name=f"fk_{table}_contact_person",
        ),
    )


class ProjectLeadColumns:
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class BuyerLeadColumns(ProjectLeadColumns):
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class PersonLeadColumns:
    person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class LeadPrivatePayload(Base, TenantMixin, ProjectLeadColumns):
    """Only this content may be cleared by the narrowly scoped retention function."""
    __tablename__ = "lead_private_payloads"
    __table_args__ = (
        *_project_keys(__tablename__),
        ForeignKeyConstraint(["workspace_id", "company_id"], ["companies.workspace_id", "companies.id"]),
        *_person_keys(__tablename__),
        Index("ix_lead_payload_subject", "workspace_id", "person_id", "contact_id"),
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    contents: Mapped[dict | None] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    retention_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    redacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LeadCaseState(Base, TenantMixin, BuyerLeadColumns):
    __tablename__ = "lead_case_states"
    __table_args__ = (
        *_buyer_keys(__tablename__),
        UniqueConstraint("workspace_id", "project_id", "buyer_id", name="uq_lead_case_one"),
        CheckConstraint("version >= 1", name="lead_case_version"),
    )
    priority: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    priority_reason: Mapped[str] = mapped_column(String(4000), nullable=False, default="", server_default="")
    next_action: Mapped[str] = mapped_column(String(200), nullable=False, default="", server_default="")
    due_on: Mapped[date | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class LeadObservation(Base, TenantMixin, BuyerLeadColumns, PersonLeadColumns):
    __tablename__ = "lead_observations"
    __table_args__ = (
        *_buyer_keys(__tablename__), *_person_keys(__tablename__),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "payload_id"],
            ["lead_private_payloads.workspace_id", "lead_private_payloads.project_id", "lead_private_payloads.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "buyer_id", "supersedes_id"],
            ["lead_observations.workspace_id", "lead_observations.project_id",
             "lead_observations.buyer_id", "lead_observations.id"],
        ),
        ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"]),
        CheckConstraint("claim IN ('employment','procurement_scope','channel_ownership')", name="lead_observation_claim"),
        CheckConstraint("stance IN ('supports','refutes','uncertain')", name="lead_observation_stance"),
        Index("ix_lead_observations_case", "workspace_id", "project_id", "buyer_id", "created_at"),
    )
    claim: Mapped[str] = mapped_column(String(32), nullable=False)
    stance: Mapped[str] = mapped_column(String(16), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class LeadReview(Base, TenantMixin, BuyerLeadColumns, PersonLeadColumns):
    __tablename__ = "lead_reviews"
    __table_args__ = (
        *_buyer_keys(__tablename__), *_person_keys(__tablename__),
        ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"]),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "buyer_id", "previous_review_id"],
            ["lead_reviews.workspace_id", "lead_reviews.project_id", "lead_reviews.buyer_id", "lead_reviews.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "payload_id"],
            ["lead_private_payloads.workspace_id", "lead_private_payloads.project_id", "lead_private_payloads.id"],
        ),
        CheckConstraint("employment IN ('accepted','uncertain','rejected')", name="lead_review_employment"),
        CheckConstraint("procurement_scope IN ('accepted','uncertain','rejected')", name="lead_review_procurement"),
        CheckConstraint("channel_ownership IN ('accepted','uncertain','rejected')", name="lead_review_channel"),
        UniqueConstraint("workspace_id", "project_id", "buyer_id", "case_version", name="uq_lead_review_sequence"),
    )
    employment: Mapped[str] = mapped_column(String(16), nullable=False)
    procurement_scope: Mapped[str] = mapped_column(String(16), nullable=False)
    channel_ownership: Mapped[str] = mapped_column(String(16), nullable=False)
    case_version: Mapped[int] = mapped_column(Integer, nullable=False)
    context_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    previous_review_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class LeadReviewEvidence(Base, TenantMixin, BuyerLeadColumns):
    __tablename__ = "lead_review_evidence"
    __table_args__ = (
        *_buyer_keys(__tablename__),
        UniqueConstraint("workspace_id", "review_id", "observation_id", name="uq_lead_review_ref"),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "buyer_id", "review_id"],
            ["lead_reviews.workspace_id", "lead_reviews.project_id", "lead_reviews.buyer_id", "lead_reviews.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "buyer_id", "observation_id"],
            ["lead_observations.workspace_id", "lead_observations.project_id",
             "lead_observations.buyer_id", "lead_observations.id"],
        ),
    )
    review_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    observation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class LeadPreparation(Base, TenantMixin, BuyerLeadColumns):
    __tablename__ = "lead_preparations"
    __table_args__ = (
        *_buyer_keys(__tablename__),
        CheckConstraint(
            "state IN ('editing','review_requested','reviewed','needs_review','archived')",
            name="lead_preparation_state",
        ),
    )
    state: Mapped[str] = mapped_column(String(24), nullable=False, default="editing", server_default="editing")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class LeadPreparationRevision(Base, TenantMixin, BuyerLeadColumns, PersonLeadColumns):
    __tablename__ = "lead_preparation_revisions"
    __table_args__ = (
        *_buyer_keys(__tablename__), *_person_keys(__tablename__),
        ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"]),
        UniqueConstraint("workspace_id", "preparation_id", "revision_number", name="uq_lead_prep_revision"),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "buyer_id", "preparation_id"],
            ["lead_preparations.workspace_id", "lead_preparations.project_id",
             "lead_preparations.buyer_id", "lead_preparations.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "payload_id"],
            ["lead_private_payloads.workspace_id", "lead_private_payloads.project_id", "lead_private_payloads.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "buyer_id", "lead_review_id"],
            ["lead_reviews.workspace_id", "lead_reviews.project_id", "lead_reviews.buyer_id", "lead_reviews.id"],
        ),
    )
    preparation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    lead_review_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    context_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class LeadPreparationEvidence(Base, TenantMixin, BuyerLeadColumns):
    __tablename__ = "lead_preparation_evidence"
    __table_args__ = (
        *_buyer_keys(__tablename__),
        UniqueConstraint("workspace_id", "revision_id", "observation_id", name="uq_lead_prep_ref"),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "buyer_id", "revision_id"],
            ["lead_preparation_revisions.workspace_id", "lead_preparation_revisions.project_id",
             "lead_preparation_revisions.buyer_id", "lead_preparation_revisions.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "buyer_id", "observation_id"],
            ["lead_observations.workspace_id", "lead_observations.project_id",
             "lead_observations.buyer_id", "lead_observations.id"],
        ),
    )
    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    observation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class LeadPreparationContentReview(Base, TenantMixin, BuyerLeadColumns):
    __tablename__ = "lead_preparation_content_reviews"
    __table_args__ = (
        *_buyer_keys(__tablename__),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "buyer_id", "revision_id"],
            ["lead_preparation_revisions.workspace_id", "lead_preparation_revisions.project_id",
             "lead_preparation_revisions.buyer_id", "lead_preparation_revisions.id"],
        ),
        ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"]),
    )
    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    context_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class LeadActionIntent(Base, TenantMixin, ProjectLeadColumns):
    __tablename__ = "lead_action_intents"
    __table_args__ = (
        *_project_keys(__tablename__),
        ForeignKeyConstraint(["actor_id"], ["users.id"]),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "buyer_id"],
            ["project_buyers.workspace_id", "project_buyers.project_id", "project_buyers.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "payload_id"],
            ["lead_private_payloads.workspace_id", "lead_private_payloads.project_id", "lead_private_payloads.id"],
        ),
        UniqueConstraint("workspace_id", "project_id", "actor_id", "prepare_key", name="uq_lead_intent_prepare"),
        Index(
            "uq_lead_intent_unresolved", "workspace_id", "project_id", "actor_id", "fingerprint",
            unique=True, postgresql_where=text("state <> 'cancelled' AND acknowledged_at IS NULL"),
        ),
        CheckConstraint("state IN ('prepared','applied','cancelled')", name="lead_intent_state"),
    )
    buyer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    expected_version: Mapped[int | None] = mapped_column(Integer)
    prepare_key: Mapped[str] = mapped_column(String(200), nullable=False)
    submission_key: Mapped[str] = mapped_column(String(200), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="prepared", server_default="prepared")
    resource_type: Mapped[str | None] = mapped_column(String(40))
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    resource_version: Mapped[int | None] = mapped_column(Integer)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PilotBudgetPolicy(Base, TenantMixin, ProjectLeadColumns):
    __tablename__ = "pilot_budget_policies"
    __table_args__ = (
        *_project_keys(__tablename__),
        UniqueConstraint("workspace_id", "project_id", name="uq_pilot_policy_one"),
        CheckConstraint("monthly_limit BETWEEN 0 AND 10", name="pilot_limit"),
    )
    monthly_limit: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("10"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    ledger_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class PilotCostEvent(Base, TenantMixin, ProjectLeadColumns):
    __tablename__ = "pilot_cost_events"
    __table_args__ = (
        *_project_keys(__tablename__),
        ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"]),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "previous_event_id"],
            ["pilot_cost_events.workspace_id", "pilot_cost_events.project_id", "pilot_cost_events.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "native_operation_id"],
            ["budget_reservations.workspace_id", "budget_reservations.operation_id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "payload_id"],
            ["lead_private_payloads.workspace_id", "lead_private_payloads.project_id", "lead_private_payloads.id"],
        ),
        UniqueConstraint("workspace_id", "project_id", "economic_key_hash", "sequence", name="uq_pilot_cost_sequence"),
        CheckConstraint("state IN ('committed','settled','unknown','corrected')", name="pilot_cost_state"),
        CheckConstraint("usd_amount IS NULL OR usd_amount >= 0", name="pilot_cost_nonnegative"),
        CheckConstraint("usd_upper_bound IS NULL OR usd_upper_bound >= 0", name="pilot_cost_upper"),
    )
    economic_key_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    native_operation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    effective_state: Mapped[str] = mapped_column(String(16), nullable=False)
    usd_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    usd_upper_bound: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    payload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class PilotCreditObservation(Base, TenantMixin, ProjectLeadColumns):
    __tablename__ = "pilot_credit_observations"
    __table_args__ = (
        *_project_keys(__tablename__),
        ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"]),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "payload_id"],
            ["lead_private_payloads.workspace_id", "lead_private_payloads.project_id", "lead_private_payloads.id"],
        ),
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    remaining: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class PilotReconciliation(Base, TenantMixin, ProjectLeadColumns):
    __tablename__ = "pilot_reconciliations"
    __table_args__ = (
        *_project_keys(__tablename__),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "payload_id"],
            ["lead_private_payloads.workspace_id", "lead_private_payloads.project_id", "lead_private_payloads.id"],
        ),
        ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"]),
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ledger_version: Mapped[int] = mapped_column(Integer, nullable=False)
    ledger_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    coverage_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    coverage_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    shared_usage_known: Mapped[bool] = mapped_column(Boolean, nullable=False)
    payload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


LEAD_TABLES = (
    LeadPrivatePayload.__table__, LeadCaseState.__table__, LeadObservation.__table__,
    LeadReview.__table__, LeadReviewEvidence.__table__, LeadPreparation.__table__,
    LeadPreparationRevision.__table__, LeadPreparationEvidence.__table__,
    LeadPreparationContentReview.__table__, LeadActionIntent.__table__,
    PilotBudgetPolicy.__table__, PilotCostEvent.__table__,
    PilotCreditObservation.__table__, PilotReconciliation.__table__,
)

# The repository's generic FK convention uses only the first local column.
# Every composite tenant FK begins with workspace_id, so use stable distinct
# names for this module and index its actual lookup paths.
for _table in LEAD_TABLES:
    for _foreign_key in _table.foreign_key_constraints:
        _identity = "|".join(
            f"{element.parent.name}:{element.target_fullname}" for element in _foreign_key.elements
        )
        _suffix = sha256(_identity.encode()).hexdigest()[:10]
        _foreign_key.name = f"fk_{_table.name[:34]}_{_suffix}"
        _columns = list(_foreign_key.column_keys)
        _covered = any(
            [column.name for column in index.columns][:len(_columns)] == _columns
            for index in _table.indexes
        )
        if not _covered:
            Index(f"ix_{_table.name[:34]}_{_suffix}", *[_table.c[name] for name in _columns])
