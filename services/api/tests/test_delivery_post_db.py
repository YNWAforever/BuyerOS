"""Owned post-commit recheck and one permanent POST permit; no network calls."""
import asyncio,importlib,uuid
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
import psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.api.errors import ApiError
from buyeros_api.db.session import tenant_session
from buyeros_api.execution.step_runner import LocalExecution
from tests.test_delivery_submission_db import submission_case,apply as initial_claim,operation,snapshot,counts,worker_dsn,DenySession
from tests.test_delivery_admission_db import admission_case
from tests.test_lookup_quotes_db import WORKSPACE_A

def module():
 path=Path(__file__).resolve().parents[1]/'buyeros_api/services/delivery_post.py'
 assert path.is_file(),'permanent original delivery POST permit missing'
 return importlib.import_module('buyeros_api.services.delivery_post')

def test_delivery_post_default_refuses_before_any_database_or_provider_IO():
 with pytest.raises(ApiError) as error:asyncio.run(module().claim_delivery_post(DenySession(),execution=None,claim=None))
 assert (error.value.status_code,error.value.code)==(503,'PROVIDER_UNAVAILABLE')

@pytest.fixture
def post_case(submission_case):
 client,dsn,args,auth,original,execution=submission_case;claimed=initial_claim(dsn,execution,auth)
 yield client,dsn,args,auth,original,execution,claimed

def apply(dsn,execution,claimed,auth,*,abort=False,catch=False):
 async def one():
  engine=create_async_engine(async_database_url(worker_dsn(dsn)))
  try:
   async with tenant_session(engine,execution.envelope.workspace_id) as session:
    try:result=await module().claim_delivery_post(session,execution=execution,claim=claimed,authorization=auth)
    except ApiError:
     if not catch:raise
     result=None
    if abort:raise RuntimeError('owned post permit abort')
    return result
  finally:await engine.dispose()
 return asyncio.run(one())

def test_delivery_post_one_committed_permit_keeps_original_scope_payload_and_permanent_unknown_hold(post_case):
 client,dsn,args,auth,original,execution,claimed=post_case;before=snapshot(dsn,original);money=counts(dsn);op=operation(dsn,original)
 result=apply(dsn,execution,claimed,auth);after=snapshot(dsn,original)
 assert result.claim is claimed and result.prepared.intent==claimed.prepared.intent and dict(result.prepared.payload)==dict(claimed.prepared.payload)
 assert after[0][:8]==before[0][:8] and after[0][8:10]==('unknown',None) and after[0][10:]==before[0][10:] and after[1:]==before[1:] and counts(dsn)==money
 assert operation(dsn,original)==('unknown_acceptance',None,*op[2:])
 assert 'recipient=' not in repr(result)
 with pytest.raises(ApiError) as error:apply(dsn,execution,claimed,auth)
 assert (error.value.status_code,error.value.code)==(409,'RETRY_UNSAFE') and snapshot(dsn,original)==after

@pytest.mark.parametrize('changed',['role','approval','policy','suppression','revision','recipient','sender'])
def test_delivery_post_permission_revoked_after_initial_claim_blocks_before_IO_without_losing_hold(post_case,changed):
 client,dsn,args,auth,original,execution,claimed=post_case
 with psycopg.connect(dsn) as db:
  if changed=='role':db.execute('UPDATE memberships SET active=false,version=version+1 WHERE workspace_id=%s AND user_id=%s',(args['workspace_id'],args['actor_id']))
  elif changed=='approval':db.execute("UPDATE approvals SET invalidated_reason='owned-late-revocation',invalidated_at=now() WHERE id=%s",(args['approval_id'],))
  elif changed=='policy':db.execute("UPDATE policy_decisions SET status='blocked',version=version+1 WHERE workspace_id=%s AND purpose='outreach'",(WORKSPACE_A,))
  elif changed=='suppression':db.execute("INSERT INTO suppressions(id,workspace_id,subject_key_hash,subject_type,subject_id,controller_scope_id,purpose,purposes,reason,active,actor_id) VALUES (%s,%s,%s,'contact_point',%s,%s,'outreach',ARRAY['outreach'],'owned post opt out',true,%s)",(uuid.uuid4(),WORKSPACE_A,'d'*64,args['recipient_ref'],WORKSPACE_A,args['actor_id']))
  elif changed=='revision':db.execute("UPDATE outreach_drafts SET state='draft',state_version=state_version+1 WHERE id=%s",(args['draft_id'],))
  elif changed=='recipient':db.execute('UPDATE contact_points SET version=version+1 WHERE id=%s',(args['recipient_ref'],))
  else:db.execute('UPDATE projects SET active_sender_identity_version_id=NULL WHERE id=%s',(auth.project_id,))
 before=snapshot(dsn,original);op=operation(dsn,original)
 with pytest.raises(ApiError) as error:apply(dsn,execution,claimed,auth)
 expected=(403,'PERMISSION_DENIED') if changed=='role' else (403,'POLICY_BLOCKED') if changed in {'policy','suppression'} else (412,'STALE_REVISION')
 assert (error.value.status_code,error.value.code)==expected and snapshot(dsn,original)==before and operation(dsn,original)==op

