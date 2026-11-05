"""Connection policy and refresh races on the actual0062 migration and grants."""
import importlib
import uuid
import pytest


def owner():
    assert importlib.util.find_spec('buyeros_api.services.xverum_connections'), 'project connection owner missing'
    return importlib.import_module('buyeros_api.services.xverum_connections')


def test_connection_binding_is_public_metadata_only():
    owner()
    from buyeros_api.sales.contracts import ConnectionBinding
    row=ConnectionBinding(id=uuid.uuid4(),generation=1,version=1,account_ref='account',
        tariff_version='v1',project_ids=[uuid.uuid4()],status='connected')
    assert set(row.model_dump())=={'id','generation','version','account_ref','tariff_version','project_ids','status'}


@pytest.mark.asyncio
async def test_live_credential_provider_disabled():
    m=owner()
    with pytest.raises(m.ApiError) as error:await m.CREDENTIAL_PROVIDER.resolve(None)
    assert error.value.code=='XVERUM_CONFIGURATION_REQUIRED'
    await m.CREDENTIAL_PROVIDER.revoke_local(None)


def test_process_local_refresh_provider_cannot_activate(monkeypatch):
    m=owner()
    class Unsafe:
        enabled=True
        durable_generation_singleflight=False
    monkeypatch.setattr(m,'CREDENTIAL_PROVIDER',Unsafe())
    with pytest.raises(m.ApiError):m.provider()


@pytest.mark.asyncio
async def test_uninstalled_schema_fails_closed():
    m=owner()
    class Session:
        async def execute(self,query):return self
        def scalar_one(self):return False
    with pytest.raises(m.ApiError) as caught:await m.require_schema(Session())
    assert caught.value.code=='XVERUM_SCHEMA_NOT_READY'


@pytest.fixture
def provisional_pg(isolated_seeded):
    """Historical fixture name; now uses ONLY actual0062 DDL and grants."""
    import psycopg
    with psycopg.connect(isolated_seeded) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0065_sales_lifecycle'
    return isolated_seeded


@pytest.fixture
def connection_case(provisional_pg,request,monkeypatch):
    from tests.test_sales_execution_db import execution_api
    # Request the existing authenticated fixture after provisional table setup.
    client=request.getfixturevalue('execution_api')
    import psycopg
    from types import SimpleNamespace
    from tests.test_buyer_review_db import WORKSPACE_A,PROJECT_A,ADMIN
    from buyeros_api.sales.contracts import Scope
    cid=uuid.uuid4();account=uuid.uuid4();ws=uuid.UUID(WORKSPACE_A);project=uuid.UUID(PROJECT_A)
    actor=uuid.uuid5(uuid.NAMESPACE_URL,ADMIN)
    with psycopg.connect(provisional_pg) as db:
        db.execute("INSERT INTO xverum_credit_accounts(id,workspace_id,account_ref,credit_limit) VALUES(%s,%s,'synthetic-account',0)",(account,ws))
        db.execute("INSERT INTO xverum_connections(id,workspace_id,generation,version,account_ref,tariff_version,secret_ref,status,configured_by) VALUES (%s,%s,1,1,'synthetic-account','fixture-v1',%s,'connected',%s)",(cid,ws,uuid.uuid4(),actor))
        db.execute('INSERT INTO xverum_project_assignments(id,workspace_id,connection_id,project_id) VALUES(%s,%s,%s,%s)',(uuid.uuid4(),ws,cid,project))
    return SimpleNamespace(client=client,dsn=provisional_pg,id=cid,account=account,ws=ws,project=project,
        scope=Scope(workspace_id=ws,project_id=project,actor_id=actor),
        path=f'/v1/workspaces/{ws}/projects/{project}/xverum/connections')


# Fixture import only, no execution/model/credit setup is requested.
from tests.test_sales_execution_db import execution_api


def pg(case,fn):
    from sqlalchemy.ext.asyncio import create_async_engine
    from buyeros_api.execution.engine import run_async,async_database_url
    from buyeros_api.db.session import tenant_session
    from tests.conftest import runtime_role_dsn
    async def run():
        engine=create_async_engine(async_database_url(runtime_role_dsn(case.dsn)))
        try:return await fn(lambda:tenant_session(engine,case.ws))
        finally:await engine.dispose()
    return run_async(run())


def headers(subject=None,version=1,key='xverum-fixture-key'):
    from tests import auth_fixtures as fx
    from tests.test_buyer_review_db import ADMIN
    return {'Authorization':'Bearer '+fx.make_token(sub=subject or ADMIN),'If-Match':f'"{version}"','Idempotency-Key':key}


