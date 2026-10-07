"""Transactional outbox (BO-011).

Business intent and its outbox row commit in the same transaction; the
dispatcher publishes deterministic task IDs to the single Celery/Valkey broker.
Queue acknowledgement is not durable business completion.

Terminal states (``done``/``failed``) end the row's life: the worker writes one
in the same transaction as the work, and the claim query never re-claims them,
so a duplicate broker delivery after completion is a no-op.
"""

from datetime import datetime
import uuid

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
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
    runtime_backend: Mapped[str] = mapped_column(String(16), nullable=False, default="celery")
    runtime_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)



class AsyncJob(Base, TenantMixin):
    """Actor-bound durable bulk command; outbox is its wakeup, not its truth."""
    __tablename__ = "async_jobs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_async_jobs_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_async_jobs_workspace"),
        ForeignKeyConstraint(["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_async_jobs_project"),
        ForeignKeyConstraint(["actor_user_id"], ["users.id"], name="fk_async_jobs_actor"),
        ForeignKeyConstraint(["workspace_id", "manifest_id"], ["bulk_manifests.workspace_id", "bulk_manifests.id"], name="fk_async_jobs_manifest"),
        CheckConstraint("requested BETWEEN 1 AND 1000 OR (manifest_id IS NOT NULL AND requested BETWEEN 1 AND 10000)", name="requested_range"),
        CheckConstraint("processed >= 0 AND processed <= requested", name="processed_range"),
        CheckConstraint("status IN ('queued','running','cancel_requested','cancelled','completed','failed')", name="status"),
    )

    manifest_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="bulk_mutation")
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    command: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    requested: Mapped[int] = mapped_column(Integer, nullable=False)
    processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unchanged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conflicts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AsyncJobItem(Base, TenantMixin):
    """One immutable selected buyer/version and at most one committed result."""
    __tablename__ = "async_job_items"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_async_job_items_workspace_id"),
        UniqueConstraint("workspace_id", "job_id", "buyer_id", name="uq_async_job_items_job_buyer"),
        UniqueConstraint("workspace_id", "job_id", "ordinal", name="uq_async_job_items_job_ordinal"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_async_job_items_workspace"),
        ForeignKeyConstraint(["workspace_id", "job_id"], ["async_jobs.workspace_id", "async_jobs.id"], name="fk_async_job_items_job"),
        CheckConstraint("ordinal >= 0 AND expected_version > 0", name="position_version"),
        CheckConstraint("status IN ('pending','updated','unchanged','blocked','conflict','cancelled')", name="status"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resulting_version: Mapped[int | None] = mapped_column(Integer, nullable=True)


class BulkManifest(Base, TenantMixin):
    """Frozen actor-bound maintenance selection; readiness commits atomically."""
    __tablename__ = "bulk_manifests"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_bulk_manifests_workspace_id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_bulk_manifests_workspace"),
        ForeignKeyConstraint(["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_bulk_manifests_project"),
        ForeignKeyConstraint(["actor_user_id"], ["users.id"], name="fk_bulk_manifests_actor"),
        CheckConstraint("count BETWEEN 0 AND 10000", name="count_range"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint("status IN ('preparing','ready','executed')", name="status"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    specification: Mapped[dict] = mapped_column(JSONB, nullable=False)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    command: Mapped[dict] = mapped_column(JSONB, nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="preparing")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class BulkManifestItem(Base, TenantMixin):
    __tablename__ = "bulk_manifest_items"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_bulk_manifest_items_workspace_id"),
        UniqueConstraint("workspace_id", "manifest_id", "buyer_id", name="uq_bulk_manifest_items_buyer"),
        UniqueConstraint("workspace_id", "manifest_id", "ordinal", name="uq_bulk_manifest_items_ordinal"),
        ForeignKeyConstraint(["workspace_id", "manifest_id"], ["bulk_manifests.workspace_id", "bulk_manifests.id"], name="fk_bulk_manifest_items_manifest"),
        CheckConstraint("ordinal BETWEEN 0 AND 9999 AND expected_version > 0", name="position_version"),
    )
    manifest_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_version: Mapped[int] = mapped_column(Integer, nullable=False)
