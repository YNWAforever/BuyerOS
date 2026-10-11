"""Owned native worker fence and one durable submit claim; no vendor I/O."""
import asyncio,importlib,uuid
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
import psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.api.errors import ApiError
from buyeros_api.api.worker_schemas import JobEnvelope
from buyeros_api.db.session import tenant_session
from buyeros_api.execution.step_runner import LocalExecution
from tests.test_delivery_admission_db import admission_case,run as admit,snapshot,counts,claim as dispatch,dispatch_flags,worker_dsn
from tests.test_delivery_budget_db import authority as fixture_authority
from tests.test_lookup_quotes_db import WORKSPACE_A

def module():
 path=Path(__file__).resolve().parents[1]/'buyeros_api/services/delivery_submission.py'
 assert path.is_file(),'durable fenced delivery submit claim missing'
 return importlib.import_module('buyeros_api.services.delivery_submission')

class DenySession:
 def __getattr__(self,name):raise AssertionError('refusal must precede any database or network I/O: '+name)

def test_delivery_submit_default_refuses_before_any_IO():
 with pytest.raises(ApiError) as error:asyncio.run(module().claim_delivery_submission(DenySession(),execution=None))
 assert (error.value.status_code,error.value.code)==(503,'PROVIDER_UNAVAILABLE')

def random_authority():
 return fixture_authority({key:uuid.uuid4() for key in ('workspace_id','project_id','sender_identity_id','recipient_ref')})

@pytest.mark.parametrize('paid,delivery',[(False,False),(False,True),(True,False)])
def test_delivery_submit_requires_both_closed_dispatch_flags_before_IO(monkeypatch,paid,delivery):
 dispatch_flags(monkeypatch,paid=paid,delivery=delivery,cloudflare=True)
 try:
  with pytest.raises(ApiError) as error:asyncio.run(module().claim_delivery_submission(DenySession(),execution=None,authorization=random_authority()))
  assert (error.value.status_code,error.value.code)==(503,'CAPABILITY_DISABLED')
 finally:
  from buyeros_api.execution.config import get_settings
  get_settings.cache_clear()

@pytest.fixture
def submission_case(admission_case,monkeypatch):
 from buyeros_api.services.worker_execution import claim_execution_step
 client,dsn,args,auth=admission_case;original=admit(dsn,args,auth)
 with psycopg.connect(dsn) as db:db.execute("UPDATE worker_runtime_control SET backend='cloudflare',epoch=epoch+1 WHERE singleton=1")
 dispatch_flags(monkeypatch,paid=True,delivery=True,cloudflare=True)
 rows=dispatch(dsn,args,backend='cloudflare',epoch=3);assert len(rows)==1 and rows[0]['id']==original.outbox_id
 envelope=JobEnvelope(v=1,workspace_id=args['workspace_id'],outbox_id=original.outbox_id,generation=1,runtime_epoch=3)
 async def native_claim():
  engine=create_async_engine(async_database_url(worker_dsn(dsn)))
  try:
   async with tenant_session(engine,args['workspace_id']) as session:return await claim_execution_step(session,envelope,'start',datetime.now(timezone.utc))
  finally:await engine.dispose()
 native=asyncio.run(native_claim());assert native.state=='claimed' and native.owner is not None
 execution=LocalExecution(envelope,'start',native.owner)
 try:yield client,dsn,args,auth,original,execution
 finally:
  from buyeros_api.execution.config import get_settings as worker_settings
  from buyeros_api.settings import get_settings as api_settings
  worker_settings.cache_clear();api_settings.cache_clear()

def apply(dsn,execution,auth,*,abort=False,catch=False):
 async def one():
  engine=create_async_engine(async_database_url(worker_dsn(dsn)))
  try:
   async with tenant_session(engine,execution.envelope.workspace_id) as session:
    try:result=await module().claim_delivery_submission(session,execution=execution,authorization=auth)
    except ApiError:
     if not catch:raise
     result=None
    if abort:raise RuntimeError('owned submit claim abort')
    return result
  finally:await engine.dispose()
 return asyncio.run(one())

def operation(dsn,original):
 with psycopg.connect(dsn) as db:return db.execute('SELECT status,provider_ref,intent_key,input_hash,provider_name,account_reference FROM provider_operations WHERE id=%s',(original.operation_id,)).fetchone()

def test_delivery_submit_real_worker_claim_persists_once_before_IO_and_keeps_exact_payload_and_hold(submission_case):
 client,dsn,args,auth,original,execution=submission_case;before=snapshot(dsn,original);money=counts(dsn);op=operation(dsn,original)
 result=apply(dsn,execution,auth);after=snapshot(dsn,original)
 assert result.message_id==original.message_id and result.operation_id==original.operation_id and result.reservation_id==original.reservation_id and result.outbox_id==original.outbox_id and result.scope_hash==auth.scope_hash
 assert result.prepared.intent.key==args['key'] and result.prepared.intent.payload_digest==before[0][-1]
 assert set(result.prepared.payload)=={'subject','body','recipient','sender'} and 'subject=' not in repr(result)
 with pytest.raises(TypeError):result.prepared.payload['body']='new draft'
 assert after[0][:8]==before[0][:8] and after[0][8]=='submitting' and after[0][9:]==before[0][9:] and after[1:]==before[1:] and counts(dsn)==money
 assert operation(dsn,original)==('submitted',None,*op[2:])
 with pytest.raises(ApiError) as error:apply(dsn,execution,auth)
 assert (error.value.status_code,error.value.code)==(409,'RETRY_UNSAFE') and snapshot(dsn,original)==after

