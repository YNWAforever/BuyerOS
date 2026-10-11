"""C19 native API preparation and worker submission. All vendor data is synthetic."""
import asyncio,importlib,json,uuid
from dataclasses import replace
from decimal import Decimal
import httpx,psycopg,pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.db.session import tenant_session
from buyeros_api.db.outbox import OutboxEvent
from buyeros_api.execution.external_runner import execute_external
from buyeros_api.providers.live_search import PostgresSearchReceipts,LiveSearchAdapter,BraveSearchClient
from buyeros_api.providers.registry import ProviderRegistration
from tests.test_live_search_adapter import capability
from tests.test_api_projects_db import api as project_api,WORKSPACE_A,OPERATOR
from tests.test_run_admission_integration_db import admission_case,_post
from tests.conftest import runtime_role_dsn
from tests.cutover_fixtures import role_dsn
from tests.test_cloudflare_bridge_db import machine_keys,signed_headers

@pytest.fixture
def migrated(isolated_migrated):return isolated_migrated

def preparation():
    spec=importlib.util.find_spec('buyeros_api.services.run_search')
    assert spec is not None,'C61-19 API run search preparation is missing'
    fn=getattr(importlib.import_module('buyeros_api.services.run_search'),'prepare_run_search',None)
    assert callable(fn),'C61-19 atomic frozen run request port is missing'
    return fn

@pytest.fixture
def run_case(admission_case,monkeypatch,request):
    api,dsn=admission_case
    if getattr(request,'param',None)=='native':
        from buyeros_api.settings import get_settings
        with psycopg.connect(dsn) as db:
            db.execute("UPDATE worker_runtime_control SET backend='cloudflare',enabled=true,epoch=epoch+1,active_owner=NULL,active_until=NULL WHERE singleton=1")
        monkeypatch.setenv('BUYEROS_CLOUDFLARE_EXECUTION_ENABLED','true');get_settings.cache_clear()
    reply=_post(api,key='c19-run-search-preparation');assert reply.status_code==202,reply.text
    run=uuid.UUID(reply.json()['data']['id']);ws=uuid.UUID(WORKSPACE_A);actor=uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR)
    cap=replace(capability(),idempotency='verified',status='verified')
    from buyeros_api.providers import base
    monkeypatch.setattr(base,'SELECTED_LIVE_PROVIDERS',frozenset({'brave-search'}))
    from buyeros_api.providers import registry
    scope=ProviderRegistration(cap,lambda:None,('synthetic:run-search-owned-fixture',),frozenset({'market','language'}),(('US',('en',)),('HK',('zh-HK',))))
    monkeypatch.setattr(registry,'SELECTED_LIVE_PROVIDERS',frozenset({'brave-search'}))
    monkeypatch.setattr(registry,'DEFAULT_REGISTRY',registry.ProviderRegistry((scope,)))
    with psycopg.connect(dsn) as db:
        project,snapshot=db.execute('SELECT project_id,execution_snapshot FROM search_runs WHERE id=%s',(run,)).fetchone()
        # Explicit owned fixture overlay; default production registry remains empty.
        snapshot['capability'].update(provider=cap.provider,price_version=cap.pricing_version,
            receipt_contract_hash=ProviderRegistration(cap,lambda:None).contract_hash,registry_contract_hash=scope.contract_hash,
            market_languages={market:list(languages) for market,languages in scope.market_languages})
        db.execute('UPDATE search_runs SET execution_snapshot=%s::jsonb WHERE id=%s',(json.dumps(snapshot),run))
        db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 WHERE payload->>'run_id'=%s",(str(run),))
        outbox,key,payload=db.execute("SELECT id,intent_key,payload FROM outbox_events WHERE payload->>'run_id'=%s",(str(run),)).fetchone()
        db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
    c=dict(api=api,dsn=dsn,run=run,workspace=ws,actor=actor,project=project,cap=cap,outbox=outbox,key=key,payload=payload,calls=[])
    yield c
    with psycopg.connect(dsn) as db:
        db.execute("DELETE FROM worker_steps WHERE outbox_id IN(SELECT id FROM outbox_events WHERE id=%s OR payload->>'operation_id' IN(SELECT id::text FROM provider_operations WHERE intent_key=%s))",(outbox,key))
        db.execute('DELETE FROM receipt_source_bindings WHERE source_id IN(SELECT id FROM source_documents WHERE run_id=%s)',(run,))
        db.execute('DELETE FROM raw_candidates WHERE run_id=%s',(run,));db.execute('DELETE FROM source_documents WHERE run_id=%s',(run,))
        db.execute('DELETE FROM search_receipts WHERE outbox_id=%s',(outbox,))
        db.execute('DELETE FROM budget_reservation_allocations WHERE reservation_id IN(SELECT id FROM budget_reservations WHERE operation_id IN(SELECT id FROM provider_operations WHERE intent_key=%s))',(key,))
        db.execute('DELETE FROM budget_reservations WHERE operation_id IN(SELECT id FROM provider_operations WHERE intent_key=%s)',(key,))
        db.execute('DELETE FROM provider_operations WHERE intent_key=%s',(key,))

