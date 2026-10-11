"""Reviewed model route scope before new calls; originals reconcile unchanged."""
import asyncio,uuid
from dataclasses import replace
from decimal import Decimal
import psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.execution.external_runner import execute_external
from buyeros_api.providers import registry
from buyeros_api.providers.registry import ProviderRegistration,ProviderRegistry
from buyeros_api.providers.live_model import LiveModelAdapter,ModelResponseUnknown,validate_live_proposal
from buyeros_api.providers.model_receipts import PostgresModelReceipts
from tests.cutover_fixtures import role_dsn
from tests.test_run_model_admission_db import model_case,native_basis_case,review_case,page_case,run_case,project_api,admission_case,migrated,queue,dispatched,prepare
from tests.test_run_model_dispatch_db import clean_model_native_steps

pytestmark=pytest.mark.parametrize('run_case',['native'],indirect=True)

@pytest.fixture
def scope_case(model_case,monkeypatch):
    c=model_case
    item=ProviderRegistration(c['model_cap'],lambda:None,('synthetic:model-new-call-scope-only',),model_route=c['route'],model_id='local-owned-model-v1')
    others=tuple(x for x in registry.DEFAULT_REGISTRY.registrations if x.capability.service!='model')
    monkeypatch.setattr(registry,'SELECTED_LIVE_PROVIDERS',registry.SELECTED_LIVE_PROVIDERS|{'openai-responses'})
    monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry(others+(item,)))
    return {**c,'registration':item,'others':others}

def mutate(c,monkeypatch,gate,event=None):
    item=c['registration']
    if gate=='registry-empty':monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry(c['others']))
    elif gate=='unscoped':monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry(c['others']+(replace(item,model_route=None,model_id=None),)))
    elif gate=='review-changed':monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry(c['others']+(replace(item,sandbox_evidence=('synthetic:changed-review',)),)))
    elif gate=='route-changed':monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry(c['others']+(replace(item,model_route=replace(item.model_route,prompt_version='synthetic-changed-prompt')),)))
    elif gate=='model-changed':monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry(c['others']+(replace(item,model_id='synthetic-changed-model'),)))
    else:
        with psycopg.connect(c['dsn']) as db:
            if gate=='missing-hash':db.execute("UPDATE outbox_events SET payload=payload-'model_registry_contract_hash' WHERE id=%s",(event,))
            else:db.execute("UPDATE outbox_events SET payload=jsonb_set(payload,'{model_registry_contract_hash}',to_jsonb(%s::text)) WHERE id=%s",('a'*64,event))

def counts(c):
    with psycopg.connect(c['dsn']) as db:
        return tuple(db.execute('SELECT count(*) FROM '+table+' WHERE workspace_id=%s'+(" AND intent_key LIKE 'run-model:%%'" if table in {'provider_operations','outbox_events'} else ''),(c['workspace'],)).fetchone()[0] for table in ['outbox_events','provider_operations','model_receipts'])

def test_model_queue_freezes_full_reviewed_route_hash_separately_from_receipt_hash(scope_case):
    c=scope_case;event=queue(c);assert queue(c)==event
    with psycopg.connect(c['dsn']) as db:
        payload=db.execute('SELECT payload FROM outbox_events WHERE id=%s',(event,)).fetchone()[0]
        assert payload.get('model_registry_contract_hash')==c['registration'].contract_hash,'native model queue omits full reviewed route/model hash'
        assert payload['model_contract_hash']==ProviderRegistration(c['model_cap'],lambda:None).contract_hash
        assert db.execute('SELECT usage_counters,version FROM search_runs WHERE id=%s',(c['run'],)).fetchone()==c['before']
    assert counts(c)==(1,0,0)

@pytest.mark.parametrize('gate',['registry-empty','unscoped'])
def test_model_new_queue_requires_current_typed_registry_before_any_outbox(scope_case,monkeypatch,gate):
    c=scope_case;mutate(c,monkeypatch,gate)
    with pytest.raises(ValueError,match='model'):queue(c)
    assert counts(c)==(0,0,0)
    with psycopg.connect(c['dsn']) as db:assert db.execute('SELECT usage_counters,version FROM search_runs WHERE id=%s',(c['run'],)).fetchone()==c['before']

