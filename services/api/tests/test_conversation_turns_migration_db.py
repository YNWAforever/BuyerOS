"""Migration 0066 invariants: head, RLS/grants, app-rollback shape, downgrade.

Runs only on PostgreSQL; skipped when no disposable database is available.
"""
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.conftest import ALEMBIC_INI, SERVICE_ROOT, runtime_role_dsn
from tests.test_buyer_review_db import WORKSPACE_A, PROJECT_A

HEAD = '0067_conversation_buyer'
PREVIOUS = '0065_sales_lifecycle'
NEW_TABLES = ('conversation_turns', 'conversation_turn_proposals',
              'conversation_turn_decisions')


def config():
    value = Config(str(ALEMBIC_INI))
    value.set_main_option('script_location', str(SERVICE_ROOT / 'alembic'))
    return value


def _user(db, issuer='turn-migration-fixture'):
    user = uuid.uuid4()
    db.execute("INSERT INTO users(id,issuer,subject) VALUES(%s,%s,%s)",
        (user, issuer, str(user)))
    return user


def _thread(db, user, title='migration fixture'):
    ident = uuid.uuid4()
    db.execute("INSERT INTO conversation_threads(id,workspace_id,project_id,owner_user_id,"
        "template_id,title) VALUES(%s,%s,%s,%s,'custom',%s)",
        (ident, WORKSPACE_A, PROJECT_A, user, title))
    return ident


def test_new_relations_are_tenant_scoped_and_closed_to_the_worker(isolated_migrated):
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == HEAD
        for table in NEW_TABLES:
            assert db.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',
                (table,)).fetchone() == (True, True)
            for verb in ('SELECT', 'INSERT', 'UPDATE'):
                assert db.execute('SELECT has_table_privilege(%s,%s,%s)',
                    ('buyeros_worker', table, verb)).fetchone()[0] is False
                assert db.execute('SELECT has_table_privilege(%s,%s,%s)',
                    ('buyeros_api', table, verb)).fetchone()[0] == (verb != 'UPDATE')
        assert db.execute("SELECT has_column_privilege('buyeros_api','conversation_turn_proposals',"
            "'status','UPDATE')").fetchone()[0] is True
        assert db.execute("SELECT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname="
            "'conversation_thread_message_seq' AND NOT tgisinternal)").fetchone()[0] is True
        for service in ('search', 'model', 'contact'):
            assert db.execute(f'SELECT public.buyeros_{service}_receipts_writable()').fetchone()[0] is True
        assert db.execute('SELECT public.buyeros_xverum_connections_ready()').fetchone()[0] is True


def test_previous_app_insert_shape_stays_writable_and_gets_a_monotonic_seq(isolated_seeded):
    with psycopg.connect(isolated_seeded) as db:
        user = _user(db, 'thread-rollback-fixture')
        thread = _thread(db, user)
    dsn = runtime_role_dsn(isolated_seeded)
    with psycopg.connect(dsn) as db:
        db.execute("SELECT set_config('app.workspace_id',%s,true)", (WORKSPACE_A,))
        # Exact previous-revision insert: no role, seq, parts or client identity.
        for index, text in enumerate(('legacy one', 'legacy two'), start=1):
            db.execute("INSERT INTO conversation_thread_messages(id,workspace_id,project_id,"
                "thread_id,owner_user_id,author_user_id,text) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (uuid.uuid4(), WORKSPACE_A, PROJECT_A, thread, user, user, text))
            assert db.execute('SELECT seq,role,parts FROM conversation_thread_messages '
                'WHERE text=%s', (text,)).fetchone() == (index, 'user', [])
    with psycopg.connect(isolated_seeded) as db:
        rows = db.execute('SELECT text,seq FROM conversation_thread_messages WHERE thread_id=%s '
            'ORDER BY seq', (thread,)).fetchall()
        assert rows == [('legacy one', 1), ('legacy two', 2)]


def test_upgrade_backfills_seq_in_creation_order_from_the_previous_head(isolated_migrated):
    cfg = config()
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(isolated_migrated) as db:
        user = _user(db)
        thread = _thread(db, user)
        base = datetime.now(timezone.utc)
        for index, text in enumerate(('first', 'second', 'third')):
            db.execute("INSERT INTO conversation_thread_messages(id,workspace_id,project_id,"
                "thread_id,owner_user_id,author_user_id,text,created_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (uuid.uuid4(), WORKSPACE_A, PROJECT_A, thread, user, user, text,
                 base + timedelta(microseconds=index)))
    command.upgrade(cfg, 'head')
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == HEAD
        rows = db.execute('SELECT text,seq,role,parts FROM conversation_thread_messages '
            'WHERE thread_id=%s ORDER BY seq', (thread,)).fetchall()
        assert rows == [('first', 1, 'user', []), ('second', 2, 'user', []),
                        ('third', 3, 'user', [])]


