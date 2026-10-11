"""Bounded frozen query continuations; owned PG16 and synthetic HTTP only."""
import asyncio,json,uuid
from decimal import Decimal
from datetime import datetime,timezone,timedelta
import httpx,psycopg,pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.api.routes.runs import selected_run_capability
from buyeros_api.api.worker_schemas import JobEnvelope
from buyeros_api.db.session import tenant_session
from buyeros_api.db.icp import canonical_hash
from buyeros_api.db.outbox import OutboxEvent
from buyeros_api.execution.provider_context import pending_run_work
from buyeros_api.execution.fit_execution import execute_fit
from buyeros_api.providers import base,registry
from buyeros_api.providers.base import Money
from buyeros_api.providers.registry import ProviderRegistration,ProviderRegistry
from buyeros_api.providers.live_search import LiveSearchAdapter,PostgresSearchReceipts,BraveSearchClient
from buyeros_api.services.search_intake import ingest_received_search
from buyeros_api.services.worker_execution import execute_step
from buyeros_api.settings import get_settings
from tests.test_provider_contracts import capability
from tests.test_api_projects_db import api as project_api,WORKSPACE_A,OPERATOR
from tests.test_run_admission_integration_db import admission_case,_post,_request,ICP_ID,PROJECT_A
from tests.test_run_search_preparation_db import prepare,dispatch
from tests.conftest import runtime_role_dsn
from tests.cutover_fixtures import role_dsn

@pytest.fixture
def migrated(isolated_migrated):return isolated_migrated

