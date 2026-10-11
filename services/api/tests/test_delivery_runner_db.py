"""Actual owned native delivery orchestration; no external transport/account."""
import asyncio,contextlib,importlib,uuid
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.api.errors import ApiError
from buyeros_api.db.session import tenant_session
from buyeros_api.execution.step_runner import LocalExecution
from buyeros_api.providers.base import Money,SubmissionResult
from tests.test_delivery_admission_db import admission_case,dispatch_flags
from tests.test_delivery_submission_db import submission_case,random_authority,worker_dsn,operation,counts,DenySession
from tests.test_delivery_status_db import authority,snapshot

def module():
    p=Path(__file__).resolve().parents[1]/'buyeros_api/execution/delivery_runner.py'
    assert p.is_file(),'transaction-separated native delivery runner missing'
    return importlib.import_module('buyeros_api.execution.delivery_runner')

class OwnedAdapter:
    def __init__(self,dsn,original,prepared,*,result=None,error=None,estimate=None,before_result=None):
        self.dsn,self.original,self.prepared=dsn,original,prepared
        self.result=result or SubmissionResult('accepted','original-ref')
        self.error,self.quoted,self.before_result=error,estimate,before_result
        self.calls=[]
    def estimate(self,intent):
        assert intent==self.prepared.intent
        return self.quoted if self.quoted is not None else Money(Decimal('0.010000'))
    async def submit(self,intent):
        assert intent==self.prepared.intent
        # A separate connection must see the permanent original permit. No DB
        # lock or open runtime transaction may survive into the provider await.
        current=snapshot(self.dsn,self.original)
        assert current['original'][0][8:10]==('unknown',None)
        assert current['operation']==('unknown_acceptance',None)
        assert current['original'][1][2]==current['original'][1][3]
        with psycopg.connect(self.dsn) as db:
            db.execute("SET LOCAL lock_timeout='200ms'")
            assert db.execute('SELECT id FROM delivery_messages WHERE id=%s FOR UPDATE NOWAIT',(self.original.message_id,)).fetchone()
            assert db.execute('SELECT singleton FROM worker_runtime_control WHERE singleton=1 FOR UPDATE NOWAIT').fetchone()
            assert db.execute('SELECT id FROM outbox_events WHERE id=%s FOR UPDATE NOWAIT',(self.original.outbox_id,)).fetchone()
        self.calls.append(intent)
        if self.before_result is not None:self.before_result()
        if self.error is not None:raise self.error
        return self.result
    async def status(self,ref):
        raise AssertionError('submit runner must not query status or retry POST')

def selected(case,*,factory=None,**adapter_options):
    client,dsn,args,auth,original,execution=case
    adapters=[]
    def build(prepared):
        current=snapshot(dsn,original)
        assert current['original'][0][8:10]==('submitting',None)
        assert current['operation']==('submitted',None)
        assert set(prepared.payload)=={'subject','body','recipient','sender'}
        with pytest.raises(TypeError):prepared.payload['body']='client replacement'
        adapter=OwnedAdapter(dsn,original,prepared,**adapter_options)
        adapters.append(adapter)
        return factory(adapter) if factory is not None else adapter
    return module().DeliverySelection(auth,authority(args,auth),build),adapters

def run(case,selection):
    async def one():
        engine=create_async_engine(async_database_url(worker_dsn(case[1])))
        try:return await module().submit_delivery_claimed(engine,case[5],selection=selection)
        finally:await engine.dispose()
    return asyncio.run(one())

def assert_retained(before,after):
    assert before['original'][0][:8]==after['original'][0][:8]
    assert before['original'][0][10:]==after['original'][0][10:]
    assert before['original'][1:]==after['original'][1:]
    assert before['cost']==after['cost']==0

def test_delivery_runner_unselected_refuses_before_all_IO():
    with pytest.raises(ApiError) as error:asyncio.run(module().submit_delivery_claimed(DenySession(),None))
    assert (error.value.status_code,error.value.code)==(503,'PROVIDER_UNAVAILABLE')

