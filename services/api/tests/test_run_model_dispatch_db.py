"""Native fenced worker step with actual PG, synthetic model client; no live IO."""
import asyncio,uuid
from decimal import Decimal
import psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.api.worker_schemas import JobEnvelope
from buyeros_api.services.worker_execution import execute_step
from buyeros_api.providers.live_model import LiveModelAdapter,ModelResponseUnknown,validate_live_proposal
from buyeros_api.providers.model_receipts import PostgresModelReceipts
from tests.cutover_fixtures import role_dsn
from tests.test_run_model_admission_db import model_case,native_basis_case,review_case,page_case,run_case,project_api,admission_case,migrated,dispatched

@pytest.fixture(autouse=True)
def clean_model_native_steps(model_case):
    c=model_case;yield
    with psycopg.connect(c['dsn']) as db:
        ids=[x[0] for x in db.execute("SELECT id FROM provider_operations WHERE workspace_id=%s AND intent_key LIKE 'run-model:%%'",(c['workspace'],))]
        if ids:
            refs=[str(x) for x in ids]
            db.execute("DELETE FROM worker_steps WHERE outbox_id IN(SELECT id FROM outbox_events WHERE workspace_id=%s AND (intent_key LIKE 'run-model:%%' OR payload->>'operation_id'=ANY(%s)))",(c['workspace'],refs))
            db.execute("DELETE FROM outbox_events WHERE workspace_id=%s AND event_type='provider.reconcile' AND payload->>'operation_id'=ANY(%s)",(c['workspace'],refs))
        else:db.execute("DELETE FROM worker_steps WHERE outbox_id IN(SELECT id FROM outbox_events WHERE workspace_id=%s AND intent_key LIKE 'run-model:%%')",(c['workspace'],))

@pytest.mark.parametrize('run_case',['native'],indirect=True)
@pytest.mark.parametrize('outcome',['received','lost-response','epoch','actor','source'])
def test_native_model_dispatch_prepares_before_IO_and_keeps_single_intent_and_liability(model_case,outcome):
    c=model_case;event=dispatched(c);calls=[]
    with psycopg.connect(c['dsn']) as db:
        epoch,payload=db.execute('SELECT runtime_epoch,payload FROM outbox_events WHERE id=%s',(event,)).fetchone();operation=uuid.UUID(payload['operation_id'])
    class Client:
        model_id='local-owned-model-v1'
        async def complete(self,basis,route):
            calls.append(1)
            with psycopg.connect(c['dsn']) as db:
                # Native preparation and durable worker claim must have committed.
                assert db.execute('SELECT id FROM model_receipts WHERE operation_id=%s FOR UPDATE NOWAIT',(operation,)).fetchone()
                assert db.execute('SELECT id FROM provider_operations WHERE id=%s FOR UPDATE NOWAIT',(operation,)).fetchone()
                assert db.execute('SELECT id FROM search_runs WHERE id=%s FOR UPDATE NOWAIT',(c['run'],)).fetchone()
                if outcome=='epoch':db.execute('UPDATE worker_runtime_control SET epoch=epoch+1 WHERE singleton=1')
                elif outcome=='actor':db.execute('UPDATE memberships SET active=false WHERE workspace_id=%s AND user_id=%s',(c['workspace'],c['actor']))
                elif outcome=='source':db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c['page_source'],))
            if outcome=='lost-response':raise ModelResponseUnknown('synthetic accepted response lost')
            proposal={'company_id':basis['company_id'],'verdict':'needs_review','rationale':'Native entity context does not prove buyer role or ICP fit','citations':[]}
            return {'provider_ref':'resp_local_native_model1','proposal':proposal,'assessment':validate_live_proposal(proposal,basis),'usage':{'input_tokens':100,'output_tokens':60,'total_tokens':160},'model_id':self.model_id,'prompt_version':route.prompt_version}
    async def run():
        worker=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')));api=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_api')))
        try:
            adapter=LiveModelAdapter(capability=c['model_cap'],client=Client(),receipts=PostgresModelReceipts(worker,c['workspace'],c['model_cap'],model_id=Client.model_id,route=c['route']))
            env=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=event,generation=1,runtime_epoch=epoch)
            first=await execute_step(worker,env,'start',adapter=adapter,research_engine=api,environment='test')
            second=await execute_step(worker,env,'start',adapter=adapter,research_engine=api,environment='test')
            assert first.state==second.state==('stale' if outcome=='epoch' else 'reconcile')
        finally:await worker.dispose();await api.dispose()
    asyncio.run(run());assert len(calls)==1
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT payload FROM outbox_events WHERE id=%s',(event,)).fetchone()==(payload,)
        assert db.execute("SELECT count(*) FROM provider_operations WHERE workspace_id=%s AND capability='model'",(c['workspace'],)).fetchone()==(1,)
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(operation,)).fetchone()==('active',Decimal('0.100000'))
        assert db.execute('SELECT count(*) FROM cost_events WHERE operation_id=%s',(operation,)).fetchone()==(0,)
        # Accepted submit finishes its native owner. Publication belongs to the original status child.
        assert db.execute('SELECT count(*) FROM fit_assessments WHERE run_id=%s',(c['run'],)).fetchone()==(0,)
        counters=db.execute('SELECT usage_counters FROM search_runs WHERE id=%s',(c['run'],)).fetchone()[0]
        assert counters['model_tokens']==1500 and counters['in_flight']==1
    assert c['transport'].calls==1