@pytest.fixture
def query_case(admission_case,monkeypatch,request):
    api,dsn=admission_case;ws=uuid.UUID(WORKSPACE_A);holder={};calls=[];factories=[]
    cap=capability(provider='brave-search',service='search',markets=frozenset({'US','HK'}),languages=frozenset({'en','zh-HK'}),roles=frozenset({'company','distributor'}),max_liability=Money(Decimal('0.005000')))
    def factory():factories.append('native');return holder['adapter']
    scope=ProviderRegistration(cap,factory,('synthetic:bounded-query-fixture-only',),frozenset({'market','language'}),(('HK',('zh-HK',)),('US',('en',))))
    monkeypatch.setattr(base,'SELECTED_LIVE_PROVIDERS',frozenset({'brave-search'}));monkeypatch.setattr(registry,'SELECTED_LIVE_PROVIDERS',frozenset({'brave-search'}));monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry((scope,)))
    monkeypatch.setenv('BUYEROS_PAID_ADMISSION_ENABLED','true');monkeypatch.setenv('BUYEROS_CLOUDFLARE_EXECUTION_ENABLED','true');get_settings.cache_clear();api.app.dependency_overrides.pop(selected_run_capability)
    with psycopg.connect(dsn) as db:
        content=db.execute('SELECT content FROM icp_versions WHERE id=%s',(ICP_ID,)).fetchone()[0]
        content.update(markets=['US','HK'],languages=['en','zh-HK'])
        db.execute('UPDATE icp_versions SET content=%s::jsonb,content_hash=%s WHERE id=%s',(json.dumps(content),canonical_hash(content),ICP_ID))
        db.execute("UPDATE projects SET markets='{US,HK}' WHERE id=%s",(PROJECT_A,))
        db.execute("UPDATE policy_decisions SET countries='{US,HK}' WHERE workspace_id=%s",(ws,))
        db.execute("UPDATE worker_runtime_control SET backend='cloudflare',enabled=true,epoch=epoch+1,active_owner=NULL,active_until=NULL WHERE singleton=1")
        db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
    body=_request();body['limits']=dict(body['limits'])
    if getattr(request,'param',None)=='result-cap':body['limits']['max_results']=1
    reply=_post(api,key='c61-bounded-query-'+request.node.name,body=body);assert reply.status_code==202,reply.text
    run=uuid.UUID(reply.json()['data']['id'])
    with psycopg.connect(dsn) as db:
        snapshot=db.execute('SELECT execution_snapshot FROM search_runs WHERE id=%s',(run,)).fetchone()[0]
        assert len(snapshot['query_plan']['queries'])==2 and snapshot['capability']['registry_contract_hash']==scope.contract_hash
        db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 WHERE event_type='run.discover' AND payload->>'run_id'=%s",(str(run),))
        outbox,key,payload,epoch=db.execute("SELECT id,intent_key,payload,runtime_epoch FROM outbox_events WHERE event_type='run.discover' AND payload->>'run_id'=%s",(str(run),)).fetchone()
    c=dict(api=api,dsn=dsn,workspace=ws,run=run,actor=uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR),project=uuid.UUID(PROJECT_A),cap=cap,scope=scope,outbox=outbox,key=key,payload=payload,epoch=epoch,snapshot=snapshot,calls=calls,factories=factories,holder=holder)
    try:yield c
    finally:
        # Exactly this disposable run, including all independent query intents.
        with psycopg.connect(dsn) as db:
            keys=[x[0] for x in db.execute("SELECT intent_key FROM outbox_events WHERE workspace_id=%s AND (payload->>'run_id'=%s OR id=%s)",(ws,str(run),outbox))]
            ops=[x[0] for x in db.execute('SELECT id FROM provider_operations WHERE workspace_id=%s AND intent_key=ANY(%s)',(ws,keys))]
            db.execute("DELETE FROM worker_steps WHERE workspace_id=%s AND outbox_id IN(SELECT id FROM outbox_events WHERE workspace_id=%s AND (payload->>'run_id'=%s OR id=%s OR payload->>'operation_id'=ANY(%s)))",(ws,ws,str(run),outbox,[str(x) for x in ops]))
            db.execute('DELETE FROM receipt_source_bindings WHERE workspace_id=%s AND source_id IN(SELECT id FROM source_documents WHERE run_id=%s)',(ws,run))
            db.execute('DELETE FROM raw_candidates WHERE workspace_id=%s AND run_id=%s',(ws,run));db.execute('DELETE FROM source_documents WHERE workspace_id=%s AND run_id=%s',(ws,run))
            db.execute('DELETE FROM search_receipts WHERE workspace_id=%s AND operation_id=ANY(%s)',(ws,ops))
            db.execute('DELETE FROM budget_reservation_allocations WHERE workspace_id=%s AND reservation_id IN(SELECT id FROM budget_reservations WHERE workspace_id=%s AND operation_id=ANY(%s))',(ws,ws,ops))
            db.execute('DELETE FROM budget_reservations WHERE workspace_id=%s AND operation_id=ANY(%s)',(ws,ops));db.execute('DELETE FROM provider_operations WHERE workspace_id=%s AND id=ANY(%s)',(ws,ops))
        get_settings.cache_clear()

def intake(c,prepared,*,rollback=False):
    async def consume():
        engine=create_async_engine(async_database_url(runtime_role_dsn(c['dsn'])))
        try:
            async with tenant_session(engine,c['workspace']) as session:
                result=await ingest_received_search(session,workspace_id=c['workspace'],run_id=c['run'],receipt_id=prepared.receipt_id,capability=c['cap'])
                if rollback:raise RuntimeError('owned caller transaction rollback')
                return result
        finally:await engine.dispose()
    return asyncio.run(consume())

def queries(c):
    with psycopg.connect(c['dsn']) as db:return db.execute("SELECT id,intent_key,payload,state FROM outbox_events WHERE workspace_id=%s AND event_type='run.discover' AND payload->>'run_id'=%s ORDER BY COALESCE((payload->>'query_index')::int,0)",(c['workspace'],str(c['run']))).fetchall()