def test_downgrade_is_honest_for_legacy_data_and_refuses_typed_turns(isolated_migrated):
    cfg = config()
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == PREVIOUS
        assert db.execute("SELECT to_regclass('public.conversation_turns')").fetchone()[0] is None
        assert db.execute("SELECT attname FROM pg_attribute WHERE attrelid="
            "'public.conversation_thread_messages'::regclass AND attname IN "
            "('role','seq','parts','client_message_id','turn_id')").fetchall() == []
        # Legacy notes stay intact and ordered by created_at/id after downgrade.
        user = _user(db)
        thread = _thread(db, user)
        db.execute("INSERT INTO conversation_thread_messages(id,workspace_id,project_id,"
            "thread_id,owner_user_id,author_user_id,text) VALUES(%s,%s,%s,%s,%s,%s,'kept')",
            (uuid.uuid4(), WORKSPACE_A, PROJECT_A, thread, user, user))
    command.upgrade(cfg, 'head')
    with psycopg.connect(isolated_migrated) as db:
        user = _user(db, 'thread-typed-fixture')
        thread = _thread(db, user)
        db.execute("INSERT INTO conversation_turns(id,workspace_id,project_id,thread_id,"
            "owner_user_id,actor_id,request_fingerprint,language,status,step_count,parts,notices) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,'en','completed',1,'[]','[]')",
            (uuid.uuid4(), WORKSPACE_A, PROJECT_A, thread, user, user, 'a' * 64))
    with pytest.raises(RuntimeError, match='preserve populated conversation turns'):
        command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == HEAD
        assert db.execute('SELECT count(*) FROM conversation_turns').fetchone()[0] == 1


def test_company_link_and_proposal_only_capabilities(isolated_seeded):
    cfg = config()
    with psycopg.connect(isolated_seeded) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == HEAD
        user = _user(db, 'thread-buyer-fixture')
        thread = _thread(db, user)
        company, buyer = uuid.uuid4(), uuid.uuid4()
        db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) "
            "VALUES(%s,%s,'Linked Co','Linked Co')", (company, WORKSPACE_A))
        db.execute("INSERT INTO project_buyers(id,workspace_id,project_id,company_id) "
            "VALUES(%s,%s,%s,%s)", (buyer, WORKSPACE_A, PROJECT_A, company))
        db.execute('UPDATE conversation_threads SET buyer_id=%s WHERE id=%s', (buyer, thread))
        turn, proposal = uuid.uuid4(), uuid.uuid4()
        db.execute("INSERT INTO conversation_turns(id,workspace_id,project_id,thread_id,"
            "owner_user_id,actor_id,request_fingerprint,language,status,step_count,parts,notices) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,'en','needs_approval',2,'[]','[]')",
            (turn, WORKSPACE_A, PROJECT_A, thread, user, user, 'b' * 64))
        db.execute("INSERT INTO conversation_turn_proposals(id,workspace_id,project_id,thread_id,"
            "turn_id,actor_id,capability,skill_id,skill_version,title,rationale,arguments,"
            "source_refs,arguments_preview) VALUES(%s,%s,%s,%s,%s,%s,'xverum.enrich_company',"
            "'sales-contacts','1','Enrich','Reviewed enrichment for the linked buyer',"
            "'{}','[]','{}')", (proposal, WORKSPACE_A, PROJECT_A, thread, turn, user))
        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute("INSERT INTO conversation_turn_proposals(id,workspace_id,project_id,"
                "thread_id,turn_id,actor_id,capability,skill_id,skill_version,title,rationale,"
                "arguments,source_refs,arguments_preview) VALUES(%s,%s,%s,%s,%s,%s,'unknown.read',"
                "'sales-contacts','1','x','x','{}','[]','{}')",
                (uuid.uuid4(), WORKSPACE_A, PROJECT_A, thread, turn, user))
    with pytest.raises(RuntimeError, match='preserve thread company links'):
        command.downgrade(cfg, '0066_conversation_turns')
    with psycopg.connect(isolated_seeded) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == HEAD
        assert db.execute('SELECT buyer_id FROM conversation_threads WHERE id=%s',
            (thread,)).fetchone()[0] == buyer
        assert db.execute('SELECT capability FROM conversation_turn_proposals').fetchone()[0] \
            == 'xverum.enrich_company'