def test_postgres_admin_assignment_versions_replay_and_scope(connection_case):
    c=connection_case
    from tests.test_buyer_review_db import OPERATOR,PROJECT_B
    url=c.path+f'/{c.id}/assignment'
    body={'project_ids':[str(c.project)],'expected_generation':1}
    assert c.client.put(url,json=body,headers=headers(OPERATOR)).status_code==404
    foreign=c.client.put(url,json={**body,'project_ids':[PROJECT_B]},headers=headers())
    assert foreign.status_code==404
    response=c.client.put(url,json=body,headers=headers())
    assert response.status_code==200,response.text
    assert response.json()['data']['generation']==2
    assert response.headers['etag']=='"2"' and response.headers['cache-control']=='no-store'
    assert 'secret_ref' not in response.text
    replay=c.client.put(url,json=body,headers=headers())
    assert replay.status_code==200 and replay.json()['data']==response.json()['data']
    stale=c.client.put(url,json=body,headers=headers(key='different-key'))
    assert stale.status_code==409


def test_postgres_foreign_generation_and_cross_project_cannot_dispatch(connection_case,monkeypatch):
    c=connection_case;m=owner()
    import psycopg
    other_project=uuid.uuid4()
    with psycopg.connect(c.dsn) as db:
        db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) VALUES (%s,%s,'Other','Synthetic','Fixture','{US}','{en}',1)",(other_project,c.ws))
    from buyeros_api.sales.contracts import ConnectionBinding
    expected=ConnectionBinding(id=c.id,generation=2,version=1,account_ref='synthetic-account',tariff_version='fixture-v1',project_ids=[c.project],status='connected')
    async def run(factory):
        with pytest.raises(m.ApiError) as err:await m.call_xverum(factory,c.scope,expected,'get_email_xverum',{'id':'1'})
        assert err.value.code=='STALE_REVISION'
        async with factory() as session:
            foreign=c.scope.model_copy(update={'project_id':other_project})
            with pytest.raises(m.ApiError):await m.require_xverum_connection(session,foreign)
    pg(c,run)


def test_disconnect_wins_over_late_refresh(connection_case,monkeypatch):
    import asyncio
    c=connection_case;m=owner()
    from buyeros_api.sales.contracts import SecretHandle
    started=asyncio.Event();release=asyncio.Event()
    class Provider:
        enabled=True;durable_generation_singleflight=True
        async def refresh(self,binding):
            started.set();await release.wait()
            return SecretHandle(connection_id=binding.id,generation=binding.generation+1,token='SYNTHETIC')
        async def resolve(self,binding):raise AssertionError('disconnected credential must never resolve')
        async def revoke_local(self,binding):raise RuntimeError('owned provider outage')
    class Transport:
        calls=0
        async def activate(self,handle):return {}
        async def call(self,*args):self.calls+=1;raise AssertionError('must not dispatch')
    transport=Transport()
    monkeypatch.setattr(m,'CREDENTIAL_PROVIDER',Provider())
    monkeypatch.setattr(m,'XverumTransport',lambda **kwargs:transport)
    async def run(factory):
        async with factory() as session:
            old,replay=await m.prepare_rotation(session,c.scope,c.id,1,'rotate-key',1)
        task=asyncio.create_task(m.refresh_credential(old));await started.wait()
        # Independent transaction finishes while external refresh is waiting.
        async with factory() as session:
            disconnected=await asyncio.wait_for(m.disconnect_xverum(session,c.scope,1,'disconnect-key'),2)
        assert not await m.revoke_local(disconnected)
        release.set();handle=await task
        with pytest.raises(m.ApiError):
            async with factory() as session:await m.publish_rotation(session,c.scope,old,handle,1,'rotate-key')
        async with factory() as session:
            row=await m.load(session,c.scope)
            assert row.status=='disconnected'
        with pytest.raises(m.ApiError):await m.call_xverum(factory,c.scope,old,'get_email_xverum',{'id':'1'})
        assert transport.calls==0
    pg(c,run)


def test_postgres_disconnect_route_survives_provider_outage(connection_case,monkeypatch):
    c=connection_case;m=owner()
    class Down:
        async def revoke_local(self,binding):raise RuntimeError('PRIVATE_BODY')
    monkeypatch.setattr(m,'CREDENTIAL_PROVIDER',Down())
    response=c.client.post(c.path+f'/{c.id}/disconnect',headers=headers())
    assert response.status_code==200,response.text
    assert response.json()['data']['status']=='disconnected'
    assert 'PRIVATE_BODY' not in response.text
    assert c.client.post(c.path+f'/{c.id}/disconnect',headers=headers()).json()['data']==response.json()['data']


