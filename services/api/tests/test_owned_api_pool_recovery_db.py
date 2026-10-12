"""C61-25: configured API pools return cancelled slots with cleared RLS context."""
import asyncio
import json
import uuid
from contextlib import AsyncExitStack

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.conftest import runtime_role_dsn
from tests.test_api_tenant_isolation import WORKSPACE_A, WORKSPACE_B
from tests.owned_api_evidence import record_property
from tests.owned_api_process import wait_for_backend_exit
from tests.test_api_projects_db import api as project_api, OPERATOR, REVIEWER, _h


async def connection_context(connection):
    return (await connection.execute(text("SELECT pg_backend_pid(),current_setting('app.workspace_id',true),current_setting('app.user_id',true)"))).one()


def setup(monkeypatch, seeded):
    from buyeros_api.settings import get_settings
    monkeypatch.setenv('BUYEROS_DATABASE_URL', runtime_role_dsn(seeded))
    get_settings.cache_clear()


@pytest.mark.parametrize('kind', ['tenant', 'rate'])
def test_owned_cancelled_transaction_recycles_original_backend_without_tenant_or_partial_write(seeded, monkeypatch, record_property, kind):
    from buyeros_api.api import deps
    from buyeros_api.api.app import create_app
    from buyeros_api.db.session import tenant_session
    setup(monkeypatch, seeded)
    result = {}
    project = uuid.uuid4()
    async def scenario():
        app = create_app()
        async with app.router.lifespan_context(app):
            engine = deps.get_engine() if kind == 'tenant' else deps.get_rate_engine()
            entered = asyncio.Event()
            async def cancelled():
                async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                    pid = (await session.execute(text('SELECT pg_backend_pid()'))).scalar_one()
                    result['cancelled_pid'] = pid
                    await session.execute(text('INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) '
                        "VALUES (:id,:ws,'Owned cancelled','Owned','Owned',ARRAY['HK'],ARRAY['zh-HK'],1)"),
                        {'id': project, 'ws': uuid.UUID(WORKSPACE_A)})
                    entered.set()
                    await asyncio.Event().wait()
            request = asyncio.create_task(cancelled())
            try:
                await asyncio.wait_for(entered.wait(), timeout=10)
                assert engine.pool.checkedout() == 1
                with psycopg.connect(seeded) as db:
                    assert db.execute('SELECT count(*) FROM projects WHERE id=%s', (project,)).fetchone() == (0,)
                request.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await request
            finally:
                if not request.done():
                    request.cancel()
                    await asyncio.gather(request, return_exceptions=True)
            assert engine.pool.checkedout() == 0
            with psycopg.connect(seeded) as db:
                assert db.execute('SELECT count(*) FROM projects WHERE id=%s', (project,)).fetchone() == (0,)
                assert db.execute('SELECT state FROM pg_stat_activity WHERE pid=%s', (result['cancelled_pid'],)).fetchone() == ('idle',)
            async with engine.connect() as raw:
                no_scope = await connection_context(raw)
                assert no_scope[0] == result['cancelled_pid']
                assert no_scope[1] in (None, '') and no_scope[2] in (None, '')
                # Existing policies cast the cleared transaction-local GUC to UUID.
                # They fail closed with 22P02, rather than returning an empty list.
                with pytest.raises(DBAPIError) as denied:
                    await raw.execute(text('SELECT count(*) FROM projects'))
                assert denied.value.orig.sqlstate == '22P02'
                await raw.rollback()
            checks = []
            for workspace in (WORKSPACE_B, WORKSPACE_A, WORKSPACE_B):
                async with tenant_session(engine, uuid.UUID(workspace)) as session:
                    row = (await session.execute(text('SELECT pg_backend_pid(),current_user'))).one()
                    assert row[0] == result['cancelled_pid'] and row[1] == 'buyeros_api'
                    assert (await session.execute(text('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user'))).one() == (False, False)
                    rows = (await session.execute(text('SELECT DISTINCT workspace_id FROM projects'))).scalars().all()
                    assert rows == [uuid.UUID(workspace)]
                    checks.append((workspace, row, rows))
            with pytest.raises(DBAPIError) as forbidden:
                async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                    await session.execute(text('INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) '
                        "VALUES (:id,:ws,'Foreign','Owned','Owned',ARRAY['HK'],ARRAY['en'],1)"),
                        {'id': project, 'ws': uuid.UUID(WORKSPACE_B)})
            assert forbidden.value.orig.sqlstate == '42501'
            assert engine.pool.checkedout() == 0
            result.update(no_scope=no_scope, tenant_checks=checks, checked_out_after=0)
        assert not deps._ENGINES and not deps._RATE_ENGINES
        assert wait_for_backend_exit(seeded, [result['cancelled_pid']]) == []
        result['backend_remaining'] = []
    asyncio.run(scenario())
    record_property('owned_evidence', json.dumps(dict(kind=kind, live_acceptance=False, **result), default=str, sort_keys=True))