@pytest.mark.parametrize('paid,delivery',[(False,False),(False,True),(True,False)])
def test_delivery_runner_both_dispatch_flags_required_before_IO(monkeypatch,paid,delivery):
    auth=random_authority();selected_authority=authority({'workspace_id':auth.workspace_id},auth)
    selection=module().DeliverySelection(auth,selected_authority,lambda prepared:pytest.fail('closed factory called'))
    dispatch_flags(monkeypatch,paid=paid,delivery=delivery,cloudflare=True)
    try:
        with pytest.raises(ApiError) as error:asyncio.run(module().submit_delivery_claimed(DenySession(),None,selection=selection))
        assert (error.value.status_code,error.value.code)==(503,'CAPABILITY_DISABLED')
    finally:
        from buyeros_api.execution.config import get_settings
        get_settings.cache_clear()

@pytest.mark.parametrize('fault',['selection','selected','reviewed','sender','expired','status-reviewed','status-expired','workspace','provider','account','scope','contract','factory'])
def test_delivery_runner_selection_and_retained_authority_bound_before_IO(monkeypatch,fault):
    auth=random_authority();retained=authority({'workspace_id':auth.workspace_id},auth)
    factory=lambda prepared:pytest.fail('invalid selection called factory')
    if fault in {'selected','reviewed','sender'}:auth=replace(auth,**{{'sender':'sender_verified'}.get(fault,fault):False})
    elif fault=='expired':auth=replace(auth,valid_until=datetime.now(timezone.utc)-timedelta(seconds=1))
    elif fault=='status-reviewed':retained=replace(retained,reviewed=False)
    elif fault=='status-expired':retained=replace(retained,valid_until=datetime.now(timezone.utc)-timedelta(seconds=1))
    elif fault=='workspace':retained=replace(retained,workspace_id=uuid.uuid4())
    elif fault=='provider':retained=replace(retained,provider_name='other-provider')
    elif fault=='account':retained=replace(retained,account_reference='other-account')
    elif fault=='scope':retained=replace(retained,scope_hash='c'*64)
    elif fault=='contract':retained=replace(retained,reviewed_contract_hash='c'*64)
    elif fault=='factory':factory=None
    selection=SimpleNamespace() if fault=='selection' else module().DeliverySelection(auth,retained,factory)
    with pytest.raises(ApiError) as error:asyncio.run(module().submit_delivery_claimed(DenySession(),None,selection=selection))
    assert (error.value.status_code,error.value.code)==(503,'PROVIDER_UNAVAILABLE')

def test_delivery_runner_same_intent_once_committed_unknown_before_POST_then_accepted_receipt(submission_case):
    selection,adapters=selected(submission_case);original=submission_case[4];dsn=submission_case[1]
    before=snapshot(dsn,original);money=counts(dsn)
    receipt=run(submission_case,selection);after=snapshot(dsn,original)
    assert receipt.state=='accepted' and receipt.provider_ref=='original-ref' and receipt.event_id is not None
    assert after['original'][0][8:10]==('accepted','original-ref') and len(after['events'])==1
    assert after['events'][0][1].startswith('submission:') and after['operation']==('accepted','original-ref')
    assert len(adapters)==len(adapters[0].calls)==1 and counts(dsn)==money
    assert_retained(before,after)
    with pytest.raises(ApiError) as error:run(submission_case,selection)
    assert (error.value.status_code,error.value.code)==(409,'RETRY_UNSAFE')
    assert snapshot(dsn,original)==after and len(adapters)==len(adapters[0].calls)==1

