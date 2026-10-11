"""C16 owned runtime PG receipt/external boundary; fake contract+HTTP only."""
import asyncio,importlib,json,uuid
from dataclasses import replace
from decimal import Decimal
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
import httpx,psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.db.session import tenant_session
from buyeros_api.execution.external_runner import execute_external,input_digest,reconcile_intent_key
from buyeros_api.providers.base import ProviderIntent
from tests.test_live_search_adapter import capability,module
from tests.test_buyer_review_db import api,OPERATOR,PROJECT_A,WORKSPACE_A,WORKSPACE_B
from tests.test_budget_rollover_db import _run
from tests.conftest import runtime_role_dsn
from tests.cutover_fixtures import role_dsn

@pytest.fixture
def search_case(api,seeded,monkeypatch):
    from buyeros_api.providers import base
    from buyeros_api.services.budget_service import ensure_period_accounts,reserve_operation
    monkeypatch.setattr(base,'SELECTED_LIVE_PROVIDERS',frozenset({'brave-search'}))
    cap=replace(capability(),idempotency='verified',status='verified') # synthetic owned protocol contract only
    actor=uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR);workspace=uuid.UUID(WORKSPACE_A);project=uuid.UUID(PROJECT_A);operation=uuid.uuid4();outbox=uuid.uuid4()
    intent=ProviderIntent('c61-search:'+operation.hex,'search','US','en','company')
    _run(seeded,lambda session:ensure_period_accounts(session,workspace,project,None,'discovery'))
    with psycopg.connect(seeded) as db:db.execute('UPDATE budget_accounts SET approved_limit=2 WHERE workspace_id=%s',(workspace,))
    _run(seeded,lambda session:reserve_operation(session,operation,{'workspace_id':workspace,'project_id':project,'category':'discovery'},cap.max_liability.amount,'USD',cap.pricing_version))
    with psycopg.connect(seeded) as db:
        db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
        db.execute("INSERT INTO provider_operations(id,workspace_id,intent_key,capability,input_hash,status) VALUES (%s,%s,%s,'search',%s,'reserved')",(operation,workspace,intent.key,input_digest(intent)))
        backend,epoch=db.execute('SELECT backend,epoch FROM worker_runtime_control').fetchone()
        db.execute("INSERT INTO outbox_events(id,workspace_id,intent_key,event_type,payload,state,fencing_generation,runtime_backend,runtime_epoch) VALUES (%s,%s,%s,'provider.external',%s::jsonb,'dispatched',1,%s,%s)",(outbox,workspace,intent.key,json.dumps({'operation_id':str(operation),'service':'search','market':'US','language':'en','role':'company'}),backend,epoch))
        db.execute("INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,controller_scope_id,purpose,status,policy_version,basis_reference,provenance,countries,expires_at,retention_days,decision_author_id) VALUES(%s,%s,'project',%s,%s,'account_research','permitted','c61-offline-fixture-only','offline-synthetic','fixture','{US}',now()+interval '1 day',1,%s)",(uuid.uuid4(),workspace,project,workspace,actor))
    yield {'dsn':seeded,'cap':cap,'actor':actor,'workspace':workspace,'project':project,'operation':operation,'outbox':outbox,'intent':intent}
    with psycopg.connect(seeded) as db:
        if db.execute("SELECT to_regclass('public.search_receipts')").fetchone()[0]:db.execute('DELETE FROM search_receipts WHERE workspace_id=%s',(workspace,))
        db.execute('DELETE FROM outbox_events WHERE intent_key IN (%s,%s)',(intent.key,reconcile_intent_key(operation)))
        db.execute('DELETE FROM provider_operations WHERE id=%s',(operation,))

