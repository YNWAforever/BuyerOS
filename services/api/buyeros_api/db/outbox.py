"""Transactional outbox (BO-011).

Business intent and its outbox row commit in the same transaction; the
dispatcher publishes deterministic task IDs to the single Celery/Valkey broker.
Queue acknowledgement is not durable business completion.

Terminal states (``done``/``failed``) end the row's life: the worker writes one
in the same transaction as the work, and the claim query never re-claims them,
so a duplicate broker delivery after completion is a no-op.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin

READY_STATE = "ready"
DISPATCHED_STATE = "dispatched"
OUTBOX_STATES = (READY_STATE, DISPATCHED_STATE, "done", "failed")
TERMINAL_STATES = frozenset({"done", "failed"})


class OutboxEvent(Base, TenantMixin):
    __tablename__ = "outbox_events"
    __table_args__ = (
        CheckConstraint("state IN ('ready', 'dispatched', 'done', 'failed')", name="state"),
        UniqueConstraint("workspace_id", "id", name="uq_outbox_events_workspace_id"),
        UniqueConstraint("workspace_id", "intent_key", "event_type", name="uq_outbox_events_intent_type"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_outbox_events_workspace"),
    )

    intent_key: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default=READY_STATE)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fencing_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
