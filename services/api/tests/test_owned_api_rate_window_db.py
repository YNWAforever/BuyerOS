"""C61-25: original RS256 HTTP admission and durable owned PG window controls.

These are source/isolated proofs, with a controlled minute clock; no live SLO.
"""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier

import psycopg
import pytest

from tests.conftest import runtime_role_dsn
from tests.test_api_projects_db import api as project_api, WORKSPACE_A, OPERATOR, CREATE, _h
from tests.test_api_tenant_isolation import WORKSPACE_B
from tests.owned_api_evidence import record_property


@pytest.fixture
def api(project_api):
    with project_api as client:
        yield client


def clock(monkeypatch, limit):
    from buyeros_api.settings import get_settings
    value = [datetime(2026, 10, 12, 13, 59, 59, tzinfo=timezone.utc)]
    class OwnedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return value[0]
    monkeypatch.setattr('buyeros_api.services.api_rate_limit.datetime', OwnedClock)
    monkeypatch.setenv('BUYEROS_EXPENSIVE_READ_PER_MINUTE', str(limit))
    monkeypatch.setenv('BUYEROS_EXPENSIVE_WRITE_PER_MINUTE', str(limit))
    get_settings.cache_clear()
    return value


def proof(record_property, requests, rows):
    record_property('owned_evidence', json.dumps({
        'scope': 'ownedPG16/realRS256localJWKS/originalAPI',
        'live_acceptance': False, 'requests': [{
            'status': r.status_code, 'body': r.json(),
            'request_id': r.headers.get('X-Request-ID'),
            'retry_after': r.headers.get('Retry-After'),
        } for r in requests], 'sql_rows': rows,
    }, default=str, sort_keys=True))


def windows(dsn):
    with psycopg.connect(dsn) as db:
        return db.execute('SELECT workspace_id,actor_id,bucket,window_start,hits '
                          'FROM api_rate_windows ORDER BY workspace_id,actor_id,bucket,window_start').fetchall()


def test_owned_parallel_rate_window_admits_exactly_two_and_persists_counter(api, seeded, monkeypatch, record_property):
    clock(monkeypatch, 2)
    headers = _h(OPERATOR)  # initialize signing key before threads
    barrier = Barrier(8)
    def request(_):
        barrier.wait(timeout=10)
        return api.get(f'/v1/workspaces/{WORKSPACE_A}/projects', headers=headers)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(request, range(8)))
    assert sorted(r.status_code for r in results) == [200, 200, 429, 429, 429, 429, 429, 429]
    assert all(r.json()['code'] == 'RATE_LIMITED' and r.headers['Retry-After'] == '60'
               for r in results if r.status_code == 429)
    rows = windows(seeded)
    assert rows == [(uuid.UUID(WORKSPACE_A), uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR),
                     'expensive_read', datetime(2026, 10, 12, 13, 59, tzinfo=timezone.utc), 2)]
    assert len({r.headers['X-Request-ID'] for r in results}) == 8
    proof(record_property, results, rows)


def test_owned_minute_rollover_and_same_actor_other_tenant_have_independent_windows(api, seeded, monkeypatch, record_property):
    now = clock(monkeypatch, 1)
    actor = uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR)
    with psycopg.connect(seeded) as db:
        db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES (%s,%s,%s,ARRAY['operator'],true)",
                   (uuid.uuid4(), WORKSPACE_B, actor))
    a = f'/v1/workspaces/{WORKSPACE_A}/projects'
    b = f'/v1/workspaces/{WORKSPACE_B}/projects'
    results = [api.get(path, headers=_h()) for path in (a, a, b, b)]
    assert [r.status_code for r in results] == [200, 429, 200, 429]
    now[0] = datetime(2026, 10, 12, 14, 0, tzinfo=timezone.utc)
    results += [api.get(path, headers=_h()) for path in (a, b)]
    assert [r.status_code for r in results[-2:]] == [200, 200]
    rows = windows(seeded)
    assert len(rows) == 4 and all(row[1] == actor and row[2] == 'expensive_read' and row[4] == 1 for row in rows)
    assert {(str(r[0]), r[3].strftime('%H:%M')) for r in rows} == {
        (WORKSPACE_A, '13:59'), (WORKSPACE_A, '14:00'), (WORKSPACE_B, '13:59'), (WORKSPACE_B, '14:00')}
    with psycopg.connect(runtime_role_dsn(seeded)) as db:
        assert db.execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone() == (False, False)
        db.execute("SELECT set_config('app.workspace_id',%s,true)", (WORKSPACE_B,))
        assert db.execute('SELECT DISTINCT workspace_id FROM api_rate_windows').fetchall() == [(uuid.UUID(WORKSPACE_B),)]
    proof(record_property, results, rows)


def test_owned_failed_business_write_consumes_slot_without_creating_idempotency_or_project(api, seeded, monkeypatch, record_property):
    now = clock(monkeypatch, 1)
    path = f'/v1/workspaces/{WORKSPACE_A}/projects'
    key = 'owned-rate-invalid'
    with psycopg.connect(seeded) as db:
        before = db.execute('SELECT count(*) FROM projects WHERE workspace_id=%s', (WORKSPACE_A,)).fetchone()[0]
    failed = api.post(path, headers=_h(key='short'), json=CREATE)
    rejected = api.post(path, headers=_h(key=key), json=CREATE)
    assert (failed.status_code, failed.json()['code']) == (400, 'INVALID_REQUEST')
    assert (rejected.status_code, rejected.json()['code']) == (429, 'RATE_LIMITED')
    with psycopg.connect(seeded) as db:
        assert db.execute('SELECT count(*) FROM projects WHERE workspace_id=%s', (WORKSPACE_A,)).fetchone()[0] == before
        assert db.execute("SELECT count(*) FROM idempotency_records WHERE key IN ('short',%s)", (key,)).fetchone() == (0,)
    assert windows(seeded)[0][-1] == 1
    now[0] = datetime(2026, 10, 12, 14, 0, tzinfo=timezone.utc)
    owned = api.post(path, headers=_h(key=key), json=CREATE)
    assert owned.status_code == 201, owned.text
    proof(record_property, [failed, rejected, owned], windows(seeded))
