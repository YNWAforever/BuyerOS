"""First explicit page review to real native model factory; owned synthetic IO."""
import asyncio,json,uuid
from dataclasses import replace
from datetime import datetime,timezone
from decimal import Decimal
import psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.api.worker_schemas import JobEnvelope
from buyeros_api.db.outbox import OutboxEvent
from buyeros_api.providers import base,registry
from buyeros_api.providers.base import Money,ProviderCapability
from buyeros_api.providers.registry import ProviderRegistration,ProviderRegistry
from buyeros_api.providers.live_model import LiveModelAdapter,ModelRoute,ModelResponseUnknown,validate_live_proposal
from buyeros_api.providers.model_receipts import PostgresModelReceipts
from buyeros_api.services.worker_execution import execute_step
from buyeros_api.settings import get_settings
from tests.cutover_fixtures import role_dsn
from tests.test_research_review_registry_db import selected_review_case,review_case,page_case,project_api,migrated
from tests.test_native_query_continuation_db import query_case as run_case
from tests.test_run_model_admission_db import admission_case
from tests.test_research_candidate_api_db import post
from tests.test_api_projects_db import _h

pytestmark=pytest.mark.parametrize('run_case',['native'],indirect=True)

@pytest.fixture
def model_review_case(selected_review_case,monkeypatch):
    c=selected_review_case;factories=[];holder={}
    cap=ProviderCapability(provider='openai-responses',adapter_version='c61-review-owned-model-v1',service='model',markets=frozenset({'US','HK'}),languages=frozenset({'en','zh-HK'}),roles=frozenset({'company'}),auth_model='server-key',pricing_version='synthetic-review-model-v1',max_liability=Money(Decimal('0.100000'),'USD'),idempotency='verified',status='verified',callback='unsupported',cancel='unsupported',retention='fixture-only',verified_at=datetime.now(timezone.utc),source_urls=('https://developers.openai.com/api/reference/responses/overview',))
    route=ModelRoute('synthetic-review-prompt-v1',frozenset(),1000,500,30,0,'synthetic-review-route-v1')
    def factory():factories.append('model');return holder['adapter']
    item=ProviderRegistration(cap,factory,('synthetic:owned-review-to-model-only',),model_route=route,model_id='synthetic-review-model-v1')
    search=registry.DEFAULT_REGISTRY.registration('search')
    monkeypatch.setattr(base,'SELECTED_LIVE_PROVIDERS',base.SELECTED_LIVE_PROVIDERS|{'openai-responses'})
    monkeypatch.setattr(registry,'SELECTED_LIVE_PROVIDERS',registry.SELECTED_LIVE_PROVIDERS|{'openai-responses'})
    monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry((search,item)))
    monkeypatch.setenv('BUYEROS_PAID_ADMISSION_ENABLED','true');get_settings.cache_clear()
    with psycopg.connect(c['dsn']) as db:
        before=db.execute('SELECT usage_counters,execution_snapshot FROM search_runs WHERE id=%s',(c['run'],)).fetchone()
        operations=db.execute('SELECT count(*) FROM provider_operations WHERE workspace_id=%s',(c['workspace'],)).fetchone()[0]
    try:yield {**c,'model_cap':cap,'route':route,'model_registration':item,'search_registration':search,'model_factories':factories,'holder':holder,'before':before,'original_operations':operations}
    finally:
        with psycopg.connect(c['dsn']) as db:
            extra=[x[0] for x in db.execute("SELECT p.id FROM provider_operations p JOIN outbox_events o ON o.workspace_id=p.workspace_id AND o.intent_key=p.intent_key WHERE o.workspace_id=%s AND o.event_type='run.discover' AND o.payload->>'run_id'=%s AND p.intent_key!=%s",(c['workspace'],str(c['run']),c['key']))]
            if extra:
                db.execute('DELETE FROM search_receipts WHERE operation_id=ANY(%s)',(extra,))
                db.execute('DELETE FROM budget_reservation_allocations WHERE reservation_id IN(SELECT id FROM budget_reservations WHERE operation_id=ANY(%s))',(extra,))
                db.execute('DELETE FROM budget_reservations WHERE operation_id=ANY(%s)',(extra,))
                db.execute('DELETE FROM provider_operations WHERE id=ANY(%s)',(extra,))
            ids=[x[0] for x in db.execute("SELECT id FROM provider_operations WHERE workspace_id=%s AND intent_key LIKE 'run-model:%%'",(c['workspace'],))]
            db.execute("DELETE FROM worker_steps WHERE outbox_id IN(SELECT id FROM outbox_events WHERE workspace_id=%s AND (intent_key LIKE 'run-model:%%' OR payload->>'operation_id'=ANY(%s)))",(c['workspace'],[str(x) for x in ids]))
            db.execute("DELETE FROM outbox_events WHERE workspace_id=%s AND event_type='provider.reconcile' AND payload->>'operation_id'=ANY(%s)",(c['workspace'],[str(x) for x in ids]))
            db.execute("DELETE FROM model_receipts WHERE workspace_id=%s AND intent_key LIKE 'run-model:%%'",(c['workspace'],))
            if ids:
                db.execute('DELETE FROM budget_reservation_allocations WHERE reservation_id IN(SELECT id FROM budget_reservations WHERE operation_id=ANY(%s))',(ids,))
                db.execute('DELETE FROM budget_reservations WHERE operation_id=ANY(%s)',(ids,))
            db.execute("DELETE FROM outbox_events WHERE workspace_id=%s AND intent_key LIKE 'run-model:%%'",(c['workspace'],))
            db.execute("DELETE FROM provider_operations WHERE workspace_id=%s AND intent_key LIKE 'run-model:%%'",(c['workspace'],))
        get_settings.cache_clear()

