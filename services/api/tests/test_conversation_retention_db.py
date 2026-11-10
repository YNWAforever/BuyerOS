"""PostgreSQL: derived conversation retention enforcement (Phase 3.4).

CI-only (no local PostgreSQL). Deterministic clock, no sleeps, synthetic fixture
data only. Turns, parts and decisions are user content: every assertion below
also proves the sweep leaves them untouched.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from buyeros_api.api.deps import async_database_url
from buyeros_api.services.conversation_retention import MAX_SWEEP, prune_rate_windows, prune_turn_events
from tests.test_buyer_review_db import WORKSPACE_A, WORKSPACE_B, api  # noqa: F401 (fixture registration)
from tests.test_conversation_turns_api import enabled, post_turn, turn_api, turn_body  # noqa: F401

NOW = datetime(2026, 11, 11, 9, 0, tzinfo=timezone.utc)


def _run(dsn, action):
    async def body():
        engine = create_async_engine(async_database_url(dsn), poolclass=NullPool)
        try:
            return await action(engine)
        finally:
            await engine.dispose()
    return asyncio.run(body())


def _insert_windows(db, workspace, *, starts, actor=None):
    for index, start in enumerate(starts):
        db.execute('INSERT INTO api_rate_windows(workspace_id,actor_id,bucket,window_start,hits) '
                   'VALUES(%s,%s,%s,%s,2)',
                   (workspace, actor or uuid.uuid4(), 'read-%d' % index, start))
        db.execute('INSERT INTO conversation_turn_rate_windows(workspace_id,window_start,hits) '
                   'VALUES(%s,%s,1)', (workspace, start))


def _window_counts(dsn):
    with psycopg.connect(dsn) as db:
        return {
            'api': db.execute('SELECT count(*) FROM api_rate_windows').fetchone()[0],
            'turn': db.execute('SELECT count(*) FROM conversation_turn_rate_windows').fetchone()[0],
        }


def _clear_windows(dsn):
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute('DELETE FROM api_rate_windows')
        db.execute('DELETE FROM conversation_turn_rate_windows')


def test_sweep_deletes_only_expired_windows_and_keeps_other_workspaces(turn_api):
    _, dsn = turn_api
    expired = (NOW - timedelta(hours=3), NOW - timedelta(hours=2))
    fresh = (NOW - timedelta(minutes=10), NOW - timedelta(minutes=1))
    try:
        with psycopg.connect(dsn, autocommit=True) as db:
            for workspace in (WORKSPACE_A, WORKSPACE_B):
                _insert_windows(db, workspace, starts=expired + fresh)
        pruned = _run(dsn, lambda engine: prune_rate_windows(
            engine, NOW, retention_minutes=60))
        # Two expired rows per workspace, both counter tables.
        assert pruned == 8
        assert _window_counts(dsn) == {'api': 4, 'turn': 4}
        # A second sweep can only be a no-op; the retained fresh windows stay.
        assert _run(dsn, lambda engine: prune_rate_windows(
            engine, NOW, retention_minutes=60)) == 0
        assert _window_counts(dsn) == {'api': 4, 'turn': 4}
    finally:
        _clear_windows(dsn)


def test_only_expired_derived_events_are_pruned_and_turn_content_survives(turn_api):
    client, dsn = turn_api
    response = post_turn(client, turn_body())
    assert response.status_code == 200, response.text
    turn_id = response.json()['data']['turn']['id']
    with psycopg.connect(dsn) as db:
        event_ids = [row[0] for row in db.execute(
            'SELECT id FROM conversation_turn_events WHERE turn_id=%s ORDER BY seq',
            (turn_id,)).fetchall()]
        assert len(event_ids) >= 2, 'a completed turn emits and finalizes events'
        kept, expired = event_ids[-1], event_ids[:-1]
        db.execute('UPDATE conversation_turn_events SET created_at=%s WHERE id=ANY(%s)',
                   (NOW - timedelta(days=40), expired))
        db.commit()
        before = db.execute('SELECT status,parts,notices FROM conversation_turns WHERE id=%s',
                            (turn_id,)).fetchone()
        thread_before = db.execute(
            'SELECT version FROM conversation_threads WHERE id=(SELECT thread_id FROM conversation_turns '
            'WHERE id=%s)', (turn_id,)).fetchone()
        assert thread_before is not None
    pruned = _run(dsn, lambda engine: prune_turn_events(
        engine, NOW, retention_days=30))
    assert pruned == len(expired)
    with psycopg.connect(dsn) as db:
        remaining = [row[0] for row in db.execute(
            'SELECT id FROM conversation_turn_events WHERE turn_id=%s', (turn_id,)).fetchall()]
        assert remaining == [kept]
        # User content is never derivation: status, parts and the thread version survive.
        assert db.execute('SELECT status,parts,notices FROM conversation_turns WHERE id=%s',
                          (turn_id,)).fetchone() == before
        assert db.execute('SELECT version FROM conversation_threads WHERE id='
                          '(SELECT thread_id FROM conversation_turns WHERE id=%s)',
                          (turn_id,)).fetchone() == thread_before


def test_zero_retention_disables_both_sweeps(turn_api):
    client, dsn = turn_api
    response = post_turn(client, turn_body())
    assert response.status_code == 200, response.text
    turn_id = response.json()['data']['turn']['id']
    try:
        # The POST itself legitimately consumed one live rate window; start the
        # retention fixture from a known-empty counter state.
        _clear_windows(dsn)
        with psycopg.connect(dsn, autocommit=True) as db:
            _insert_windows(db, WORKSPACE_A, starts=(NOW - timedelta(days=2),))
            db.execute('UPDATE conversation_turn_events SET created_at=%s WHERE turn_id=%s',
                       (NOW - timedelta(days=400), turn_id))
        assert _run(dsn, lambda engine: prune_rate_windows(
            engine, NOW, retention_minutes=0)) == 0
        assert _run(dsn, lambda engine: prune_turn_events(
            engine, NOW, retention_days=0)) == 0
        assert _window_counts(dsn) == {'api': 1, 'turn': 1}
        with psycopg.connect(dsn) as db:
            assert db.execute('SELECT count(*) FROM conversation_turn_events WHERE turn_id=%s',
                              (turn_id,)).fetchone()[0] >= 2
    finally:
        _clear_windows(dsn)


def test_retention_bounds_are_validated_before_any_query(turn_api):
    _, dsn = turn_api
    with pytest.raises(ValueError):
        _run(dsn, lambda engine: prune_turn_events(engine, NOW, retention_days=-1))
    with pytest.raises(ValueError):
        _run(dsn, lambda engine: prune_turn_events(engine, NOW, retention_days=True))
    with pytest.raises(ValueError):
        _run(dsn, lambda engine: prune_turn_events(engine, NOW, retention_days=30, limit=0))
    with pytest.raises(ValueError):
        _run(dsn, lambda engine: prune_rate_windows(engine, NOW, retention_minutes=-5))
    with pytest.raises(ValueError):
        _run(dsn, lambda engine: prune_rate_windows(
            engine, NOW, retention_minutes=60, limit=MAX_SWEEP + 1))