def prepare(c,**kw):
    fn=preparation()
    async def exercise():
        engine=create_async_engine(async_database_url(runtime_role_dsn(c['dsn'])))
        try:
            async with tenant_session(engine,c['workspace']) as session:
                return await fn(session,workspace_id=c['workspace'],outbox_id=c['outbox'],generation=kw.get('generation',1),capability=kw.get('capability',c['cap']))
        finally:await engine.dispose()
    return asyncio.run(exercise())

def observe(c):
    with psycopg.connect(c['dsn']) as db:
        return dict(operations=db.execute('SELECT count(*) FROM provider_operations WHERE workspace_id=%s',(c['workspace'],)).fetchone()[0],
            receipts=db.execute('SELECT count(*) FROM search_receipts WHERE workspace_id=%s',(c['workspace'],)).fetchone()[0],
            holds=db.execute('SELECT count(*) FROM budget_reservations WHERE workspace_id=%s',(c['workspace'],)).fetchone()[0],
            run=db.execute('SELECT status,usage_counters,first_dispatch_at FROM search_runs WHERE id=%s',(c['run'],)).fetchone())

def test_run_request_prepared_atomically_on_original_intent_once(run_case):
    c=run_case;a=prepare(c);b=prepare(c);assert a==b and a.request.key==c['key'] and a.intent.role=='company'
    state=observe(c);assert state['operations']==state['receipts']==state['holds']==1
    assert state['run'][0]=='running' and state['run'][1]['queries']==state['run'][1]['in_flight']==1
    assert state['run'][1]['pages']==0 and state['run'][2] is None
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT payload FROM outbox_events WHERE id=%s',(c['outbox'],)).fetchone()==(c['payload'],)
        assert db.execute('SELECT intent_key,state FROM search_receipts WHERE id=%s',(a.receipt_id,)).fetchone()==(c['key'],'prepared')
        assert db.execute('SELECT remaining_hold FROM budget_reservations WHERE operation_id=%s',(a.operation_id,)).fetchone()==(Decimal('0.005000'),)

