"""Connections/credits installed by0062, staged dispatch by0063; metadata is not readiness.

Only opaque secret references, never OAuth tokens or provider response bodies.
One account connection may be explicitly assigned to several projects.
"""
import uuid
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TenantMixin


class XverumConnection(TenantMixin, Base):
    __tablename__ = 'xverum_connections'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'id'),
        ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        ForeignKeyConstraint(['workspace_id','account_ref'], ['xverum_credit_accounts.workspace_id','xverum_credit_accounts.account_ref'], name='fk_xverum_connection_account'),
        CheckConstraint('generation >= 1 AND version >= 1', name='positive_versions'),
        CheckConstraint("status IN ('configuration_required','connected','expired','disconnected')", name='status'),
    )
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    account_ref: Mapped[str] = mapped_column(String(240), nullable=False)
    tariff_version: Mapped[str] = mapped_column(String(240), nullable=False)
    secret_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='configuration_required')
    configured_by: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)


class XverumProjectAssignment(TenantMixin, Base):
    __tablename__ = 'xverum_project_assignments'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'id'),
        UniqueConstraint('workspace_id', 'project_id'),
        ForeignKeyConstraint(['workspace_id','connection_id'], ['xverum_connections.workspace_id','xverum_connections.id'], name='fk_xverum_assignment_connection'),
        ForeignKeyConstraint(['workspace_id','project_id'], ['projects.workspace_id','projects.id'], name='fk_xverum_assignment_project'),
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, Numeric
from sqlalchemy.dialects.postgresql import JSONB


class XverumCreditAccount(TenantMixin, Base):
    __tablename__ = 'xverum_credit_accounts'
    __table_args__ = (UniqueConstraint('workspace_id','id'),UniqueConstraint('workspace_id','account_ref'),
        ForeignKeyConstraint(['workspace_id'],['workspaces.id']),CheckConstraint('credit_limit>=0',name='credit_limit'))
    account_ref: Mapped[str] = mapped_column(String(240))
    credit_limit: Mapped[int] = mapped_column(Integer)


class XverumCreditLimit(TenantMixin, Base):
    __tablename__ = 'xverum_credit_limits'
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    credit_limit: Mapped[int] = mapped_column(Integer)


class XverumTariff(TenantMixin, Base):
    __tablename__ = 'xverum_tariffs'
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    version: Mapped[str] = mapped_column(String(240))
    usd_per_credit: Mapped[Decimal] = mapped_column(Numeric(20,6))


class XverumQuoteRow(TenantMixin, Base):
    __tablename__ = 'xverum_quotes'
    source_receipt_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source_digest: Mapped[str | None] = mapped_column(String(64))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    buyer_version: Mapped[int] = mapped_column(Integer)
    connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    connection_generation: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    tariff_version: Mapped[str] = mapped_column(String(240))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fingerprint: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB)


class XverumCreditReservation(TenantMixin, Base):
    __tablename__ = 'xverum_credit_reservations'
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    quote_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    operation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    max_credits: Mapped[int] = mapped_column(Integer)
    held_credits: Mapped[int] = mapped_column(Integer)
    usd_reservation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))


class XverumReceiptRow(TenantMixin, Base):
    __tablename__ = 'xverum_receipts'
    version: Mapped[int] = mapped_column(Integer,default=1)
    outbox_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    claim_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    reservation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    operation_key: Mapped[str] = mapped_column(String(200))
    dispatch_state: Mapped[str] = mapped_column(String(32))
    request_id: Mapped[str | None] = mapped_column(String(240))
    projection_digest: Mapped[str | None] = mapped_column(String(64))
    returned_ids: Mapped[list] = mapped_column(JSONB,default=list)


class XverumCreditSettlement(TenantMixin, Base):
    __tablename__ = 'xverum_credit_settlements'
    receipt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    credits_used: Mapped[int] = mapped_column(Integer)


class XverumStage(TenantMixin, Base):
    """One immutable stage authority; id equals the admitted Task8 receipt id."""
    __tablename__ = 'xverum_stages'
    project_id: Mapped[uuid.UUID] = mapped_column(UUID)
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID)
    task_revision: Mapped[int | None] = mapped_column(Integer)
    thread_id: Mapped[uuid.UUID | None] = mapped_column(UUID)
    context_digest: Mapped[str | None] = mapped_column(String(64))
    intake_hash: Mapped[str | None] = mapped_column(String(64))
    binding: Mapped[dict] = mapped_column(JSONB)
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)


class XverumToolReceipt(TenantMixin, Base):
    __tablename__ = 'xverum_tool_receipts'
    stage_id: Mapped[uuid.UUID] = mapped_column(UUID)
    ordinal: Mapped[int] = mapped_column(Integer)
    tool: Mapped[str] = mapped_column(String(64))
    arguments: Mapped[dict] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(24), default='queued')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    claim_id: Mapped[uuid.UUID | None] = mapped_column(UUID)
    request_id: Mapped[str | None] = mapped_column(String(128))
    credits_used: Mapped[int | None] = mapped_column(Integer)
    projection: Mapped[dict | None] = mapped_column(JSONB)
    projection_digest: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class XverumReconciliation(TenantMixin, Base):
    __tablename__ = 'xverum_reconciliations'
    receipt_id: Mapped[uuid.UUID] = mapped_column(UUID)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID)
    evidence_ref: Mapped[uuid.UUID] = mapped_column(UUID)
    fingerprint: Mapped[str] = mapped_column(String(64))
    expected_version: Mapped[int] = mapped_column(Integer)
    resolution: Mapped[str] = mapped_column(String(24))
