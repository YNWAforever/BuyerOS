"""Native receipt intake on API/worker roles; HTTP and verified contract are synthetic.

No real provider activation, canonical entity, page retrieval or billing proof.
"""
import asyncio,hashlib,importlib,json,uuid
from dataclasses import replace
from datetime import datetime,timezone
from decimal import Decimal
import httpx,psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.db.session import tenant_session
from buyeros_api.execution.external_runner import execute_external,input_digest
from buyeros_api.providers.base import ProviderIntent
from buyeros_api.providers.live_search import PostgresSearchReceipts,SearchRequest,LiveSearchAdapter,BraveSearchClient
from tests.test_live_search_adapter import capability
from tests.test_api_projects_db import api as project_api,WORKSPACE_A,OPERATOR
from tests.test_buyer_review_db import WORKSPACE_B
from tests.test_run_admission_integration_db import admission_case,_post
from tests.conftest import runtime_role_dsn
from tests.cutover_fixtures import role_dsn
from tests.test_budget_rollover_db import _run

@pytest.fixture
def migrated(isolated_migrated):return isolated_migrated

def intake():
    spec=importlib.util.find_spec('buyeros_api.services.search_intake')
    assert spec is not None,'C61-19 received search intake is missing'
    fn=getattr(importlib.import_module('buyeros_api.services.search_intake'),'ingest_received_search',None)
    assert callable(fn),'C61-19 received search intake port is missing'
    return fn