@pytest.mark.parametrize('change',['actor','policy','offer','icp','epoch','query-index','contract','budget','limit','generation','event-kind'])
def test_run_request_current_guards_rollback_every_write(run_case,change):
    c=run_case
    with psycopg.connect(c['dsn']) as db:
        if change=='actor':db.execute('UPDATE memberships SET active=false WHERE workspace_id=%s AND user_id=%s',(c['workspace'],c['actor']))
        elif change=='policy':db.execute("UPDATE policy_decisions SET status='blocked' WHERE workspace_id=%s",(c['workspace'],))
        elif change=='offer':db.execute('UPDATE projects SET offer_revision=offer_revision+1 WHERE id=%s',(c['project'],))
        elif change=='icp':db.execute('UPDATE icp_versions SET approved_at=NULL WHERE project_id=%s',(c['project'],))
        elif change=='epoch':db.execute('UPDATE worker_runtime_control SET epoch=epoch+1 WHERE singleton=1')
        elif change=='query-index':db.execute("UPDATE outbox_events SET payload=jsonb_set(payload,'{query_index}','true') WHERE id=%s",(c['outbox'],))
        elif change=='contract':db.execute("UPDATE search_runs SET execution_snapshot=jsonb_set(execution_snapshot,'{capability,receipt_contract_hash}','\"other\"') WHERE id=%s",(c['run'],))
        elif change=='budget':db.execute('UPDATE budget_accounts SET approved_limit=0 WHERE scope=\'run\' AND scope_id=%s',(c['run'],))
        elif change=='limit':db.execute("UPDATE search_runs SET usage_counters=jsonb_set(usage_counters,'{queries}',to_jsonb((limits->>'max_queries_per_run')::int)) WHERE id=%s",(c['run'],))
        elif change=='generation':db.execute('UPDATE outbox_events SET fencing_generation=2 WHERE id=%s',(c['outbox'],))
        elif change=='event-kind':db.execute("UPDATE outbox_events SET event_type='run.fit' WHERE id=%s",(c['outbox'],))
    before=observe(c)
    from buyeros_api.api.errors import ApiError
    with pytest.raises((ValueError,ApiError)):prepare(c)
    assert observe(c)==before and not c['calls']

async def dispatch(c,prepared,*,unknown=False):
    engine=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')))
    def response(req):
        c['calls'].append(req)
        if unknown:raise httpx.ReadTimeout('synthetic lost response',request=req)
        return httpx.Response(200,json={'web':{'results':[{'url':'https://sensors.example.test/company','title':'Unreviewed sensors','description':'ONLY_SEARCH_METADATA_C19'}]}})
    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as http:
            adapter=LiveSearchAdapter(capability=c['cap'],receipts=PostgresSearchReceipts(engine,c['workspace'],c['cap']),
                client=BraveSearchClient(api_key='synthetic-offline-only',http=http,language_codes={'en':'en'},api_version='2026-10-01'))
            return await execute_external(engine,c['workspace'],prepared.operation_id,1,adapter,prepared.intent,environment='test')
    finally:await engine.dispose()

def test_run_request_received_metadata_intake_and_unknown_hold_remain(run_case):
    c=run_case;a=prepare(c);assert asyncio.run(dispatch(c,a))=='accepted';assert len(c['calls'])==1
    async def consume():
        from buyeros_api.services.search_intake import ingest_received_search
        from buyeros_api.execution.provider_context import terminal_business_outcome
        engine=create_async_engine(async_database_url(runtime_role_dsn(c['dsn'])))
        try:
            async with tenant_session(engine,c['workspace']) as session:
                result=await ingest_received_search(session,workspace_id=c['workspace'],run_id=c['run'],receipt_id=a.receipt_id,capability=c['cap'])
                event=(await session.execute(select(OutboxEvent).where(OutboxEvent.id==c['outbox']))).scalar_one()
                outcome=await terminal_business_outcome(session,event)
                assert outcome.state=='reconcile' and outcome.code=='PROVIDER_UNKNOWN'
                return result
        finally:await engine.dispose()
    result=asyncio.run(consume());assert result['candidate_count']==1 and asyncio.run(consume())==result
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT canonical_company_id,merge_state FROM raw_candidates WHERE run_id=%s',(c['run'],)).fetchone()==(None,'needs_review')
        assert db.execute('SELECT count(*) FROM companies').fetchone()==(0,)
        assert db.execute('SELECT count(*) FROM cost_events').fetchone()==(0,)
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(a.operation_id,)).fetchone()==('active',Decimal('0.005000'))
    with pytest.raises(ValueError):prepare(c)
    assert len(c['calls'])==1

