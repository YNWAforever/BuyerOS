"""Durable conversation turns, inline proposals and their explicit decisions.

Every row is tenant-scoped under its discussion's deletion boundary. Turn
identity is independent of idempotency-receipt expiry: ``client_message_id`` is
unique per thread and per actor so a duplicate submission cannot execute twice.
"""
import uuid
from sqlalchemy import (Boolean, ForeignKey, ForeignKeyConstraint, Index, Integer,
    String, Text, UniqueConstraint, text)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TenantMixin


class ConversationTurn(TenantMixin, Base):
    __tablename__ = 'conversation_turns'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'id'),
        UniqueConstraint('workspace_id', 'project_id', 'thread_id', 'id'),
        UniqueConstraint('workspace_id', 'thread_id', 'client_message_id'),
        Index('uq_conversation_turns_actor_client', 'workspace_id', 'actor_id', 'client_message_id',
            unique=True, postgresql_where=text('client_message_id IS NOT NULL')),
        ForeignKeyConstraint(['workspace_id', 'project_id', 'thread_id', 'owner_user_id'],
            ['conversation_threads.workspace_id', 'conversation_threads.project_id',
             'conversation_threads.id', 'conversation_threads.owner_user_id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['workspace_id', 'project_id', 'thread_id', 'parent_turn_id'],
            ['conversation_turns.workspace_id', 'conversation_turns.project_id',
             'conversation_turns.thread_id', 'conversation_turns.id'], ondelete='CASCADE'),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    # NULL only for continuation turns created by an explicit decision.
    client_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_turn_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    skill_id: Mapped[str | None] = mapped_column(String(240))
    skill_version: Mapped[str | None] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='needs_input')
    step_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expected_thread_version: Mapped[int | None] = mapped_column(Integer)
    parts: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    notices: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)


class ConversationTurnProposal(TenantMixin, Base):
    __tablename__ = 'conversation_turn_proposals'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'id'),
        UniqueConstraint('workspace_id', 'project_id', 'thread_id', 'turn_id', 'id'),
        ForeignKeyConstraint(['workspace_id', 'project_id', 'thread_id', 'turn_id'],
            ['conversation_turns.workspace_id', 'conversation_turns.project_id',
             'conversation_turns.thread_id', 'conversation_turns.id'], ondelete='CASCADE'),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    turn_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    capability: Mapped[str] = mapped_column(String(64), nullable=False)
    skill_id: Mapped[str] = mapped_column(String(240), nullable=False)
    skill_version: Mapped[str] = mapped_column(String(240), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    rationale: Mapped[str] = mapped_column(String(1000), nullable=False)
    # Trusted server-built typed arguments and exact source refs; never client input.
    arguments: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_refs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Preview only: no tenant identity, permissions, approvals or budget.
    arguments_preview: Mapped[dict] = mapped_column(JSONB, nullable=False)
    cost: Mapped[dict | None] = mapped_column(JSONB)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='proposed')
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    result: Mapped[dict | None] = mapped_column(JSONB)


class ConversationTurnDecision(TenantMixin, Base):
    __tablename__ = 'conversation_turn_decisions'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'id'),
        # Exactly one effective decision per inline proposal.
        UniqueConstraint('workspace_id', 'proposal_id'),
        UniqueConstraint('workspace_id', 'project_id', 'thread_id', 'id'),
        ForeignKeyConstraint(['workspace_id', 'proposal_id'],
            ['conversation_turn_proposals.workspace_id', 'conversation_turn_proposals.id'],
            ondelete='CASCADE'),
        ForeignKeyConstraint(['workspace_id', 'project_id', 'thread_id', 'turn_id'],
            ['conversation_turns.workspace_id', 'conversation_turns.project_id',
             'conversation_turns.thread_id', 'conversation_turns.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['workspace_id', 'project_id', 'thread_id', 'continuation_turn_id'],
            ['conversation_turns.workspace_id', 'conversation_turns.project_id',
             'conversation_turns.thread_id', 'conversation_turns.id'], ondelete='CASCADE'),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    turn_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    decision: Mapped[str] = mapped_column(String(8), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    continuation_turn_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='applied')
