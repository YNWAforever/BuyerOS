"""Effective turn reconciliations keyed by persisted-evidence digest."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDPk


class ConversationTurnReconciliation(UUIDPk, Base):
    __tablename__ = 'conversation_turn_reconciliations'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'source_turn_id', 'evidence_digest',
            name='uq_conversation_turn_reconciliations_evidence'),
        UniqueConstraint('workspace_id', 'source_turn_id', 'evidence_seq',
            name='uq_conversation_turn_reconciliations_seq'),
        Index('ix_conversation_turn_reconciliations_source', 'workspace_id',
            'source_turn_id', 'evidence_seq'),
        ForeignKeyConstraint(['workspace_id', 'project_id', 'thread_id', 'source_turn_id'],
            ['conversation_turns.workspace_id', 'conversation_turns.project_id',
             'conversation_turns.thread_id', 'conversation_turns.id'], ondelete='CASCADE',
            name='fk_conversation_turn_reconciliations_source'),
        ForeignKeyConstraint(['workspace_id', 'project_id', 'thread_id', 'continuation_turn_id'],
            ['conversation_turns.workspace_id', 'conversation_turns.project_id',
             'conversation_turns.thread_id', 'conversation_turns.id'], ondelete='CASCADE',
            name='fk_conversation_turn_reconciliations_continuation'),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_turn_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    evidence_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    continuation_turn_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
        server_default=func.now(), nullable=False)
