"""Workspace discussions: user notes and code-owned references only."""
import uuid
from sqlalchemy import ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TenantMixin


class ConversationThread(TenantMixin, Base):
    __tablename__ = 'conversation_threads'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'id'),
        UniqueConstraint('workspace_id', 'project_id', 'id', 'owner_user_id'),
        ForeignKeyConstraint(['workspace_id', 'project_id'], ['projects.workspace_id', 'projects.id']),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    template_id: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sources: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    runs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)


class ConversationThreadMessage(TenantMixin, Base):
    __tablename__ = 'conversation_thread_messages'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'id'),
        ForeignKeyConstraint(['workspace_id', 'project_id', 'thread_id', 'owner_user_id'],
            ['conversation_threads.workspace_id', 'conversation_threads.project_id', 'conversation_threads.id', 'conversation_threads.owner_user_id'], ondelete='CASCADE'),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    author_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)


class ConversationThreadShare(TenantMixin, Base):
    __tablename__ = 'conversation_thread_shares'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'id'),
        UniqueConstraint('workspace_id', 'thread_id', 'grantee_user_id'),
        ForeignKeyConstraint(['workspace_id', 'project_id', 'thread_id', 'owner_user_id'],
            ['conversation_threads.workspace_id', 'conversation_threads.project_id', 'conversation_threads.id', 'conversation_threads.owner_user_id'], ondelete='CASCADE'),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    grantee_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    granted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    role: Mapped[str] = mapped_column(String(6), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