@pytest.mark.parametrize('fault',['role','approval','policy','suppression','generation','epoch'])
def test_delivery_runner_revocation_after_claim_before_POST_has_zero_provider_calls(submission_case,fault):
    client,dsn,args,auth,original,execution=submission_case
    def revoked(adapter):
        with psycopg.connect(dsn) as db:
            if fault=='role':db.execute('UPDATE memberships SET active=false,version=version+1 WHERE workspace_id=%s AND user_id=%s',(args['workspace_id'],args['actor_id']))
            elif fault=='approval':db.execute("UPDATE approvals SET invalidated_reason='owned revocation',invalidated_at=now() WHERE id=%s",(args['approval_id'],))
            elif fault=='policy':db.execute("UPDATE policy_decisions SET status='blocked',version=version+1 WHERE workspace_id=%s AND purpose='outreach'",(args['workspace_id'],))
            elif fault=='suppression':db.execute("INSERT INTO suppressions(id,workspace_id,subject_key_hash,subject_type,subject_id,controller_scope_id,purpose,purposes,reason,active,actor_id) VALUES (%s,%s,%s,'contact_point',%s,%s,'outreach',ARRAY['outreach'],'owned optout',true,%s)",(uuid.uuid4(),args['workspace_id'],'d'*64,args['recipient_ref'],args['workspace_id'],args['actor_id']))
            elif fault=='generation':db.execute('UPDATE outbox_events SET fencing_generation=fencing_generation+1 WHERE id=%s',(original.outbox_id,))
            else:db.execute('UPDATE worker_runtime_control SET epoch=epoch+1 WHERE singleton=1')
        return adapter
    selection,adapters=selected(submission_case,factory=revoked);before=snapshot(dsn,original)
    with pytest.raises(ApiError) as error:run(submission_case,selection)
    expected=(403,'PERMISSION_DENIED') if fault=='role' else (412,'STALE_REVISION') if fault=='approval' else (403,'POLICY_BLOCKED') if fault in {'policy','suppression'} else (409,'STALE_FENCE')
    assert (error.value.status_code,error.value.code)==expected and len(adapters)==1 and adapters[0].calls==[]
    after=snapshot(dsn,original);assert after['original'][0][8:10]==('submitting',None) and after['operation']==('submitted',None)
    assert before['original'][1:3]==after['original'][1:3] and before['original'][4]==after['original'][4] and after['cost']==0

@pytest.mark.parametrize('estimate',[SimpleNamespace(amount=Decimal('0.010000'),currency='USD'),Money(Decimal('0')),Money(Decimal('0.020000'))])
def test_delivery_runner_invalid_or_over_limit_estimate_never_obtains_POST_permit(submission_case,estimate):
    selection,adapters=selected(submission_case,estimate=estimate);before=snapshot(submission_case[1],submission_case[4])
    with pytest.raises(ApiError) as error:run(submission_case,selection)
    assert (error.value.status_code,error.value.code)==(503,'PROVIDER_UNAVAILABLE') and len(adapters)==1 and adapters[0].calls==[]
    after=snapshot(submission_case[1],submission_case[4]);assert after['original'][0][8:10]==('submitting',None) and after['operation']==('submitted',None)
    assert_retained(before,after)

@pytest.mark.parametrize('result,error',[(SubmissionResult('unknown',None),None),(SubmissionResult('rejected',None),None),(None,RuntimeError('opaque provider failure')),(SimpleNamespace(state='accepted',provider_ref='untrusted-ref'),None),(SubmissionResult('accepted',None),None)])
def test_delivery_runner_unknown_error_rejection_or_invalid_response_never_resends_or_releases(submission_case,result,error):
    selection,adapters=selected(submission_case,result=result,error=error);dsn=submission_case[1];original=submission_case[4];before=snapshot(dsn,original)
    receipt=run(submission_case,selection);after=snapshot(dsn,original)
    assert receipt.state=='unknown' and receipt.provider_ref is None and after['original'][0][8:10]==('unknown',None)
    assert after['operation']==('unknown_acceptance',None) and after['events']==[] and len(adapters[0].calls)==1
    assert_retained(before,after)
    with pytest.raises(ApiError) as denied:run(submission_case,selection)
    assert (denied.value.status_code,denied.value.code)==(409,'RETRY_UNSAFE') and snapshot(dsn,original)==after and len(adapters)==1

def test_delivery_runner_cancellation_after_POST_keeps_permanent_unknown_and_full_hold(submission_case):
    selection,adapters=selected(submission_case,error=asyncio.CancelledError());dsn=submission_case[1];original=submission_case[4];before=snapshot(dsn,original)
    with pytest.raises(asyncio.CancelledError):run(submission_case,selection)
    after=snapshot(dsn,original);assert after['original'][0][8:10]==('unknown',None) and after['operation']==('unknown_acceptance',None) and len(adapters[0].calls)==1
    assert_retained(before,after)
    with pytest.raises(ApiError) as denied:run(submission_case,selection)
    assert denied.value.code=='RETRY_UNSAFE' and snapshot(dsn,original)==after and len(adapters)==1

