"""Restricted-role native model scheduling/preparation; synthetic protocol only."""
import asyncio,importlib,json,uuid
from datetime import datetime,timezone
from decimal import Decimal
import psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.api.errors import ApiError
from buyeros_api.db.session import tenant_session
from buyeros_api.providers import base
from buyeros_api.providers.base import ProviderCapability,Money
from buyeros_api.providers.model import ModelRoute
from tests.cutover_fixtures import role_dsn
from tests.test_research_native_basis_db import native_basis_case,review_case,page_case,run_case,project_api,migrated
from tests.test_run_admission_integration_db import admission_case as base_admission_case,ICP_ID
from buyeros_api.db.icp import canonical_hash

@pytest.fixture
def admission_case(project_api,seeded):
    # Complete the owned synthetic model profile BEFORE original run admission.
    # Never rewrite an admitted snapshot, native claim or production profile.
    original=base_admission_case.__wrapped__(project_api,seeded)
    value=next(original)
    try:
        with psycopg.connect(seeded) as db:
            content=db.execute('SELECT content FROM icp_versions WHERE id=%s',(ICP_ID,)).fetchone()[0]
            for requirement in content['requirements']:requirement['hard_exclusion']=False
            db.execute('UPDATE icp_versions SET content=%s::jsonb,content_hash=%s WHERE id=%s',(json.dumps(content),canonical_hash(content),ICP_ID))
        yield value
    finally:
        try:next(original)
        except StopIteration:pass


def port():
    spec=importlib.util.find_spec('buyeros_api.services.run_model')
    assert spec is not None,'C61-19 atomic native model scheduling/preparation is missing'
    module=importlib.import_module('buyeros_api.services.run_model')
    assert callable(getattr(module,'queue_run_model',None)) and callable(getattr(module,'prepare_run_model',None))
    return module

def build_model_registration(monkeypatch):
    monkeypatch.setattr(base,'SELECTED_LIVE_PROVIDERS',base.SELECTED_LIVE_PROVIDERS|{'openai-responses'})
    cap=ProviderCapability(provider='openai-responses',adapter_version='c61-local-model-v1',service='model',markets=frozenset({'US'}),languages=frozenset({'en'}),roles=frozenset({'company'}),auth_model='server-key',pricing_version='local-model-price-v1',max_liability=Money(Decimal('0.100000'),'USD'),idempotency='verified',status='verified',callback='unsupported',cancel='unsupported',retention='fixture-only',verified_at=datetime.now(timezone.utc),source_urls=('https://developers.openai.com/api/reference/responses/overview',))
    route=ModelRoute('c61-local-prompt-v1',frozenset(),1000,500,30,0,'c61-local-route-v1')
    from buyeros_api.providers import registry
    from buyeros_api.providers.registry import ProviderRegistration,ProviderRegistry
    scope=ProviderRegistration(cap,lambda:None,('synthetic:owned-native-model-fixture-only',),model_route=route,model_id='local-owned-model-v1',
                               policy_account_reference='owned-native-model-account')
    others=tuple(item for item in registry.DEFAULT_REGISTRY.registrations if item.capability.service!='model')
    monkeypatch.setattr(registry,'SELECTED_LIVE_PROVIDERS',registry.SELECTED_LIVE_PROVIDERS|{'openai-responses'})
    monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry(others+(scope,)))
    return scope


from tests.test_research_page_scope_db import page_case as _page_case


@pytest.fixture
def page_case(run_case,native_model_registration):
    return _page_case.__wrapped__(run_case)


@pytest.fixture
def model_case(native_basis_case,native_model_registration):
    c=native_basis_case
    scope=native_model_registration
    cap,route=scope.capability,scope.model_route
    with psycopg.connect(c['dsn']) as db:
        before=db.execute('SELECT usage_counters,version FROM search_runs WHERE id=%s',(c['run'],)).fetchone()
    try:yield {**c,'model_cap':cap,'route':route,'before':before,'registration':scope}
    finally:
        with psycopg.connect(c['dsn']) as db:
            ids=[x[0] for x in db.execute("SELECT id FROM provider_operations WHERE workspace_id=%s AND intent_key LIKE 'run-model:%%'",(c['workspace'],))]
            db.execute("DELETE FROM model_receipts WHERE workspace_id=%s AND intent_key LIKE 'run-model:%%'",(c['workspace'],))
            if ids:
                db.execute('DELETE FROM budget_reservation_allocations WHERE reservation_id IN(SELECT id FROM budget_reservations WHERE operation_id=ANY(%s))',(ids,))
                db.execute('DELETE FROM budget_reservations WHERE operation_id=ANY(%s)',(ids,))
            db.execute("DELETE FROM outbox_events WHERE workspace_id=%s AND intent_key LIKE 'run-model:%%'",(c['workspace'],))
            db.execute("DELETE FROM provider_operations WHERE workspace_id=%s AND intent_key LIKE 'run-model:%%'",(c['workspace'],))