def test_run_request_lost_response_never_reprepares_or_resubmits(run_case):
    c=run_case;a=prepare(c);assert asyncio.run(dispatch(c,a,unknown=True))=='unknown'
    with pytest.raises(ValueError):prepare(c)
    assert asyncio.run(dispatch(c,a))=='stale' and len(c['calls'])==1
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT state FROM search_receipts WHERE id=%s',(a.receipt_id,)).fetchone()==('unknown',)
        assert db.execute('SELECT count(*) FROM outbox_events WHERE event_type=\'provider.reconcile\'').fetchone()==(1,)
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(a.operation_id,)).fetchone()==('active',Decimal('0.005000'))

def test_live_admission_freezes_complete_receipt_contract(run_case):
    c=run_case
    from tests.test_run_admission_integration_db import CAPABILITY
    from buyeros_api.api.routes.runs import selected_run_capability
    contract=ProviderRegistration(c['cap'],lambda:None).contract_hash
    from buyeros_api.providers import registry
    scope=registry.DEFAULT_REGISTRY.search_run_capability(environment='production')
    caps={**CAPABILITY,'provider':c['cap'].provider,'price_version':c['cap'].pricing_version,'receipt_contract_hash':contract,
          'registry_contract_hash':scope['registry_contract_hash'],'market_languages':scope['market_languages']}
    c['api'].app.dependency_overrides[selected_run_capability]=lambda:(caps,'test')
    reply=_post(c['api'],key='c19-complete-contract');assert reply.status_code==202,reply.text
    with psycopg.connect(c['dsn']) as db:
        frozen=db.execute('SELECT execution_snapshot FROM search_runs WHERE id=%s',(uuid.UUID(reply.json()['data']['id']),)).fetchone()[0]
        assert frozen['capability']['receipt_contract_hash']==contract

@pytest.mark.parametrize('contract',[None,'not-a-hash'])
def test_live_admission_missing_contract_stays_unavailable(run_case,contract):
    c=run_case
    from tests.test_run_admission_integration_db import CAPABILITY
    from buyeros_api.api.routes.runs import selected_run_capability
    caps={**CAPABILITY,'provider':c['cap'].provider,'price_version':c['cap'].pricing_version}
    if contract is not None:caps['receipt_contract_hash']=contract
    c['api'].app.dependency_overrides[selected_run_capability]=lambda:(caps,'test')
    reply=_post(c['api'],key='c19-incomplete-contract');assert reply.status_code==503,reply.text
    with psycopg.connect(c['dsn']) as db:assert db.execute('SELECT count(*) FROM search_runs WHERE workspace_id=%s',(c['workspace'],)).fetchone()==(1,)

@pytest.mark.parametrize('change',['actor','query','contract','run-allocation'])
def test_run_prepared_receipt_rechecks_before_worker_http(run_case,change):
    c=run_case;a=prepare(c)
    with psycopg.connect(c['dsn']) as db:
        if change=='actor':db.execute('UPDATE memberships SET active=false WHERE workspace_id=%s AND user_id=%s',(c['workspace'],c['actor']))
        elif change=='query':db.execute("UPDATE search_runs SET execution_snapshot=jsonb_set(execution_snapshot,'{query_plan,queries,0,query}','\"changed after preparation\"') WHERE id=%s",(c['run'],))
        elif change=='run-allocation':db.execute("DELETE FROM budget_reservation_allocations WHERE reservation_id IN(SELECT id FROM budget_reservations WHERE operation_id=%s) AND account_id IN(SELECT id FROM budget_accounts WHERE scope='run')",(a.operation_id,))
    if change=='contract':c['cap']=replace(c['cap'],adapter_version='changed-after-preparation')
    assert asyncio.run(dispatch(c,a))=='unknown' and not c['calls']
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(a.operation_id,)).fetchone()==('active',Decimal('0.005000'))
        assert db.execute('SELECT count(*) FROM cost_events').fetchone()==(0,)

