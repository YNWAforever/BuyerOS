"""Minimal financial tombstones; no FK cascade from private tasks or outputs."""
from decimal import Decimal
import uuid
from sqlalchemy import Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TenantMixin


class SalesFinancialEvidence(TenantMixin, Base):
    __tablename__ = 'sales_financial_evidence'
    __table_args__ = (UniqueConstraint('workspace_id', 'execution_id', 'step_id'),)
    execution_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)
    step_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    observation: Mapped[dict] = mapped_column(JSONB, nullable=False)


class SalesAccountingReceipt(TenantMixin, Base):
    __tablename__ = 'sales_accounting_receipts'
    __table_args__ = (UniqueConstraint('workspace_id', 'execution_id', 'revision'),)
    execution_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)
    reservation_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    settled_usd: Mapped[Decimal] = mapped_column(Numeric(20,6), nullable=False)
    remaining_hold: Mapped[Decimal] = mapped_column(Numeric(20,6), nullable=False)
    cost_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID)