async def queued(c,session,**changes):
    return await port().queue_run_model(session,workspace_id=c['workspace'],run_id=c['run'],buyer_id=c['buyer'],capability=c['model_cap'],route=c['route'],model_id='local-owned-model-v1',market='US',language='en',environment='test',**changes)

def queue(c):
    async def run():
        engine=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_api')))
        try:
            async with tenant_session(engine,c['workspace']) as session:return await queued(c,session)
        finally:await engine.dispose()
    return asyncio.run(run())

def dispatched(c):
    event=queue(c)
    with psycopg.connect(c['dsn']) as db:db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 WHERE id=%s",(event,))
    return event

async def prepared(c,event,session,**changes):
    args={'workspace_id':c['workspace'],'outbox_id':event,'generation':1,'capability':c['model_cap'],'route':c['route'],'model_id':'local-owned-model-v1','environment':'test',**changes}
    return await port().prepare_run_model(session,**args)

def prepare(c,event,**changes):
    async def run():
        engine=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_api')))
        try:
            async with tenant_session(engine,c['workspace']) as session:return await prepared(c,event,session,**changes)
        finally:await engine.dispose()
    return asyncio.run(run())

def model_counts(c):
    with psycopg.connect(c['dsn']) as db:
        return tuple(db.execute(sql,(c['workspace'],)).fetchone()[0] for sql in ["SELECT count(*) FROM provider_operations WHERE workspace_id=%s AND capability='model'","SELECT count(*) FROM model_receipts WHERE workspace_id=%s","SELECT count(*) FROM budget_reservations r JOIN provider_operations o ON o.id=r.operation_id WHERE r.workspace_id=%s AND o.capability='model'"])

def test_queue_then_atomic_prepare_freezes_one_basis_operation_receipt_hold_and_token_ceiling(model_case):
    c=model_case;event=queue(c);assert queue(c)==event and model_counts(c)==(0,0,0)
    with psycopg.connect(c['dsn']) as db:
        payload,state=db.execute('SELECT payload,state FROM outbox_events WHERE id=%s',(event,)).fetchone()
        assert state=='ready' and 'source_excerpt' not in json.dumps(payload) and 'actor_id' not in payload
        db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 WHERE id=%s",(event,))
    value=prepare(c,event);assert prepare(c,event)==value and model_counts(c)==(1,1,1)
    assert value.request.basis['evidence'][0]['current'] is True and value.request.basis['evidence'][0]['is_inference'] is True
    with psycopg.connect(c['dsn']) as db:
        counters,version=db.execute('SELECT usage_counters,version FROM search_runs WHERE id=%s',(c['run'],)).fetchone()
        assert counters['model_tokens']==c['before'][0]['model_tokens']+1500 and counters['in_flight']==c['before'][0]['in_flight']+1 and version==c['before'][1]+1
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(value.operation_id,)).fetchone()==('active',Decimal('0.100000'))
        assert db.execute('SELECT count(*) FROM cost_events WHERE operation_id=%s',(value.operation_id,)).fetchone()==(0,)
        assert db.execute('SELECT request_hash,generation FROM model_receipts WHERE id=%s',(value.receipt_id,)).fetchone()==(value.request.digest,1)
        assert db.execute('SELECT count(*) FROM companies WHERE workspace_id=%s',(c['workspace'],)).fetchone()==(2,)
    assert c['transport'].calls==1

def test_caller_rollback_leaves_no_partial_model_receipt_hold_operation_or_usage(model_case):
    c=model_case;event=dispatched(c)
    async def run():
        engine=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_api')))
        try:
            with pytest.raises(RuntimeError,match='after atomic prepare'):
                async with tenant_session(engine,c['workspace']) as session:
                    await prepared(c,event,session);raise RuntimeError('after atomic prepare')
        finally:await engine.dispose()
    asyncio.run(run());assert model_counts(c)==(0,0,0)
    with psycopg.connect(c['dsn']) as db:assert db.execute('SELECT usage_counters,version FROM search_runs WHERE id=%s',(c['run'],)).fetchone()==c['before']

