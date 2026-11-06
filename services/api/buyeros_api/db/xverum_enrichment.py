"""Durable reviewed provider producer and exact native mutation proof."""
import uuid
from sqlalchemy import Integer, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TenantMixin


class XverumEnrichment(Base, TenantMixin):
    __tablename__ = 'xverum_enrichments'
    __table_args__ = (UniqueConstraint('workspace_id','id'),
        ForeignKeyConstraint(['workspace_id','project_id','buyer_id'],
            ['project_buyers.workspace_id','project_buyers.project_id','project_buyers.id']),
        ForeignKeyConstraint(['workspace_id','project_id','thread_id','task_id'],
            ['sales_tasks.workspace_id','sales_tasks.project_id','sales_tasks.thread_id','sales_tasks.id']))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID,nullable=False)
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID,nullable=True)
    thread_id: Mapped[uuid.UUID | None] = mapped_column(UUID,nullable=True)
    proposal: Mapped[dict] = mapped_column(JSONB,nullable=False)
    proof: Mapped[dict] = mapped_column(JSONB,nullable=False)
    applied: Mapped[dict | None] = mapped_column(JSONB,nullable=True)
    output_revision: Mapped[int | None] = mapped_column(Integer,nullable=True)
