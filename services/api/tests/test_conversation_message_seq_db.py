"""Collision-proof per-thread message sequence allocation (PostgreSQL only).

Regression for the latent pre-0066 shape: a message already pending in the
current tenant transaction is invisible to a bare ``MAX(seq)`` query, so an
append could reuse ``seq=1`` and violate
``uq_conversation_thread_messages_workspace_id_thread_id_seq``. The shared
allocator must flush the pending row (the database trigger assigns its seq)
before computing the next value.

This suite is CI-only here: the local sandbox cannot run PostgreSQL (docker
named pipe denied, pytest tempdirs read-only).
"""
import uuid

import psycopg
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import runtime_role_dsn
from tests.test_buyer_review_db import WORKSPACE_A, PROJECT_A


def test_pending_message_gets_a_distinct_sequence_before_append(isolated_seeded):
    from buyeros_api.db.conversation_threads import ConversationThreadMessage as Message
    from buyeros_api.db.session import tenant_session
    from buyeros_api.execution.engine import async_database_url, run_async
    from buyeros_api.services.conversation_messages import next_message_seq

    user, thread = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(isolated_seeded, autocommit=True) as db:
        db.execute("INSERT INTO users(id,issuer,subject) VALUES(%s,'seq-fixture',%s)",
            (user, str(user)))
        db.execute("INSERT INTO conversation_threads(id,workspace_id,project_id,"
            "owner_user_id,template_id,title) VALUES(%s,%s,%s,%s,'custom','seq fixture')",
            (thread, WORKSPACE_A, PROJECT_A, user))

    async def scenario():
        engine = create_async_engine(async_database_url(runtime_role_dsn(isolated_seeded)))
        try:
            async with tenant_session(engine, WORKSPACE_A) as session:
                # Exact failing shape: one message from this transaction's batch is
                # still pending when the append allocates the next sequence.
                session.add(Message(workspace_id=WORKSPACE_A, project_id=PROJECT_A,
                    thread_id=thread, owner_user_id=user, author_user_id=user,
                    text='pending fixture', seq=None))
                allocated = await next_message_seq(session, WORKSPACE_A, thread)
                assert allocated == 2, 'pending row must be flushed and visible'
                session.add(Message(workspace_id=WORKSPACE_A, project_id=PROJECT_A,
                    thread_id=thread, owner_user_id=user, author_user_id=user,
                    text='appended', seq=allocated))
            async with tenant_session(engine, WORKSPACE_A) as session:
                rows = (await session.execute(select(Message.seq, Message.text).where(
                    Message.workspace_id == WORKSPACE_A,
                    Message.thread_id == thread).order_by(Message.seq))).all()
                assert [(seq, text) for seq, text in rows] == [
                    (1, 'pending fixture'), (2, 'appended')]
        finally:
            await engine.dispose()

    run_async(scenario())