@pytest.fixture
def received_case(admission_case,monkeypatch,request):
    mode=getattr(request,'param','one')
    api,dsn=admission_case;reply=_post(api,key='c19-received-source');assert reply.status_code==202,reply.text
    run=uuid.UUID(reply.json()['data']['id']);workspace=uuid.UUID(WORKSPACE_A);actor=uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR)
    cap=replace(capability(),idempotency='verified',status='verified')
    from buyeros_api.providers.registry import ProviderRegistration
    binding=ProviderRegistration(cap,lambda:None,policy_account_reference='owned-received-intake-account').policy_binding
    from buyeros_api.providers import base
    monkeypatch.setattr(base,'SELECTED_LIVE_PROVIDERS',frozenset({'brave-search'}))
    operation=uuid.uuid4();outbox=uuid.uuid4();intent=ProviderIntent('c19-intake:'+operation.hex,'search','US','en','company')
    with psycopg.connect(dsn) as db:
        project,snapshot=db.execute('SELECT project_id,execution_snapshot FROM search_runs WHERE id=%s',(run,)).fetchone()
        query=snapshot['query_plan']['queries'][0]
        # This is an explicitly synthetic prepared run contract. Admission's
        # real selector is still closed; no fixture capability is deployed.
        snapshot['capability'].update(provider=cap.provider,price_version=cap.pricing_version)
        snapshot['capability']['policy_binding']=binding.model_dump(mode='json')
        db.execute("UPDATE search_runs SET execution_snapshot=%s::jsonb,status='running',stage='discovering' WHERE id=%s",(json.dumps(snapshot),run))
        db.execute("UPDATE outbox_events SET state='done' WHERE payload->>'run_id'=%s",(str(run),))
        db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
        backend,epoch=db.execute('SELECT backend,epoch FROM worker_runtime_control').fetchone()
        payload={'operation_id':str(operation),'service':'search','market':'US','language':'en','role':'company','run_id':str(run),'query_id':query['id']}
        db.execute("INSERT INTO provider_operations(id,workspace_id,intent_key,capability,input_hash,status) VALUES(%s,%s,%s,'search',%s,'reserved')",(operation,workspace,intent.key,input_digest(intent)))
        db.execute("INSERT INTO outbox_events(id,workspace_id,intent_key,event_type,payload,state,fencing_generation,runtime_backend,runtime_epoch) VALUES(%s,%s,%s,'provider.external',%s::jsonb,'dispatched',1,%s,%s)",(outbox,workspace,intent.key,json.dumps(payload),backend,epoch))
    from tests.policy_activation_fixtures import approve_research_fixture
    approve_research_fixture(dsn,workspace,project,domains=('sensors.example.test','other.example.test'),
                             search=binding,countries=('US',))
    from buyeros_api.services.budget_service import reserve_operation
    _run(dsn,lambda session:reserve_operation(session,operation,{'workspace_id':workspace,'project_id':project,'run_id':run,'category':'discovery'},cap.max_liability.amount,'USD',cap.pricing_version))
    case={'dsn':dsn,'run':run,'workspace':workspace,'project':project,'actor':actor,'cap':cap,'binding':binding,
          'operation':operation,'outbox':outbox,'intent':intent,'query':query,'calls':[]}
    async def receive():
        api_engine=create_async_engine(async_database_url(runtime_role_dsn(dsn)));worker_engine=create_async_engine(async_database_url(role_dsn(dsn,'buyeros_worker')))
        try:
            api_store=PostgresSearchReceipts(api_engine,workspace,cap,policy_binding=binding)
            store=PostgresSearchReceipts(worker_engine,workspace,cap,policy_binding=binding)
            request=SearchRequest(key=intent.key,query=query['query'],market=query['market'],language=query['language'],role='company',limit=10,project_id=project,actor_id=actor)
            case['ref']=uuid.UUID(await api_store.prepare(request,operation_id=operation,outbox_id=outbox))
            def response(req):
                case['calls'].append(req)
                item={'url':'https://sensors.example.test/company','title':'Unreviewed sensors','description':'PRIVATE_METADATA_C19'}
                items=[] if mode=='empty' else [item,item] if mode=='duplicate' else [item,{**item,'url':'https://other.example.test/company'}] if mode=='two' else [item]
                return httpx.Response(200,json={'web':{'results':items}})
            async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as http:
                adapter=LiveSearchAdapter(capability=cap,receipts=store,client=BraveSearchClient(api_key='synthetic-offline-only',http=http,language_codes={'en':'en'},api_version='2026-10-01'))
                assert await execute_external(worker_engine,workspace,operation,1,adapter,intent,environment='test')=='accepted'
        finally:await api_engine.dispose();await worker_engine.dispose()
    try:
        asyncio.run(receive());assert len(case['calls'])==1
        yield case
    finally:
        # A prepare failure can precede case['ref']; clean the exact owned
        # operation as well as its allocation before the parent account reset.
        with psycopg.connect(dsn) as db:
            db.execute('DELETE FROM receipt_source_bindings WHERE source_id IN(SELECT id FROM source_documents WHERE run_id=%s)',(run,))
            db.execute('DELETE FROM raw_candidates WHERE run_id=%s',(run,))
            db.execute('DELETE FROM source_documents WHERE run_id=%s',(run,))
            db.execute('DELETE FROM search_receipts WHERE operation_id=%s',(operation,))
            db.execute('DELETE FROM budget_reservation_allocations WHERE reservation_id IN(SELECT id FROM budget_reservations WHERE operation_id=%s)',(operation,))
            db.execute('DELETE FROM budget_reservations WHERE operation_id=%s',(operation,))
            db.execute('DELETE FROM provider_operations WHERE id=%s',(operation,))

def consume(case,*,workspace=None,run=None):
    fn=intake()
    async def exercise():
        engine=create_async_engine(async_database_url(runtime_role_dsn(case['dsn'])))
        try:
            async with tenant_session(engine,workspace or case['workspace']) as session:
                return await fn(session,workspace_id=workspace or case['workspace'],run_id=run or case['run'],receipt_id=case['ref'],capability=case['cap'])
        finally:await engine.dispose()
    return asyncio.run(exercise())

def counts(case):
    with psycopg.connect(case['dsn']) as db:
        return tuple(db.execute('SELECT count(*) FROM '+table+' WHERE workspace_id=%s',(case['workspace'],)).fetchone()[0] for table in ['source_documents','raw_candidates','companies','project_buyers','evidence','fit_assessments','cost_events'])