@pytest.mark.parametrize('run_case',['native'],indirect=True)
@pytest.mark.parametrize('change',['none','no-api','adapter-scope','source','actor','offer','epoch','original-envelope','operation-hash','status-envelope','source-before-persist','epoch-before-persist','legacy-scope-revoked','new-scope-revoked','invalid-registry-hash','extra-registry-authority'])
def test_native_received_model_status_recovers_current_fit_without_a_second_submit(model_case,change,monkeypatch):
    c=model_case;event=dispatched(c);calls=[]
    from buyeros_api.execution import live_run_model
    publication_errors=[];publish=live_run_model.persist_received_run_model
    async def observed_publish(*args,**kwargs):
        try:return await publish(*args,**kwargs)
        except Exception as exc:
            publication_errors.append(type(exc).__name__+': '+str(exc));raise
    monkeypatch.setattr(live_run_model,'persist_received_run_model',observed_publish)
    if change in {'source-before-persist','epoch-before-persist'}:
        original_persist=live_run_model.NativeReceivedFitRunner.persist
        async def changed_before_persist(self,state):
            with psycopg.connect(c['dsn']) as db:
                if change=='source-before-persist':db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c['page_source'],))
                else:db.execute('UPDATE worker_runtime_control SET epoch=epoch+1 WHERE singleton=1')
            return await original_persist(self,state)
        monkeypatch.setattr(live_run_model.NativeReceivedFitRunner,'persist',changed_before_persist)
    with psycopg.connect(c['dsn']) as db:
        epoch,payload=db.execute('SELECT runtime_epoch,payload FROM outbox_events WHERE id=%s',(event,)).fetchone();operation=uuid.UUID(payload['operation_id'])
    class Client:
        model_id='local-owned-model-v1'
        async def complete(self,basis,route):
            calls.append(1)
            proposal={'company_id':basis['company_id'],'verdict':'needs_review','rationale':'Entity context cannot prove a requirement','citations':[]}
            return {'provider_ref':'resp_local_native_model1','proposal':proposal,'assessment':validate_live_proposal(proposal,basis),'usage':{'input_tokens':100,'output_tokens':60,'total_tokens':160},'model_id':self.model_id,'prompt_version':route.prompt_version}
    async def run():
        worker=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')));api=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_api')))
        try:
            adapter=LiveModelAdapter(capability=c['model_cap'],client=Client(),receipts=PostgresModelReceipts(worker,c['workspace'],c['model_cap'],model_id=Client.model_id,route=c['route']))
            original=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=event,generation=1,runtime_epoch=epoch)
            assert (await execute_step(worker,original,'start',adapter=adapter,research_engine=api,environment='test')).state=='reconcile'
            with psycopg.connect(c['dsn']) as db:
                assert db.execute('SELECT count(*) FROM fit_assessments WHERE run_id=%s',(c['run'],)).fetchone()==(0,)
                status=db.execute("SELECT id FROM outbox_events WHERE workspace_id=%s AND event_type='provider.reconcile' AND payload->>'operation_id'=%s",(c['workspace'],str(operation))).fetchone()[0]
                db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 WHERE id=%s",(status,))
                if change=='source':db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c['page_source'],))
                elif change=='actor':db.execute('UPDATE memberships SET active=false WHERE workspace_id=%s AND user_id=%s',(c['workspace'],c['actor']))
                elif change=='offer':db.execute('UPDATE projects SET offer_revision=offer_revision+1 WHERE id=%s',(c['project'],))
                elif change=='epoch':db.execute('UPDATE worker_runtime_control SET epoch=epoch+1 WHERE singleton=1')
                elif change=='original-envelope':
                    corrupt={**payload,'model_request_hash':'f'*64};db.execute('UPDATE outbox_events SET payload=%s::jsonb WHERE id=%s',(__import__('json').dumps(corrupt),event))
                elif change=='legacy-scope-revoked':db.execute("UPDATE outbox_events SET payload=payload-'model_registry_contract_hash' WHERE id=%s",(event,))
                elif change=='invalid-registry-hash':db.execute("UPDATE outbox_events SET payload=jsonb_set(payload,'{model_registry_contract_hash}',to_jsonb(%s::text)) WHERE id=%s",('g'*64,event))
                elif change=='extra-registry-authority':db.execute("UPDATE outbox_events SET payload=payload||'{\"extra_authority\":true}'::jsonb WHERE id=%s",(event,))
                elif change=='operation-hash':db.execute("UPDATE provider_operations SET input_hash=%s WHERE id=%s",('e'*64,operation))
                elif change=='status-envelope':db.execute("UPDATE outbox_events SET payload=jsonb_set(payload,'{market}','\"HK\"'::jsonb) WHERE id=%s",(status,))
            if change in {'legacy-scope-revoked','new-scope-revoked'}:
                from buyeros_api.providers import registry
                from buyeros_api.providers.registry import ProviderRegistry
                monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry(tuple(x for x in registry.DEFAULT_REGISTRY.registrations if x.capability.service!='model')))
            if change=='adapter-scope':
                adapter=LiveModelAdapter(capability=c['model_cap'],client=Client(),receipts=PostgresModelReceipts(worker,uuid.UUID('22222222-2222-2222-2222-222222222222'),c['model_cap'],model_id=Client.model_id,route=c['route']))
            env=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=status,generation=1,runtime_epoch=epoch)
            first=await execute_step(worker,env,'start',adapter=adapter,research_engine=None if change=='no-api' else api,environment='test')
            again=await execute_step(worker,env,'start',adapter=adapter,research_engine=None if change=='no-api' else api,environment='test')
            assert first.state==again.state
            if change in {'none','no-api','adapter-scope','legacy-scope-revoked','new-scope-revoked'}:assert first.state=='done',publication_errors
            else:assert first.state!='done'
        finally:await worker.dispose();await api.dispose()
    asyncio.run(run());assert len(calls)==1
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT count(*) FROM fit_assessments WHERE run_id=%s',(c['run'],)).fetchone()==((1 if change in {'none','no-api','adapter-scope','legacy-scope-revoked','new-scope-revoked'} else 0),)
        if change in {'none','no-api','adapter-scope','legacy-scope-revoked','new-scope-revoked'}:
            verdict,details=db.execute('SELECT verdict,assessment_details FROM fit_assessments WHERE run_id=%s',(c['run'],)).fetchone()
            assert verdict=='needs_review' and details['evidence_ids']==[] and details['supported_requirement_ids']==[] and details['model_provenance']['token_usage']['total_tokens']==160
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(operation,)).fetchone()==('active',Decimal('0.100000'))
        assert db.execute('SELECT count(*) FROM cost_events WHERE operation_id=%s',(operation,)).fetchone()==(0,)
        counters=db.execute('SELECT usage_counters FROM search_runs WHERE id=%s',(c['run'],)).fetchone()[0]
        assert counters['model_tokens']==1500 and counters['in_flight']==1
    assert c['transport'].calls==1


