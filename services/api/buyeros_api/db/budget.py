"""Budget accounts, reservations and the append-only cost ledger (BO-010).

Money is NUMERIC(20,6)/Decimal. The invariant is
``settled + active_reserved_upper_bounds + proposed <= approved_limit`` and
every applicable account is locked in deterministic ID order.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKeyConstraint, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin

MONEY = Numeric(20, 6)


class BudgetAccount(Base, TenantMixin):
    __tablename__ = "budget_accounts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_budget_accounts_workspace_id"),
        UniqueConstraint("workspace_id", "scope", "currency", "period", name="uq_budget_accounts_scope_period"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_budget_accounts_workspace"),
    )

    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    period: Mapped[str] = mapped_column(String(16), nullable=False)
    approved_limit: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0.000000"))
    settled_spend: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0.000000"))


class BudgetReservation(Base, TenantMixin):
    __tablename__ = "budget_reservations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_budget_reservations_workspace_id"),
        UniqueConstraint("workspace_id", "intent_key", name="uq_budget_reservations_intent"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_budget_reservations_workspace"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    intent_key: Mapped[str] = mapped_column(String(128), nullable=False)
    upper_bound: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    remaining_hold: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class CostEvent(Base, TenantMixin):
    """Append-only; corrections are new reversal events, never edits."""

    __tablename__ = "cost_events"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_cost_events_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_cost_events_workspace"),
    )

    operation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # reserve|commit|release|reconcile|reversal
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    pricing_version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1")