def test_owned_cancelled_directory_clears_populated_canonical_user_on_same_backend_before_other_actor(project_api, seeded, monkeypatch, record_property):
    import httpx
    from buyeros_api.api import deps
    from buyeros_api.services import workspace_directory
    actor_a = uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR)
    actor_b = uuid.uuid5(uuid.NAMESPACE_URL, REVIEWER)
    with psycopg.connect(seeded) as db:
        db.execute('DELETE FROM memberships WHERE user_id=%s', (actor_b,))
        db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES (%s,%s,%s,ARRAY['reviewer'],true)",
                   (uuid.uuid4(), WORKSPACE_B, actor_b))
    original = workspace_directory.list_authorized_workspaces
    result = {}
    async def scenario():
        from buyeros_api.api.auth import Principal
        from buyeros_api.db.session import workspace_directory_session
        from buyeros_api.services.identity_resolver import resolve_user_id
        from tests import auth_fixtures as fx
        reached = asyncio.Event()
        engine = deps.get_engine()
        async def populated():
            async with workspace_directory_session(engine) as session:
                canonical = await resolve_user_id(session, Principal(issuer=fx.ISSUER, subject=OPERATOR))
                assert canonical == actor_a
                page = await original(session, user_id=canonical, offset=0, limit=20)
                result['populated_user'] = (await session.execute(text("SELECT current_setting('app.user_id',true)"))).scalar_one()
                result['before_cancel'] = await connection_context(session)
                result['first_page'] = page
                reached.set()
                await asyncio.Event().wait()
        async with project_api.app.router.lifespan_context(project_api.app):
            request = asyncio.create_task(populated())
            try:
                await asyncio.wait_for(reached.wait(), timeout=10)
                assert result['populated_user'] == str(actor_a)
                assert result['before_cancel'][2] == str(actor_a), 'pool observer must see the actual populated directory user'
                assert [i['id'] for i in result['first_page']['items']] == [WORKSPACE_A]
            finally:
                request.cancel()
                await asyncio.gather(request, return_exceptions=True)
            assert request.cancelled()
            assert engine.pool.checkedout() == 0
            async with engine.connect() as raw:
                context = await connection_context(raw)
                assert context[0] == result['before_cancel'][0]
                assert context[1] in (None, '') and context[2] in (None, '')
                with pytest.raises(DBAPIError) as denied:
                    await raw.execute(text('SELECT public.buyeros_workspace_directory(:actor,0,20)'), {'actor': actor_a})
                assert denied.value.orig.sqlstate == '42501'
                await raw.rollback()
                result['after_cancel'] = context
            async def observed_directory(session, **kwargs):
                page = await original(session, **kwargs)
                result.setdefault('signed_contexts', []).append(await connection_context(session))
                return page
            monkeypatch.setattr(workspace_directory, 'list_authorized_workspaces', observed_directory)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=project_api.app), base_url='http://owned.test') as client:
                responses = []
                for subject, actor, workspace in [(REVIEWER, actor_b, WORKSPACE_B), (OPERATOR, actor_a, WORKSPACE_A)]:
                    response = await client.get('/v1/workspaces', headers=_h(subject))
                    assert response.status_code == 200, response.text
                    assert [i['id'] for i in response.json()['data']['items']] == [workspace]
                    assert result['signed_contexts'][-1] == (result['before_cancel'][0], '', str(actor))
                    assert engine.pool.checkedout() == 0
                    responses.append(response.json())
            async with engine.connect() as raw:
                final_context = await connection_context(raw)
                assert final_context[0] == result['before_cancel'][0]
                assert final_context[1] in (None, '') and final_context[2] in (None, '')
            result.update(signed_responses=responses, after_success=final_context)
        assert wait_for_backend_exit(seeded, [result['before_cancel'][0]]) == []
        result['backend_remaining'] = []
    asyncio.run(scenario())
    record_property('owned_evidence', json.dumps(dict(live_acceptance=False, **result), default=str, sort_keys=True))


@pytest.mark.parametrize('kind', ['tenant', 'rate'])
def test_owned_cancelled_pool_waiter_cannot_leak_a_slot_and_owned_request_succeeds_after_return(seeded, monkeypatch, record_property, kind):
    from buyeros_api.api import deps
    from buyeros_api.api.app import create_app
    from buyeros_api.db.session import tenant_session
    setup(monkeypatch, seeded)
    result = {}
    async def scenario():
        app = create_app()
        async with app.router.lifespan_context(app):
            engine = deps.get_engine() if kind == 'tenant' else deps.get_rate_engine()
            capacity = engine.pool.size() + engine.pool._max_overflow
            assert capacity > 0
            pids = []
            async with AsyncExitStack() as held:
                for _ in range(capacity):
                    session = await held.enter_async_context(tenant_session(engine, uuid.UUID(WORKSPACE_A)))
                    pids.append((await session.execute(text('SELECT pg_backend_pid()'))).scalar_one())
                assert len(set(pids)) == engine.pool.checkedout() == capacity
                attempting = asyncio.Event()
                async def waiting():
                    attempting.set()
                    async with tenant_session(engine, uuid.UUID(WORKSPACE_B)) as session:
                        await session.execute(text('SELECT 1'))
                        raise AssertionError('all original configured slots are still held')
                waiter = asyncio.create_task(waiting())
                await attempting.wait()
                assert not waiter.done()
                waiter.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await waiter
                assert engine.pool.checkedout() == capacity
            assert engine.pool.checkedout() == 0
            async with tenant_session(engine, uuid.UUID(WORKSPACE_B)) as success:
                rows = (await success.execute(text('SELECT DISTINCT workspace_id FROM projects'))).scalars().all()
                assert rows == [uuid.UUID(WORKSPACE_B)]
                success_pid = (await success.execute(text('SELECT pg_backend_pid()'))).scalar_one()
                assert success_pid in pids
            assert engine.pool.checkedout() == 0
            result.update(capacity=capacity, held_pids=pids, success_pid=success_pid,
                          cancelled_waiter=waiter.cancelled(), checked_out_after=0)
        assert wait_for_backend_exit(seeded, pids) == []
        result['backend_remaining'] = []
    asyncio.run(scenario())
    record_property('owned_evidence', json.dumps(dict(kind=kind, live_acceptance=False, **result), default=str, sort_keys=True))