def test_received_intake_atomically_queues_one_independent_next_query_without_replaying_original(query_case):
    c=query_case;a=prepare(c);assert asyncio.run(dispatch(c,a))=='accepted'
    result=intake(c,a);again=intake(c,a);assert result==again
    rows=queries(c);assert len(rows)==2,'received native query never schedules its frozen successor'
    assert rows[0][:3]==(c['outbox'],c['key'],c['payload']) and rows[0][3]=='done'
    assert rows[1][1]!=c['key'] and rows[1][2]=={'run_id':str(c['run']),'query_index':1} and rows[1][3]=='ready'
    with psycopg.connect(c['dsn']) as db:
        usage,snapshot=db.execute('SELECT usage_counters,execution_snapshot FROM search_runs WHERE id=%s',(c['run'],)).fetchone()
        assert usage['queries']==usage['raw_results']==1 and usage['in_flight']==0 and snapshot==c['snapshot']
        assert db.execute('SELECT count(*) FROM provider_operations WHERE workspace_id=%s',(c['workspace'],)).fetchone()==(1,)
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(a.operation_id,)).fetchone()==('active',Decimal('0.005000'))
        assert db.execute('SELECT count(*) FROM cost_events').fetchone()==(0,)
    assert len(c['calls'])==1

@pytest.mark.parametrize('state',['ready','dispatched','done','failed'])
def test_unreserved_discovery_is_pending_only_until_original_outbox_terminal(query_case,state):
    c=query_case
    with psycopg.connect(c['dsn']) as db:db.execute('UPDATE outbox_events SET state=%s WHERE id=%s',(state,c['outbox']))
    async def read():
        engine=create_async_engine(async_database_url(runtime_role_dsn(c['dsn'])))
        try:
            async with tenant_session(engine,c['workspace']) as session:
                assert await pending_run_work(session,c['workspace'],c['run']) is (state in {'ready','dispatched'}),'unreserved frozen discovery omitted from completion fence'
                assert await pending_run_work(session,c['workspace'],c['run'],uncertain_only=True) is False
                assert await pending_run_work(session,c['workspace'],uuid.uuid4()) is False
        finally:await engine.dispose()
    asyncio.run(read())

@pytest.mark.parametrize('state',['ready','dispatched'])
def test_native_fit_cannot_complete_before_unreserved_discovery(query_case,state):
    c=query_case;fit=uuid.uuid4();key='c61-query-fit:'+str(fit)
    with psycopg.connect(c['dsn']) as db:
        db.execute("UPDATE search_runs SET status='running',stage='fit' WHERE id=%s",(c['run'],))
        db.execute('UPDATE outbox_events SET state=%s WHERE id=%s',(state,c['outbox']))
        db.execute("INSERT INTO outbox_events(id,workspace_id,intent_key,event_type,payload,state,fencing_generation,runtime_backend,runtime_epoch) VALUES(%s,%s,%s,'run.fit',%s::jsonb,'dispatched',1,'cloudflare',%s)",(fit,c['workspace'],key,json.dumps({'run_id':str(c['run'])}),c['epoch']))
    async def execute():
        engine=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')))
        try:return await execute_fit(engine,c['workspace'],key,1,checkpoint_dsn=role_dsn(c['dsn'],'buyeros_worker'),max_buyers=1)
        finally:await engine.dispose()
    assert asyncio.run(execute())=='pending','fit proceeded to checkpoint/completion before discovery'
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT status,stage FROM search_runs WHERE id=%s',(c['run'],)).fetchone()==('running','fit')
        assert db.execute("SELECT count(*) FROM run_events WHERE run_id=%s AND event_type='run.completed'",(c['run'],)).fetchone()==(0,)

def test_caller_rollback_does_not_leave_query_child_sources_or_usage_then_retry_commits_once(query_case):
    c=query_case;a=prepare(c);assert asyncio.run(dispatch(c,a))=='accepted'
    with pytest.raises(RuntimeError,match='caller transaction rollback'):intake(c,a,rollback=True)
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT count(*) FROM raw_candidates WHERE run_id=%s',(c['run'],)).fetchone()==(0,)
        assert db.execute('SELECT raw_result_count FROM search_runs WHERE id=%s',(c['run'],)).fetchone()==(0,)
    assert len(queries(c))==1
    intake(c,a);intake(c,a);assert len(queries(c))==2,'atomic retry failed to schedule exactly one successor'
    assert len(c['calls'])==1