@asynccontextmanager
async def stores(case):
    m=module();cls=getattr(m,'PostgresSearchReceipts',None);assert callable(cls),'C61-16 durable PG receipt store missing'
    api_engine=create_async_engine(async_database_url(runtime_role_dsn(case['dsn'])));worker_engine=create_async_engine(async_database_url(role_dsn(case['dsn'],'buyeros_worker')))
    try:
        request=m.SearchRequest(key=case['intent'].key,query='industrial sensors',market='US',language='en',role='company',limit=20,project_id=case['project'],actor_id=case['actor'])
        api_store=cls(api_engine,case['workspace'],case['cap']);worker_store=cls(worker_engine,case['workspace'],case['cap'])
        ref=await api_store.prepare(request,operation_id=case['operation'],outbox_id=case['outbox'])
        yield m,worker_engine,api_store,worker_store,ref
    finally:await api_engine.dispose();await worker_engine.dispose()

def hold(case):
    with psycopg.connect(case['dsn']) as db:
        return db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(case['operation'],)).fetchone(),db.execute('SELECT count(*) FROM cost_events WHERE operation_id=%s',(case['operation'],)).fetchone()[0]

def test_real_external_boundary_persists_reopens_sources_and_holds_until_billing(search_case):
    case=search_case;calls=[]
    def response(req):
        calls.append(req)
        with psycopg.connect(case['dsn']) as db:
            db.execute('SELECT id FROM provider_operations WHERE id=%s FOR UPDATE NOWAIT',(case['operation'],))
            db.execute('SELECT id FROM search_receipts WHERE workspace_id=%s FOR UPDATE NOWAIT',(case['workspace'],))
        return httpx.Response(200,json={'web':{'results':[{'url':'https://sensors.example.test/company','title':'Fictional Sensors','description':'Source data, never legal entity proof'}]}})
    async def exercise():
        async with stores(case) as (m,engine,_,store,ref):
            async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as http:
                client=m.BraveSearchClient(api_key='offline-token-not-real',http=http,language_codes={'en':'en'},api_version='2026-10-01')
                adapter=m.LiveSearchAdapter(capability=case['cap'],client=client,receipts=store)
                assert await execute_external(engine,case['workspace'],case['operation'],1,adapter,case['intent'],environment='test')=='accepted'
                assert await execute_external(engine,case['workspace'],case['operation'],1,adapter,case['intent'],environment='test')=='stale'
                assert (await adapter.submit(case['intent'])).state=='accepted'
                reopened=m.PostgresSearchReceipts(engine,case['workspace'],case['cap']);saved=await reopened.get(ref)
                assert saved['state']=='received' and len(saved['sources'])==1 and saved['sources'][0]['company_ref'] is None
                assert (await m.LiveSearchAdapter(capability=case['cap'],client=None,receipts=reopened).status(ref)).state=='succeeded'
                assert hold(case)==(('active',Decimal('0.005000')),0)
    asyncio.run(exercise());assert len(calls)==1

def test_timeout_restart_uses_status_only_and_never_resubmits(search_case):
    case=search_case;calls=[]
    def response(req):calls.append(req);raise httpx.ReadTimeout('offline accepted response lost')
    async def exercise():
        async with stores(case) as (m,engine,_,store,ref):
            async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as http:
                client=m.BraveSearchClient(api_key='offline-token-not-real',http=http,language_codes={'en':'en'},api_version='2026-10-01')
                adapter=m.LiveSearchAdapter(capability=case['cap'],client=client,receipts=store)
                assert await execute_external(engine,case['workspace'],case['operation'],1,adapter,case['intent'],environment='test')=='unknown'
                assert await execute_external(engine,case['workspace'],case['operation'],1,adapter,case['intent'],environment='test')=='stale'
                assert (await adapter.submit(case['intent'])).state=='unknown'
                reopened=m.PostgresSearchReceipts(engine,case['workspace'],case['cap']);new=m.LiveSearchAdapter(capability=case['cap'],client=None,receipts=reopened)
                assert (await new.status(ref)).state=='unknown'
                assert hold(case)==(('active',Decimal('0.005000')),0)
    asyncio.run(exercise());assert len(calls)==1

