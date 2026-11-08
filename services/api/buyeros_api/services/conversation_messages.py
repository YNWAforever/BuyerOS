"""Collision-proof per-thread message sequence allocation.

Callers must hold the discussion row lock (``load(..., lock=True)``) so
concurrent appends serialize. This helper additionally flushes pending rows
first: the tenant session may already hold a message inserted earlier in the
same transaction (fixture seed, import, or a batched write), which a bare
``MAX(seq)`` query cannot see. Flushing makes the database trigger assign the
pending row's sequence before the next value is computed.
"""
from sqlalchemy import func, select

from ..db.conversation_threads import ConversationThreadMessage as Message


async def next_message_seq(session, workspace_id, thread_id) -> int:
    await session.flush()
    return (await session.execute(select(func.coalesce(func.max(Message.seq), 0)).where(
        Message.workspace_id == workspace_id,
        Message.thread_id == thread_id))).scalar_one() + 1
