"""PostgreSQL: migration 0070 invariants (head, RLS/grants, rollback shape).

CI-only; skipped without a disposable database. The table holds transient
admission counters, so downgrade intentionally drops them without a populated
guard (unlike evidence tables).
"""
import uuid
from datetime import datetime, timezone

import psycopg
from alembic import command

from tests.conftest import runtime_role_dsn
from tests.test_buyer_review_db import WORKSPACE_A, WORKSPACE_B
from tests.test_conversation_turns_migration_db import config

HEAD = '0071_conversation_retention'
PREVIOUS = '0069_turn_reconciliations'
TABLE = 'conversation_turn_rate_windows'
WINDOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def test_rate_window_table_is_tenant_scoped_and_closed_to_the_worker(isolated_migrated):
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == HEAD
        assert db.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class '
            'WHERE oid=%s::regclass', (TABLE,)).fetchone() == (True, True)
        assert db.execute("SELECT count(*) FROM pg_constraint WHERE conname="
            "'conversation_turn_rate_windows_pkey' AND contype='p'").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM pg_constraint WHERE conname="
            "'ck_conversation_turn_rate_windows_positive_hits' AND contype='c'"
            ).fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM pg_indexes WHERE tablename=%s AND "
            "indexname='ix_conversation_turn_rate_windows_expiry'", (TABLE,)).fetchone()[0] == 1
        for verb in ('SELECT', 'INSERT', 'UPDATE'):
            assert db.execute('SELECT has_table_privilege(%s,%s,%s)',
                ('buyeros_worker', TABLE, verb)).fetchone()[0] is False
        # Retention (0071) grants only the delete the bounded sweeper needs.
        assert db.execute('SELECT has_table_privilege(%s,%s,%s)',
            ('buyeros_worker', TABLE, 'DELETE')).fetchone()[0] is True
        for verb, expected in (('SELECT', True), ('INSERT', True), ('UPDATE', True),
                               ('DELETE', False)):
            assert db.execute('SELECT has_table_privilege(%s,%s,%s)',
                ('buyeros_api', TABLE, verb)).fetchone()[0] is expected
        assert db.execute('SELECT public.buyeros_xverum_connections_ready()').fetchone()[0] is True


def test_rate_windows_are_isolated_by_workspace(isolated_seeded):
    dsn = runtime_role_dsn(isolated_seeded)
    with psycopg.connect(dsn) as db:
        for workspace in (WORKSPACE_A, WORKSPACE_B):
            db.execute("SELECT set_config('app.workspace_id',%s,true)", (workspace,))
            db.execute('INSERT INTO conversation_turn_rate_windows'
                '(workspace_id,window_start,hits) VALUES(%s,%s,1)', (workspace, WINDOW))
        db.commit()
    with psycopg.connect(dsn) as db:
        db.execute("SELECT set_config('app.workspace_id',%s,true)", (WORKSPACE_A,))
        rows = db.execute('SELECT workspace_id::text,hits FROM conversation_turn_rate_windows'
            ).fetchall()
        assert rows == [(str(WORKSPACE_A), 1)]
        db.execute("SELECT set_config('app.workspace_id',%s,true)", (WORKSPACE_B,))
        rows = db.execute('SELECT workspace_id::text,hits FROM conversation_turn_rate_windows'
            ).fetchall()
        assert rows == [(str(WORKSPACE_B), 1)]


def test_empty_and_populated_counter_downgrade_round_trips(isolated_seeded):
    cfg = config()
    with psycopg.connect(isolated_seeded) as db:
        db.execute("SELECT set_config('app.workspace_id',%s,true)", (WORKSPACE_A,))
        db.execute('INSERT INTO conversation_turn_rate_windows'
            '(workspace_id,window_start,hits) VALUES(%s,%s,4)', (WORKSPACE_A, WINDOW))
        db.commit()
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(isolated_seeded) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == PREVIOUS
        assert db.execute('SELECT to_regclass(%s)', ('public.' + TABLE,)).fetchone()[0] is None
    command.upgrade(cfg, 'head')
    with psycopg.connect(isolated_seeded) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == HEAD
        assert db.execute('SELECT to_regclass(%s)', ('public.' + TABLE,)).fetchone()[0] is not None
        # Transient counters are not evidence; the downgrade intentionally discards them.
        assert db.execute('SELECT count(*) FROM conversation_turn_rate_windows'
            ).fetchone()[0] == 0
