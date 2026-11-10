"""PostgreSQL: dedicated per-workspace conversation-turn admission (Phase 3.4).

CI-only (no local PostgreSQL). Deterministic: the UTC window is monkeypatched and
no test sleeps. Synthetic fixture data only; no provider/model call is enabled.
"""
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from buyeros_api.settings import get_settings
from buyeros_api.services import turn_rate_limit
from tests.test_buyer_review_db import (ADMIN, PROJECT_A, PROJECT_B, WORKSPACE_A,
    WORKSPACE_B, _h)
from tests.test_conversation_turns_api import (TURN_ROOT, key, post_turn, turn_api,
    turn_body)

WINDOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
TABLES = ('conversation_threads', 'conversation_turns', 'conversation_turn_events',
          'sales_tasks', 'sales_executions', 'sales_steps', 'budget_accounts',
          'budget_reservations', 'idempotency_records')


@pytest.fixture
def turn_rate(turn_api, monkeypatch):
    """Fixed clock plus cleanup of transient windows around each test."""
    client, dsn = turn_api
    clock = {'now': WINDOW}
    monkeypatch.setattr(turn_rate_limit, 'current_window', lambda: clock['now'])
    yield client, dsn, clock
    get_settings.cache_clear()
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute('DELETE FROM conversation_turn_rate_windows')


def configure(monkeypatch, value):
    monkeypatch.setenv('BUYEROS_TURN_PER_MINUTE', str(value))
    get_settings.cache_clear()


def window_hits(dsn, *, workspace=WORKSPACE_A, window=WINDOW):
    with psycopg.connect(dsn) as db:
        row = db.execute('SELECT hits FROM conversation_turn_rate_windows '
            'WHERE workspace_id=%s AND window_start=%s', (workspace, window)).fetchone()
        return row[0] if row else 0


def counts(dsn):
    with psycopg.connect(dsn) as db:
        return {table: db.execute('SELECT count(*) FROM ' + table +
            ' WHERE workspace_id=%s', (WORKSPACE_A,)).fetchone()[0] for table in TABLES}


def test_under_limit_accepts_and_completed_replay_does_not_consume(turn_rate, monkeypatch):
    client, dsn, _ = turn_rate
    configure(monkeypatch, 2)
    body = turn_body()
    mutation_key = key()
    first = post_turn(client, body, mutation_key=mutation_key)
    assert first.status_code == 200, first.text
    turn_id = first.json()['data']['turn']['id']
    assert window_hits(dsn) == 1
    replay = post_turn(client, body, mutation_key=mutation_key)
    assert replay.status_code == 200, replay.text
    assert replay.json()['data']['turn']['id'] == turn_id
    # A completed replay is served before admission and consumes nothing.
    assert window_hits(dsn) == 1
    second = post_turn(client, turn_body())
    assert second.status_code == 200, second.text
    assert window_hits(dsn) == 2


def test_limit_rejection_has_no_residue_and_other_workspace_is_unaffected(turn_rate,
        monkeypatch):
    client, dsn, _ = turn_rate
    configure(monkeypatch, 1)
    assert post_turn(client, turn_body()).status_code == 200
    assert window_hits(dsn) == 1
    before = counts(dsn)
    rejected = post_turn(client, turn_body())
    assert rejected.status_code == 429, rejected.text
    error = rejected.json()
    assert (error['code'], error['retryable']) == ('TURN_RATE_LIMITED', True)
    assert error['message'] == 'turn rate limit reached'
    # No turn/thread/event/task/budget/idempotency write survives the rejection.
    assert window_hits(dsn) == 1
    assert counts(dsn) == before
    # The counter is workspace-keyed: another workspace still admits a turn.
    user_id = uuid.uuid5(uuid.NAMESPACE_URL, ADMIN)
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute('DELETE FROM memberships WHERE workspace_id=%s AND user_id=%s',
            (WORKSPACE_B, user_id))
        db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) "
            "VALUES(%s,%s,%s,ARRAY['workspace_admin'],true)",
            (uuid.uuid4(), WORKSPACE_B, user_id))
    other_root = TURN_ROOT.replace(WORKSPACE_A, WORKSPACE_B).replace(PROJECT_A, PROJECT_B)
    other = client.post(other_root, headers=dict(_h(ADMIN, key())), json=turn_body())
    assert other.status_code == 200, other.text
    assert window_hits(dsn, workspace=WORKSPACE_B) == 1
    assert window_hits(dsn) == 1


def test_window_rollover_accepts_again(turn_rate, monkeypatch):
    client, dsn, clock = turn_rate
    configure(monkeypatch, 1)
    assert post_turn(client, turn_body()).status_code == 200
    assert post_turn(client, turn_body()).status_code == 429
    clock['now'] = WINDOW + timedelta(minutes=1)
    accepted = post_turn(client, turn_body())
    assert accepted.status_code == 200, accepted.text
    assert window_hits(dsn, window=WINDOW) == 1
    assert window_hits(dsn, window=WINDOW + timedelta(minutes=1)) == 1


def test_zero_limit_disables_the_ceiling(turn_rate, monkeypatch):
    client, dsn, _ = turn_rate
    configure(monkeypatch, 0)
    for _ in range(3):
        accepted = post_turn(client, turn_body())
        assert accepted.status_code == 200, accepted.text
    assert window_hits(dsn) == 0