def test_postgres_installed_real_schema_returns_no_store(execution_api):
    from tests.test_buyer_review_db import WORKSPACE_A,PROJECT_A
    response=execution_api.get(f'/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/xverum/connections',headers=headers())
    assert response.status_code==200,response.text
    assert response.json()['data']['connections']==[]
    assert response.headers['cache-control']=='no-store'


def test_postgres_prior_schema_returns_sanitized_503(execution_api,isolated_seeded):
    from alembic import command
    from tests.test_conversation_threads_db import config
    from tests.test_buyer_review_db import WORKSPACE_A,PROJECT_A
    command.downgrade(config(),'0061_sales_outputs')
    response=execution_api.get(f'/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/xverum/connections',headers=headers())
    assert response.status_code==503,response.text
    assert response.json()['code']=='XVERUM_SCHEMA_NOT_READY'
    assert response.headers['cache-control']=='no-store'


def test_postgres_competing_assignments_have_one_project_winner(connection_case):
    import asyncio,psycopg
    from buyeros_api.sales.contracts import ConnectionAssignment
    c=connection_case;m=owner();second=uuid.uuid4()
    with psycopg.connect(c.dsn) as db:
        db.execute('DELETE FROM xverum_project_assignments')
        db.execute("INSERT INTO xverum_connections(id,workspace_id,generation,version,account_ref,tariff_version,secret_ref,status,configured_by) VALUES(%s,%s,1,1,'synthetic-account','fixture-v1',%s,'connected',%s)",(second,c.ws,uuid.uuid4(),c.scope.actor_id))
    async def run(factory):
        async def assign(cid):
            try:
                async with factory() as s:
                    result=await m.assign_xverum(s,c.scope,cid,ConnectionAssignment(project_ids=[c.project],expected_generation=1),1,str(cid))
                    assert result.generation==result.version==2
                return 1
            except m.ApiError as e:
                assert e.code=='CONNECTION_ASSIGNED'
                return 0
        assert sum(await asyncio.gather(assign(c.id),assign(second)))==1
    pg(c,run)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT count(*) FROM xverum_project_assignments').fetchone()[0]==1


def test_postgres_tenant_fk_and_worker_readonly_connection(connection_case):
    import psycopg
    from tests.test_buyer_review_db import PROJECT_B
    c=connection_case
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with psycopg.connect(c.dsn) as db:
            db.execute('INSERT INTO xverum_project_assignments(id,workspace_id,connection_id,project_id) VALUES(%s,%s,%s,%s)',(uuid.uuid4(),c.ws,c.id,PROJECT_B))
    with psycopg.connect(c.dsn) as db:
        db.execute('SET LOCAL ROLE buyeros_worker')
        assert db.execute('SELECT current_user').fetchone()[0]=='buyeros_worker'
        db.execute("SELECT set_config('app.workspace_id',%s,true)",(str(c.ws),))
        assert db.execute('SELECT public.buyeros_xverum_connections_ready()').fetchone()[0] is True
        assert db.execute('SELECT id FROM xverum_connections').fetchone()[0]==c.id
        with pytest.raises(psycopg.errors.InsufficientPrivilege):db.execute("UPDATE xverum_connections SET status='disconnected'")