def model_events(c):
    with psycopg.connect(c['dsn']) as db:return db.execute("SELECT id,payload,state,runtime_epoch FROM outbox_events WHERE workspace_id=%s AND intent_key LIKE 'run-model:%%' ORDER BY id",(c['workspace'],)).fetchall()

def test_first_actual_review_queues_one_frozen_model_without_factory_hold_or_token_admission(model_review_case,monkeypatch):
    c=model_review_case;queue_errors=[]
    from buyeros_api.services import run_model
    real_queue=run_model.queue_run_model
    async def observed_queue(*args,**kwargs):
        try:return await real_queue(*args,**kwargs)
        except ValueError as exc:queue_errors.append(str(exc));raise
    monkeypatch.setattr(run_model,'queue_run_model',observed_queue)
    reply=post(c);assert reply.status_code==200,reply.text
    events=model_events(c)
    with psycopg.connect(c['dsn']) as db:
        gate=db.execute("SELECT payload->>'code' FROM run_events WHERE run_id=%s AND event_type='candidate.model_queue_blocked'",(c['run'],)).fetchall()
        stage=db.execute('SELECT stage,status FROM search_runs WHERE id=%s',(c['run'],)).fetchone()
    assert len(events)==1,('accepted first page review did not queue bounded model work',gate,stage,queue_errors)
    event,payload,state,epoch=events[0]
    assert state=='ready' and payload['buyer_id']==reply.json()['data']['buyer_id']
    original_query=c['before'][1]['query_plan']['queries'][0]
    assert (payload['market'],payload['language'])==(original_query['market'],original_query['language'])
    assert payload['model_registry_contract_hash']==c['model_registration'].contract_hash
    assert post(c).json()['data']==reply.json()['data']
    assert post(c,headers=_h(key='same-review-new-http-key')).json()['data']==reply.json()['data']
    assert model_events(c)==events and c['model_factories']==[] and c['factory_calls']==[]
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT usage_counters,execution_snapshot FROM search_runs WHERE id=%s',(c['run'],)).fetchone()==c['before']
        assert db.execute('SELECT count(*) FROM provider_operations WHERE workspace_id=%s',(c['workspace'],)).fetchone()==(c['original_operations'],)
        assert db.execute('SELECT count(*) FROM model_receipts WHERE workspace_id=%s',(c['workspace'],)).fetchone()==(0,)
        assert db.execute('SELECT count(*) FROM fit_assessments WHERE run_id=%s',(c['run'],)).fetchone()==(0,)
        assert db.execute('SELECT stage,status FROM search_runs WHERE id=%s',(c['run'],)).fetchone()==('fit','running')
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations').fetchall()==c['hold']

