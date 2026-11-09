"""Durable, derived turn events (SSE replay source).

Events are derived data: pruning them never changes ``conversation_turns.parts``
or the turn status. Append happens in the same transaction as the state change
the event describes, so the terminal ``turn.final`` event and the persisted
``turn.status`` cannot disagree.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDPk

EVENT_KINDS = ('turn.started', 'part', 'tool', 'proposal', 'notice', 'turn.final')


class ConversationTurnEvent(UUIDPk, Base):
    __tablename__ = 'conversation_turn_events'
    __table_args__ = (
        UniqueConstraint('turn_id', 'seq'),
        Index('ix_conversation_turn_events_turn', 'workspace_id', 'turn_id', 'seq'),
        ForeignKeyConstraint(['workspace_id', 'project_id', 'thread_id', 'turn_id'],
            ['conversation_turns.workspace_id', 'conversation_turns.project_id',
             'conversation_turns.thread_id', 'conversation_turns.id'], ondelete='CASCADE'),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    turn_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # Per-turn monotonic sequence, allocated by the shared flushing allocator.
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
        server_default=func.now(), nullable=False)