@pytest.mark.parametrize('state',['submitting','unknown','accepted','delivered'])
def test_delivery_submit_crash_or_known_acceptance_never_resubmits_original_intent(submission_case,state):
 client,dsn,args,auth,original,execution=submission_case
 with psycopg.connect(dsn) as db:
  db.execute("UPDATE delivery_messages SET state='submitting' WHERE id=%s",(original.message_id,))
  if state!='submitting':db.execute('UPDATE delivery_messages SET state=%s,provider_ref=%s WHERE id=%s',(state,None if state=='unknown' else 'original-ref',original.message_id))
 before=snapshot(dsn,original);op=operation(dsn,original);money=counts(dsn)
 with pytest.raises(ApiError) as error:apply(dsn,execution,auth)
 assert (error.value.status_code,error.value.code)==(409,'RETRY_UNSAFE') and snapshot(dsn,original)==before and operation(dsn,original)==op and counts(dsn)==money

@pytest.mark.parametrize('changed',['role','policy','suppression','revision','sender'])
def test_delivery_submit_rechecks_current_role_approval_policy_and_recipient_before_claim(submission_case,changed):
 client,dsn,args,auth,original,execution=submission_case
 with psycopg.connect(dsn) as db:
  if changed=='role':db.execute('UPDATE memberships SET active=false,version=version+1 WHERE workspace_id=%s AND user_id=%s',(args['workspace_id'],args['actor_id']))
  elif changed=='policy':db.execute("UPDATE policy_decisions SET status='blocked',version=version+1 WHERE workspace_id=%s AND purpose='outreach'",(WORKSPACE_A,))
  elif changed=='suppression':db.execute("INSERT INTO suppressions(id,workspace_id,subject_key_hash,subject_type,subject_id,controller_scope_id,purpose,purposes,reason,active,actor_id) VALUES (%s,%s,%s,'contact_point',%s,%s,'outreach',ARRAY['outreach'],'owned claim opt out',true,%s)",(uuid.uuid4(),WORKSPACE_A,'d'*64,args['recipient_ref'],WORKSPACE_A,args['actor_id']))
  elif changed=='revision':db.execute("UPDATE outreach_drafts SET state='draft',state_version=state_version+1 WHERE id=%s",(args['draft_id'],))
  else:db.execute('UPDATE projects SET active_sender_identity_version_id=NULL WHERE id=%s',(args['project_id'] if 'project_id' in args else auth.project_id,))
 before=snapshot(dsn,original);op=operation(dsn,original)
 with pytest.raises(ApiError) as error:apply(dsn,execution,auth)
 expected=(403,'PERMISSION_DENIED') if changed=='role' else (403,'POLICY_BLOCKED') if changed in {'policy','suppression'} else (412,'STALE_REVISION')
 assert (error.value.status_code,error.value.code)==expected and snapshot(dsn,original)==before and operation(dsn,original)==op

@pytest.mark.parametrize('changed',['scope','expired','unreviewed'])
def test_delivery_submit_cannot_replace_the_original_reviewed_authority(submission_case,changed):
 client,dsn,args,auth,original,execution=submission_case;before=snapshot(dsn,original);op=operation(dsn,original)
 bad=replace(auth,account_reference='another-account') if changed=='scope' else replace(auth,valid_until=datetime.now(timezone.utc)-timedelta(seconds=1)) if changed=='expired' else replace(auth,reviewed=False)
 with pytest.raises(ApiError) as error:apply(dsn,execution,bad)
 assert (error.value.status_code,error.value.code)==((409,'IDEMPOTENCY_CONFLICT') if changed=='scope' else (503,'PROVIDER_UNAVAILABLE')) and snapshot(dsn,original)==before and operation(dsn,original)==op

@pytest.mark.parametrize('changed',['epoch','owner','lease','generation','disabled'])
def test_delivery_submit_current_native_worker_fence_denies_stale_claim_without_mutation(submission_case,changed):
 client,dsn,args,auth,original,execution=submission_case
 with psycopg.connect(dsn) as db:
  if changed=='epoch':db.execute('UPDATE worker_runtime_control SET epoch=epoch+1 WHERE singleton=1')
  elif changed=='owner':db.execute('UPDATE worker_steps SET owner=%s WHERE outbox_id=%s',(uuid.uuid4(),original.outbox_id))
  elif changed=='lease':db.execute("UPDATE worker_steps SET expires_at=now()-interval '1 second' WHERE outbox_id=%s",(original.outbox_id,))
  elif changed=='generation':db.execute('UPDATE outbox_events SET fencing_generation=fencing_generation+1 WHERE id=%s',(original.outbox_id,))
  else:db.execute('UPDATE worker_runtime_control SET enabled=false,epoch=epoch+1 WHERE singleton=1')
 before=snapshot(dsn,original);op=operation(dsn,original)
 with pytest.raises(ApiError) as error:apply(dsn,execution,auth)
 assert (error.value.status_code,error.value.code)==(409,'STALE_FENCE') and snapshot(dsn,original)==before and operation(dsn,original)==op

