"""Native completion is fenced by pending work and current assessment basis."""
import asyncio,uuid
from decimal import Decimal
from contextlib import asynccontextmanager
from datetime import datetime,timezone
import httpx,psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.api.worker_schemas import JobEnvelope
from buyeros_api.db.session import tenant_session
from buyeros_api.db.contact import ProviderOperation
from buyeros_api.providers.base import ProviderIntent
from buyeros_api.providers.live_model import LiveModelAdapter,ModelResponseUnknown,validate_live_proposal
from buyeros_api.providers.model_receipts import PostgresModelReceipts
from buyeros_api.providers.live_search import LiveSearchAdapter,PostgresSearchReceipts,BraveSearchClient
from buyeros_api.execution.external_runner import execute_external,input_digest
from buyeros_api.services.worker_execution import execute_step
from buyeros_api.services.budget_service import reserve_operation
from tests.cutover_fixtures import role_dsn
from tests.test_run_model_admission_db import model_case,native_basis_case,review_case,page_case,run_case,project_api,admission_case,migrated,queue,dispatched,prepare
from tests.test_run_model_dispatch_db import clean_model_native_steps

@pytest.fixture(autouse=True)
def clean_completion_steps(model_case):
    c=model_case;yield
    with psycopg.connect(c['dsn']) as db:
        db.execute("DELETE FROM worker_steps WHERE outbox_id IN(SELECT id FROM outbox_events WHERE workspace_id=%s AND intent_key LIKE 'c61-fit-completion:%%')",(c['workspace'],))
        db.execute("DELETE FROM outbox_events WHERE workspace_id=%s AND intent_key LIKE 'c61-fit-completion:%%'",(c['workspace'],))
        extra=[x[0] for x in db.execute("SELECT id FROM provider_operations WHERE workspace_id=%s AND intent_key LIKE 'c61-independent-model:%%'",(c['workspace'],))]
        if extra:
            db.execute('DELETE FROM budget_reservation_allocations WHERE reservation_id IN(SELECT id FROM budget_reservations WHERE operation_id=ANY(%s))',(extra,))
            db.execute('DELETE FROM budget_reservations WHERE operation_id=ANY(%s)',(extra,))
            db.execute('DELETE FROM provider_operations WHERE id=ANY(%s)',(extra,))

async def confirmed_search(c,worker):
    # Confirm the actual received search through its original status child;
    # never rewrite the search operation to manufacture completion evidence.
    with psycopg.connect(c['dsn']) as db:
        row=db.execute("SELECT o.id,e.id,e.intent_key,e.payload FROM provider_operations o JOIN outbox_events e ON e.workspace_id=o.workspace_id AND e.event_type='provider.reconcile' AND e.payload->>'operation_id'=o.id::text WHERE o.workspace_id=%s AND o.capability='search'",(c['workspace'],)).fetchone()
        operation,event,key,payload=row
        db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 WHERE id=%s",(event,))
    def unexpected(req):raise AssertionError('search status performed another HTTP submit')
    async with httpx.AsyncClient(transport=httpx.MockTransport(unexpected)) as http:
        adapter=LiveSearchAdapter(capability=c['cap'],receipts=PostgresSearchReceipts(worker,c['workspace'],c['cap']),client=BraveSearchClient(api_key='local-owned-status-only',http=http,language_codes={'en':'en'},api_version='2026-10-01'))
        intent=ProviderIntent(payload['original_intent_key'],'search',payload['market'],payload['language'],payload['role'])
        assert await execute_external(worker,c['workspace'],operation,1,adapter,intent,environment='test',outbox_intent_key=key)=='succeeded'