def test_delivery_runner_twelve_parallel_native_calls_send_original_once(submission_case):
    selection,adapters=selected(submission_case);before=snapshot(submission_case[1],submission_case[4])
    async def race():
        engine=create_async_engine(async_database_url(worker_dsn(submission_case[1])),pool_size=12,max_overflow=0)
        async def one():
            execution=LocalExecution(submission_case[5].envelope,'start',submission_case[5].owner)
            try:return await module().submit_delivery_claimed(engine,execution,selection=selection)
            except ApiError as error:return error
        try:return await asyncio.gather(*(one() for _ in range(12)))
        finally:await engine.dispose()
    results=asyncio.run(race());denied=[x for x in results if isinstance(x,ApiError)];ok=[x for x in results if not isinstance(x,ApiError)]
    assert len(ok)==1 and ok[0].state=='accepted' and len(denied)==11 and all(x.code=='RETRY_UNSAFE' for x in denied)
    assert len(adapters)==len(adapters[0].calls)==1 and len(snapshot(submission_case[1],submission_case[4])['events'])==1
    assert_retained(before,snapshot(submission_case[1],submission_case[4]))

def test_delivery_runner_permit_transaction_commit_failure_cannot_start_POST(submission_case,monkeypatch):
    selection,adapters=selected(submission_case);native=module().tenant_session;calls=[]
    @contextlib.asynccontextmanager
    async def fail_commit(engine,workspace):
        calls.append(1)
        async with native(engine,workspace) as session:
            yield session
            if len(calls)==2:raise RuntimeError('owned permit commit failure')
    monkeypatch.setattr(module(),'tenant_session',fail_commit)
    with pytest.raises(RuntimeError,match='owned permit commit failure'):run(submission_case,selection)
    assert len(calls)==2 and len(adapters)==1 and adapters[0].calls==[]
    after=snapshot(submission_case[1],submission_case[4]);assert after['original'][0][8:10]==('submitting',None) and after['operation']==('submitted',None)

def test_delivery_runner_response_write_failure_retains_unknown_without_second_POST(submission_case,monkeypatch):
    selection,adapters=selected(submission_case);native=module().record_delivery_submission
    async def fail_response(session,**args):
        await native(session,**args)
        raise RuntimeError('owned response write failure')
    monkeypatch.setattr(module(),'record_delivery_submission',fail_response)
    with pytest.raises(RuntimeError,match='owned response write failure'):run(submission_case,selection)
    after=snapshot(submission_case[1],submission_case[4]);assert after['original'][0][8:10]==('unknown',None) and after['operation']==('unknown_acceptance',None) and after['events']==[]
    assert len(adapters[0].calls)==1
    with pytest.raises(ApiError) as denied:run(submission_case,selection)
    assert denied.value.code=='RETRY_UNSAFE' and snapshot(submission_case[1],submission_case[4])==after and len(adapters)==1

def test_delivery_runner_accepted_response_survives_permission_and_worker_lease_revocation(submission_case):
    client,dsn,args,auth,original,execution=submission_case
    def revoke():
        with psycopg.connect(dsn) as db:
            db.execute('UPDATE memberships SET active=false,version=version+1 WHERE workspace_id=%s AND user_id=%s',(args['workspace_id'],args['actor_id']))
            db.execute("UPDATE worker_steps SET expires_at=now()-interval '1 second' WHERE outbox_id=%s",(original.outbox_id,))
    selection,adapters=selected(submission_case,before_result=revoke)
    receipt=run(submission_case,selection);after=snapshot(dsn,original)
    assert receipt.state=='accepted' and receipt.provider_ref=='original-ref' and len(after['events'])==1 and len(adapters[0].calls)==1
    assert after['original'][1][2]==after['original'][1][3] and after['cost']==0


def native_run(case,*,fresh_claim=False,common=None):
    async def one():
        from buyeros_api.execution.step_runner import execute_claimed
        from buyeros_api.services.worker_execution import execute_step
        engine=create_async_engine(async_database_url(worker_dsn(case[1])))
        try:
            execution=case[5]
            if fresh_claim:return await execute_step(engine,execution.envelope,'start',adapter=common,environment='test')
            return await execute_claimed(engine,execution.envelope,'start',execution.owner,adapter=common,environment='test')
        finally:await engine.dispose()
    return asyncio.run(one())

