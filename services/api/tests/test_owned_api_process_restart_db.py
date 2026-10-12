"""C61-19/20/25: original API recovery across actual OS process death."""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import httpx
import psycopg
import pytest

from tests.test_api_projects_db import api as project_api, WORKSPACE_A, CREATE, _h
from tests.test_delivery_public_admission_db import public_case, selected, url, body
from tests.test_delivery_admission_db import admission_case, counts, snapshot
from tests.test_lookup_quotes_db import _h as delivery_headers, REVIEWER
from tests.owned_api_evidence import record_property
from tests.owned_api_process import OwnedAPIProcess, process_config, runtime_backends, wait_for_backend_exit


def project_rows(dsn, key):
    with psycopg.connect(dsn) as db:
        return {
            'projects': db.execute('SELECT id,workspace_id,name,version FROM projects ORDER BY id').fetchall(),
            'idempotency': db.execute('SELECT id,key,request_hash,status,resource_id,response FROM idempotency_records WHERE key=%s ORDER BY id', (key,)).fetchall(),
            'audit': db.execute('SELECT id,subject_id,action,actor_id,request_id FROM audit_events ORDER BY id').fetchall(),
            'accounts': db.execute('SELECT * FROM budget_accounts ORDER BY id').fetchall(),
        }


def interrupted_post(server, path, headers, payload):
    try:
        httpx.post(server.base_url + path, headers=headers, json=payload, timeout=20)
    except httpx.RequestError as error:
        return type(error).__name__
    raise AssertionError('owned interrupted transport unexpectedly received response')


@pytest.mark.parametrize('phase', ['before-commit', 'after-commit'])
def test_owned_process_death_reuses_original_key_after_confirmed_rollback_or_commit(project_api, seeded, record_property, phase):
    key = 'owned-process-project-' + phase
    path = f'/v1/workspaces/{WORKSPACE_A}/projects'
    headers = _h(key=key)
    before = project_rows(seeded, key)
    config = process_config(seeded, phase=phase, blocked_key=key)
    with OwnedAPIProcess(config) as first:
        with ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(interrupted_post, first, path, headers, CREATE)
            boundary = first.event(phase)
            rows_at_boundary = project_rows(seeded, key)
            pids = [r[0] for r in runtime_backends(seeded)]
            assert pids
            if phase == 'before-commit':
                assert rows_at_boundary == before
            else:
                assert boundary['status'] == 201
                assert len(rows_at_boundary['projects']) == len(before['projects']) + 1
                assert len(rows_at_boundary['idempotency']) == 1
                assert rows_at_boundary['idempotency'][0][3] == 'completed'
            first.stop(hard=True)
            lost_transport = pending.result(timeout=5)
        assert wait_for_backend_exit(seeded, pids) == []
    durable = project_rows(seeded, key)
    assert durable == rows_at_boundary
    with psycopg.connect(seeded) as db:
        assert db.execute('SELECT sum(hits) FROM api_rate_windows WHERE workspace_id=%s', (WORKSPACE_A,)).fetchone() == (1,)
    with OwnedAPIProcess(process_config(seeded)) as second:
        assert second.ready['pid'] != first.ready['pid']
        replay = httpx.post(second.base_url + path, headers=headers, json=CREATE, timeout=10)
        assert replay.status_code == 201, replay.text
        assert replay.headers['ETag'] == '"1"'
        once = project_rows(seeded, key)
        assert len(once['projects']) == len(before['projects']) + 1
        assert len(once['audit']) == len(before['audit']) + 1
        assert len(once['idempotency']) == 1
        assert once['idempotency'][0][4] == replay.json()['data']['id']
        if phase == 'after-commit':
            assert once == durable
            assert replay.json()['data'] == durable['idempotency'][0][5]['data']
        again = httpx.post(second.base_url + path, headers=headers, json=CREATE, timeout=10)
        changed = httpx.post(second.base_url + path, headers=headers, json=dict(CREATE, name='Rebound'), timeout=10)
        assert again.status_code == 201 and again.json()['data'] == replay.json()['data']
        assert (changed.status_code, changed.json()['code']) == (409, 'IDEMPOTENCY_CONFLICT')
        assert project_rows(seeded, key) == once
        assert not second.control.poll()
        second_pids = [r[0] for r in runtime_backends(seeded)]
        assert second_pids
    assert second.exit['exitcode'] == 0
    assert wait_for_backend_exit(seeded, second_pids) == []
    record_property('owned_evidence', json.dumps({'phase': phase, 'boundary': boundary,
        'processes': [first.ready, first.exit, second.ready, second.exit], 'transport': lost_transport,
        'rows_at_boundary': rows_at_boundary, 'final_rows': once, 'replay': replay.json(),
        'changed_body_code': changed.json()['code'], 'backend_pids': [pids, second_pids],
        'backend_remaining': [], 'live_acceptance': False}, default=str, sort_keys=True))