@pytest.mark.parametrize('gate',['paid-disabled','unselected-model','unscoped-model'])
def test_unavailable_model_keeps_accepted_review_and_later_activation_never_creates_work_on_replay(model_review_case,monkeypatch,gate):
    c=model_review_case
    if gate=='paid-disabled':monkeypatch.setenv('BUYEROS_PAID_ADMISSION_ENABLED','false');get_settings.cache_clear()
    elif gate=='unselected-model':monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry((c['search_registration'],)))
    else:monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry((c['search_registration'],replace(c['model_registration'],model_id=None,model_route=None))))
    reply=post(c);assert reply.status_code==200,reply.text
    assert reply.json()['data']['entity_status']=='reviewed' and reply.json()['data']['fit_status']=='needs_review'
    with psycopg.connect(c['dsn']) as db:
        assert db.execute("SELECT count(*) FROM run_events WHERE run_id=%s AND event_type='candidate.model_queue_blocked'",(c['run'],)).fetchone()==(1,),'missing durable model admission gate result'
    monkeypatch.setenv('BUYEROS_PAID_ADMISSION_ENABLED','true');get_settings.cache_clear()
    monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry((c['search_registration'],c['model_registration'])))
    assert post(c).json()['data']==reply.json()['data']
    assert post(c,headers=_h(key='replay-after-model-activation')).json()['data']==reply.json()['data']
    assert model_events(c)==[] and c['model_factories']==[]

def test_model_queue_failure_rolls_back_only_new_wakeup_without_dropping_accepted_review(model_review_case,monkeypatch):
    c=model_review_case
    from buyeros_api.services import run_model
    original=run_model.queue_run_model;written=[]
    async def fail_after_queue(*args,**kwargs):
        await original(*args,**kwargs)
        written.append('queued-before-loss')
        raise ValueError('synthetic reviewed scope revoked before scheduling commit')
    monkeypatch.setattr(run_model,'queue_run_model',fail_after_queue)
    reply=post(c);assert reply.status_code==200,reply.text
    assert written==['queued-before-loss']
    assert model_events(c)==[]
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT count(*) FROM company_aliases WHERE raw_candidate_id=%s',(c['raw'],)).fetchone()==(1,)
        assert db.execute('SELECT count(*) FROM evidence WHERE raw_candidate_id=%s',(c['raw'],)).fetchone()==(1,)
        assert db.execute("SELECT count(*) FROM run_events WHERE run_id=%s AND event_type='candidate.model_queue_blocked'",(c['run'],)).fetchone()==(1,)