@pytest.mark.parametrize('response',[SubmissionResult('accepted','original-ref'),SubmissionResult('unknown',None),SubmissionResult('rejected',None)])
def test_native_delivery_selected_attempt_is_reconcile_not_delivered_and_finishes_fresh_receipt(submission_case,monkeypatch,response):
    selection,adapters=selected(submission_case,result=response)
    monkeypatch.setattr(module(),'selected_delivery_runtime',lambda execution:selection,raising=False)
    reply=native_run(submission_case);after=snapshot(submission_case[1],submission_case[4])
    assert (reply.state,reply.code)==('reconcile','PROVIDER_UNKNOWN') and len(adapters)==len(adapters[0].calls)==1
    assert after['original'][0][8]==('accepted' if response.state=='accepted' else 'unknown') and after['cost']==0
    with psycopg.connect(submission_case[1]) as db:
        state,receipt=db.execute('SELECT state,outcome FROM worker_steps WHERE outbox_id=%s',(submission_case[4].outbox_id,)).fetchone()
        assert state=='reconcile' and receipt==reply.model_dump(mode='json') and set(receipt)=={'state','code','next_step_key','retry_at'}

def test_native_delivery_unselected_keeps_closed_behavior_and_never_uses_common_adapter(submission_case,monkeypatch):
    monkeypatch.setattr(module(),'selected_delivery_runtime',lambda execution:None,raising=False)
    before=snapshot(submission_case[1],submission_case[4]);reply=native_run(submission_case,common=DenySession())
    assert (reply.state,reply.code)==('blocked','CAPABILITY_UNAVAILABLE')
    after=snapshot(submission_case[1],submission_case[4]);assert after['original'][:3]==before['original'][:3] and after['original'][4]==before['original'][4] and after['cost']==0

def test_native_delivery_selected_invalid_scope_refuses_before_factory_and_keeps_full_hold(submission_case,monkeypatch):
    selection,adapters=selected(submission_case)
    selection=replace(selection,reconciliation=replace(selection.reconciliation,scope_hash='c'*64))
    monkeypatch.setattr(module(),'selected_delivery_runtime',lambda execution:selection,raising=False)
    before=snapshot(submission_case[1],submission_case[4]);reply=native_run(submission_case)
    assert (reply.state,reply.code)==('blocked','CAPABILITY_UNAVAILABLE') and adapters==[]
    after=snapshot(submission_case[1],submission_case[4]);assert after['original'][:3]==before['original'][:3] and after['original'][4]==before['original'][4] and after['cost']==0

def test_native_delivery_received_acceptance_retained_when_late_worker_lease_cannot_finish(submission_case,monkeypatch):
    dsn=submission_case[1];original=submission_case[4]
    def expire():
        with psycopg.connect(dsn) as db:db.execute("UPDATE worker_steps SET expires_at=now()-interval '1 second' WHERE outbox_id=%s",(original.outbox_id,))
    selection,adapters=selected(submission_case,before_result=expire)
    monkeypatch.setattr(module(),'selected_delivery_runtime',lambda execution:selection,raising=False)
    reply=native_run(submission_case);after=snapshot(dsn,original)
    assert (reply.state,reply.code)==('stale','STALE_FENCE') and after['original'][0][8:10]==('accepted','original-ref') and len(after['events'])==1
    assert len(adapters)==len(adapters[0].calls)==1 and after['cost']==0

def test_native_delivery_fresh_real_worker_entrypoint_uses_independent_delivery_and_never_contact(submission_case,monkeypatch):
    dsn=submission_case[1];original=submission_case[4]
    with psycopg.connect(dsn) as db:
        db.execute('DELETE FROM worker_steps WHERE outbox_id=%s',(original.outbox_id,))
        db.execute('UPDATE worker_runtime_control SET active_owner=NULL,active_until=NULL WHERE singleton=1')
    selection,adapters=selected(submission_case)
    monkeypatch.setattr(module(),'selected_delivery_runtime',lambda execution:selection,raising=False)
    reply=native_run(submission_case,fresh_claim=True,common=DenySession())
    assert (reply.state,reply.code)==('reconcile','PROVIDER_UNKNOWN') and len(adapters)==len(adapters[0].calls)==1
    assert snapshot(dsn,original)['original'][0][8:10]==('accepted','original-ref')

def test_native_delivery_disabled_dispatch_never_resolves_factory(submission_case,monkeypatch):
    monkeypatch.setattr(module(),'selected_delivery_runtime',lambda execution:pytest.fail('disabled selection called'),raising=False)
    dispatch_flags(monkeypatch,paid=False,delivery=True,cloudflare=True)
    reply=native_run(submission_case)
    assert (reply.state,reply.code)==('blocked','EXECUTION_DISABLED') and snapshot(submission_case[1],submission_case[4])['original'][0][8:10]==('prepared',None)