@pytest.mark.parametrize('run_case',['native'],indirect=True)
@pytest.mark.parametrize('mode',['received','unknown','epoch-during-http','no-api-port'])
def test_native_run_discover_prepares_submits_intakes_or_reconciles_once(run_case,mode):
    c=run_case
    async def exercise():
        from buyeros_api.api.worker_schemas import JobEnvelope
        from buyeros_api.services.worker_execution import execute_step
        api_engine=create_async_engine(async_database_url(runtime_role_dsn(c['dsn'])))
        worker_engine=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')))
        with psycopg.connect(c['dsn']) as db:epoch=db.execute('SELECT epoch FROM worker_runtime_control').fetchone()[0]
        envelope=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=c['outbox'],generation=1,runtime_epoch=epoch)
        def response(req):
            c['calls'].append(req)
            # Real lock probes, not a promise that the network has no DB TX.
            with psycopg.connect(c['dsn']) as db:
                db.execute('SELECT id FROM search_runs WHERE id=%s FOR UPDATE NOWAIT',(c['run'],))
                db.execute('SELECT id FROM outbox_events WHERE id=%s FOR UPDATE NOWAIT',(c['outbox'],))
                db.execute('SELECT id FROM search_receipts WHERE outbox_id=%s FOR UPDATE NOWAIT',(c['outbox'],))
                if mode=='epoch-during-http':db.execute('UPDATE worker_runtime_control SET epoch=epoch+1 WHERE singleton=1')
            if mode=='unknown':raise httpx.ReadTimeout('synthetic lost response',request=req)
            return httpx.Response(200,json={'web':{'results':[{'url':'https://sensors.example.test/company','title':'Needs review','description':'NATIVE_METADATA_C19'}]}})
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as http:
                adapter=LiveSearchAdapter(capability=c['cap'],receipts=PostgresSearchReceipts(worker_engine,c['workspace'],c['cap']),
                    client=BraveSearchClient(api_key='synthetic-offline-only',http=http,language_codes={'en':'en'},api_version='2026-10-01'))
                kwargs=dict(adapter=adapter,environment='test',research_engine=None if mode=='no-api-port' else api_engine)
                first=await execute_step(worker_engine,envelope,'start',**kwargs)
                replay=await execute_step(worker_engine,envelope,'start',**kwargs)
                return first,replay
        finally:await api_engine.dispose();await worker_engine.dispose()
    a,b=asyncio.run(exercise())
    if mode=='no-api-port':assert a.state=='blocked' and a.code=='CAPABILITY_UNAVAILABLE' and not c['calls']
    elif mode=='epoch-during-http':assert a.state==b.state=='stale' and a.code=='STALE_FENCE' and len(c['calls'])==1
    else:assert a.state==b.state=='reconcile' and a.code==b.code=='PROVIDER_UNKNOWN' and len(c['calls'])==1
    with psycopg.connect(c['dsn']) as db:
        ops=db.execute('SELECT count(*) FROM provider_operations WHERE workspace_id=%s',(c['workspace'],)).fetchone()[0]
        assert ops==(0 if mode=='no-api-port' else 1)
        assert db.execute('SELECT count(*) FROM source_documents WHERE run_id=%s',(c['run'],)).fetchone()==(1 if mode=='received' else 0,)
        assert db.execute('SELECT count(*) FROM cost_events').fetchone()==(0,)
        assert db.execute('SELECT payload FROM outbox_events WHERE id=%s',(c['outbox'],)).fetchone()==(c['payload'],)
        if ops:
            assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE workspace_id=%s',(c['workspace'],)).fetchone()==('active',Decimal('0.005000'))
            assert db.execute('SELECT usage_counters FROM search_runs WHERE id=%s',(c['run'],)).fetchone()[0]['queries']==1

