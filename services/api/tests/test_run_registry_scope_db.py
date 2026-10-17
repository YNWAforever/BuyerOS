"""Current registry scope for NEW calls; synthetic owned DB/HTTP only."""
import asyncio,json,uuid
from dataclasses import replace
from decimal import Decimal
import httpx,psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.api.routes.runs import selected_run_capability
from buyeros_api.db.session import tenant_session
from buyeros_api.execution.external_runner import execute_external,reconcile_intent_key
from buyeros_api.providers import base,registry
from buyeros_api.providers.registry import ProviderRegistration,ProviderRegistry
from buyeros_api.providers.live_search import LiveSearchAdapter,PostgresSearchReceipts,BraveSearchClient
from buyeros_api.services.run_search import resume_received_run_search
from tests.test_run_search_preparation_db import run_case,migrated,project_api,admission_case,prepare,dispatch,observe
from tests.test_run_admission_integration_db import _post,_count
from tests.test_provider_contracts import capability
from tests.cutover_fixtures import role_dsn
from tests.conftest import runtime_role_dsn

def selected(monkeypatch,cap):
    calls=[]
    item=ProviderRegistration(cap,lambda:calls.append('factory-must-not-run'),
        ('synthetic:scope-proof-only',),frozenset({'market','language'}),(('US',('en',)),),
        policy_account_reference='owned-scope-account')
    monkeypatch.setattr(base,'SELECTED_LIVE_PROVIDERS',frozenset({'brave-search'}))
    monkeypatch.setattr(registry,'SELECTED_LIVE_PROVIDERS',frozenset({'brave-search'}))
    monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry((item,)))
    return item,calls

def frozen_scope(c,monkeypatch):
    item,calls=selected(monkeypatch,c['cap'])
    with psycopg.connect(c['dsn']) as db:
        snapshot=db.execute('SELECT execution_snapshot FROM search_runs WHERE id=%s',(c['run'],)).fetchone()[0]
        # Explicit owned fixture overlay; never changes a production row.
        snapshot['capability'].update(registry_contract_hash=item.contract_hash,market_languages={'US':['en']},
                                      policy_binding=item.policy_binding.model_dump(mode='json'))
        from tests.policy_activation_fixtures import approve_research_fixture
        approve_research_fixture(c['dsn'],c['workspace'],c['project'],domains=('example.org','fixture.invalid','fixture.example','sensors.example.test'),
            search=item.policy_binding)
        db.execute('UPDATE search_runs SET execution_snapshot=%s::jsonb WHERE id=%s',(json.dumps(snapshot),c['run']))
    return item,calls

def change_scope(c,monkeypatch,item,change):
    if change=='registry-empty':monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry(()))
    elif change in {'scope-changed','evidence-changed'}:
        newer=replace(item,market_languages=(('US',('zh-HK',)),)) if change=='scope-changed' else replace(item,sandbox_evidence=('synthetic:new-proof',))
        monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry((newer,)))
    elif change in {'missing-hash','forged-hash','matrix-changed'}:
        with psycopg.connect(c['dsn']) as db:
            snapshot=db.execute('SELECT execution_snapshot FROM search_runs WHERE id=%s',(c['run'],)).fetchone()[0]
            if change=='missing-hash':snapshot['capability'].pop('registry_contract_hash')
            elif change=='forged-hash':snapshot['capability']['registry_contract_hash']='0'*64
            else:snapshot['capability']['market_languages']={'US':['zh-HK']}
            db.execute('UPDATE search_runs SET execution_snapshot=%s::jsonb WHERE id=%s',(json.dumps(snapshot),c['run']))

def test_selected_scope_returns_full_registry_hash_without_factory(monkeypatch):
    cap=capability(provider='brave-search',service='search',markets=frozenset({'US'}),languages=frozenset({'en'}),roles=frozenset({'company'}))
    item,calls=selected(monkeypatch,cap)
    actual,environment=selected_run_capability()
    assert environment=='production' and calls==[]
    assert actual.get('registry_contract_hash')==item.contract_hash,'Full reviewed registry scope is absent from producer'
    assert actual['receipt_contract_hash']==ProviderRegistration(cap,lambda:None).contract_hash

def test_real_admission_freezes_registry_hash_and_explicit_pairs(admission_case,monkeypatch):
    from buyeros_api.settings import get_settings
    api,dsn=admission_case
    cap=capability(provider='brave-search',service='search',markets=frozenset({'US'}),languages=frozenset({'en'}),roles=frozenset({'company','distributor'}))
    item,calls=selected(monkeypatch,cap)
    from tests.policy_activation_fixtures import approve_research_fixture
    from tests.test_run_admission_integration_db import PROJECT_A,WORKSPACE_A,RESEARCH_FIXTURE_DOMAINS
    approve_research_fixture(dsn,WORKSPACE_A,PROJECT_A,domains=RESEARCH_FIXTURE_DOMAINS,search=item.policy_binding)
    api.app.dependency_overrides.pop(selected_run_capability)
    monkeypatch.setenv('BUYEROS_PAID_ADMISSION_ENABLED','true');get_settings.cache_clear()
    try:
        reply=_post(api,key='c61-current-registry-scope');assert reply.status_code==202,reply.text
        again=_post(api,key='c61-current-registry-scope');assert again.status_code==202 and again.json()['data']==reply.json()['data']
        with psycopg.connect(dsn) as db:snapshot=db.execute('SELECT execution_snapshot FROM search_runs WHERE id=%s',(reply.json()['data']['id'],)).fetchone()[0]
        assert snapshot['capability'].get('registry_contract_hash')==item.contract_hash,'Admission loses full registry scope'
        assert snapshot['capability']['market_languages']=={'US':['en']}
        assert _count(dsn,'search_runs')==_count(dsn,'outbox_events')==1
        assert _count(dsn,'provider_operations')==_count(dsn,'cost_events')==0 and calls==[]
    finally:get_settings.cache_clear()