@pytest.mark.parametrize('changed',['message','operation','reservation','outbox','scope','provider','account','generation','epoch','owner','payload'])
def test_delivery_post_cannot_rebind_an_original_claim_or_replace_its_payload(post_case,changed):
 from buyeros_api.services.delivery_service import PreparedDelivery
 from types import MappingProxyType
 client,dsn,args,auth,original,execution,claimed=post_case
 if changed in {'message','operation','reservation','outbox'}:bad=replace(claimed,**{changed+'_id':uuid.uuid4()})
 elif changed=='scope':bad=replace(claimed,scope_hash='c'*64)
 elif changed=='provider':bad=replace(claimed,provider_name='another-provider')
 elif changed=='account':bad=replace(claimed,account_reference='another-account')
 elif changed=='generation':bad=replace(claimed,generation=2)
 elif changed=='epoch':bad=replace(claimed,runtime_epoch=4)
 elif changed=='owner':bad=replace(claimed,owner=uuid.uuid4())
 else:bad=replace(claimed,prepared=PreparedDelivery(claimed.prepared.intent,MappingProxyType(dict(claimed.prepared.payload,body='different unsent copy'))))
 before=snapshot(dsn,original);op=operation(dsn,original)
 with pytest.raises(ApiError) as error:apply(dsn,execution,bad,auth)
 assert (error.value.status_code,error.value.code)==(409,'RETRY_UNSAFE') and snapshot(dsn,original)==before and operation(dsn,original)==op

@pytest.mark.parametrize('changed',['epoch','lease','hold','operation'])
def test_delivery_post_current_fence_and_full_liability_are_rechecked_after_initial_commit(post_case,changed):
 client,dsn,args,auth,original,execution,claimed=post_case
 with psycopg.connect(dsn) as db:
  if changed=='epoch':db.execute('UPDATE worker_runtime_control SET epoch=epoch+1 WHERE singleton=1')
  elif changed=='lease':db.execute("UPDATE worker_steps SET expires_at=now()-interval '1 second' WHERE outbox_id=%s",(original.outbox_id,))
  elif changed=='hold':db.execute('UPDATE budget_reservations SET remaining_hold=0 WHERE id=%s',(original.reservation_id,))
  else:db.execute("UPDATE provider_operations SET status='unknown_acceptance' WHERE id=%s",(original.operation_id,))
 before=snapshot(dsn,original);op=operation(dsn,original)
 with pytest.raises(ApiError) as error:apply(dsn,execution,claimed,auth)
 assert (error.value.status_code,error.value.code)==((409,'STALE_FENCE') if changed in {'epoch','lease'} else (409,'RETRY_UNSAFE')) and snapshot(dsn,original)==before and operation(dsn,original)==op

def test_delivery_post_caller_abort_keeps_committed_initial_claim_and_full_hold(post_case):
 client,dsn,args,auth,original,execution,claimed=post_case;before=snapshot(dsn,original);op=operation(dsn,original)
 with pytest.raises(RuntimeError,match='owned post permit abort'):apply(dsn,execution,claimed,auth,abort=True)
 assert snapshot(dsn,original)==before and operation(dsn,original)==op