@pytest.mark.parametrize('run_case',['native'],indirect=True)
@pytest.mark.parametrize('crash_point',['submit-ack','status-read'])
def test_native_model_process_loss_preserves_original_receipt_and_recovers_fit_once(model_case,monkeypatch,crash_point):
    c=model_case;event=dispatched(c);calls=[]
    with psycopg.connect(c['dsn']) as db:
        epoch,payload=db.execute('SELECT runtime_epoch,payload FROM outbox_events WHERE id=%s',(event,)).fetchone();operation=uuid.UUID(payload['operation_id'])
    class ProcessLost(BaseException):pass
    class Client:
        model_id='local-owned-model-v1'
        async def complete(self,basis,route):
            calls.append(1)
            proposal={'company_id':basis['company_id'],'verdict':'needs_review','rationale':'Entity context is not factual fit coverage','citations':[]}
            return {'provider_ref':'resp_local_native_model1','proposal':proposal,'assessment':validate_live_proposal(proposal,basis),'usage':{'input_tokens':100,'output_tokens':60,'total_tokens':160},'model_id':self.model_id,'prompt_version':route.prompt_version}
    async def run():
        worker=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')));api=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_api')))
        original_submit,original_status=LiveModelAdapter.submit,LiveModelAdapter.status
        async def lost_submit(self,intent):
            assert (await original_submit(self,intent)).state=='accepted'
            raise ProcessLost('process lost after durable received response, before finalize')
        async def lost_status(self,ref):
            assert (await original_status(self,ref)).state=='succeeded'
            raise ProcessLost('process lost after fit committed, before status finalize')
        def recover_event(oid):
            with psycopg.connect(c['dsn']) as db:
                db.execute("UPDATE worker_steps SET expires_at=now()-interval '1 second' WHERE outbox_id=%s",(oid,))
                db.execute("UPDATE worker_runtime_control SET active_until=now()-interval '1 second' WHERE singleton=1")
                return db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=fencing_generation+1 WHERE id=%s RETURNING fencing_generation",(oid,)).fetchone()[0]
        try:
            adapter=LiveModelAdapter(capability=c['model_cap'],client=Client(),receipts=PostgresModelReceipts(worker,c['workspace'],c['model_cap'],model_id=Client.model_id,route=c['route']))
            env=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=event,generation=1,runtime_epoch=epoch)
            if crash_point=='submit-ack':
                monkeypatch.setattr(LiveModelAdapter,'submit',lost_submit)
                with pytest.raises(ProcessLost):await execute_step(worker,env,'start',adapter=adapter,research_engine=api,environment='test')
                monkeypatch.setattr(LiveModelAdapter,'submit',original_submit)
                with psycopg.connect(c['dsn']) as db:
                    assert db.execute('SELECT state,generation FROM model_receipts WHERE operation_id=%s',(operation,)).fetchone()==('received',1)
                    assert db.execute('SELECT status FROM provider_operations WHERE id=%s',(operation,)).fetchone()==('submitting',)
                env=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=event,generation=recover_event(event),runtime_epoch=epoch)
                await execute_step(worker,env,'start',adapter=adapter,research_engine=api,environment='test')
                # Original recovery queues the original status child and keeps unknown; only that child confirms succeeded.
                with psycopg.connect(c['dsn']) as db:assert db.execute('SELECT status FROM provider_operations WHERE id=%s',(operation,)).fetchone()==('unknown',)
            else:assert (await execute_step(worker,env,'start',adapter=adapter,research_engine=api,environment='test')).state=='reconcile'
            with psycopg.connect(c['dsn']) as db:
                status=db.execute("SELECT id FROM outbox_events WHERE workspace_id=%s AND event_type='provider.reconcile' AND payload->>'operation_id'=%s",(c['workspace'],str(operation))).fetchone()[0]
                db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 WHERE id=%s",(status,))
            env=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=status,generation=1,runtime_epoch=epoch)
            if crash_point=='status-read':
                monkeypatch.setattr(LiveModelAdapter,'status',lost_status)
                with pytest.raises(ProcessLost):await execute_step(worker,env,'start',adapter=adapter,research_engine=api,environment='test')
                monkeypatch.setattr(LiveModelAdapter,'status',original_status)
                with psycopg.connect(c['dsn']) as db:assert db.execute('SELECT count(*) FROM fit_assessments WHERE run_id=%s',(c['run'],)).fetchone()==(1,)
                env=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=status,generation=recover_event(status),runtime_epoch=epoch)
            first=await execute_step(worker,env,'start',adapter=adapter,research_engine=api,environment='test')
            again=await execute_step(worker,env,'start',adapter=adapter,research_engine=api,environment='test')
            assert first.state==again.state=='done'
        finally:
            monkeypatch.setattr(LiveModelAdapter,'submit',original_submit);monkeypatch.setattr(LiveModelAdapter,'status',original_status)
            await worker.dispose();await api.dispose()
    asyncio.run(run());assert len(calls)==1
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT count(*) FROM fit_assessments WHERE run_id=%s',(c['run'],)).fetchone()==(1,)
        assert db.execute('SELECT state,generation FROM model_receipts WHERE operation_id=%s',(operation,)).fetchone()==('received',1)
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(operation,)).fetchone()==('active',Decimal('0.100000'))
        assert db.execute('SELECT count(*) FROM cost_events WHERE operation_id=%s',(operation,)).fetchone()==(0,)
        assert db.execute('SELECT payload FROM outbox_events WHERE id=%s',(event,)).fetchone()==(payload,)
    assert c['transport'].calls==1