@pytest.mark.parametrize('change',['stable','registry-empty','scope-changed','evidence-changed','missing-hash','forged-hash','matrix-changed'])
def test_new_prepare_requires_current_full_scope_before_hold_or_counters(run_case,monkeypatch,change):
    c=run_case;item,calls=frozen_scope(c,monkeypatch);change_scope(c,monkeypatch,item,change)
    before=observe(c)
    if change=='stable':
        first=prepare(c);again=prepare(c)
        assert first==again and first.intent.role=='company' and first.request.language=='en'
        after=observe(c);assert after['operations']==before['operations']+1 and after['holds']==before['holds']+1
    else:
        with pytest.raises(ValueError):prepare(c)
        assert observe(c)==before,'Blocked current scope must roll back all writes'
    assert calls==[] and c['calls']==[]

@pytest.mark.parametrize('change',['registry-empty','scope-changed','missing-hash'])
def test_prepared_claim_rechecks_scope_before_worker_http(run_case,monkeypatch,change):
    c=run_case;item,calls=frozen_scope(c,monkeypatch);first=prepare(c)
    change_scope(c,monkeypatch,item,change)
    assert asyncio.run(dispatch(c,first))=='unknown' and c['calls']==[]
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(first.operation_id,)).fetchone()==('active',Decimal('0.005000'))
        assert db.execute('SELECT count(*) FROM cost_events').fetchone()==(0,)
    assert calls==[]

@pytest.mark.parametrize('outcome',['unknown','received-after-crash'])
def test_original_uncertain_receipt_reconciles_after_registry_revocation_without_post(run_case,monkeypatch,outcome):
    c=run_case;item,calls=frozen_scope(c,monkeypatch);first=prepare(c)
    if outcome=='unknown':assert asyncio.run(dispatch(c,first,unknown=True))=='unknown'
    else:
        class SimulatedCrash(BaseException):pass
        submit=LiveSearchAdapter.submit
        async def accepted_then_crash(self,intent):
            result=await submit(self,intent);assert result.state=='accepted'
            raise SimulatedCrash('synthetic crash after original durable receipt')
        monkeypatch.setattr(LiveSearchAdapter,'submit',accepted_then_crash)
        with pytest.raises(SimulatedCrash):asyncio.run(dispatch(c,first))
        monkeypatch.setattr(LiveSearchAdapter,'submit',submit)
        assert asyncio.run(dispatch(c,first))=='unknown'
    assert len(c['calls'])==1
    # Model an original pre-upgrade receipt: no new scope hash and no registry.
    change_scope(c,monkeypatch,item,'missing-hash');change_scope(c,monkeypatch,item,'registry-empty')
    async def reconcile_only():
        key=reconcile_intent_key(first.operation_id)
        with psycopg.connect(c['dsn']) as db:db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 WHERE intent_key=%s",(key,))
        worker=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')))
        api=create_async_engine(async_database_url(runtime_role_dsn(c['dsn'])))
        def unexpected(req):c['calls'].append(req);raise AssertionError('reconciliation may only read original receipt')
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(unexpected)) as http:
                adapter=LiveSearchAdapter(capability=c['cap'],receipts=PostgresSearchReceipts(worker,c['workspace'],c['cap']),client=BraveSearchClient(api_key='synthetic-offline-only',http=http,language_codes={'en':'en'},api_version='2026-10-01'))
                state=await execute_external(worker,c['workspace'],first.operation_id,1,adapter,first.intent,environment='test',outbox_intent_key=key)
            assert state==('unknown' if outcome=='unknown' else 'succeeded')
            if outcome!='unknown':
                async with tenant_session(api,c['workspace']) as session:result=await resume_received_run_search(session,workspace_id=c['workspace'],operation_id=first.operation_id,capability=c['cap'])
                assert result['candidate_count']==1
        finally:await worker.dispose();await api.dispose()
    asyncio.run(reconcile_only())
    assert len(c['calls'])==1 and calls==[]
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(first.operation_id,)).fetchone()==('active',Decimal('0.005000'))
        assert db.execute('SELECT count(*) FROM cost_events').fetchone()==(0,)

@pytest.mark.parametrize('value',[None,'malformed'])
def test_real_admission_without_full_registry_hash_stays_unavailable(admission_case,monkeypatch,value):
    api,dsn=admission_case
    cap=capability(provider='brave-search',service='search',markets=frozenset({'US'}),languages=frozenset({'en'}),roles=frozenset({'company','distributor'}))
    item,calls=selected(monkeypatch,cap);caps,_=selected_run_capability()
    if value is None:caps.pop('registry_contract_hash')
    else:caps['registry_contract_hash']=value
    # Explicit owned dependency injection verifies the already-correct server guard.
    api.app.dependency_overrides[selected_run_capability]=lambda:(caps,'test')
    reply=_post(api,key='c61-missing-registry-'+str(value));assert reply.status_code==503,reply.text
    assert _count(dsn,'search_runs')==_count(dsn,'outbox_events')==_count(dsn,'provider_operations')==_count(dsn,'cost_events')==0
    assert calls==[]