def test_received_metadata_ingests_once_without_guessing_entities_or_cost(received_case):
    c=received_case;before=counts(c);first=consume(c);replay=consume(c)
    assert first==replay and first['source_count']==first['candidate_count']==1
    assert counts(c)==(before[0]+1,before[1]+1,*before[2:]) and len(c['calls'])==1
    with psycopg.connect(c['dsn']) as db:
        source=db.execute('SELECT id,excerpt,storage_mode,retention_until,permission_purpose FROM source_documents WHERE run_id=%s',(c['run'],)).fetchone()
        receipt=db.execute('SELECT retention_until FROM search_receipts WHERE id=%s',(c['ref'],)).fetchone()
        raw=db.execute('SELECT canonical_company_id,merge_state,raw_payload FROM raw_candidates WHERE run_id=%s',(c['run'],)).fetchone()
        assert source[1]=='PRIVATE_METADATA_C19' and source[2]=='search_result_metadata' and source[3]<=receipt[0] and source[4]=='account_research'
        assert raw[0] is None and raw[1]=='needs_review' and raw[2]['source_document_id']==str(source[0])
        assert raw[2]['page_retrieved'] is False and 'PRIVATE_METADATA_C19' not in json.dumps(raw[2])
        assert db.execute('SELECT count(*) FROM receipt_source_bindings WHERE source_id=%s AND receipt_id=%s',(source[0],c['ref'])).fetchone()==(1,)
        assert db.execute("SELECT count(*) FROM run_events WHERE run_id=%s AND payload->>'receipt_id'=%s",(c['run'],str(c['ref']))).fetchone()==(1,)
        assert db.execute('SELECT raw_result_count,usage_counters FROM search_runs WHERE id=%s',(c['run'],)).fetchone()[0]==1
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(c['operation'],)).fetchone()==('active',Decimal('0.005000'))

@pytest.mark.parametrize('change',['actor','policy','offer','icp','epoch','cancel','query','run-allocation','expired','unknown'])
def test_received_metadata_rechecks_current_context_before_copy(received_case,change):
    c=received_case;before=counts(c)
    with psycopg.connect(c['dsn']) as db:
        if change=='actor':db.execute('UPDATE memberships SET active=false WHERE workspace_id=%s AND user_id=%s',(c['workspace'],c['actor']))
        elif change=='policy':db.execute("UPDATE policy_decisions SET status='blocked' WHERE workspace_id=%s",(c['workspace'],))
        elif change=='offer':db.execute('UPDATE projects SET offer_revision=offer_revision+1 WHERE id=%s',(c['project'],))
        elif change=='icp':db.execute('UPDATE icp_versions SET approved_at=NULL WHERE project_id=%s',(c['project'],))
        elif change=='epoch':db.execute('UPDATE worker_runtime_control SET epoch=epoch+1 WHERE singleton=1')
        elif change=='cancel':db.execute("UPDATE search_runs SET status='cancel_requested' WHERE id=%s",(c['run'],))
        elif change=='query':db.execute("UPDATE outbox_events SET payload=jsonb_set(payload,'{query_id}','\"foreign-query\"') WHERE id=%s",(c['outbox'],))
        elif change=='run-allocation':db.execute("DELETE FROM budget_reservation_allocations WHERE reservation_id IN(SELECT id FROM budget_reservations WHERE operation_id=%s) AND account_id IN(SELECT id FROM budget_accounts WHERE scope='run')",(c['operation'],))
        elif change=='expired':
            # Own fixture only: preserve immutable production deadline guard.
            db.execute('ALTER TABLE search_receipts DISABLE TRIGGER USER');db.execute("UPDATE search_receipts SET retention_until=now()-interval '1 second' WHERE id=%s",(c['ref'],));db.execute('ALTER TABLE search_receipts ENABLE TRIGGER USER')
        elif change=='unknown':db.execute("UPDATE provider_operations SET status='unknown' WHERE id=%s",(c['operation'],))
    with pytest.raises(ValueError):consume(c)
    assert counts(c)==before and len(c['calls'])==1

def test_received_metadata_foreign_workspace_is_hidden(received_case):
    c=received_case;before=counts(c)
    with pytest.raises(ValueError):consume(c,workspace=uuid.UUID(WORKSPACE_B))
    assert counts(c)==before

def test_received_metadata_obeys_cumulative_raw_limit_atomically(received_case):
    c=received_case;before=counts(c)
    with psycopg.connect(c['dsn']) as db:db.execute("UPDATE search_runs SET usage_counters=jsonb_set(usage_counters,'{raw_results}',to_jsonb((limits->>'max_results')::int)) WHERE id=%s",(c['run'],))
    from buyeros_api.services.run_usage import UsageExceeded
    with pytest.raises(UsageExceeded):consume(c)
    assert counts(c)==before