@pytest.mark.parametrize('query_case,gate',[('result-cap','result-cap'),(None,'elapsed'),(None,'registry-revoked')],indirect=['query_case'])
def test_receipt_still_intakes_when_new_query_gate_blocks_without_hold_or_child(query_case,gate,monkeypatch):
    c=query_case;a=prepare(c);assert asyncio.run(dispatch(c,a))=='accepted'
    if gate=='elapsed':
        with psycopg.connect(c['dsn']) as db:db.execute("UPDATE search_runs SET first_dispatch_at=now()-interval '2 day' WHERE id=%s",(c['run'],))
    if gate=='registry-revoked':monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry(()))
    result=intake(c,a);assert result['candidate_count']==1 and intake(c,a)==result and len(queries(c))==1
    with psycopg.connect(c['dsn']) as db:
        status,reason,usage=db.execute('SELECT status,terminal_reason,usage_counters FROM search_runs WHERE id=%s',(c['run'],)).fetchone()
        assert status=='partial' and reason==('capability_unavailable' if gate=='registry-revoked' else 'query_limit'),'new-query gate was silently treated as completed discovery'
        assert usage['queries']==1 and usage['raw_results']==1 and usage['in_flight']==0
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(a.operation_id,)).fetchone()==('active',Decimal('0.005000'))
        assert db.execute('SELECT count(*) FROM cost_events').fetchone()==(0,)
    assert len(c['calls'])==1

@pytest.mark.parametrize('outcome',['received','unknown'])
def test_actual_native_factory_walks_frozen_queries_individually_and_never_repeats_unknown(query_case,outcome):
    c=query_case
    async def native():
        worker=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')));research=create_async_engine(async_database_url(runtime_role_dsn(c['dsn'])))
        def response(req):
            c['calls'].append(req)
            if outcome=='unknown':raise httpx.ReadTimeout('synthetic original response lost',request=req)
            language=req.url.params['search_lang']
            return httpx.Response(200,json={'web':{'results':[{'url':'https://bounded.example.test/'+language,'title':'Synthetic unreviewed company','description':'SEARCH_METADATA_ONLY'}]}})
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as http:
                c['holder']['adapter']=LiveSearchAdapter(capability=c['cap'],receipts=PostgresSearchReceipts(worker,c['workspace'],c['cap']),client=BraveSearchClient(api_key='synthetic-offline-only',http=http,language_codes={'en':'en','zh-HK':'zh-hant'},api_version='2026-10-01'))
                first=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=c['outbox'],generation=1,runtime_epoch=c['epoch'])
                result=await execute_step(worker,first,'start',research_engine=research,environment='test')
                assert result.state=='reconcile' and await execute_step(worker,first,'start',research_engine=research,environment='test')==result
                rows=queries(c)
                assert len(rows)==(2 if outcome=='received' else 1),'native known receipt did not schedule next frozen query'
                if outcome=='received':
                    child=rows[1]
                    with psycopg.connect(c['dsn']) as db:db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 WHERE id=%s",(child[0],))
                    second=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=child[0],generation=1,runtime_epoch=c['epoch'])
                    final=await execute_step(worker,second,'start',research_engine=research,environment='test')
                    assert final.state=='reconcile' and await execute_step(worker,second,'start',research_engine=research,environment='test')==final
        finally:await worker.dispose();await research.dispose()
    asyncio.run(native())
    count=2 if outcome=='received' else 1
    assert len(c['calls'])==len(c['factories'])==count and len(queries(c))==count
    with psycopg.connect(c['dsn']) as db:
        ops=db.execute('SELECT id,status FROM provider_operations WHERE workspace_id=%s',(c['workspace'],)).fetchall();assert len(ops)==count and all(x[1]==('accepted' if outcome=='received' else 'unknown') for x in ops)
        assert db.execute('SELECT count(*) FROM cost_events').fetchone()==(0,)
        holds=db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=ANY(%s)',([x[0] for x in ops],)).fetchall();assert holds==[('active',Decimal('0.005000'))]*count
        usage,snapshot=db.execute('SELECT usage_counters,execution_snapshot FROM search_runs WHERE id=%s',(c['run'],)).fetchone();assert usage['queries']==count and snapshot==c['snapshot']
        assert db.execute('SELECT canonical_company_id,merge_state FROM raw_candidates WHERE run_id=%s',(c['run'],)).fetchall()==([(None,'needs_review')]*2 if outcome=='received' else [])