def test_received_receipt_crash_recovers_status_reference_without_resubmit(run_case,monkeypatch):
    c=run_case;a=prepare(c)
    class SimulatedCrash(BaseException):pass
    submit=LiveSearchAdapter.submit
    async def accepted_then_crash(self,intent):
        result=await submit(self,intent)
        assert result.state=='accepted'
        raise SimulatedCrash('owned fixture process lost after durable received result')
    monkeypatch.setattr(LiveSearchAdapter,'submit',accepted_then_crash)
    with pytest.raises(SimulatedCrash):asyncio.run(dispatch(c,a))
    monkeypatch.setattr(LiveSearchAdapter,'submit',submit)
    assert len(c['calls'])==1
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT state FROM search_receipts WHERE id=%s',(a.receipt_id,)).fetchone()==('received',)
        assert db.execute('SELECT status,provider_ref FROM provider_operations WHERE id=%s',(a.operation_id,)).fetchone()==('submitting',str(a.receipt_id))
    assert asyncio.run(dispatch(c,a))=='unknown' and len(c['calls'])==1
    async def reconcile_and_intake():
        from buyeros_api.execution.external_runner import reconcile_intent_key
        from buyeros_api.services.run_search import resume_received_run_search
        key=reconcile_intent_key(a.operation_id)
        with psycopg.connect(c['dsn']) as db:
            db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 WHERE intent_key=%s",(key,))
        worker_engine=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')))
        api_engine=create_async_engine(async_database_url(runtime_role_dsn(c['dsn'])))
        def unexpected(req):c['calls'].append(req);raise AssertionError('status must only reopen local durable receipt')
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(unexpected)) as http:
                adapter=LiveSearchAdapter(capability=c['cap'],receipts=PostgresSearchReceipts(worker_engine,c['workspace'],c['cap']),
                    client=BraveSearchClient(api_key='synthetic-offline-only',http=http,language_codes={'en':'en'},api_version='2026-10-01'))
                assert await execute_external(worker_engine,c['workspace'],a.operation_id,1,adapter,a.intent,environment='test',outbox_intent_key=key)=='succeeded'
            async with tenant_session(api_engine,c['workspace']) as session:
                result=await resume_received_run_search(session,workspace_id=c['workspace'],operation_id=a.operation_id,capability=c['cap'])
            async with tenant_session(api_engine,c['workspace']) as session:
                assert await resume_received_run_search(session,workspace_id=c['workspace'],operation_id=a.operation_id,capability=c['cap'])==result
            return result
        finally:await worker_engine.dispose();await api_engine.dispose()
    assert asyncio.run(reconcile_and_intake())['candidate_count']==1 and len(c['calls'])==1
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(a.operation_id,)).fetchone()==('active',Decimal('0.005000'))
        assert db.execute('SELECT count(*) FROM cost_events').fetchone()==(0,)
        assert db.execute('SELECT usage_counters FROM search_runs WHERE id=%s',(c['run'],)).fetchone()[0]['in_flight']==0

@pytest.mark.parametrize('run_case',['native'],indirect=True)
def test_native_status_recovery_intakes_received_search_without_another_http(run_case,monkeypatch):
    c=run_case;a=prepare(c)
    class SimulatedCrash(BaseException):pass
    submit=LiveSearchAdapter.submit
    async def crash(self,intent):
        assert (await submit(self,intent)).state=='accepted'
        raise SimulatedCrash('owned durable received crash')
    monkeypatch.setattr(LiveSearchAdapter,'submit',crash)
    with pytest.raises(SimulatedCrash):asyncio.run(dispatch(c,a))
    monkeypatch.setattr(LiveSearchAdapter,'submit',submit)
    assert asyncio.run(dispatch(c,a))=='unknown'
    async def native_reconcile():
        from buyeros_api.api.worker_schemas import JobEnvelope
        from buyeros_api.services.worker_execution import execute_step
        from buyeros_api.execution.external_runner import reconcile_intent_key
        with psycopg.connect(c['dsn']) as db:
            key=reconcile_intent_key(a.operation_id)
            db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 WHERE intent_key=%s",(key,))
            oid,epoch=db.execute('SELECT id,runtime_epoch FROM outbox_events WHERE intent_key=%s',(key,)).fetchone()
        env=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=oid,generation=1,runtime_epoch=epoch)
        worker=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')))
        api=create_async_engine(async_database_url(runtime_role_dsn(c['dsn'])))
        def unexpected(req):c['calls'].append(req);raise AssertionError('status performed another HTTP')
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(unexpected)) as http:
                adapter=LiveSearchAdapter(capability=c['cap'],receipts=PostgresSearchReceipts(worker,c['workspace'],c['cap']),
                    client=BraveSearchClient(api_key='synthetic-offline-only',http=http,language_codes={'en':'en'},api_version='2026-10-01'))
                first=await execute_step(worker,env,'start',adapter=adapter,research_engine=api,environment='test')
                replay=await execute_step(worker,env,'start',adapter=adapter,research_engine=api,environment='test')
                assert first.state==replay.state=='done' and first.code==replay.code=='OK'
        finally:await worker.dispose();await api.dispose()
    asyncio.run(native_reconcile());assert len(c['calls'])==1
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT count(*) FROM source_documents WHERE run_id=%s',(c['run'],)).fetchone()==(1,)
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(a.operation_id,)).fetchone()==('active',Decimal('0.005000'))
        assert db.execute('SELECT count(*) FROM cost_events').fetchone()==(0,)
        assert db.execute('SELECT status FROM search_runs WHERE id=%s',(c['run'],)).fetchone()==('running',)