def test_received_metadata_source_expiry_redacts_candidate_copy_and_no_replay(received_case):
    c=received_case;result=consume(c)
    with psycopg.connect(c['dsn']) as db:
        source=db.execute('SELECT id FROM source_documents WHERE run_id=%s',(c['run'],)).fetchone()[0]
        hashes=db.execute('SELECT request_hash,response_hash,intent_key FROM search_receipts WHERE id=%s',(c['ref'],)).fetchone()
        db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(source,))
    async def erase():
        from buyeros_api.services.retention import expire_subject_data
        engine=create_async_engine(async_database_url(runtime_role_dsn(c['dsn'])))
        try:
            async with tenant_session(engine,c['workspace']) as session:await expire_subject_data(session,source,'c19-metadata-v1',datetime.now(timezone.utc),subject_type='source_document')
        finally:await engine.dispose()
    asyncio.run(erase())
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT excerpt FROM source_documents WHERE id=%s',(source,)).fetchone()==(None,)
        url,normalized,payload=db.execute('SELECT source_url,normalized_url,raw_payload FROM raw_candidates WHERE run_id=%s',(c['run'],)).fetchone()
        assert url==normalized=='https://redacted.invalid/'+str(source) and payload.get('redacted') is True
        assert db.execute('SELECT request_hash,response_hash,intent_key FROM search_receipts WHERE id=%s',(c['ref'],)).fetchone()==hashes
        assert db.execute('SELECT response FROM search_receipts WHERE id=%s',(c['ref'],)).fetchone()==(None,)
    with pytest.raises(ValueError):consume(c)
    assert len(c['calls'])==1

@pytest.mark.parametrize('received_case',['empty','duplicate'],indirect=True)
def test_received_metadata_empty_or_duplicate_response_has_one_checkpoint(received_case):
    c=received_case;result=consume(c);assert consume(c)==result
    with psycopg.connect(c['dsn']) as db:
        returned=len(db.execute('SELECT response FROM search_receipts WHERE id=%s',(c['ref'],)).fetchone()[0])
        assert result['candidate_count']==result['source_count']==min(returned,1)
        assert db.execute('SELECT raw_result_count FROM search_runs WHERE id=%s',(c['run'],)).fetchone()==(returned,)
        assert db.execute('SELECT count(*) FROM source_documents WHERE run_id=%s',(c['run'],)).fetchone()==(min(returned,1),)
        assert db.execute("SELECT count(*) FROM run_events WHERE run_id=%s AND payload->>'receipt_id'=%s",(c['run'],str(c['ref']))).fetchone()==(1,)


@pytest.mark.parametrize('received_case',['empty'],indirect=True)
def test_empty_receipt_still_requires_exact_current_search_account_and_policy(received_case):
    c=received_case
    async def read():
        engine=create_async_engine(async_database_url(runtime_role_dsn(c['dsn'])))
        try:
            right=PostgresSearchReceipts(engine,c['workspace'],c['cap'],policy_binding=c['binding'])
            assert (await right.get(str(c['ref'])))['sources']==[]
            wrong=PostgresSearchReceipts(engine,c['workspace'],c['cap'],
                policy_binding=c['binding'].model_copy(update={'account_reference':'unapproved-account'}))
            missing=PostgresSearchReceipts(engine,c['workspace'],c['cap'])
            for denied in (wrong,missing):
                with pytest.raises(ValueError,match='purpose policy'):
                    await denied.get(str(c['ref']))
            with psycopg.connect(c['dsn']) as db:
                db.execute("UPDATE policy_decisions SET status='blocked',version=version+1 WHERE workspace_id=%s",(c['workspace'],))
            with pytest.raises(ValueError,match='purpose policy'):
                await right.get(str(c['ref']))
        finally:
            await engine.dispose()
    asyncio.run(read())

