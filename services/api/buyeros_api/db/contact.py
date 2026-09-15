"""Contact quote/job/provider-operation state (BO-017..BO-020).

A quote is immutable and holds no money; confirmation atomically reserves and
creates a job. Provider operations persist intent before any network call and
retain an unknown-result hold until authoritative reconciliation.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin
from .budget import MONEY


class EnrichmentQuote(Base, TenantMixin):
    __tablename__ = "enrichment_quotes"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_enrichment_quotes_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_enrichment_quotes_workspace"),
    )

    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    selection: Mapped[dict] = mapped_column(JSONB, nullable=False)
    request_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    quote_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    price_version: Mapped[str] = mapped_column(String(64), nullable=False)
    max_cost: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="quoted")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    consumed_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class EnrichmentJob(Base, TenantMixin):
    __tablename__ = "enrichment_jobs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_enrichment_jobs_workspace_id"),
        UniqueConstraint("workspace_id", "quote_id", name="uq_enrichment_jobs_quote"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_enrichment_jobs_workspace"),
    )

    quote_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="reserved")
    cancel_requested: Mapped[bool] = mapped_column(nullable=False, default=False)


class ProviderOperation(Base, TenantMixin):
    __tablename__ = "provider_operations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_provider_operations_workspace_id"),
        UniqueConstraint("workspace_id", "intent_key", name="uq_provider_operations_intent"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_provider_operations_workspace"),
    )

    intent_key: Mapped[str] = mapped_column(String(128), nullable=False)
    capability: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="intent")
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(nullable=False, default=False)


class ProviderEvent(Base, TenantMixin):
    __tablename__ = "provider_events"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_provider_events_workspace_id"),
        UniqueConstraint("provider", "account_reference", "event_id", name="uq_provider_events_identity"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_provider_events_workspace"),
    )

    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    account_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    digest: Mapped[str] = mapped_column(String(80), nullable=False)
    operation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    processing_state: Mapped[str] = mapped_column(String(32), nullable=False, default="received")


class IdempotencyRecord(Base, TenantMixin):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_idempotency_records_workspace_id"),
        UniqueConstraint("workspace_id", "actor_id", "operation_id", "key", name="uq_idempotency_records_scope"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_idempotency_records_workspace"),
    )

    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    operation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="in_progress")
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
