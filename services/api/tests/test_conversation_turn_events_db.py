"""PostgreSQL: turn event store contract, RLS/grants, allocator and atomicity.

CI-only here (no local PostgreSQL). Fixture/deterministic data only.
"""
import uuid
from datetime import datetime, timezone

import psycopg
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import runtime_role_dsn
from tests.test_buyer_review_db import WORKSPACE_A, PROJECT_A

HEAD = '0072_turn_event_boundaries'


def _user(db, issuer='turn-event-fixture'):
    user = uuid.uuid4()
    db.execute("INSERT INTO users(id,issuer,subject) VALUES(%s,%s,%s)",
        (user, issuer, str(user)))
    return user


def _thread(db, user):
    thread = uuid.uuid4()
    db.execute("INSERT INTO conversation_threads(id,workspace_id,project_id,owner_user_id,"
        "template_id,title) VALUES(%s,%s,%s,%s,'custom','event fixture')",
        (thread, WORKSPACE_A, PROJECT_A, user))
    return thread


def _turn(db, user, thread, status='needs_input'):
    turn = uuid.uuid4()
    db.execute("INSERT INTO conversation_turns(id,workspace_id,project_id,thread_id,"
        "owner_user_id,actor_id,request_fingerprint,language,status,step_count,parts,notices) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,'en',%s,1,'[]','[]')",
        (turn, WORKSPACE_A, PROJECT_A, thread, user, user, 'c' * 64, status))
    return turn


def test_event_store_contract_rls_and_grants(isolated_migrated):
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == HEAD
        assert db.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class '
            "WHERE oid='conversation_turn_events'::regclass").fetchone() == (True, True)
        policy = db.execute("SELECT qual,with_check FROM pg_policies WHERE tablename="
            "'conversation_turn_events' AND policyname='tenant_isolation'").fetchone()
        assert policy and all("NULLIF(current_setting('app.workspace_id'" in value
            for value in policy)
        # Retention (0071) lets the sweeper read a bounded id set and delete
        # exactly those derived rows; the API stays the only event producer.
        for verb, expected in (('SELECT', True), ('INSERT', False),
                               ('UPDATE', False), ('DELETE', True)):
            assert db.execute('SELECT has_table_privilege(%s,%s,%s)',
                ('buyeros_worker', 'conversation_turn_events', verb)).fetchone()[0] is expected
        for verb in ('SELECT', 'INSERT', 'UPDATE', 'DELETE'):
            assert db.execute('SELECT has_table_privilege(%s,%s,%s)',
                ('buyeros_api', 'conversation_turn_events', verb)).fetchone()[0] == (
                    verb in {'SELECT', 'INSERT'})
        assert db.execute("SELECT EXISTS(SELECT 1 FROM pg_constraint WHERE conname="
            "'conversation_turn_events_turn_id_seq_key')").fetchone()[0] is True
        assert db.execute("SELECT public.buyeros_turn_event_valid('turn.final', "
            "jsonb_build_object('status','completed'))").fetchone()[0] is True
        assert db.execute("SELECT public.buyeros_turn_event_valid('turn.final', "
            "jsonb_build_object('status','running'))").fetchone()[0] is False
        # 0072: optional application-observed boundaries; old events stay valid.
        assert db.execute("SELECT public.buyeros_turn_event_valid('turn.started', "
            "jsonb_build_object('status','running','started_at','2026-11-11T12:00:00Z'))"
            ).fetchone()[0] is True
        assert db.execute("SELECT public.buyeros_turn_event_valid('turn.final', "
            "jsonb_build_object('status','completed',"
            "'finished_at','2026-11-11T12:00:01.250Z'))").fetchone()[0] is True
        assert db.execute("SELECT public.buyeros_turn_event_valid('turn.started', "
            "jsonb_build_object('status','running','started_at','not-an-instant'))"
            ).fetchone()[0] is False
        assert db.execute("SELECT public.buyeros_turn_event_valid('turn.final', "
            "jsonb_build_object('status','completed','finished_at',42))").fetchone()[0] is False
        assert db.execute("SELECT public.buyeros_turn_event_valid('turn.final', "
            "jsonb_build_object('status','completed','unknown_field','x'))"
            ).fetchone()[0] is False


