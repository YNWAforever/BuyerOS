"""Current native receipt/run API progress and safe checkpoint retry."""
import asyncio,uuid
import psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.api.worker_schemas import JobEnvelope
from buyeros_api.providers.live_model import LiveModelAdapter,ModelResponseUnknown,validate_live_proposal
from buyeros_api.providers.model_receipts import PostgresModelReceipts
from buyeros_api.services.worker_execution import execute_step
from tests.cutover_fixtures import role_dsn
from tests.test_run_model_admission_db import model_case,native_basis_case,review_case,page_case,run_case,project_api,admission_case,migrated,queue,dispatched,prepare
from tests.test_run_model_dispatch_db import clean_model_native_steps
from tests.test_native_model_completion_db import confirmed_search
from tests.test_run_admission_integration_db import _h

@pytest.mark.parametrize('run_case',['native'],indirect=True)
@pytest.mark.parametrize('mode',['ready','reserved','accepted','unknown','succeeded','retry-ready','retry-reserved','retry-accepted','retry-unknown','cancel-accepted','cancel-unknown'])
def test_native_run_api_exposes_current_reconciliation_and_rejects_unsafe_retry(model_case,mode):
    c=model_case;kind=mode.removeprefix('retry-').removeprefix('cancel-');calls=[]
    event=queue(c) if kind=='ready' else dispatched(c)
    if kind=='reserved':prepare(c,event)
    class Client:
        model_id='local-owned-model-v1'
        async def complete(self,basis,route):
            calls.append(1)
            if kind=='unknown':raise ModelResponseUnknown('synthetic unknown response')
            proposal={'company_id':basis['company_id'],'verdict':'needs_review','rationale':'Native entity context requires human factual review','citations':[]}
            return {'provider_ref':'resp_local_native_progress1','proposal':proposal,'assessment':validate_live_proposal(proposal,basis),'usage':{'input_tokens':100,'output_tokens':60,'total_tokens':160},'model_id':self.model_id,'prompt_version':route.prompt_version}
    async def submit():
        worker=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')));api=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_api')))
        try:
            await confirmed_search(c,worker)
            if kind in {'ready','reserved'}:return
            adapter=LiveModelAdapter(capability=c['model_cap'],client=Client(),receipts=PostgresModelReceipts(worker,c['workspace'],c['model_cap'],model_id=Client.model_id,route=c['route']))
            with psycopg.connect(c['dsn']) as db:epoch=db.execute('SELECT runtime_epoch FROM outbox_events WHERE id=%s',(event,)).fetchone()[0]
            env=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=event,generation=1,runtime_epoch=epoch)
            assert (await execute_step(worker,env,'start',adapter=adapter,research_engine=api,environment='test')).state=='reconcile'
            if kind=='succeeded':
                with psycopg.connect(c['dsn']) as db:
                    status=db.execute("SELECT id FROM outbox_events WHERE workspace_id=%s AND event_type='provider.reconcile' AND payload->>'original_intent_key' LIKE 'run-model:%%'",(c['workspace'],)).fetchone()[0]
                    db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 WHERE id=%s",(status,))
                status_env=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=status,generation=1,runtime_epoch=epoch)
                assert (await execute_step(worker,status_env,'start',adapter=adapter,environment='test')).state=='done'
        finally:await worker.dispose();await api.dispose()
    asyncio.run(submit())
    path=f"/v1/workspaces/{c['workspace']}/runs/{c['run']}"
    with psycopg.connect(c['dsn']) as db:
        if mode.startswith('retry-'):db.execute("UPDATE search_runs SET status='partial',stage='fit_review_required' WHERE id=%s",(c['run'],))
        before=db.execute('SELECT version,attempt,status,stage FROM search_runs WHERE id=%s',(c['run'],)).fetchone()
        holds=db.execute('SELECT to_jsonb(r) FROM budget_reservations r WHERE workspace_id=%s ORDER BY id',(c['workspace'],)).fetchall()
        events=db.execute('SELECT id,intent_key,state FROM outbox_events WHERE workspace_id=%s ORDER BY id',(c['workspace'],)).fetchall()
    response=c['api'].get(path,headers=_h());assert response.status_code==200,response.text
    data=response.json()['data']
    if mode.startswith('cancel-'):
        reply=c['api'].post(path+'/cancel',json={'reason':'Stop new work without discarding original model reconciliation'},headers={**_h(key='native-stop-'+kind),'If-Match':f'"{before[0]}"'})
        assert reply.status_code==202,reply.text
        assert reply.json()['data']['status']=='cancel_requested'
        assert reply.json()['data']['reconciliation_pending'] is True
        with psycopg.connect(c['dsn']) as db:
            assert db.execute('SELECT status,attempt FROM search_runs WHERE id=%s',(c['run'],)).fetchone()==('cancel_requested',before[1])
            assert db.execute('SELECT id,intent_key,state FROM outbox_events WHERE workspace_id=%s ORDER BY id',(c['workspace'],)).fetchall()==events
    elif mode.startswith('retry-'):
        reply=c['api'].post(path+'/retry',json={'reason':'Review exact original pending model before retry','resume_from_last_committed_checkpoint':True},headers={**_h(key='native-safe-retry-'+kind),'If-Match':f'"{before[0]}"'})
        assert reply.status_code==409 and reply.json()['code']=='RETRY_UNSAFE',reply.text
        with psycopg.connect(c['dsn']) as db:
            assert db.execute('SELECT version,attempt,status,stage FROM search_runs WHERE id=%s',(c['run'],)).fetchone()==before
            assert db.execute('SELECT id,intent_key,state FROM outbox_events WHERE workspace_id=%s ORDER BY id',(c['workspace'],)).fetchall()==events
    else:
        assert data['status']==('awaiting_reconciliation' if kind in {'accepted','unknown'} else 'running')
    assert data.get('retryable') is False
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT to_jsonb(r) FROM budget_reservations r WHERE workspace_id=%s ORDER BY id',(c['workspace'],)).fetchall()==holds
        assert db.execute('SELECT count(*) FROM cost_events WHERE workspace_id=%s',(c['workspace'],)).fetchone()==(0,)
    assert len(calls)==(0 if kind in {'ready','reserved'} else 1)


