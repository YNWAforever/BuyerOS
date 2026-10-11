"""Actual producer -> registry factory -> native receipt; owned synthetic HTTP only."""
import asyncio,uuid
from decimal import Decimal
import httpx,psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.api.routes.runs import selected_run_capability
from buyeros_api.api.worker_schemas import JobEnvelope
from buyeros_api.providers import base,registry
from buyeros_api.providers.base import Money
from buyeros_api.providers.registry import ProviderRegistration,ProviderRegistry
from buyeros_api.providers.live_search import LiveSearchAdapter,PostgresSearchReceipts,BraveSearchClient
from buyeros_api.services.worker_execution import execute_step
from buyeros_api.settings import get_settings
from tests.test_provider_contracts import capability
from tests.test_api_projects_db import api as project_api,WORKSPACE_A
from tests.test_run_admission_integration_db import admission_case,_post,_count
from tests.conftest import runtime_role_dsn
from tests.cutover_fixtures import role_dsn

@pytest.fixture
def migrated(isolated_migrated):return isolated_migrated

@pytest.mark.parametrize('outcome',['received','unknown'])
def test_real_selected_producer_and_native_registry_factory_share_original_scope_and_one_submit(admission_case,monkeypatch,outcome):
    api,dsn=admission_case;workspace=uuid.UUID(WORKSPACE_A);calls=[];factories=[];run=None;outbox=None;key=None
    cap=capability(provider='brave-search',service='search',markets=frozenset({'US'}),languages=frozenset({'en'}),roles=frozenset({'company','distributor'}),max_liability=Money(Decimal('0.005000')))
    holder={}
    def factory():
        factories.append('native-dispatch');return holder['adapter']
    item=ProviderRegistration(cap,factory,('synthetic:actual-producer-fixture-only',),frozenset({'market','language'}),(('US',('en',)),))
    monkeypatch.setattr(base,'SELECTED_LIVE_PROVIDERS',frozenset({'brave-search'}))
    monkeypatch.setattr(registry,'SELECTED_LIVE_PROVIDERS',frozenset({'brave-search'}))
    monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry((item,)))
    monkeypatch.setenv('BUYEROS_PAID_ADMISSION_ENABLED','true');monkeypatch.setenv('BUYEROS_CLOUDFLARE_EXECUTION_ENABLED','true');get_settings.cache_clear()
    api.app.dependency_overrides.pop(selected_run_capability)
    try:
        with psycopg.connect(dsn) as db:
            db.execute("UPDATE worker_runtime_control SET backend='cloudflare',enabled=true,epoch=epoch+1,active_owner=NULL,active_until=NULL WHERE singleton=1")
            db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
        reply=_post(api,key='c61-native-selected-producer-'+outcome);assert reply.status_code==202,reply.text
        run=uuid.UUID(reply.json()['data']['id'])
        assert factories==[] and calls==[]
        with psycopg.connect(dsn) as db:
            snapshot=db.execute('SELECT execution_snapshot FROM search_runs WHERE id=%s',(run,)).fetchone()[0]
            assert snapshot['capability']['registry_contract_hash']==item.contract_hash and snapshot['capability']['market_languages']=={'US':['en']}
            # Native dispatcher lease, not an execution snapshot/capability overlay.
            db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 WHERE event_type='run.discover' AND payload->>'run_id'=%s",(str(run),))
            outbox,key,epoch=db.execute("SELECT id,intent_key,runtime_epoch FROM outbox_events WHERE event_type='run.discover' AND payload->>'run_id'=%s",(str(run),)).fetchone()
        envelope=JobEnvelope(v=1,workspace_id=workspace,outbox_id=outbox,generation=1,runtime_epoch=epoch)
        async def native():
            worker=create_async_engine(async_database_url(role_dsn(dsn,'buyeros_worker')))
            research=create_async_engine(async_database_url(runtime_role_dsn(dsn)))
            def response(req):
                calls.append(req)
                if outcome=='unknown':raise httpx.ReadTimeout('owned synthetic lost response',request=req)
                return httpx.Response(200,json={'web':{'results':[{'url':'https://native-producer.example.test/company','title':'Unreviewed company','description':'SYNTHETIC_SEARCH_METADATA_ONLY'}]}})
            try:
                async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as http:
                    holder['adapter']=LiveSearchAdapter(capability=cap,receipts=PostgresSearchReceipts(worker,workspace,cap),client=BraveSearchClient(api_key='synthetic-offline-only',http=http,language_codes={'en':'en'},api_version='2026-10-01'))
                    # No adapter parameter: exercises the actual code-owned registry factory.
                    invalid=await execute_step(worker,envelope,'step:0',research_engine=research,environment='test')
                    assert invalid.state=='blocked' and invalid.code=='INVALID_INTENT' and factories==calls==[]
                    first=await execute_step(worker,envelope,'start',research_engine=research,environment='test')
                    again=await execute_step(worker,envelope,'start',research_engine=research,environment='test')
                    assert first==again and first.state=='reconcile' and first.code=='PROVIDER_UNKNOWN'
            finally:await worker.dispose();await research.dispose()
        asyncio.run(native())
        assert len(factories)==len(calls)==1
        again=_post(api,key='c61-native-selected-producer-'+outcome)
        assert again.status_code==202 and again.json()['data']==reply.json()['data']
        with psycopg.connect(dsn) as db:
            assert db.execute('SELECT execution_snapshot FROM search_runs WHERE id=%s',(run,)).fetchone()==(snapshot,)
            assert db.execute("SELECT count(*) FROM outbox_events WHERE event_type='run.discover' AND payload->>'run_id'=%s",(str(run),)).fetchone()==(1,)
            operation=db.execute('SELECT id,status,intent_key FROM provider_operations WHERE workspace_id=%s',(workspace,)).fetchall();assert len(operation)==1 and operation[0][2]==key
            assert operation[0][1]==('accepted' if outcome=='received' else 'unknown')
            receipt=db.execute('SELECT state,operation_id,contract_hash FROM search_receipts WHERE workspace_id=%s',(workspace,)).fetchall()
            assert len(receipt)==1 and receipt[0][:2]==('received' if outcome=='received' else 'unknown',operation[0][0])
            assert receipt[0][2]==snapshot['capability']['receipt_contract_hash']
            assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(operation[0][0],)).fetchone()==('active',Decimal('0.005000'))
            rows=db.execute('SELECT canonical_company_id,merge_state FROM raw_candidates WHERE run_id=%s',(run,)).fetchall()
            assert rows==([(None,'needs_review')] if outcome=='received' else [])
            assert db.execute('SELECT count(*) FROM cost_events').fetchone()==(0,)
            assert db.execute('SELECT count(*) FROM search_runs WHERE workspace_id=%s',(workspace,)).fetchone()==(1,)
    finally:
        # Only this disposable run/intent is cleaned, after immutable assertions.
        if run is not None:
            with psycopg.connect(dsn) as db:
                db.execute("DELETE FROM worker_steps WHERE workspace_id=%s AND outbox_id IN(SELECT id FROM outbox_events WHERE workspace_id=%s AND (id=%s OR payload->>'operation_id' IN(SELECT id::text FROM provider_operations WHERE workspace_id=%s AND intent_key=%s)))",(workspace,workspace,outbox,workspace,key))
                db.execute('DELETE FROM receipt_source_bindings WHERE workspace_id=%s AND source_id IN(SELECT id FROM source_documents WHERE run_id=%s)',(workspace,run))
                db.execute('DELETE FROM raw_candidates WHERE workspace_id=%s AND run_id=%s',(workspace,run))
                db.execute('DELETE FROM source_documents WHERE workspace_id=%s AND run_id=%s',(workspace,run))
                db.execute('DELETE FROM search_receipts WHERE workspace_id=%s AND outbox_id=%s',(workspace,outbox))
                db.execute('DELETE FROM budget_reservation_allocations WHERE workspace_id=%s AND reservation_id IN(SELECT id FROM budget_reservations WHERE workspace_id=%s AND operation_id IN(SELECT id FROM provider_operations WHERE workspace_id=%s AND intent_key=%s))',(workspace,workspace,workspace,key))
                db.execute('DELETE FROM budget_reservations WHERE workspace_id=%s AND operation_id IN(SELECT id FROM provider_operations WHERE workspace_id=%s AND intent_key=%s)',(workspace,workspace,key))
                db.execute('DELETE FROM provider_operations WHERE workspace_id=%s AND intent_key=%s',(workspace,key))
                assert db.execute('SELECT count(*) FROM search_receipts WHERE workspace_id=%s AND outbox_id=%s',(workspace,outbox)).fetchone()==(0,)
        get_settings.cache_clear()