@pytest.mark.parametrize('received_case',['two'],indirect=True)
def test_receipt_erasure_clears_all_intake_source_copies_atomically(received_case):
    c=received_case;consume(c)
    with psycopg.connect(c['dsn']) as db:
        source=db.execute('SELECT id FROM source_documents WHERE run_id=%s ORDER BY id LIMIT 1',(c['run'],)).fetchone()[0]
        hashes=db.execute('SELECT request_hash,response_hash,intent_key FROM search_receipts WHERE id=%s',(c['ref'],)).fetchone()
        db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(source,))
    async def erase():
        from buyeros_api.services.retention import expire_subject_data
        engine=create_async_engine(async_database_url(runtime_role_dsn(c['dsn'])))
        try:
            async with tenant_session(engine,c['workspace']) as session:await expire_subject_data(session,source,'c19-copy-v1',datetime.now(timezone.utc),subject_type='source_document')
        finally:await engine.dispose()
    asyncio.run(erase())
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT count(*) FROM source_documents WHERE run_id=%s AND excerpt IS NOT NULL',(c['run'],)).fetchone()==(0,)
        assert db.execute("SELECT count(*) FROM raw_candidates WHERE run_id=%s AND (source_url NOT LIKE 'https://redacted.invalid/%%' OR NOT raw_payload @> '{\"redacted\":true}')",(c['run'],)).fetchone()==(0,)
        assert db.execute('SELECT request_hash,response_hash,intent_key FROM search_receipts WHERE id=%s',(c['ref'],)).fetchone()==hashes
        assert db.execute('SELECT count(*) FROM cost_events WHERE operation_id=%s',(c['operation'],)).fetchone()==(0,)

def test_search_intake_lock_is_scoped_without_table_update_grant(received_case):
    c=received_case
    async def exercise():
        from sqlalchemy import text
        engine=create_async_engine(async_database_url(runtime_role_dsn(c['dsn'])))
        try:
            async with tenant_session(engine,c['workspace']) as session:
                exists=(await session.execute(text("SELECT to_regprocedure('public.buyeros_lock_search_receipt(uuid,uuid)')"))).scalar_one()
                assert exists is not None,'C19 atomic search receipt read lock is missing'
                assert (await session.execute(text("SELECT has_table_privilege(current_user,'search_receipts','UPDATE')"))).scalar_one() is False
                assert (await session.execute(text('SELECT public.buyeros_lock_search_receipt(:ws,:id)'),{'ws':c['workspace'],'id':c['ref']})).scalar_one() is True
            async with tenant_session(engine,uuid.UUID(WORKSPACE_B)) as session:
                assert (await session.execute(text('SELECT public.buyeros_lock_search_receipt(:ws,:id)'),{'ws':c['workspace'],'id':c['ref']})).scalar_one() is False
        finally:await engine.dispose()
    asyncio.run(exercise())

def test_intake_read_lock_prevents_concurrent_erase_then_no_resurrection(received_case):
    c=received_case;consume(c)
    with psycopg.connect(c['dsn']) as db:source=db.execute('SELECT id FROM source_documents WHERE run_id=%s',(c['run'],)).fetchone()[0]
    async def exercise():
        from sqlalchemy import text
        from sqlalchemy.exc import DBAPIError
        from buyeros_api.services.receipt_retention import expire_provider_receipts
        engine=create_async_engine(async_database_url(runtime_role_dsn(c['dsn'])))
        try:
            async with tenant_session(engine,c['workspace']) as parent:
                assert (await parent.execute(text('SELECT public.buyeros_lock_search_receipt(:ws,:id)'),{'ws':c['workspace'],'id':c['ref']})).scalar_one() is True
                with psycopg.connect(c['dsn']) as db:db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(source,))
                async def concurrent_erase():
                    async with tenant_session(engine,c['workspace']) as child:
                        return await expire_provider_receipts(child,now=datetime.now(timezone.utc),policy_version='c19-concurrent-v1',source_id=source)
                with pytest.raises(DBAPIError) as blocked:
                    await asyncio.wait_for(concurrent_erase(),3)
                assert 'lock timeout' in str(blocked.value).lower()
            async with tenant_session(engine,c['workspace']) as session:
                erased=await expire_provider_receipts(session,now=datetime.now(timezone.utc),policy_version='c19-concurrent-v1',source_id=source)
                assert erased==[{'service':'search','id':str(c['ref'])}]
            async with tenant_session(engine,c['workspace']) as session:
                assert (await session.execute(text('SELECT public.buyeros_lock_search_receipt(:ws,:id)'),{'ws':c['workspace'],'id':c['ref']})).scalar_one() is False
        finally:await engine.dispose()
    asyncio.run(exercise())
    with pytest.raises(ValueError):consume(c)
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT response,request FROM search_receipts WHERE id=%s',(c['ref'],)).fetchone()==(None,{'redacted':True})
        assert db.execute('SELECT count(*) FROM source_documents WHERE run_id=%s AND excerpt IS NOT NULL',(c['run'],)).fetchone()==(0,)
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(c['operation'],)).fetchone()==('active',Decimal('0.005000'))
    assert len(c['calls'])==1

