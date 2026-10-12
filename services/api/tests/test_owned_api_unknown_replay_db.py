"""C61-19/20/25: owned response loss, rollback and retained liability controls.

Admission only: no worker dispatch, paid provider POST, send, settle or release.
"""
import json
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from tests.test_bulk_manifest_db import api, _seed_many, _admin_membership, _preview, _execute
from tests.test_buyer_review_db import api as buyer_api
from tests.test_delivery_public_admission_db import public_case, selected, url, body
from tests.test_delivery_admission_db import admission_case, counts, snapshot
from tests.test_lookup_quotes_db import _h, REVIEWER
from tests.owned_api_evidence import record_property


class LoseCommittedResponse:
    """Drop transport bytes after the original route's transaction commits."""
    def __init__(self, app):
        self.app = app
        self.discarded_status = None
    async def __call__(self, scope, receive, send):
        async def drop(message):
            if scope['type'] == 'http':
                if message['type'] == 'http.response.start':
                    self.discarded_status = message['status']
                return  # deliberately discard all response bytes, never retry
            await send(message)
        await self.app(scope, receive, drop)


def bulk_rows(dsn):
    with psycopg.connect(dsn) as db:
        return {
            'jobs': db.execute('SELECT id,manifest_id,status,processed FROM async_jobs ORDER BY id').fetchall(),
            'outbox': db.execute("SELECT id,intent_key,payload,state FROM outbox_events WHERE event_type='bulk.mutate' ORDER BY id").fetchall(),
            'idempotency': db.execute("SELECT id,key,request_hash,status,resource_id,response FROM idempotency_records WHERE operation_id='executeBulkManifest' ORDER BY id").fetchall(),
        }


def test_owned_bulk_lost_committed_response_replays_original_job_payload_and_one_outbox(api, seeded, record_property):
    _seed_many(seeded, 101)
    manifest = _preview(api, _admin_membership(seeded))
    key = 'owned-lost-bulk-response'
    transport = LoseCommittedResponse(api.app)
    with TestClient(transport, raise_server_exceptions=False) as lost:
        unavailable = _execute(lost, manifest, key)
    assert unavailable.status_code == 500 and transport.discarded_status == 202
    committed = bulk_rows(seeded)
    assert len(committed['jobs']) == len(committed['outbox']) == len(committed['idempotency']) == 1
    assert committed['idempotency'][0][3] == 'completed'
    replay = _execute(api, manifest, key)
    assert replay.status_code == 202, replay.text
    assert replay.json()['data'] == committed['idempotency'][0][5]['data']
    assert replay.json()['data']['id'] == str(committed['jobs'][0][0])
    assert committed['outbox'][0][2]['job_id'] == replay.json()['data']['id']
    fresh = _execute(api, manifest, 'owned-no-new-key-after-loss')
    assert fresh.status_code == 409
    assert bulk_rows(seeded) == committed
    record_property('owned_evidence', json.dumps({'transport_response': 500, 'discarded_committed_status': 202,
        'original_durable_rows': committed, 'replay': replay.json(), 'fresh_key_status': 409,
        'provider_posts': 0, 'send_calls': 0, 'live_acceptance': False}, default=str, sort_keys=True))


