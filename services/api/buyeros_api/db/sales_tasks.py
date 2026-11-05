"""Task identity and content live under their discussion's deletion boundary."""
import uuid
from sqlalchemy import Boolean, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TenantMixin


class SalesTask(TenantMixin, Base):
    __tablename__ = 'sales_tasks'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'project_id', 'thread_id', 'id'),
        UniqueConstraint('workspace_id', 'actor_id', 'client_message_id'),
        UniqueConstraint('workspace_id', 'thread_id', 'message_sequence'),
        ForeignKeyConstraint(['workspace_id','project_id','thread_id','owner_user_id'],
            ['conversation_threads.workspace_id','conversation_threads.project_id','conversation_threads.id','conversation_threads.owner_user_id'], ondelete='CASCADE'),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    client_message_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)
    intent_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    message_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    skill_id: Mapped[str] = mapped_column(String(240), nullable=False)
    skill_version: Mapped[str] = mapped_column(String(240), nullable=False)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    arguments: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_refs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    intake_history: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default='needs_input')
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    event_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    context_digest: Mapped[str | None] = mapped_column(String(64))
    output_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    pending_review: Mapped[dict | None] = mapped_column(JSONB)


class SalesTaskEvent(TenantMixin, Base):
    __tablename__ = 'sales_task_events'
    __table_args__ = (
        UniqueConstraint('workspace_id','task_id','sequence'),
        ForeignKeyConstraint(['workspace_id','project_id','thread_id','task_id'],
            ['sales_tasks.workspace_id','sales_tasks.project_id','sales_tasks.thread_id','sales_tasks.id'], ondelete='CASCADE'),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


class SalesTaskDependency(TenantMixin, Base):
    __tablename__ = 'sales_task_dependencies'
    __table_args__ = (
        UniqueConstraint('workspace_id','task_id','source_id','kind','source_version'),
        ForeignKeyConstraint(['workspace_id','project_id','thread_id','task_id'],
            ['sales_tasks.workspace_id','sales_tasks.project_id','sales_tasks.thread_id','sales_tasks.id'], ondelete='CASCADE'),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)
    source_version: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    retention_class: Mapped[str] = mapped_column(String(16), nullable=False)


class ConversationThreadPreference(TenantMixin, Base):
    __tablename__ = 'conversation_thread_preferences'
    __table_args__ = (
        UniqueConstraint('workspace_id','thread_id','actor_id'),
        ForeignKeyConstraint(['workspace_id','project_id','thread_id','owner_user_id'],
            ['conversation_threads.workspace_id','conversation_threads.project_id','conversation_threads.id','conversation_threads.owner_user_id'], ondelete='CASCADE'),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