@pytest.mark.parametrize('run_case',['native'],indirect=True)
def test_native_confirmed_original_work_allows_one_safe_checkpoint_retry(model_case):
    c=model_case
    async def confirm():
        worker=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')))
        try:await confirmed_search(c,worker)
        finally:await worker.dispose()
    asyncio.run(confirm())
    with psycopg.connect(c['dsn']) as db:
        db.execute("UPDATE search_runs SET status='partial',stage='fit_review_required' WHERE id=%s",(c['run'],))
        before=db.execute('SELECT version,attempt FROM search_runs WHERE id=%s',(c['run'],)).fetchone()
        holds=db.execute('SELECT to_jsonb(r) FROM budget_reservations r WHERE workspace_id=%s ORDER BY id',(c['workspace'],)).fetchall()
        old_fits=db.execute("SELECT id FROM outbox_events WHERE workspace_id=%s AND event_type='run.fit'",(c['workspace'],)).fetchall()
    path=f"/v1/workspaces/{c['workspace']}/runs/{c['run']}"
    response=c['api'].get(path,headers=_h());assert response.status_code==200,response.text
    assert response.json()['data']['retryable'] is True
    assert response.json()['data']['reconciliation_pending'] is False
    headers={**_h(key='native-current-safe-positive'),'If-Match':f'"{before[0]}"'}
    body={'reason':'Resume locally confirmed original checkpoint','resume_from_last_committed_checkpoint':True}
    reply=c['api'].post(path+'/retry',json=body,headers=headers);assert reply.status_code==202,reply.text
    duplicate=c['api'].post(path+'/retry',json=body,headers=headers);assert duplicate.status_code==202,duplicate.text
    assert duplicate.json()['data']==reply.json()['data']
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT version,attempt FROM search_runs WHERE id=%s',(c['run'],)).fetchone()==(before[0]+1,before[1]+1)
        assert len(db.execute("SELECT id FROM outbox_events WHERE workspace_id=%s AND event_type='run.fit'",(c['workspace'],)).fetchall())==len(old_fits)+1
        assert db.execute('SELECT to_jsonb(r) FROM budget_reservations r WHERE workspace_id=%s ORDER BY id',(c['workspace'],)).fetchall()==holds
        assert db.execute('SELECT count(*) FROM cost_events WHERE workspace_id=%s',(c['workspace'],)).fetchone()==(0,)