@pytest.mark.parametrize('state', ['unknown', 'accepted'])
def test_owned_delivery_process_restart_keeps_original_uncertain_identity_ref_and_full_hold(public_case, monkeypatch, record_property, state):
    client, dsn, args, authority = public_case
    selected(monkeypatch, authority)
    payload = body(args)
    headers = delivery_headers(REVIEWER, key=args['key'])
    with OwnedAPIProcess(process_config(dsn, phase='after-commit', authority=authority)) as first:
        with ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(interrupted_post, first, url(args), headers, payload)
            boundary = first.event('after-commit')
            assert boundary['status'] == 202
            with psycopg.connect(dsn) as db:
                message, operation, reservation, outbox = db.execute(
                    'SELECT m.id,m.operation_id,r.id,a.outbox_id FROM delivery_messages m '
                    'JOIN budget_reservations r ON r.operation_id=m.operation_id '
                    'JOIN delivery_authorizations a ON a.message_id=m.id WHERE m.intent_key=%s', (args['key'],)).fetchone()
                ref = 'owned-process-retained-ref' if state == 'accepted' else None
                db.execute("UPDATE delivery_messages SET state='submitting' WHERE id=%s", (message,))
                db.execute('UPDATE delivery_messages SET state=%s,provider_ref=%s WHERE id=%s', (state, ref, message))
                db.execute('UPDATE provider_operations SET status=%s,provider_ref=%s WHERE id=%s',
                    ('accepted' if state == 'accepted' else 'unknown_acceptance', ref, operation))
            first.stop(hard=True)
            lost_transport = pending.result(timeout=5)
    result = SimpleNamespace(message_id=message, operation_id=operation, reservation_id=reservation, outbox_id=outbox)
    original = snapshot(dsn, result)
    original_counts = counts(dsn)
    with psycopg.connect(dsn) as db:
        original_operation = db.execute('SELECT id,intent_key,input_hash,status,provider_ref FROM provider_operations WHERE id=%s', (operation,)).fetchone()
    assert original_operation[4] == original[0][9] == ref
    assert original[1][2:4] == (authority.upper_bound, authority.upper_bound) and original[1][-1] == 'active'
    with OwnedAPIProcess(process_config(dsn, authority=authority)) as second:
        assert second.ready['pid'] != first.ready['pid']
        replies = [httpx.post(second.base_url + url(args), headers=headers, json=payload, timeout=10) for _ in range(3)]
        assert all(r.status_code == 202 and r.json()['data'] == {
            'message_id': str(message), 'state': state, 'replayed': True} for r in replies)
        denied = httpx.post(second.base_url + url(args), headers=delivery_headers(REVIEWER, key='owned-new-key-unsafe-' + state), json=payload, timeout=10)
        assert (denied.status_code, denied.json()['code']) == (409, 'RETRY_UNSAFE')
        assert snapshot(dsn, result) == original and counts(dsn) == original_counts
        with psycopg.connect(dsn) as db:
            assert db.execute('SELECT id,intent_key,input_hash,status,provider_ref FROM provider_operations WHERE id=%s', (operation,)).fetchone() == original_operation
            assert db.execute('SELECT count(*) FROM cost_events WHERE operation_id=%s', (operation,)).fetchone() == (0,)
        assert not second.control.poll()
    assert second.exit['exitcode'] == 0
    record_property('owned_evidence', json.dumps({'state': state, 'boundary': boundary,
        'processes': [first.ready, first.exit, second.ready, second.exit], 'transport': lost_transport,
        'original_snapshot': original, 'provider_operation': original_operation, 'counts': original_counts,
        'replays': [r.json() for r in replies], 'fresh_key_code': denied.json()['code'],
        'provider_posts': 0, 'send_calls': 0, 'live_acceptance': False}, default=str, sort_keys=True))