def test_delivery_post_authority_expiry_after_actual_writes_rolls_back_even_outer_commit(post_case,monkeypatch):
 client,dsn,args,auth,original,execution,claimed=post_case;before=snapshot(dsn,original);op=operation(dsn,original);check=module()._require_submit_authority;calls=[]
 def expired(value):
  check(value);calls.append(1)
  if len(calls)==2:raise ApiError(503,'PROVIDER_UNAVAILABLE','owned post permit expiry after actual writes')
 monkeypatch.setattr(module(),'_require_submit_authority',expired)
 assert apply(dsn,execution,claimed,auth,catch=True) is None and len(calls)==2 and snapshot(dsn,original)==before and operation(dsn,original)==op

def test_delivery_post_twelve_parallel_original_claims_issue_one_permanent_permit(post_case):
 client,dsn,args,auth,original,execution,claimed=post_case;before=snapshot(dsn,original);money=counts(dsn)
 async def race():
  engine=create_async_engine(async_database_url(worker_dsn(dsn)),pool_size=12,max_overflow=0)
  try:
   async def one():
    try:
     current=LocalExecution(execution.envelope,execution.step_key,execution.owner)
     async with tenant_session(engine,args['workspace_id']) as session:return await module().claim_delivery_post(session,execution=current,claim=claimed,authorization=auth)
    except ApiError as error:return error
   return await asyncio.gather(*(one() for _ in range(12)))
  finally:await engine.dispose()
 results=asyncio.run(race());ok=[x for x in results if not isinstance(x,ApiError)];denied=[x for x in results if isinstance(x,ApiError)]
 assert len(ok)==1 and len(denied)==11 and all((x.status_code,x.code)==(409,'RETRY_UNSAFE') for x in denied)
 after=snapshot(dsn,original);assert after[0][8:10]==('unknown',None) and after[1:]==before[1:] and counts(dsn)==money


@pytest.mark.parametrize('changed',['late-generation','late-operation','late-hold','late-outbox'])
def test_delivery_post_rechecks_locked_current_values_after_unlocked_original_read(post_case,monkeypatch,changed):
 client,dsn,args,auth,original,execution,claimed=post_case;prepare=module().prepare_delivery_intent;injected=[]
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
 with pytest.raises(ApiError) as error:apply(dsn,execution,claimed,auth)
 expected=(409,'STALE_FENCE') if changed=='late-generation' else (409,'RETRY_UNSAFE')
 assert (error.value.status_code,error.value.code)==expected and len(injected)==1
 assert (snapshot(dsn,original),operation(dsn,original))==injected[0]


def test_delivery_post_late_worker_fence_refusal_rolls_back_permit_even_if_outer_commits(post_case,monkeypatch):
 client,dsn,args,auth,original,execution,claimed=post_case;before=snapshot(dsn,original);op=operation(dsn,original);guard=execution.guard;calls=[]
 async def expired(session):
  calls.append(1)
  return await guard(session) if len(calls)==1 else False
 monkeypatch.setattr(execution,'guard',expired)
 assert apply(dsn,execution,claimed,auth,catch=True) is None and len(calls)==2
 assert snapshot(dsn,original)==before and operation(dsn,original)==op


@pytest.mark.parametrize('paid,delivery',[(False,False),(False,True),(True,False)])
def test_delivery_post_closed_dispatch_after_initial_commit_preserves_original_claim(post_case,monkeypatch,paid,delivery):
 from tests.test_delivery_admission_db import dispatch_flags
 client,dsn,args,auth,original,execution,claimed=post_case;before=snapshot(dsn,original);op=operation(dsn,original)
 dispatch_flags(monkeypatch,paid=paid,delivery=delivery,cloudflare=True)
 with pytest.raises(ApiError) as error:apply(dsn,execution,claimed,auth)
 assert (error.value.status_code,error.value.code)==(503,'CAPABILITY_DISABLED') and snapshot(dsn,original)==before and operation(dsn,original)==op


def test_delivery_post_new_authority_cannot_renew_a_committed_unknown_permit(post_case):
 client,dsn,args,auth,original,execution,claimed=post_case;apply(dsn,execution,claimed,auth)
 before=snapshot(dsn,original);op=operation(dsn,original);money=counts(dsn)
 renewed=replace(auth,valid_until=auth.valid_until+timedelta(days=2))
 with pytest.raises(ApiError) as error:apply(dsn,execution,claimed,renewed)
 assert (error.value.status_code,error.value.code)==(409,'RETRY_UNSAFE') and snapshot(dsn,original)==before and operation(dsn,original)==op and counts(dsn)==money
