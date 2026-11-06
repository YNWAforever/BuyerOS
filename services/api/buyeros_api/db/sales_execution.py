"""Content-free sales execution authority, claims and usage; outputs have a separate owner."""
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TenantMixin


class SalesReview(TenantMixin, Base):
    __tablename__ = 'sales_reviews'
    __table_args__ = (
        UniqueConstraint('workspace_id','id'),
        ForeignKeyConstraint(['workspace_id','project_id','thread_id','task_id'],
            ['sales_tasks.workspace_id','sales_tasks.project_id','sales_tasks.thread_id','sales_tasks.id'],ondelete='CASCADE'),)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    task_revision: Mapped[int] = mapped_column(Integer,nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64),nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean,nullable=False,default=False)


class SalesExecution(TenantMixin, Base):
    __tablename__ = 'sales_executions'
    __table_args__ = (
        UniqueConstraint('workspace_id','id'), UniqueConstraint('workspace_id','task_id'),
        ForeignKeyConstraint(['workspace_id','project_id','thread_id','task_id'],
            ['sales_tasks.workspace_id','sales_tasks.project_id','sales_tasks.thread_id','sales_tasks.id'],ondelete='CASCADE'),
        ForeignKeyConstraint(['workspace_id','review_id'],['sales_reviews.workspace_id','sales_reviews.id']),)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    review_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    task_revision: Mapped[int] = mapped_column(Integer,nullable=False)
    intake_revision: Mapped[int] = mapped_column(Integer,nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64),nullable=False)
    intake_hash: Mapped[str] = mapped_column(String(64),nullable=False)
    registration_hash: Mapped[str] = mapped_column(String(64),nullable=False)
    reservation_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    proposal: Mapped[dict] = mapped_column(JSONB,nullable=False)
    plan: Mapped[dict] = mapped_column(JSONB,nullable=False)
    market: Mapped[str] = mapped_column(String(32),nullable=False)
    language: Mapped[str] = mapped_column(String(32),nullable=False)
    max_calls: Mapped[int] = mapped_column(Integer,nullable=False)
    max_concurrency: Mapped[int] = mapped_column(Integer,nullable=False)
    calls_started: Mapped[int] = mapped_column(Integer,nullable=False,default=0)
    upper_bound: Mapped[Decimal] = mapped_column(Numeric(20,6),nullable=False)
    consumed_usd: Mapped[Decimal] = mapped_column(Numeric(20,6),nullable=False,default=Decimal(0))
    unused_released: Mapped[bool] = mapped_column(Boolean,nullable=False,default=False)
    accounting_revision: Mapped[int] = mapped_column(Integer,nullable=False,default=0)
    accounted_bound: Mapped[Decimal] = mapped_column(Numeric(20,6),nullable=False,default=Decimal(0))
    settled_usd: Mapped[Decimal] = mapped_column(Numeric(20,6),nullable=False,default=Decimal(0))
    provider_account_hash: Mapped[str | None] = mapped_column(String(64))
    cancelled: Mapped[bool] = mapped_column(Boolean,nullable=False,default=False)


class SalesStep(TenantMixin, Base):
    __tablename__ = 'sales_steps'
    __table_args__ = (
        UniqueConstraint('workspace_id','execution_id','id',name='uq_sales_steps_output_receipt_identity'),
        UniqueConstraint('workspace_id','execution_id','section'),
        ForeignKeyConstraint(['workspace_id','execution_id'],['sales_executions.workspace_id','sales_executions.id'],ondelete='CASCADE'),
        ForeignKeyConstraint(['workspace_id','outbox_id'],['outbox_events.workspace_id','outbox_events.id']),)
    execution_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    outbox_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    section: Mapped[str] = mapped_column(String(240),nullable=False)
    state: Mapped[str] = mapped_column(String(32),nullable=False,default='queued')
    basis_hash: Mapped[str] = mapped_column(String(64),nullable=False)
    projection_hash: Mapped[str] = mapped_column(String(64),nullable=False)
    liability: Mapped[Decimal] = mapped_column(Numeric(20,6),nullable=False)
    definitely_unsubmitted: Mapped[bool] = mapped_column(Boolean,nullable=False,default=False)
    claim_id: Mapped[uuid.UUID | None] = mapped_column(UUID)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    native_operation_id: Mapped[uuid.UUID | None] = mapped_column(UUID)
    usage: Mapped[dict | None] = mapped_column(JSONB)
    result_digest: Mapped[str | None] = mapped_column(String(64))