@pytest.mark.parametrize('drift',[False,True])
def test_postgres_rotation_uses_actual_schema_guard_and_replay(connection_case,monkeypatch,drift):
    import json,httpx
    from tests.test_xverum_mcp import advertised
    from buyeros_api.sales.contracts import SecretHandle
    c=connection_case;m=owner();calls=[]
    class Staged:
        enabled=True;durable_generation_singleflight=True
        async def refresh(self,binding):
            return SecretHandle(connection_id=binding.id,generation=binding.generation+1,token='SYNTHETIC_ROTATION')
    def handle(req):
        body=json.loads(req.content);calls.append(body['method'])
        if body['method']=='initialize':return httpx.Response(200,json={'jsonrpc':'2.0','id':1,'result':{'protocolVersion':'2025-06-18','capabilities':{'tools':{}}}})
        if body['method']=='notifications/initialized':return httpx.Response(202)
        assert body['method']=='tools/list' # activation never issues a billable call
        schemas=advertised()
        if drift:schemas['tools'][0]['inputSchema']['required'].append('surprise')
        return httpx.Response(200,json={'jsonrpc':'2.0','id':2,'result':schemas})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(**kw,transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(m,'CREDENTIAL_PROVIDER',Staged())
    url=c.path+f'/{c.id}/rotate';body={'expected_generation':1}
    response=c.client.post(url,json=body,headers=headers())
    assert response.status_code==(503 if drift else 200),response.text
    assert calls==['initialize','notifications/initialized','tools/list']
    if not drift:
        assert response.json()['data']['generation']==2 and response.json()['data']['status']=='connected'
        replay=c.client.post(url,json=body,headers=headers())
        assert replay.status_code==200 and replay.json()['data']==response.json()['data']
        assert len(calls)==3
    else:
        result=c.client.get(c.path,headers=headers()).json()['data']['connections'][0]
        assert result['generation']==1


def test_postgres_replay_rechecks_current_admin_membership(connection_case):
    import psycopg
    c=connection_case;url=c.path+f'/{c.id}/disconnect'
    assert c.client.post(url,headers=headers()).status_code==200
    with psycopg.connect(c.dsn) as db:
        db.execute("UPDATE memberships SET roles=ARRAY['viewer'] WHERE workspace_id=%s AND user_id=%s",(c.ws,c.scope.actor_id))
    denied=c.client.post(url,headers=headers())
    assert denied.status_code==404 and denied.headers['cache-control']=='no-store'


def test_postgres_competing_refresh_successors_have_one_generation_cas_winner(connection_case):
    import asyncio
    from buyeros_api.sales.contracts import SecretHandle
    c=connection_case;m=owner()
    async def run(factory):
        async with factory() as session:old=await m.require_xverum_connection(session,c.scope)
        # Durable provider contract returns the SAME staged successor for this
        # binding/generation to both processes; this tests the application CAS.
        handle=SecretHandle(connection_id=c.id,generation=2,token='SYNTHETIC')
        async def publish(key):
            try:
                async with factory() as session:return await m.publish_rotation(session,c.scope,old,handle,1,key)
            except m.ApiError as exc:return exc.code
        results=await asyncio.gather(publish('rotation-one'),publish('rotation-two'))
        assert sum(not isinstance(r,str) for r in results)==1
        assert 'STALE_REVISION' in results
        async with factory() as session:
            current=await m.require_xverum_connection(session,c.scope)
            assert current.generation==2 and current.version==2
    pg(c,run)


@pytest.mark.parametrize('revoked',[False,True])
def test_postgres_current_binding_dispatch_and_recheck_before_tool(connection_case,monkeypatch,revoked):
    import json,httpx,psycopg
    from buyeros_api.sales.contracts import SecretHandle
    c=connection_case;m=owner();calls=[]
    class Provider:
        enabled=True;durable_generation_singleflight=True
        async def resolve(self,binding):return SecretHandle(connection_id=binding.id,generation=binding.generation,token='SYNTHETIC_CALL')
    def handle(req):
        body=json.loads(req.content);calls.append(body['method'])
        if body['method']=='initialize':
            # A second process revokes during initialization; the transport's
            # pre-dispatch callback must re-read committed authority.
            if revoked:
                with psycopg.connect(c.dsn) as db:db.execute("UPDATE xverum_connections SET status='disconnected',generation=generation+1 WHERE id=%s",(c.id,))
            return httpx.Response(200,json={'jsonrpc':'2.0','id':1,'result':{'protocolVersion':'2025-06-18','capabilities':{'tools':{}}}})
        if body['method']=='notifications/initialized':return httpx.Response(202)
        assert not revoked and body['method']=='tools/call'
        return httpx.Response(200,json={'jsonrpc':'2.0','id':2,'result':{'structuredContent':{
            'has_email':False,'emails':[],'credits_used':0,'credits_remaining':8,'request_id':'fixture-call'}}})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(**kw,transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(m,'CREDENTIAL_PROVIDER',Provider())
    async def run(factory):
        from buyeros_api.providers.xverum_mcp import XverumTransportError
        async with factory() as session:old=await m.require_xverum_connection(session,c.scope)
        if revoked:
            with pytest.raises(XverumTransportError) as caught:await m.call_xverum(factory,c.scope,old,'get_email_xverum',{'id':'1'})
            assert caught.value.definitely_nonaccepted
            assert calls==['initialize','notifications/initialized']
        else:
            result=await m.call_xverum(factory,c.scope,old,'get_email_xverum',{'id':'1'})
            assert result.request_id=='fixture-call' and result.projection.has_email is False
            assert calls==['initialize','notifications/initialized','tools/call']
    pg(c,run)