def test_event_validator_rejects_bad_payload_and_unique_seq(isolated_seeded):
    with psycopg.connect(isolated_seeded) as db:
        user = _user(db)
        thread = _thread(db, user)
        turn = _turn(db, user, thread, status='completed')
        db.execute("INSERT INTO conversation_turn_events(id,workspace_id,project_id,thread_id,"
            "turn_id,seq,kind,payload) VALUES(%s,%s,%s,%s,%s,1,'turn.started',"
            "jsonb_build_object('status','running'))",
            (uuid.uuid4(), WORKSPACE_A, PROJECT_A, thread, turn))
        with pytest.raises(psycopg.errors.CheckViolation):
            with db.transaction():
                db.execute("INSERT INTO conversation_turn_events(id,workspace_id,project_id,"
                    "thread_id,turn_id,seq,kind,payload) VALUES(%s,%s,%s,%s,%s,2,"
                    "'turn.final',jsonb_build_object('status','running'))",
                    (uuid.uuid4(), WORKSPACE_A, PROJECT_A, thread, turn))
        with pytest.raises(psycopg.errors.UniqueViolation):
            with db.transaction():
                db.execute("INSERT INTO conversation_turn_events(id,workspace_id,project_id,"
                    "thread_id,turn_id,seq,kind,payload) VALUES(%s,%s,%s,%s,%s,1,"
                    "'turn.final',jsonb_build_object('status','completed'))",
                    (uuid.uuid4(), WORKSPACE_A, PROJECT_A, thread, turn))


def test_event_allocator_flushes_pending_rows(isolated_seeded):
    from buyeros_api.db.conversation_turn_events import ConversationTurnEvent
    from buyeros_api.db.session import tenant_session
    from buyeros_api.execution.engine import async_database_url, run_async
    from buyeros_api.services.conversation_turn_events import next_turn_event_seq

    with psycopg.connect(isolated_seeded) as db:
        user = _user(db, 'turn-event-allocator')
        thread = _thread(db, user)
        turn = _turn(db, user, thread, status='needs_input')

    async def scenario():
        engine = create_async_engine(async_database_url(runtime_role_dsn(isolated_seeded)))
        try:
            async with tenant_session(engine, WORKSPACE_A) as session:
                # One row is pending in this transaction; the allocator must
                # flush it before computing the next sequence.
                session.add(ConversationTurnEvent(workspace_id=WORKSPACE_A,
                    project_id=PROJECT_A, thread_id=thread, turn_id=turn, seq=1,
                    kind='turn.started', payload={'status': 'running'}))
                allocated = await next_turn_event_seq(session, WORKSPACE_A, turn)
                assert allocated == 2
                session.add(ConversationTurnEvent(workspace_id=WORKSPACE_A,
                    project_id=PROJECT_A, thread_id=thread, turn_id=turn, seq=allocated,
                    kind='turn.final', payload={'status': 'needs_input'}))
            async with tenant_session(engine, WORKSPACE_A) as session:
                rows = (await session.execute(select(ConversationTurnEvent.seq,
                    ConversationTurnEvent.kind).where(
                    ConversationTurnEvent.turn_id == turn).order_by(
                    ConversationTurnEvent.seq))).all()
                assert [(seq, kind) for seq, kind in rows] == [(1, 'turn.started'),
                    (2, 'turn.final')]
        finally:
            await engine.dispose()

    run_async(scenario())


def test_terminal_event_and_turn_status_require_one_transaction(isolated_seeded):
    """The terminal event and the turn status must commit (or roll back) together."""
    with psycopg.connect(isolated_seeded) as db:
        user = _user(db, 'turn-event-atomic')
        thread = _thread(db, user)
        turn = _turn(db, user, thread, status='needs_input')
        with pytest.raises(RuntimeError):
            with db.transaction():
                db.execute("UPDATE conversation_turns SET status='failed' WHERE id=%s", (turn,))
                db.execute("INSERT INTO conversation_turn_events(id,workspace_id,project_id,"
                    "thread_id,turn_id,seq,kind,payload) VALUES(%s,%s,%s,%s,%s,1,"
                    "'turn.final','{\"status\":\"failed\"}'::jsonb)",
                    (uuid.uuid4(), WORKSPACE_A, PROJECT_A, thread, turn))
                raise RuntimeError('simulated failure after partial append')
        status = db.execute('SELECT status FROM conversation_turns WHERE id=%s',
            (turn,)).fetchone()[0]
        assert status == 'needs_input'
        assert db.execute('SELECT count(*) FROM conversation_turn_events WHERE turn_id=%s',
            (turn,)).fetchone()[0] == 0
    with psycopg.connect(isolated_seeded) as db:
        with db.transaction():
            db.execute("UPDATE conversation_turns SET status='failed' WHERE id=%s", (turn,))
            db.execute("INSERT INTO conversation_turn_events(id,workspace_id,project_id,"
                "thread_id,turn_id,seq,kind,payload) VALUES(%s,%s,%s,%s,%s,1,"
                "'turn.started','{\"status\":\"running\"}'::jsonb)",
                (uuid.uuid4(), WORKSPACE_A, PROJECT_A, thread, turn))
            db.execute("INSERT INTO conversation_turn_events(id,workspace_id,project_id,"
                "thread_id,turn_id,seq,kind,payload) VALUES(%s,%s,%s,%s,%s,2,"
                "'turn.final','{\"status\":\"failed\"}'::jsonb)",
                (uuid.uuid4(), WORKSPACE_A, PROJECT_A, thread, turn))
        assert db.execute('SELECT status FROM conversation_turns WHERE id=%s',
            (turn,)).fetchone()[0] == 'failed'
        rows = db.execute('SELECT seq,kind,payload FROM conversation_turn_events '
            'WHERE turn_id=%s ORDER BY seq', (turn,)).fetchall()
        assert [(seq, kind) for seq, kind, _ in rows] == [
            (1, 'turn.started'), (2, 'turn.final')]
        assert rows[-1][2] == {'status': 'failed'}