def test_delivery_submit_caller_abort_preserves_prepared_original_and_full_hold(submission_case):
 client,dsn,args,auth,original,execution=submission_case;before=snapshot(dsn,original);op=operation(dsn,original)
 with pytest.raises(RuntimeError,match='owned submit claim abort'):apply(dsn,execution,auth,abort=True)
 assert snapshot(dsn,original)==before and operation(dsn,original)==op

def test_delivery_submit_expiry_after_write_rolls_back_even_when_outer_caller_commits(submission_case,monkeypatch):
 client,dsn,args,auth,original,execution=submission_case;before=snapshot(dsn,original);op=operation(dsn,original);check=module()._require_submit_authority;calls=[]
 def expired(value):
  check(value);calls.append(1)
  if len(calls)==2:raise ApiError(503,'PROVIDER_UNAVAILABLE','owned authority expiry after claim writes')
 monkeypatch.setattr(module(),'_require_submit_authority',expired)
 assert apply(dsn,execution,auth,catch=True) is None and len(calls)==2
 assert snapshot(dsn,original)==before and operation(dsn,original)==op

def test_delivery_submit_twelve_parallel_current_worker_calls_claim_original_only_once(submission_case):
 client,dsn,args,auth,original,execution=submission_case;before=snapshot(dsn,original);money=counts(dsn)
 async def race():
  engine=create_async_engine(async_database_url(worker_dsn(dsn)),pool_size=12,max_overflow=0)
  try:
   async def one():
    try:
     current=LocalExecution(execution.envelope,execution.step_key,execution.owner)
     async with tenant_session(engine,args['workspace_id']) as session:return await module().claim_delivery_submission(session,execution=current,authorization=auth)
    except ApiError as error:return error
   return await asyncio.gather(*(one() for _ in range(12)))
  finally:await engine.dispose()
 results=asyncio.run(race());ok=[x for x in results if not isinstance(x,ApiError)];denied=[x for x in results if isinstance(x,ApiError)]
 assert len(ok)==1 and len(denied)==11 and all((x.status_code,x.code)==(409,'RETRY_UNSAFE') for x in denied)
 after=snapshot(dsn,original);assert after[0][8:10]==('submitting',None) and after[0][:8]==before[0][:8] and after[0][10:]==before[0][10:] and after[1:]==before[1:] and counts(dsn)==money

@pytest.mark.parametrize('changed',['late-generation','late-operation','late-hold','late-outbox'])
def test_delivery_submit_rechecks_locked_current_values_after_unlocked_original_read(submission_case,monkeypatch,changed):
 client,dsn,args,auth,original,execution=submission_case;prepare=module().prepare_delivery_intent;injected=[]
 async def drift(session,**bindings):
  result=await prepare(session,**bindings)
  with psycopg.connect(dsn) as db:
   if changed=='late-generation':db.execute('UPDATE outbox_events SET fencing_generation=fencing_generation+1 WHERE id=%s',(original.outbox_id,))
   elif changed=='late-operation':db.execute("UPDATE provider_operations SET status='unknown_acceptance' WHERE id=%s",(original.operation_id,))
   elif changed=='late-hold':db.execute('UPDATE budget_reservations SET remaining_hold=0 WHERE id=%s',(original.reservation_id,))
   else:db.execute("UPDATE outbox_events SET payload=jsonb_set(payload,'{scope_hash}',to_jsonb(%s::text)) WHERE id=%s",('c'*64,original.outbox_id))
  injected.append((snapshot(dsn,original),operation(dsn,original)))
  return result
 monkeypatch.setattr(module(),'prepare_delivery_intent',drift)
 with pytest.raises(ApiError) as error:apply(dsn,execution,auth)
 expected=(409,'STALE_FENCE') if changed=='late-generation' else (409,'RETRY_UNSAFE')
 assert (error.value.status_code,error.value.code)==expected and len(injected)==1
 assert (snapshot(dsn,original),operation(dsn,original))==injected[0]


def test_delivery_submit_late_worker_fence_refusal_rolls_back_claim_even_if_outer_commits(submission_case,monkeypatch):
 client,dsn,args,auth,original,execution=submission_case;before=snapshot(dsn,original);op=operation(dsn,original);guard=execution.guard;calls=[]
 async def expired(session):
  calls.append(1)
  return await guard(session) if len(calls)==1 else False
 monkeypatch.setattr(execution,'guard',expired)
 assert apply(dsn,execution,auth,catch=True) is None and len(calls)==2
 assert snapshot(dsn,original)==before and operation(dsn,original)==op