@pytest.mark.parametrize('outcome',['received','unknown'])
def test_review_queued_model_uses_real_registry_native_factory_once_and_retains_original_unknown_hold(model_review_case,outcome):
    c=model_review_case;reply=post(c);assert reply.status_code==200,reply.text
    rows=model_events(c);assert len(rows)==1,'review did not provide native model factory work'
    event,payload,_,epoch=rows[0];operation=uuid.UUID(payload['operation_id']);calls=[]
    class Client:
        model_id='synthetic-review-model-v1'
        async def complete(self,basis,route):
            calls.append('submit')
            with psycopg.connect(c['dsn']) as db:
                assert db.execute('SELECT id FROM model_receipts WHERE operation_id=%s FOR UPDATE NOWAIT',(operation,)).fetchone()
                assert db.execute('SELECT id FROM budget_reservations WHERE operation_id=%s FOR UPDATE NOWAIT',(operation,)).fetchone()
            if outcome=='unknown':raise ModelResponseUnknown('synthetic provider acceptance response lost')
            proposal={'company_id':basis['company_id'],'verdict':'needs_review','rationale':'Reviewed entity source is an inference and cannot establish factual buyer fit','citations':[]}
            return {'provider_ref':'resp_review_native_owned1','proposal':proposal,'assessment':validate_live_proposal(proposal,basis),'usage':{'input_tokens':100,'output_tokens':60,'total_tokens':160},'model_id':self.model_id,'prompt_version':route.prompt_version}
    async def run():
        worker=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')));api=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_api')))
        try:
            c['holder']['adapter']=LiveModelAdapter(capability=c['model_cap'],client=Client(),receipts=PostgresModelReceipts(worker,c['workspace'],c['model_cap'],model_id=Client.model_id,route=c['route']))
            with psycopg.connect(c['dsn']) as db:db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 WHERE id=%s",(event,))
            env=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=event,generation=1,runtime_epoch=epoch)
            first=await execute_step(worker,env,'start',research_engine=api,environment='test')
            assert first.state=='reconcile'
            assert await execute_step(worker,env,'start',research_engine=api,environment='test')==first
            if outcome=='received':
                with psycopg.connect(c['dsn']) as db:
                    status=db.execute("SELECT id FROM outbox_events WHERE workspace_id=%s AND event_type='provider.reconcile' AND payload->>'operation_id'=%s",(c['workspace'],str(operation))).fetchone()[0]
                    db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 WHERE id=%s",(status,))
                status_env=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=status,generation=1,runtime_epoch=epoch)
                result=await execute_step(worker,status_env,'start',research_engine=api,environment='test');assert result.state=='done'
                assert await execute_step(worker,status_env,'start',research_engine=api,environment='test')==result
        finally:await worker.dispose();await api.dispose()
    asyncio.run(run());assert calls==['submit'] and c['model_factories']==(['model','model'] if outcome=='received' else ['model'])
    assert post(c).json()['data']==reply.json()['data'];assert len(model_events(c))==1
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(operation,)).fetchone()==('active',Decimal('0.100000'))
        assert db.execute('SELECT count(*) FROM cost_events WHERE operation_id=%s',(operation,)).fetchone()==(0,)
        assert db.execute('SELECT count(*) FROM fit_assessments WHERE run_id=%s',(c['run'],)).fetchone()==((1 if outcome=='received' else 0),)
        assert db.execute('SELECT status FROM search_runs WHERE id=%s',(c['run'],)).fetchone()==('running',)
        if outcome=='received':assert db.execute('SELECT verdict FROM fit_assessments WHERE run_id=%s',(c['run'],)).fetchone()==('needs_review',)


def test_next_frozen_discovery_claim_keeps_reviewed_model_fit_stage(model_review_case):
    c=model_review_case;reply=post(c);assert reply.status_code==200,reply.text
    original=model_events(c);assert len(original)==1
    with psycopg.connect(c['dsn']) as db:
        child=db.execute("SELECT id FROM outbox_events WHERE workspace_id=%s AND event_type='run.discover' AND payload->>'run_id'=%s AND payload->>'query_index'='1'",(c['workspace'],str(c['run']))).fetchone()[0]
        db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 WHERE id=%s",(child,))
    async def claim():
        from buyeros_api.services.run_search import prepare_run_search
        from buyeros_api.db.session import tenant_session
        engine=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_api')))
        try:
            async with tenant_session(engine,c['workspace']) as session:
                return await prepare_run_search(session,workspace_id=c['workspace'],outbox_id=child,generation=1,capability=c['cap'])
        finally:await engine.dispose()
    prepared=asyncio.run(claim());assert prepared.run_id==c['run']
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT stage,status FROM search_runs WHERE id=%s',(c['run'],)).fetchone()==('fit','running'),'remaining discovery claim regressed an already reviewed model to discovery stage'
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(prepared.operation_id,)).fetchone()==('active',Decimal('0.005000'))
        assert db.execute('SELECT count(*) FROM model_receipts WHERE workspace_id=%s',(c['workspace'],)).fetchone()==(0,)
    assert model_events(c)==original and c['model_factories']==[]