def test_populated_event_downgrade_refuses_and_empty_downgrade_round_trips(isolated_seeded):
    from alembic import command
    from tests.test_conversation_turns_migration_db import config
    with psycopg.connect(isolated_seeded) as db:
        user = _user(db, 'turn-event-downgrade')
        thread = _thread(db, user)
        turn = _turn(db, user, thread, status='completed')
        db.execute("INSERT INTO conversation_turn_events(id,workspace_id,project_id,thread_id,"
            "turn_id,seq,kind,payload) VALUES(%s,%s,%s,%s,%s,1,'turn.final',"
            "'{\"status\":\"completed\"}'::jsonb)",
            (uuid.uuid4(), WORKSPACE_A, PROJECT_A, thread, turn))
    with pytest.raises(RuntimeError, match='preserve conversation turn event evidence'):
        command.downgrade(config(), '0067_conversation_buyer')
    with psycopg.connect(isolated_seeded) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == HEAD
        assert db.execute('SELECT count(*) FROM conversation_turn_events').fetchone()[0] == 1


def test_empty_event_downgrade_round_trips(isolated_migrated):
    from alembic import command
    from tests.test_conversation_turns_migration_db import config
    command.downgrade(config(), '0067_conversation_buyer')
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == '0067_conversation_buyer'
        assert db.execute("SELECT to_regclass('public.conversation_turn_events')").fetchone()[0] is None
    command.upgrade(config(), 'head')
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == HEAD
        assert db.execute("SELECT to_regclass('public.conversation_turn_events')").fetchone()[0] is not None


def test_reconciliation_table_contract_and_connector_privileges(isolated_migrated):
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == HEAD
        assert db.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class '
            "WHERE oid='conversation_turn_reconciliations'::regclass").fetchone() == (True, True)
        for verb in ('SELECT', 'INSERT', 'UPDATE', 'DELETE'):
            assert db.execute('SELECT has_table_privilege(%s,%s,%s)',
                ('buyeros_worker', 'conversation_turn_reconciliations', verb)).fetchone()[0] is False
            assert db.execute('SELECT has_table_privilege(%s,%s,%s)',
                ('buyeros_api', 'conversation_turn_reconciliations', verb)).fetchone()[0] == (
                    verb in {'SELECT', 'INSERT'})
        # The only source-turn mutation the API may perform is the single
        # authoritative transition out of outcome_unknown.
        assert db.execute("SELECT has_column_privilege('buyeros_api','conversation_turns',"
            "'status','UPDATE')").fetchone()[0] is True
        assert db.execute("SELECT count(*) FROM pg_constraint WHERE conname IN ("
            "'uq_conversation_turn_reconciliations_evidence',"
            "'uq_conversation_turn_reconciliations_seq')"
            ).fetchone()[0] == 2