@pytest.mark.parametrize('run_case',['native'],indirect=True)
def test_signed_api_host_step_uses_api_prepare_and_worker_submit_once(run_case,machine_keys,monkeypatch):
    c=run_case
    from datetime import datetime,timezone
    from buyeros_api.settings import get_settings
    from buyeros_api.execution import provider_dispatch
    monkeypatch.setenv('BUYEROS_EXECUTION_DATABASE_URL',role_dsn(c['dsn'],'buyeros_worker'))
    from buyeros_api.execution.config import get_settings as worker_settings
    monkeypatch.setenv('BUYEROS_PAID_DISPATCH_ENABLED','true');get_settings.cache_clear();worker_settings.cache_clear()
    def response(req):
        c['calls'].append(req)
        return httpx.Response(200,json={'web':{'results':[{'url':'https://sensors.example.test/company','title':'Review required','description':'SIGNED_API_HOST_C19'}]}})
    http=httpx.AsyncClient(transport=httpx.MockTransport(response))
    # Fixture-only factory override on the actual signed host route; no registry
    # entry, production key, paid network request or live admission is created.
    adapter=LiveSearchAdapter(capability=c['cap'],receipts=None,
        client=BraveSearchClient(api_key='synthetic-offline-only',http=http,language_codes={'en':'en'},api_version='2026-10-01'))
    monkeypatch.setattr(provider_dispatch,'resolve_provider_adapter',lambda service,**kw:adapter if service=='search' else None)
    with psycopg.connect(c['dsn']) as db:epoch=db.execute('SELECT epoch FROM worker_runtime_control').fetchone()[0]
    body=json.dumps({'envelope':{'v':1,'workspace_id':str(c['workspace']),'outbox_id':str(c['outbox']),'generation':1,'runtime_epoch':epoch},'step_key':'start'},separators=(',',':')).encode()
    path='/v1/internal/worker/step'
    try:
        replies=[c['api'].post(path,content=body,headers={**signed_headers(body=body,path=path,timestamp=str(int(datetime.now(timezone.utc).timestamp()))),'Content-Type':'application/json'}) for _ in range(2)]
        for reply in replies:
            assert reply.status_code==200,reply.text
            assert reply.json()['state']=='reconcile' and reply.json()['code']=='PROVIDER_UNKNOWN'
            assert reply.headers['Cache-Control']=='private, no-store'
    finally:asyncio.run(http.aclose());get_settings.cache_clear();worker_settings.cache_clear()
    assert len(c['calls'])==1
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT count(*) FROM source_documents WHERE run_id=%s',(c['run'],)).fetchone()==(1,)
        assert db.execute('SELECT count(*) FROM provider_operations WHERE workspace_id=%s',(c['workspace'],)).fetchone()==(1,)
        assert db.execute('SELECT count(*) FROM worker_steps WHERE outbox_id=%s',(c['outbox'],)).fetchone()==(1,)
        assert db.execute('SELECT count(*) FROM cost_events').fetchone()==(0,)
        assert db.execute('SELECT payload FROM outbox_events WHERE id=%s',(c['outbox'],)).fetchone()==(c['payload'],)