@pytest.mark.parametrize('run_case',['native'],indirect=True)
@pytest.mark.parametrize('mode',['ready','reserved','accepted','unknown','succeeded','project-only','stale-actor','stale-source','stale-offer','resume','late-ready'])
def test_native_fit_completion_waits_for_original_model_work_and_current_basis(model_case,mode,monkeypatch):
    c=model_case;calls=[]
    event=queue(c) if mode=='ready' else None if mode in {'project-only','late-ready'} else dispatched(c)
    if mode=='reserved':prepare(c,event)
    class Client:
        model_id='local-owned-model-v1'
        async def complete(self,basis,route):
            calls.append(1)
            if mode=='unknown':raise ModelResponseUnknown('synthetic process lost model response')
            proposal={'company_id':basis['company_id'],'verdict':'needs_review','rationale':'Native entity context is not factual requirement coverage','citations':[]}
            return {'provider_ref':'resp_local_native_model1','proposal':proposal,'assessment':validate_live_proposal(proposal,basis),'usage':{'input_tokens':100,'output_tokens':60,'total_tokens':160},'model_id':self.model_id,'prompt_version':route.prompt_version}
    async def run():
        worker_dsn=role_dsn(c['dsn'],'buyeros_worker');worker=create_async_engine(async_database_url(worker_dsn));api=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_api')))
        try:
            await confirmed_search(c,worker)
            adapter=LiveModelAdapter(capability=c['model_cap'],client=Client(),receipts=PostgresModelReceipts(worker,c['workspace'],c['model_cap'],model_id=Client.model_id,route=c['route']))
            if mode not in {'ready','reserved','project-only','late-ready'}:
                with psycopg.connect(c['dsn']) as db:epoch=db.execute('SELECT runtime_epoch FROM outbox_events WHERE id=%s',(event,)).fetchone()[0]
                env=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=event,generation=1,runtime_epoch=epoch)
                assert (await execute_step(worker,env,'start',adapter=adapter,research_engine=api,environment='test')).state=='reconcile'
                if mode=='succeeded' or mode.startswith('stale-'):
                    with psycopg.connect(c['dsn']) as db:
                        status=db.execute("SELECT id FROM outbox_events WHERE workspace_id=%s AND event_type='provider.reconcile' AND payload->>'original_intent_key' LIKE 'run-model:%%'",(c['workspace'],)).fetchone()[0]
                        db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 WHERE id=%s",(status,))
                    env=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=status,generation=1,runtime_epoch=epoch)
                    assert (await execute_step(worker,env,'start',adapter=adapter,environment='test')).state=='done'
            elif mode=='project-only':
                operation=uuid.uuid4();intent=ProviderIntent('c61-independent-model:'+str(operation),'model','US','en','company')
                async with tenant_session(api,c['workspace']) as session:
                    await reserve_operation(session,operation,{'workspace_id':c['workspace'],'project_id':c['project'],'category':'discovery'},Decimal('0.1'),'USD',c['model_cap'].pricing_version)
                    session.add(ProviderOperation(id=operation,workspace_id=c['workspace'],intent_key=intent.key,capability='model',input_hash=input_digest(intent),status='unknown'))
            with psycopg.connect(c['dsn']) as db:
                if mode=='stale-actor':db.execute('UPDATE memberships SET active=false WHERE workspace_id=%s AND user_id=%s',(c['workspace'],c['actor']))
                elif mode=='stale-source':db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c['page_source'],))
                elif mode=='stale-offer':db.execute('UPDATE projects SET offer_revision=offer_revision+1 WHERE id=%s',(c['project'],))
                fit=uuid.uuid4();key='c61-fit-completion:'+str(c['run'])
                backend,epoch=db.execute('SELECT backend,epoch FROM worker_runtime_control WHERE singleton=1').fetchone()
                db.execute("INSERT INTO outbox_events(id,workspace_id,intent_key,event_type,payload,state,fencing_generation,runtime_backend,runtime_epoch) VALUES(%s,%s,%s,'run.fit',jsonb_build_object('run_id',%s::text),'dispatched',1,%s,%s)",(fit,c['workspace'],key,str(c['run']),backend,epoch))
                holds_before=db.execute('SELECT to_jsonb(r) FROM budget_reservations r JOIN model_receipts m ON m.workspace_id=r.workspace_id AND m.operation_id=r.operation_id WHERE m.workspace_id=%s ORDER BY r.id',(c['workspace'],)).fetchall()
            env=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=fit,generation=1,runtime_epoch=epoch)
            if mode=='late-ready':
                from buyeros_api.execution import fit_execution
                original=fit_execution.open_checkpoint_saver
                @asynccontextmanager
                async def late_queue(*args,**kwargs):
                    async with original(*args,**kwargs) as saver:
                        yield saver
                    await asyncio.to_thread(queue,c)
                monkeypatch.setattr(fit_execution,'open_checkpoint_saver',late_queue)
            result=await execute_step(worker,env,'start',checkpoint_dsn=worker_dsn,environment='test')
            replay=await execute_step(worker,env,'start',checkpoint_dsn=worker_dsn,environment='test')
            assert result.state==replay.state
            with psycopg.connect(c['dsn']) as db:
                current=db.execute('SELECT status,stage FROM search_runs WHERE id=%s',(c['run'],)).fetchone()
                completed=db.execute("SELECT count(*) FROM run_events WHERE run_id=%s AND event_type='run.completed'",(c['run'],)).fetchone()[0]
                if mode=='stale-actor':assert result.code=='ACTOR_CHANGED'
                if mode in {'stale-source','stale-offer'}:assert result.code=='POLICY_CHANGED'
                if mode in {'succeeded','project-only'}:
                    assert result.state=='done' and current==('completed','review') and completed==1
                else:
                    assert result.state!='done' and current[0]!='completed' and completed==0
                    if mode in {'ready','reserved','accepted','unknown','resume','late-ready'}:
                        assert result.state=='reconcile' and current==('running','fit')
                        assert db.execute('SELECT count(*) FROM fit_assessments WHERE run_id=%s',(c['run'],)).fetchone()==((1 if mode=='late-ready' else 0),)
                assert db.execute('SELECT count(*) FROM cost_events WHERE workspace_id=%s',(c['workspace'],)).fetchone()==(0,)
                assert db.execute('SELECT to_jsonb(r) FROM budget_reservations r JOIN model_receipts m ON m.workspace_id=r.workspace_id AND m.operation_id=r.operation_id WHERE m.workspace_id=%s ORDER BY r.id',(c['workspace'],)).fetchall()==holds_before
            if mode=='resume':
                # The accepted submit remains fenced; publish only its original
                # status, then recover the local fit into a new generation.
                with psycopg.connect(c['dsn']) as db:
                    status=db.execute("SELECT id FROM outbox_events WHERE workspace_id=%s AND event_type='provider.reconcile' AND payload->>'original_intent_key' LIKE 'run-model:%%'",(c['workspace'],)).fetchone()[0]
                    db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 WHERE id=%s",(status,))
                status_env=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=status,generation=1,runtime_epoch=epoch)
                assert (await execute_step(worker,status_env,'start',adapter=adapter,environment='test')).state=='done'
                with psycopg.connect(c['dsn']) as db:
                    db.execute("UPDATE worker_steps SET expires_at=now()-interval '1 second' WHERE outbox_id=%s",(fit,))
                    db.execute("UPDATE outbox_events SET lease_expires_at=now()-interval '1 second' WHERE id=%s",(fit,))
                from buyeros_api.services.worker_recovery import recover_execution
                from buyeros_api.execution.dispatcher import claim_cycle
                await recover_execution(worker,now=datetime.now(timezone.utc),limit=10,runtime_epoch=epoch)
                batch=await claim_cycle(worker,backend='cloudflare',epoch=epoch)
                resumed=next(item for item in batch.items if item.outbox_id==fit)
                assert resumed.generation==2
                assert (await execute_step(worker,env,'start',checkpoint_dsn=worker_dsn,environment='test')).state=='stale'
                assert (await execute_step(worker,resumed,'start',checkpoint_dsn=worker_dsn,environment='test')).state=='done'
                assert (await execute_step(worker,resumed,'start',checkpoint_dsn=worker_dsn,environment='test')).state=='done'
                with psycopg.connect(c['dsn']) as db:
                    assert db.execute('SELECT status,stage FROM search_runs WHERE id=%s',(c['run'],)).fetchone()==('completed','review')
                    assert db.execute("SELECT count(*) FROM run_events WHERE run_id=%s AND event_type='run.completed'",(c['run'],)).fetchone()==(1,)
                    assert db.execute('SELECT count(*) FROM fit_assessments WHERE run_id=%s',(c['run'],)).fetchone()==(1,)
                    assert db.execute('SELECT count(*) FROM cost_events WHERE workspace_id=%s',(c['workspace'],)).fetchone()==(0,)
                    assert db.execute('SELECT state FROM model_receipts WHERE workspace_id=%s',(c['workspace'],)).fetchone()==('received',)
                    assert db.execute('SELECT to_jsonb(r) FROM budget_reservations r JOIN model_receipts m ON m.workspace_id=r.workspace_id AND m.operation_id=r.operation_id WHERE m.workspace_id=%s ORDER BY r.id',(c['workspace'],)).fetchall()==holds_before
                    assert len(calls)==1
        finally:await worker.dispose();await api.dispose()
    asyncio.run(run());assert len(calls)==(0 if mode in {'ready','reserved','project-only','late-ready'} else 1)
    assert c['transport'].calls==1