@pytest.mark.parametrize('gate',['registry-empty','review-changed','route-changed','model-changed','missing-hash','forged-hash'])
def test_model_prepare_rechecks_full_frozen_registry_before_hold_tokens_or_receipt(scope_case,monkeypatch,gate):
    c=scope_case;event=dispatched(c);mutate(c,monkeypatch,gate,event)
    with pytest.raises(ValueError,match='model'):prepare(c,event)
    assert counts(c)==(1,0,0)
    with psycopg.connect(c['dsn']) as db:assert db.execute('SELECT usage_counters,version FROM search_runs WHERE id=%s',(c['run'],)).fetchone()==c['before']

class Client:
    model_id='local-owned-model-v1'
    def __init__(self,calls,unknown=False):self.calls=calls;self.unknown=unknown
    async def complete(self,basis,route):
        self.calls.append('synthetic-submit')
        if self.unknown:raise ModelResponseUnknown('synthetic original response lost')
        proposal={'company_id':basis['company_id'],'verdict':'needs_review','rationale':'Synthetic context requires factual human review','citations':[]}
        return {'provider_ref':'resp_model_scope_owned1','proposal':proposal,'assessment':validate_live_proposal(proposal,basis),'usage':{'input_tokens':100,'output_tokens':60,'total_tokens':160},'model_id':self.model_id,'prompt_version':route.prompt_version}

async def submit(c,prepared,calls,*,unknown=False,repeat=False):
    engine=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')))
    try:
        adapter=LiveModelAdapter(capability=c['model_cap'],client=Client(calls,unknown),receipts=PostgresModelReceipts(engine,c['workspace'],c['model_cap'],model_id=Client.model_id,route=c['route']))
        if repeat:return await adapter.submit(prepared.intent),await adapter.status(str(prepared.receipt_id))
        return await execute_external(engine,c['workspace'],prepared.operation_id,1,adapter,prepared.intent,environment='test')
    finally:await engine.dispose()

@pytest.mark.parametrize('gate',['registry-empty','review-changed','route-changed','missing-hash'])
def test_prepared_model_claim_blocks_current_scope_change_before_worker_submit(scope_case,monkeypatch,gate):
    c=scope_case;event=dispatched(c);value=prepare(c,event);calls=[];mutate(c,monkeypatch,gate,event)
    asyncio.run(submit(c,value,calls));assert calls==[],'prepared model claim submitted despite revoked reviewed scope'
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT state FROM model_receipts WHERE operation_id=%s',(value.operation_id,)).fetchone()==('prepared',)
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(value.operation_id,)).fetchone()==('active',Decimal('0.100000'))
        assert db.execute('SELECT count(*) FROM cost_events').fetchone()==(0,)

@pytest.mark.parametrize('outcome',['received','unknown'])
def test_original_model_receipt_reconciles_after_scope_revocation_without_new_submit(scope_case,monkeypatch,outcome):
    c=scope_case;event=dispatched(c);value=prepare(c,event);calls=[]
    assert asyncio.run(submit(c,value,calls,unknown=outcome=='unknown'))==('accepted' if outcome=='received' else 'unknown')
    assert len(calls)==1
    with psycopg.connect(c['dsn']) as db:before=db.execute('SELECT usage_counters,version FROM search_runs WHERE id=%s',(c['run'],)).fetchone()
    mutate(c,monkeypatch,'missing-hash',event);mutate(c,monkeypatch,'registry-empty')
    repeated,status=asyncio.run(submit(c,value,calls,repeat=True));assert len(calls)==1
    assert repeated.state==('accepted' if outcome=='received' else 'unknown')
    assert status.state==('succeeded' if outcome=='received' else 'unknown')
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT usage_counters,version FROM search_runs WHERE id=%s',(c['run'],)).fetchone()==before
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(value.operation_id,)).fetchone()==('active',Decimal('0.100000'))
        assert db.execute('SELECT count(*) FROM cost_events').fetchone()==(0,)
    assert counts(c)==(1,1,1)
