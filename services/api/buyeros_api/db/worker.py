"""Durable worker leases and fencing generations (P8).

Leases are the database-side half of the dispatcher/worker handshake: the
dispatcher claims an outbox intent by writing a lease row, and the worker must
present the matching fencing generation before its writes are accepted.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin


class WorkerLease(Base, TenantMixin):
    __tablename__ = "worker_leases"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_worker_leases_workspace_id"),
        UniqueConstraint("workspace_id", "intent_key", name="uq_worker_leases_intent"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_worker_leases_workspace"),
    )

    intent_key: Mapped[str] = mapped_column(String(128), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fencing_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="free")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
