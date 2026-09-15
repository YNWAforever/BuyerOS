"""Transactional outbox (BO-011).

Business intent and its outbox row commit in the same transaction; the
dispatcher publishes deterministic task IDs to the single Celery/Valkey broker.
Queue acknowledgement is not durable business completion.
"""

from sqlalchemy import ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin


class OutboxEvent(Base, TenantMixin):
    __tablename__ = "outbox_events"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_outbox_events_workspace_id"),
        UniqueConstraint("workspace_id", "intent_key", "event_type", name="uq_outbox_events_intent_type"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_outbox_events_workspace"),
    )

    intent_key: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="ready")
