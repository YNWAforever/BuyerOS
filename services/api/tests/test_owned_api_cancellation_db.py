"""C61-25: explicit ASGI task cancellation on each side of durable commit."""
import asyncio
import json
from contextlib import asynccontextmanager

import httpx
import psycopg
import pytest

from tests.test_api_projects_db import api as project_api, WORKSPACE_A, CREATE, _h
from tests.test_owned_api_process_restart_db import project_rows
from tests.owned_api_evidence import record_property


@pytest.mark.parametrize('phase', ['before-commit', 'after-commit'])
def test_owned_cancelled_original_request_rolls_back_or_replays_committed_result(project_api, seeded, monkeypatch, record_property, phase):
    from buyeros_api.api import deps
    key = 'owned-cancelled-project-' + phase
    path = f'/v1/workspaces/{WORKSPACE_A}/projects'
    headers = _h(key=key)
    before = project_rows(seeded, key)
    original_scoped = deps.tenant_scoped
    result = {}

    async def scenario():
        reached = asyncio.Event()
        never = asyncio.Event()
        @asynccontextmanager
        async def uncommitted(workspace_id):
            async with original_scoped(workspace_id) as session:
                yield session
                await session.flush()  # original writes exist but remain uncommitted
                reached.set()
                await never.wait()
        async def committed(scope, receive, send):
            async def withhold(message):
                if scope['type'] == 'http' and message['type'] == 'http.response.start':
                    result['withheld_status'] = message['status']
                    reached.set()
                    await never.wait()
                await send(message)
            await project_api.app(scope, receive, withhold)
        if phase == 'before-commit':
            monkeypatch.setattr(deps, 'tenant_scoped', uncommitted)
        app = project_api.app if phase == 'before-commit' else committed
        async with project_api.app.router.lifespan_context(project_api.app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://owned.test') as client:
                request = asyncio.create_task(client.post(path, headers=headers, json=CREATE))
                try:
                    await asyncio.wait_for(reached.wait(), timeout=10)
                    boundary = project_rows(seeded, key)
                    if phase == 'before-commit':
                        assert boundary == before
                    else:
                        assert result['withheld_status'] == 201
                        assert len(boundary['projects']) == len(before['projects']) + 1
                        assert boundary['idempotency'][0][3] == 'completed'
                    request.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await request
                finally:
                    if not request.done():
                        request.cancel()
                        await asyncio.gather(request, return_exceptions=True)
                    monkeypatch.setattr(deps, 'tenant_scoped', original_scoped)
                assert project_rows(seeded, key) == boundary
                with psycopg.connect(seeded) as db:
                    assert db.execute('SELECT sum(hits) FROM api_rate_windows WHERE workspace_id=%s', (WORKSPACE_A,)).fetchone() == (1,)
                engines = [deps.get_engine(), deps.get_rate_engine()]
                assert all(engine.pool.checkedout() == 0 for engine in engines)
                # Reconcile durable state first, then use only the original key/body.
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=project_api.app), base_url='http://owned.test') as recovered:
                    response = await recovered.post(path, headers=headers, json=CREATE)
                    assert response.status_code == 201, response.text
                    once = project_rows(seeded, key)
                    assert len(once['projects']) == len(before['projects']) + 1
                    assert len(once['audit']) == len(before['audit']) + 1
                    assert len(once['idempotency']) == 1
                    if phase == 'after-commit':
                        assert once == boundary
                        assert response.json()['data'] == boundary['idempotency'][0][5]['data']
                    replay = await recovered.post(path, headers=headers, json=CREATE)
                    assert replay.status_code == 201 and replay.json()['data'] == response.json()['data']
                    assert project_rows(seeded, key) == once
                assert all(engine.pool.checkedout() == 0 for engine in engines)
                result.update(boundary=boundary, final_rows=once, response=response.json(),
                              request_cancelled=request.cancelled(), checked_out_after=[0, 0])
    asyncio.run(scenario())
    record_property('owned_evidence', json.dumps(dict(phase=phase, live_acceptance=False,
        cancellation='explicit ASGI task.cancel; not an inferred browser disconnect', **result), default=str, sort_keys=True))