def test_reconciliation_uniqueness_and_populated_downgrade(isolated_seeded):
    from alembic import command
    from tests.test_conversation_turns_migration_db import config
    with psycopg.connect(isolated_seeded) as db:
        user = _user(db, 'turn-reconcile-fixture')
        thread = _thread(db, user)
        source = _turn(db, user, thread, status='outcome_unknown')
        continuation = _turn(db, user, thread, status='failed')
        digest = 'a' * 64
        db.execute("INSERT INTO conversation_turn_reconciliations(id,workspace_id,project_id,"
            "thread_id,source_turn_id,actor_id,evidence_digest,evidence_seq,outcome,code,message,"
            "continuation_turn_id) VALUES(%s,%s,%s,%s,%s,%s,%s,1,'unknown',"
            "'RECONCILE_NO_EVIDENCE','no evidence',%s)",
            (uuid.uuid4(), WORKSPACE_A, PROJECT_A, thread, source, user, digest,
             continuation))
        with pytest.raises(psycopg.errors.UniqueViolation):
            with db.transaction():
                db.execute("INSERT INTO conversation_turn_reconciliations(id,workspace_id,"
                    "project_id,thread_id,source_turn_id,actor_id,evidence_digest,evidence_seq,"
                    "outcome,code,message,continuation_turn_id) VALUES(%s,%s,%s,%s,%s,%s,%s,2,"
                    "'failed','RECONCILED_FAILED','failed',%s)",
                    (uuid.uuid4(), WORKSPACE_A, PROJECT_A, thread, source, user, digest,
                     continuation))
        with pytest.raises(psycopg.errors.UniqueViolation):
            with db.transaction():
                db.execute("INSERT INTO conversation_turn_reconciliations(id,workspace_id,"
                    "project_id,thread_id,source_turn_id,actor_id,evidence_digest,evidence_seq,"
                    "outcome,code,message,continuation_turn_id) VALUES(%s,%s,%s,%s,%s,%s,%s,1,"
                    "'failed','RECONCILED_FAILED','failed',%s)",
                    (uuid.uuid4(), WORKSPACE_A, PROJECT_A, thread, source, user, 'b' * 64,
                     continuation))
    with pytest.raises(RuntimeError, match='preserve turn reconciliation evidence'):
        command.downgrade(config(), '0068_conversation_turn_events')
    with psycopg.connect(isolated_seeded) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == HEAD
        assert db.execute('SELECT count(*) FROM conversation_turn_reconciliations'
            ).fetchone()[0] == 1


def test_event_append_serializes_under_the_thread_row_lock(isolated_seeded):
    """Concurrent writers get distinct seqs because every append path locks the thread.

    The allocator itself only flushes + MAX; safety depends on the caller holding
    the discussion row lock (all production callers do). Two concurrent writers
    that take that lock serialize instead of colliding on UNIQUE(turn_id, seq).
    """
    import asyncio

    from sqlalchemy import select

    from buyeros_api.db.conversation_turn_events import ConversationTurnEvent  # noqa: F401
    from buyeros_api.db.conversation_threads import ConversationThread
    from buyeros_api.db.session import tenant_session
    from buyeros_api.execution.engine import async_database_url, run_async
    from buyeros_api.services.conversation_turn_events import next_turn_event_seq

    with psycopg.connect(isolated_seeded) as db:
        user = _user(db, 'turn-event-concurrent')
        thread = _thread(db, user)
        turn = _turn(db, user, thread, status='needs_input')

    async def scenario():
        engine = create_async_engine(async_database_url(runtime_role_dsn(isolated_seeded)))

        async def writer(code):
            async with tenant_session(engine, WORKSPACE_A) as session:
                await session.execute(select(ConversationThread.id).where(
                    ConversationThread.workspace_id == WORKSPACE_A,
                    ConversationThread.id == thread).with_for_update())
                seq = await next_turn_event_seq(session, WORKSPACE_A, turn)
                session.add(ConversationTurnEvent(workspace_id=WORKSPACE_A,
                    project_id=PROJECT_A, thread_id=thread, turn_id=turn, seq=seq,
                    kind='notice', payload={'code': code, 'message': 'concurrent append'}))
                await session.flush()

        try:
            await asyncio.gather(writer('TURN_EVENT_CONCURRENT_A'),
                writer('TURN_EVENT_CONCURRENT_B'))
            async with tenant_session(engine, WORKSPACE_A) as session:
                rows = (await session.execute(select(ConversationTurnEvent.seq,
                    ConversationTurnEvent.payload).where(
                    ConversationTurnEvent.turn_id == turn).order_by(
                    ConversationTurnEvent.seq))).all()
                assert [seq for seq, _ in rows] == [1, 2]
                assert {payload['code'] for _, payload in rows} == {
                    'TURN_EVENT_CONCURRENT_A', 'TURN_EVENT_CONCURRENT_B'}
        finally:
            await engine.dispose()

    run_async(scenario())