def test_owned_bulk_abort_before_commit_has_zero_partial_rows_and_same_key_can_commit_once(api, seeded, monkeypatch, record_property):
    from buyeros_api.api.routes import bulk_manifests
    _seed_many(seeded, 101)
    manifest = _preview(api, _admin_membership(seeded))
    before = bulk_rows(seeded)
    original = bulk_manifests.complete_idempotency
    def abort(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError('owned injected abort before transaction commit')
    monkeypatch.setattr(bulk_manifests, 'complete_idempotency', abort)
    key = 'owned-rollback-bulk-response'
    failed = _execute(api, manifest, key)
    assert failed.status_code == 500
    assert bulk_rows(seeded) == before
    monkeypatch.setattr(bulk_manifests, 'complete_idempotency', original)
    first = _execute(api, manifest, key)
    replay = _execute(api, manifest, key)
    assert first.status_code == replay.status_code == 202
    assert first.json()['data'] == replay.json()['data']
    after = bulk_rows(seeded)
    assert len(after['jobs']) == len(after['outbox']) == len(after['idempotency']) == 1
    record_property('owned_evidence', json.dumps({'rollback_rows': before, 'committed_rows': after,
        'first': first.json(), 'replay': replay.json(), 'live_acceptance': False}, default=str, sort_keys=True))


@pytest.mark.parametrize('state', ['unknown', 'accepted'])
def test_owned_same_payload_uncertain_delivery_readback_preserves_identity_hold_and_ref(public_case, monkeypatch, record_property, state):
    from buyeros_api.providers.resend_delivery import ResendDeliveryAdapter
    attempted = []
    async def refuse_submit(*args, **kwargs):
        attempted.append('submit')
        raise AssertionError('owned replay must never obtain provider POST authority')
    monkeypatch.setattr(ResendDeliveryAdapter, 'submit', refuse_submit)
    client, dsn, args, authority = public_case
    selected(monkeypatch, authority)  # synthetic server selection, original validation and ledgers
    transport = LoseCommittedResponse(client.app)
    with TestClient(transport, raise_server_exceptions=False) as lost:
        unavailable = lost.post(url(args), headers=_h(REVIEWER, key=args['key']), json=body(args))
    assert unavailable.status_code == 500 and transport.discarded_status == 202
    with psycopg.connect(dsn) as db:
        message, operation, reservation, outbox = db.execute(
            'SELECT m.id,m.operation_id,r.id,a.outbox_id FROM delivery_messages m '
            'JOIN budget_reservations r ON r.operation_id=m.operation_id '
            'JOIN delivery_authorizations a ON a.message_id=m.id WHERE m.intent_key=%s', (args['key'],)).fetchone()
        ref = 'owned-retained-provider-ref' if state == 'accepted' else None
        db.execute("UPDATE delivery_messages SET state='submitting' WHERE id=%s", (message,))
        db.execute('UPDATE delivery_messages SET state=%s,provider_ref=%s WHERE id=%s', (state, ref, message))
        db.execute('UPDATE provider_operations SET status=%s WHERE id=%s',
                   ('accepted' if state == 'accepted' else 'unknown_acceptance', operation))
    from types import SimpleNamespace
    result = SimpleNamespace(message_id=message, operation_id=operation, reservation_id=reservation, outbox_id=outbox)
    original = snapshot(dsn, result)
    before = counts(dsn)
    with psycopg.connect(dsn) as db:
        provider_before = db.execute('SELECT id,intent_key,input_hash,status,provider_ref FROM provider_operations WHERE id=%s', (operation,)).fetchone()
    replies = [client.post(url(args), headers=_h(REVIEWER, key=args['key']), json=body(args)) for _ in range(3)]
    assert all(r.status_code == 202 and r.json()['data'] == {
        'message_id': str(message), 'state': state, 'replayed': True} for r in replies)
    denied = client.post(url(args), headers=_h(REVIEWER, key='owned-unsafe-new-key-'+state), json=body(args))
    assert (denied.status_code, denied.json()['code']) == (409, 'RETRY_UNSAFE')
    assert snapshot(dsn, result) == original and counts(dsn) == before
    assert attempted == []
    assert original[0][0:3] == (message, operation, args['key']) and original[0][8:10] == (state, ref)
    assert original[1][2:4] == (authority.upper_bound, authority.upper_bound) and original[1][-1] == 'active'
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT count(*) FROM cost_events WHERE operation_id=%s', (operation,)).fetchone() == (0,)
        provider = db.execute('SELECT id,intent_key,input_hash,status,provider_ref FROM provider_operations WHERE id=%s', (operation,)).fetchone()
        assert provider == provider_before
    record_property('owned_evidence', json.dumps({'state': state, 'original_snapshot': original, 'provider_operation': provider,
        'counts_before_after': before, 'same_payload_replays': [r.json() for r in replies],
        'fresh_key_code': denied.json()['code'], 'provider_posts': 0, 'send_calls': 0,
        'live_acceptance': False}, default=str, sort_keys=True))
