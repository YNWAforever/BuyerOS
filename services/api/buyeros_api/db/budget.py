"""Tenant-scoped budget accounts, one hold per operation, and append-only costs."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin

MONEY = Numeric(20, 6)


class BudgetAccount(Base, TenantMixin):
    __tablename__ = "budget_accounts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_budget_accounts_workspace_id"),
        UniqueConstraint("workspace_id", "scope", "scope_id", "category", "currency", "period_start",
                         name="uq_budget_accounts_scope_identity_period"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_budget_accounts_workspace"),
    )
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="all")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    period: Mapped[str] = mapped_column(String(16), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved_limit: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0.000000"))
    settled_spend: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0.000000"))


class BudgetReservation(Base, TenantMixin):
    __tablename__ = "budget_reservations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_budget_reservations_workspace_id"),
        UniqueConstraint("workspace_id", "intent_key", name="uq_budget_reservations_intent"),
        UniqueConstraint("workspace_id", "operation_id", name="uq_budget_reservations_operation"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_budget_reservations_workspace"),
        ForeignKeyConstraint(["workspace_id", "account_id"],
                             ["budget_accounts.workspace_id", "budget_accounts.id"],
                             name="fk_budget_reservations_account"),
    )
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    operation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    intent_key: Mapped[str] = mapped_column(String(128), nullable=False)
    price_version: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    origin_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    upper_bound: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    remaining_hold: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class BudgetReservationAllocation(Base, TenantMixin):
    __tablename__ = "budget_reservation_allocations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_budget_reservation_allocations_workspace_id"),
        UniqueConstraint("workspace_id", "reservation_id", "account_id", name="uq_budget_allocations_pair"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_budget_allocations_workspace"),
        ForeignKeyConstraint(["workspace_id", "reservation_id"],
                             ["budget_reservations.workspace_id", "budget_reservations.id"],
                             name="fk_budget_allocations_reservation"),
        ForeignKeyConstraint(["workspace_id", "account_id"],
                             ["budget_accounts.workspace_id", "budget_accounts.id"],
                             name="fk_budget_allocations_account"),
    )
    reservation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class CostEvent(Base, TenantMixin):
    """One economic event; allocations project its effect without cloning it."""
    __tablename__ = "cost_events"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_cost_events_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_cost_events_workspace"),
    )
    operation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    external_event_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    pricing_version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1")
