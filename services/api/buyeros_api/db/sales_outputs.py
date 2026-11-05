"""Authored immutable revisions, distinct from authoritative native records."""
import uuid
from sqlalchemy import Integer, String, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TenantMixin


class SalesOutput(TenantMixin, Base):
    __tablename__ = 'sales_outputs'
    __table_args__ = (UniqueConstraint('workspace_id','id'),
        UniqueConstraint('workspace_id','task_id'),
        ForeignKeyConstraint(['workspace_id','project_id','thread_id','task_id'],
            ['sales_tasks.workspace_id','sales_tasks.project_id','sales_tasks.thread_id','sales_tasks.id'],ondelete='CASCADE'))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    revision: Mapped[int] = mapped_column(Integer,nullable=False)


class SalesOutputVersion(TenantMixin, Base):
    __tablename__ = 'sales_output_versions'
    __table_args__ = (UniqueConstraint('workspace_id','output_id','revision'),
        ForeignKeyConstraint(['workspace_id','output_id'],['sales_outputs.workspace_id','sales_outputs.id'],ondelete='CASCADE'))
    output_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    revision: Mapped[int] = mapped_column(Integer,nullable=False)
    visibility: Mapped[str] = mapped_column(String(16),nullable=False)
    candidate: Mapped[dict] = mapped_column(JSONB,nullable=False)
    source_refs: Mapped[list] = mapped_column(JSONB,nullable=False)
    context_digest: Mapped[str] = mapped_column(String(64),nullable=False)
    intake_revision: Mapped[int] = mapped_column(Integer,nullable=False)


class SalesOutputSection(TenantMixin, Base):
    __tablename__ = 'sales_output_sections'
    __table_args__ = (UniqueConstraint('workspace_id','step_id'),
        UniqueConstraint('workspace_id','execution_id','section'),
        ForeignKeyConstraint(['workspace_id','execution_id','step_id'],
            ['sales_steps.workspace_id','sales_steps.execution_id','sales_steps.id'],ondelete='CASCADE'),
        ForeignKeyConstraint(['workspace_id','execution_id'],['sales_executions.workspace_id','sales_executions.id'],ondelete='CASCADE'))
    execution_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    step_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    claim_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    section: Mapped[str] = mapped_column(String(240),nullable=False)
    basis_hash: Mapped[str] = mapped_column(String(64),nullable=False)
    projection_hash: Mapped[str] = mapped_column(String(64),nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64),nullable=False)
    candidate: Mapped[dict] = mapped_column(JSONB,nullable=False)


class SalesOutputDependency(TenantMixin, Base):
    __tablename__ = 'sales_output_dependencies'
    __table_args__ = (UniqueConstraint('workspace_id','output_id','revision','kind','source_id','source_revision'),
        ForeignKeyConstraint(['workspace_id','output_id','revision'],
            ['sales_output_versions.workspace_id','sales_output_versions.output_id','sales_output_versions.revision'],ondelete='CASCADE'))
    output_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    revision: Mapped[int] = mapped_column(Integer,nullable=False)
    kind: Mapped[str] = mapped_column(String(32),nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    source_revision: Mapped[int] = mapped_column(Integer,nullable=False)


class SalesOutputNativeLink(TenantMixin, Base):
    __tablename__ = 'sales_output_native_links'
    __table_args__ = (UniqueConstraint('workspace_id','output_id','revision','surface','native_id'),
        ForeignKeyConstraint(['workspace_id','output_id','revision'],
            ['sales_output_versions.workspace_id','sales_output_versions.output_id','sales_output_versions.revision'],ondelete='CASCADE'))
    output_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    revision: Mapped[int] = mapped_column(Integer,nullable=False)
    surface: Mapped[str] = mapped_column(String(16),nullable=False)
    native_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    native_revision: Mapped[int] = mapped_column(Integer,nullable=False)