def test_intake_migration_rollback_retains_tombstones_and_closes_writes(received_case,monkeypatch):
    c=received_case;consume(c)
    from alembic import command
    from alembic.config import Config
    from tests.conftest import ALEMBIC_INI,SERVICE_ROOT
    from buyeros_api.settings import get_settings
    from tests.migration_guards import invoke_revision
    config=Config(str(ALEMBIC_INI));config.set_main_option('script_location',str(SERVICE_ROOT/'alembic'))
    with psycopg.connect(c['dsn']) as db:
        before=db.execute('SELECT request_hash,response_hash,intent_key FROM search_receipts WHERE id=%s',(c['ref'],)).fetchone()
    monkeypatch.setenv('BUYEROS_DATABASE_URL',c['dsn']);get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError,match='preserve controller policy history'):
            command.downgrade(config,'0043_c61_receipt_retention')
        invoke_revision(c['dsn'],config,'0044_c61_search_intake')
        with psycopg.connect(c['dsn']) as db:
            assert db.execute('SELECT public.buyeros_search_receipts_writable(),public.buyeros_model_receipts_writable(),public.buyeros_contact_receipts_writable()').fetchone()==(False,False,False)
            assert db.execute('SELECT request_hash,response_hash,intent_key FROM search_receipts WHERE id=%s',(c['ref'],)).fetchone()==before
        with pytest.raises(ValueError):consume(c)
    finally:
        invoke_revision(c['dsn'],config,'0058_conversation_threads','_fences',('0058_conversation_threads',))
        monkeypatch.setenv('BUYEROS_DATABASE_URL',runtime_role_dsn(c['dsn']));get_settings.cache_clear()
    assert consume(c)['source_count']==1

def test_worker_cannot_use_api_intake_lock_or_prepare_receipts(received_case):
    c=received_case
    async def exercise():
        from sqlalchemy import text
        from sqlalchemy.exc import DBAPIError
        engine=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')))
        try:
            async with tenant_session(engine,c['workspace']) as session:
                assert (await session.execute(text("SELECT has_table_privilege(current_user,'search_receipts','INSERT'),has_table_privilege(current_user,'receipt_source_bindings','INSERT')"))).one()==(False,False)
            with pytest.raises(DBAPIError):
                async with tenant_session(engine,c['workspace']) as session:await session.execute(text('SELECT public.buyeros_lock_search_receipt(:ws,:id)'),{'ws':c['workspace'],'id':c['ref']})
        finally:await engine.dispose()
    asyncio.run(exercise())

def test_intake_receipt_lock_fences_runtime_flip_until_transaction_finishes(received_case):
    c=received_case;before=counts(c)
    async def exercise():
        from sqlalchemy import text
        engine=create_async_engine(async_database_url(runtime_role_dsn(c['dsn'])))
        try:
            async with tenant_session(engine,c['workspace']) as session:
                assert (await session.execute(text('SELECT public.buyeros_lock_search_receipt(:ws,:id)'),{'ws':c['workspace'],'id':c['ref']})).scalar_one() is True
                with psycopg.connect(c['dsn']) as owner:
                    owner.execute("SET LOCAL lock_timeout='150ms'")
                    with pytest.raises(psycopg.errors.LockNotAvailable):owner.execute('UPDATE worker_runtime_control SET epoch=epoch+1 WHERE singleton=1')
            with psycopg.connect(c['dsn']) as owner:owner.execute('UPDATE worker_runtime_control SET epoch=epoch+1 WHERE singleton=1')
        finally:await engine.dispose()
    asyncio.run(exercise())
    with pytest.raises(ValueError):consume(c)
    assert counts(c)==before and len(c['calls'])==1
