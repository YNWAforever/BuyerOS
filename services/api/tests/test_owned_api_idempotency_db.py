"""C61-25: force the original absent-key race, never replace DB arbitration."""
import asyncio
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest

from tests.test_api_projects_db import api as project_api, WORKSPACE_A, OPERATOR, CREATE, _h
from tests.owned_api_evidence import record_property


@pytest.fixture
def api(project_api):
    with project_api as client:
        yield client


@pytest.mark.parametrize('changed', [False, True], ids=['identical-payload', 'changed-payload'])
def test_owned_concurrent_absent_key_has_one_business_write_and_exact_replay_or_conflict(api, seeded, monkeypatch, record_property, changed):
    from buyeros_api.api import idempotency
    original = idempotency.begin_idempotency
    key = 'owned-forced-idempotency-race'
    observations = []
    gate = asyncio.Event()

    class ObservedSession:
        def __init__(self, actual):
            self.actual = actual
            self.first = True
        def __getattr__(self, name):
            return getattr(self.actual, name)
        async def execute(self, statement, *args, **kwargs):
            result = await self.actual.execute(statement, *args, **kwargs)
            if self.first:
                self.first = False
                frozen = result.freeze()
                observations.append({'session': id(self.actual), 'absent': frozen().scalar_one_or_none() is None})
                if len(observations) == 2:
                    gate.set()
                await asyncio.wait_for(gate.wait(), timeout=10)
                return frozen()
            return result

    async def observed(session, **kwargs):
        if kwargs['key'] == key:
            return await original(ObservedSession(session), **kwargs)
        return await original(session, **kwargs)
    monkeypatch.setattr(idempotency, 'begin_idempotency', observed)
    headers = _h(OPERATOR, key=key)
    bodies = [dict(CREATE, name='Owned race A'), dict(CREATE, name='Owned race B' if changed else 'Owned race A')]
    path = f'/v1/workspaces/{WORKSPACE_A}/projects'
    with psycopg.connect(seeded) as db:
        before = db.execute('SELECT count(*) FROM projects WHERE workspace_id=%s', (WORKSPACE_A,)).fetchone()[0]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda body: api.post(path, headers=headers, json=body), bodies))
    assert len(observations) == 2 and all(x['absent'] for x in observations)
    assert len({x['session'] for x in observations}) == 2
    if changed:
        assert sorted(r.status_code for r in responses) == [201, 409], [r.text for r in responses]
        assert next(r for r in responses if r.status_code == 409).json()['code'] == 'IDEMPOTENCY_CONFLICT'
    else:
        assert [r.status_code for r in responses] == [201, 201], [r.text for r in responses]
        assert responses[0].json()['data'] == responses[1].json()['data']
        assert responses[0].headers['ETag'] == responses[1].headers['ETag'] == '"1"'
    winner = next(r.json()['data'] for r in responses if r.status_code == 201)
    actor = uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR)
    with psycopg.connect(seeded) as db:
        assert db.execute('SELECT count(*) FROM projects WHERE workspace_id=%s', (WORKSPACE_A,)).fetchone()[0] == before + 1
        rows = db.execute('SELECT id,request_hash,status,resource_id,response FROM idempotency_records '
                          "WHERE workspace_id=%s AND actor_id=%s AND operation_id='createProject' AND key=%s",
                          (WORKSPACE_A, actor, key)).fetchall()
        assert len(rows) == 1 and rows[0][2:4] == ('completed', winner['id'])
        assert rows[0][4] == {'http_status': 201, 'version': 1, 'data': winner}
        assert db.execute("SELECT count(*) FROM audit_events WHERE action='project.created' AND subject_id=%s",
                          (winner['id'],)).fetchone() == (1,)
    # Remove observation wrapper; a later original request must read the same durable result.
    monkeypatch.setattr(idempotency, 'begin_idempotency', original)
    matching = next(body for body in bodies if body['name'] == winner['name'])
    replay = api.post(path, headers=headers, json=matching)
    assert replay.status_code == 201 and replay.json()['data'] == winner
    record_property('owned_evidence', json.dumps({'scope': 'ownedPG16/realRS256/originalAPI/forcedAbsentReadRace',
        'live_acceptance': False, 'both_absent': True, 'business_delta': 1, 'idempotency_rows': rows,
        'responses': [{'status': r.status_code, 'body': r.json(), 'request_id': r.headers.get('X-Request-ID')}
                      for r in [*responses, replay]]}, default=str, sort_keys=True))