def test_current_actor_revocation_before_claim_blocks_network(search_case):
    case=search_case;calls=[]
    async def exercise():
        async with stores(case) as (m,engine,_,store,ref):
            with psycopg.connect(case['dsn']) as db:db.execute('UPDATE memberships SET active=false,version=version+1 WHERE workspace_id=%s AND user_id=%s',(case['workspace'],case['actor']))
            class Client:
                async def search(self,*args):calls.append(args);raise AssertionError('must not call vendor')
            adapter=m.LiveSearchAdapter(capability=case['cap'],client=Client(),receipts=store)
            assert await execute_external(engine,case['workspace'],case['operation'],1,adapter,case['intent'],environment='test')=='unknown'
            assert hold(case)==(('active',Decimal('0.005000')),0)
    asyncio.run(exercise());assert calls==[]

def test_foreign_receipt_scope_is_hidden_by_runtime_RLS(search_case):
    case=search_case
    async def exercise():
        async with stores(case) as (m,engine,_,store,ref):
            assert await m.PostgresSearchReceipts(engine,uuid.UUID(WORKSPACE_B),case['cap']).get(ref) is None
            async with tenant_session(engine,uuid.UUID(WORKSPACE_B)) as session:
                from sqlalchemy import text
                assert (await session.execute(text('SELECT count(*) FROM search_receipts'))).scalar_one()==0
    asyncio.run(exercise())

def test_durable_claim_is_single_and_crash_cannot_reacquire(search_case):
    case=search_case
    async def exercise():
        async with stores(case) as (m,engine,_,store,ref):
            with psycopg.connect(case['dsn']) as db:db.execute("UPDATE provider_operations SET status='submitting' WHERE id=%s",(case['operation'],))
            first=await store.claim(case['intent']);second=await m.PostgresSearchReceipts(engine,case['workspace'],case['cap']).claim(case['intent'])
            assert first[1] is True and second[1] is False and second[0]['state']=='submitting'
            assert (await m.LiveSearchAdapter(capability=case['cap'],client=None,receipts=store).status(ref)).state=='unknown'
    asyncio.run(exercise())

def test_request_and_received_receipt_are_immutable_at_DB_boundary(search_case):
    case=search_case
    async def exercise():
        async with stores(case) as (m,engine,_,store,ref):
            with psycopg.connect(case['dsn']) as db:db.execute("UPDATE provider_operations SET status='submitting' WHERE id=%s",(case['operation'],))
            assert (await store.claim(case['intent']))[1]
            item=m.source_candidate({'url':'https://sensors.example.test/company','title':'Fictional Sensors','snippet':'Keep exact data'})
            import hashlib
            digest=hashlib.sha256(m.canonical_json([item])).hexdigest();await store.finish(ref,state='received',sources=[item],digest=digest)
            await store.finish(ref,state='unknown') # delayed acknowledgement must not erase a received result
            assert (await store.get(ref))['state']=='received'
            from sqlalchemy import text
            from sqlalchemy.exc import IntegrityError
            for statement in ["UPDATE search_receipts SET request=jsonb_set(request,'{query}','\"changed\"')","UPDATE search_receipts SET state='prepared'","UPDATE search_receipts SET response='[]'"]:
                with pytest.raises(IntegrityError):
                    async with tenant_session(engine,case['workspace']) as session:await session.execute(text(statement))
            async with tenant_session(engine,case['workspace']) as session:
                assert (await session.execute(text("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname='search_receipts'"))).one()==(True,True)
    asyncio.run(exercise())

def test_receipt_rollback_retains_rows_and_reupgrade_preserves_hash(search_case,monkeypatch):
    case=search_case
    async def exercise():
        from alembic import command
        from alembic.config import Config
        from tests.conftest import ALEMBIC_INI,SERVICE_ROOT
        async with stores(case) as (m,engine,_,store,ref):
            before=await store.get(ref);config=Config(str(ALEMBIC_INI));config.set_main_option('script_location',str(SERVICE_ROOT/'alembic'))
            from buyeros_api.settings import get_settings
            monkeypatch.setenv('BUYEROS_DATABASE_URL',case['dsn']);get_settings.cache_clear()
            try:
                command.downgrade(config,'0039_c61_user_identities')
                assert await store.get(ref)==before
            finally:
                command.upgrade(config,'head')
                monkeypatch.setenv('BUYEROS_DATABASE_URL',runtime_role_dsn(case['dsn']));get_settings.cache_clear()
            assert await store.get(ref)==before
    asyncio.run(exercise())