@pytest.mark.parametrize('mutation',['actor','source','license','offer','project','epoch','event-hash','generation','route','foreign-buyer','foreign-workspace','token-limit','concurrency','duration','budget'])
def test_model_prepare_rechecks_current_native_basis_fence_contract_and_run_ceilings(model_case,mutation):
    c=model_case;event=dispatched(c);changes={}
    with psycopg.connect(c['dsn']) as db:
        if mutation=='actor':db.execute('UPDATE memberships SET active=false WHERE workspace_id=%s AND user_id=%s',(c['workspace'],c['actor']))
        elif mutation=='source':db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c['page_source'],))
        elif mutation=='license':db.execute("UPDATE policy_decisions SET expires_at=now()-interval '1 second' WHERE id=%s",(c['policy'],))
        elif mutation=='offer':db.execute('UPDATE projects SET offer_revision=offer_revision+1 WHERE id=%s',(c['project'],))
        elif mutation=='project':db.execute("UPDATE projects SET status='archived' WHERE id=%s",(c['project'],))
        elif mutation=='epoch':db.execute('UPDATE worker_runtime_control SET epoch=epoch+1 WHERE singleton=1')
        elif mutation=='event-hash':db.execute("UPDATE outbox_events SET payload=jsonb_set(payload,'{model_request_hash}',to_jsonb(%s::text)) WHERE id=%s",('0'*64,event))
        elif mutation=='foreign-buyer':db.execute("UPDATE outbox_events SET payload=jsonb_set(payload,'{buyer_id}',to_jsonb(%s::text)) WHERE id=%s",(str(uuid.uuid4()),event))
        elif mutation=='token-limit':db.execute("UPDATE search_runs SET limits=jsonb_set(limits,'{max_model_tokens}','1000') WHERE id=%s",(c['run'],))
        elif mutation=='concurrency':db.execute("UPDATE search_runs SET usage_counters=jsonb_set(usage_counters,'{in_flight}','4') WHERE id=%s",(c['run'],))
        elif mutation=='duration':db.execute("UPDATE search_runs SET first_dispatch_at=now()-interval '2 hours' WHERE id=%s",(c['run'],))
        elif mutation=='budget':db.execute("UPDATE budget_accounts SET approved_limit=0 WHERE workspace_id=%s AND scope='run' AND scope_id=%s",(c['workspace'],c['run']))
        elif mutation=='generation':changes['generation']=2
        elif mutation=='route':changes['route']=ModelRoute('changed-prompt',frozenset(),1000,500,30,0,'c61-local-route-v1')
        else:changes['workspace_id']=uuid.uuid4()
    with pytest.raises(ValueError if mutation!='budget' else ApiError):prepare(c,event,**changes)
    assert model_counts(c)==(0,0,0)
    with psycopg.connect(c['dsn']) as db:assert db.execute('SELECT usage_counters FROM search_runs WHERE id=%s',(c['run'],)).fetchone()[0]['model_tokens']==c['before'][0]['model_tokens']

@pytest.mark.parametrize('status',['accepted','unknown'])
def test_model_accepted_unknown_prepare_requires_reconciliation_without_new_hold_or_tokens(model_case,status):
    c=model_case;event=dispatched(c);value=prepare(c,event)
    with psycopg.connect(c['dsn']) as db:
        before=db.execute('SELECT usage_counters,version FROM search_runs WHERE id=%s',(c['run'],)).fetchone()
        db.execute('UPDATE provider_operations SET status=%s WHERE id=%s',(status,value.operation_id))
    with pytest.raises(ValueError,match='reconciliation'):prepare(c,event)
    assert model_counts(c)==(1,1,1)
    with psycopg.connect(c['dsn']) as db:assert db.execute('SELECT usage_counters,version FROM search_runs WHERE id=%s',(c['run'],)).fetchone()==before

def test_concurrent_model_preparation_claims_one_durable_intent_and_upper_bound(model_case):
    c=model_case;event=dispatched(c)
    async def run():
        engine=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_api')))
        try:
            async def one():
                async with tenant_session(engine,c['workspace']) as session:return await prepared(c,event,session)
            a,b=await asyncio.gather(one(),one());assert a==b
        finally:await engine.dispose()
    asyncio.run(run());assert model_counts(c)==(1,1,1)
    with psycopg.connect(c['dsn']) as db:assert db.execute('SELECT usage_counters FROM search_runs WHERE id=%s',(c['run'],)).fetchone()[0]['model_tokens']==c['before'][0]['model_tokens']+1500

def test_changed_source_cannot_silently_queue_a_replacement_model_intent(model_case):
    c=model_case;event=queue(c)
    with psycopg.connect(c['dsn']) as db:db.execute('UPDATE evidence SET version=version+1 WHERE id=%s',(c['evidence'],))
    with pytest.raises(ValueError):queue(c)
    with psycopg.connect(c['dsn']) as db:assert db.execute("SELECT count(*) FROM outbox_events WHERE workspace_id=%s AND intent_key LIKE 'run-model:%%'",(c['workspace'],)).fetchone()==(1,)
    assert model_counts(c)==(0,0,0)

def test_native_model_queue_default_production_gate_stays_closed(model_case):
    c=model_case;module=port()
    async def run():
        engine=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_api')))
        try:
            with pytest.raises(ValueError,match='paid model admission disabled'):
                async with tenant_session(engine,c['workspace']) as session:
                    await module.queue_run_model(session,workspace_id=c['workspace'],run_id=c['run'],buyer_id=c['buyer'],capability=c['model_cap'],route=c['route'],model_id='local-owned-model-v1',market='US',language='en')
        finally:await engine.dispose()
    asyncio.run(run());assert model_counts(c)==(0,0,0)
