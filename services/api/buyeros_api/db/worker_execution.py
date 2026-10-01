"""Operational selector and tenant step receipts; no financial authority."""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TenantMixin


class WorkerRuntimeControl(Base):
    __tablename__ = "worker_runtime_control"
    singleton: Mapped[int] = mapped_column(Integer, primary_key=True)
    backend: Mapped[str] = mapped_column(String(16), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cursor: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    active_owner: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    active_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkerStep(Base, TenantMixin):
    __tablename__ = "worker_steps"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "outbox_id", "generation", "step_key"),
        ForeignKeyConstraint(["workspace_id", "outbox_id"], ["outbox_events.workspace_id", "outbox_events.id"]),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
    )
    outbox_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    runtime_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)
    owner: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    outcome: Mapped[dict | None] = mapped_column(JSONB)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class WorkerBridgeNonce(Base):
    __tablename__ = "worker_bridge_nonces"
    key_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    nonce: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
