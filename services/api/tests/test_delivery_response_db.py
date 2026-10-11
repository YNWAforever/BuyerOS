"""Owned post-permit response persistence; no HTTP or real account selection."""
import asyncio,importlib,uuid
from dataclasses import replace
from pathlib import Path
import psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.api.errors import ApiError
from buyeros_api.db.session import tenant_session
from buyeros_api.providers.base import SubmissionResult
from tests.test_delivery_admission_db import admission_case,dispatch_flags
from tests.test_delivery_submission_db import submission_case,apply as initial_claim,operation,counts,worker_dsn,DenySession
from tests.test_delivery_post_db import post_case,apply as post_permit
from tests.test_delivery_status_db import authority,snapshot,apply as observe
from tests.test_api_tenant_isolation import WORKSPACE_B

def module():
 path=Path(__file__).resolve().parents[1]/'buyeros_api/services/delivery_response.py'
 assert path.is_file(),'durable original delivery submit response service missing'
 return importlib.import_module('buyeros_api.services.delivery_response')

def test_delivery_response_default_refuses_before_database_or_provider_IO():
 with pytest.raises(ApiError) as error:asyncio.run(module().record_delivery_submission(DenySession(),permit=None,result=SubmissionResult('accepted','original-ref')))
 assert (error.value.status_code,error.value.code)==(503,'PROVIDER_UNAVAILABLE')

@pytest.fixture
def response_case(post_case):
 client,dsn,args,auth,original,execution,claimed=post_case;permit=post_permit(dsn,execution,claimed,auth)
 yield client,dsn,args,auth,original,execution,permit,authority(args,auth)

def apply(dsn,permit,result,selected,*,workspace=None,abort=False,catch=False):
 async def one():
  engine=create_async_engine(async_database_url(worker_dsn(dsn)))
  try:
   async with tenant_session(engine,workspace or selected.workspace_id) as session:
    try:receipt=await module().record_delivery_submission(session,permit=permit,result=result,authority=selected)
    except ApiError:
     if not catch:raise
     receipt=None
    if abort:raise RuntimeError('owned response caller abort')
    return receipt
  finally:await engine.dispose()
 return asyncio.run(one())

def retained(before,after):
 assert before['original'][0][:8]==after['original'][0][:8] and before['original'][0][10:]==after['original'][0][10:]
 assert before['original'][1:]==after['original'][1:] and before['cost']==after['cost']==0 and before['suppression']==after['suppression']

def test_delivery_response_accepted_once_binds_original_ref_receipt_and_full_hold_without_delivery(response_case):
 client,dsn,args,auth,original,execution,permit,selected=response_case;before=snapshot(dsn,original);money=counts(dsn);op=operation(dsn,original);result=SubmissionResult('accepted','original-ref')
 first=apply(dsn,permit,result,selected);second=apply(dsn,permit,result,selected);after=snapshot(dsn,original)
 assert first.state==second.state=='accepted' and first.provider_ref==second.provider_ref=='original-ref' and first.event_id==second.event_id and not first.replayed and second.replayed
 assert after['original'][0][8:10]==('accepted','original-ref') and len(after['events'])==1 and after['events'][0][1].startswith('submission:')
 assert operation(dsn,original)==('accepted','original-ref',*op[2:]) and counts(dsn)==money
 retained(before,after)
 from tests.test_delivery_post_db import apply as claim_again
 with pytest.raises(ApiError) as error:claim_again(dsn,execution,permit.claim,auth)
 assert (error.value.status_code,error.value.code)==(409,'RETRY_UNSAFE')

@pytest.mark.parametrize('state,ref',[('unknown',None),('unknown','original-ref'),('rejected',None)])
def test_delivery_response_unknown_and_rejection_keep_uncertainty_and_full_hold(response_case,state,ref):
 client,dsn,args,auth,original,execution,permit,selected=response_case;before=snapshot(dsn,original);op=operation(dsn,original)
 receipt=apply(dsn,permit,SubmissionResult(state,ref),selected);after=snapshot(dsn,original)
 assert receipt.state=='unknown' and receipt.event_id is None and after['original'][0][8:10]==('unknown',ref) and after['events']==[]
 assert operation(dsn,original)==('unknown_acceptance',ref,*op[2:]);retained(before,after)

@pytest.mark.parametrize('fault',['account','provider','workspace','scope','contract'])
def test_delivery_response_cannot_replace_original_retained_authority(response_case,fault):
 client,dsn,args,auth,original,execution,permit,selected=response_case;before=snapshot(dsn,original)
 changes={'account':dict(account_reference='another-account'),'provider':dict(provider_name='another-provider'),'workspace':dict(workspace_id=uuid.UUID(WORKSPACE_B)),'scope':dict(scope_hash='c'*64),'contract':dict(reviewed_contract_hash='c'*64)}
 with pytest.raises(ApiError) as error:apply(dsn,permit,SubmissionResult('accepted','original-ref'),replace(selected,**changes[fault]))
 assert (error.value.status_code,error.value.code)==(409,'RETRY_UNSAFE') and snapshot(dsn,original)==before
 assert apply(dsn,permit,SubmissionResult('accepted','original-ref'),selected).state=='accepted'

def test_delivery_response_foreign_tenant_denial_has_matching_owned_positive_control(response_case):
 client,dsn,args,auth,original,execution,permit,selected=response_case;before=snapshot(dsn,original)
 with pytest.raises(ApiError) as error:apply(dsn,permit,SubmissionResult('accepted','original-ref'),selected,workspace=uuid.UUID(WORKSPACE_B))
 assert (error.value.status_code,error.value.code)==(404,'NOT_FOUND') and snapshot(dsn,original)==before
 assert apply(dsn,permit,SubmissionResult('accepted','original-ref'),selected).state=='accepted'

def test_delivery_response_initial_claim_without_committed_post_permit_cannot_bind_acceptance(submission_case):
 from buyeros_api.services.delivery_post import DeliveryPostPermit
 client,dsn,args,auth,original,execution=submission_case;claimed=initial_claim(dsn,execution,auth);before=snapshot(dsn,original)
 with pytest.raises(ApiError) as error:apply(dsn,DeliveryPostPermit(claimed,claimed.prepared),SubmissionResult('accepted','invented-ref'),authority(args,auth))
 assert (error.value.status_code,error.value.code)==(409,'RETRY_UNSAFE') and snapshot(dsn,original)==before

@pytest.mark.parametrize('fault',['untyped','mutated'])
def test_delivery_response_malformed_observation_refuses_before_database_IO(response_case,fault):
 client,dsn,args,auth,original,execution,permit,selected=response_case;before=snapshot(dsn,original);result=SubmissionResult('accepted','original-ref')
 if fault=='untyped':result={}
 else:object.__setattr__(result,'provider_ref',None)
 with pytest.raises(ApiError) as error:asyncio.run(module().record_delivery_submission(DenySession(),permit=permit,result=result,authority=selected))
 assert (error.value.status_code,error.value.code)==(422,'INVALID_REQUEST') and snapshot(dsn,original)==before

@pytest.mark.parametrize('fault',['liability','hold','operation-ref','outbox'])
def test_delivery_response_requires_exact_original_money_and_metadata(response_case,fault):
 client,dsn,args,auth,original,execution,permit,selected=response_case
 with psycopg.connect(dsn) as db:
  if fault=='liability':db.execute('DELETE FROM delivery_liabilities WHERE message_id=%s',(original.message_id,))
  elif fault=='hold':db.execute('UPDATE budget_reservations SET remaining_hold=0 WHERE id=%s',(original.reservation_id,))
  elif fault=='operation-ref':db.execute("UPDATE provider_operations SET provider_ref='other-ref' WHERE id=%s",(original.operation_id,))
  else:db.execute("UPDATE outbox_events SET payload=jsonb_set(payload,'{scope_hash}',to_jsonb(%s::text)) WHERE id=%s",('c'*64,original.outbox_id))
 before=snapshot(dsn,original)
 with pytest.raises(ApiError) as error:apply(dsn,permit,SubmissionResult('accepted','original-ref'),selected)
 assert (error.value.status_code,error.value.code)==(409,'RETRY_UNSAFE') and snapshot(dsn,original)==before

def test_delivery_response_caller_abort_rolls_back_reference_and_local_receipt(response_case):
 client,dsn,args,auth,original,execution,permit,selected=response_case;before=snapshot(dsn,original)
 with pytest.raises(RuntimeError,match='owned response caller abort'):apply(dsn,permit,SubmissionResult('accepted','original-ref'),selected,abort=True)
 assert snapshot(dsn,original)==before

def test_delivery_response_authority_expiry_after_writes_rolls_back_even_outer_commit(response_case,monkeypatch):
 client,dsn,args,auth,original,execution,permit,selected=response_case;before=snapshot(dsn,original);check=module()._require_status_authority;calls=[]
 def expired(value):
  check(value);calls.append(1)
  if len(calls)==2:raise ApiError(503,'PROVIDER_UNAVAILABLE','owned result expiry after writes')
 monkeypatch.setattr(module(),'_require_status_authority',expired)
 assert apply(dsn,permit,SubmissionResult('accepted','original-ref'),selected,catch=True) is None and len(calls)==2 and snapshot(dsn,original)==before

def test_delivery_response_twelve_parallel_original_results_persist_one_local_acceptance_receipt(response_case):
 client,dsn,args,auth,original,execution,permit,selected=response_case;money=counts(dsn)
 async def race():
  engine=create_async_engine(async_database_url(worker_dsn(dsn)),pool_size=12,max_overflow=0)
  try:
   async def one():
    async with tenant_session(engine,args['workspace_id']) as session:return await module().record_delivery_submission(session,permit=permit,result=SubmissionResult('accepted','original-ref'),authority=selected)
   return await asyncio.gather(*(one() for _ in range(12)))
  finally:await engine.dispose()
 results=asyncio.run(race())
 assert len({x.event_id for x in results})==1 and sum(not x.replayed for x in results)==1 and sum(x.replayed for x in results)==11
 assert snapshot(dsn,original)['original'][0][8:10]==('accepted','original-ref') and counts(dsn)==money

def test_delivery_response_retained_authority_persists_after_role_flags_and_worker_lease_revoked(response_case,monkeypatch):
 client,dsn,args,auth,original,execution,permit,selected=response_case;dispatch_flags(monkeypatch,paid=False,delivery=False,cloudflare=False)
 with psycopg.connect(dsn) as db:
  db.execute('UPDATE memberships SET active=false,version=version+1 WHERE workspace_id=%s AND user_id=%s',(args['workspace_id'],args['actor_id']))
  db.execute('UPDATE worker_runtime_control SET enabled=false,epoch=epoch+1 WHERE singleton=1')
  db.execute("UPDATE worker_steps SET expires_at=now()-interval '1 second' WHERE outbox_id=%s",(original.outbox_id,))
 before=snapshot(dsn,original)
 assert apply(dsn,permit,SubmissionResult('accepted','original-ref'),selected).state=='accepted';retained(before,snapshot(dsn,original))

@pytest.mark.parametrize('state',['accepted','unknown'])
def test_delivery_response_cannot_replace_a_known_original_reference(response_case,state):
 client,dsn,args,auth,original,execution,permit,selected=response_case;apply(dsn,permit,SubmissionResult('accepted','original-ref'),selected);before=snapshot(dsn,original)
 with pytest.raises(ApiError) as error:apply(dsn,permit,SubmissionResult(state,'other-ref'),selected)
 assert (error.value.status_code,error.value.code)==(409,'IDEMPOTENCY_CONFLICT') and snapshot(dsn,original)==before

def test_delivery_response_late_unknown_rejection_and_acceptance_never_regress_delivered_or_drop_ref(response_case):
 from buyeros_api.providers.delivery import DeliveryStatusResult
 client,dsn,args,auth,original,execution,permit,selected=response_case;apply(dsn,permit,SubmissionResult('accepted','original-ref'),selected)
 observe(dsn,original.message_id,DeliveryStatusResult('delivered','original-ref'),selected);before=snapshot(dsn,original)
 for result in (SubmissionResult('unknown',None),SubmissionResult('rejected',None),SubmissionResult('accepted','original-ref')):
  receipt=apply(dsn,permit,result,selected);assert receipt.state=='delivered' and receipt.provider_ref=='original-ref'
 assert snapshot(dsn,original)==before

@pytest.mark.parametrize('fault',['message','operation','reservation','outbox','key','digest'])
def test_delivery_response_cannot_rebind_original_permit_or_payload_digest(response_case,fault):
 client,dsn,args,auth,original,execution,permit,selected=response_case;before=snapshot(dsn,original)
 if fault in {'message','operation','reservation','outbox'}:bad=replace(permit,claim=replace(permit.claim,**{fault+'_id':uuid.uuid4()}))
 else:
  intent=replace(permit.prepared.intent,**({'key':'other-key'} if fault=='key' else {'payload_digest':'c'*64}))
  prepared=replace(permit.prepared,intent=intent);bad=replace(permit,claim=replace(permit.claim,prepared=prepared),prepared=prepared)
 with pytest.raises(ApiError) as error:apply(dsn,bad,SubmissionResult('accepted','original-ref'),selected)
 assert (error.value.status_code,error.value.code)==((404,'NOT_FOUND') if fault=='message' else (409,'RETRY_UNSAFE')) and snapshot(dsn,original)==before
 assert apply(dsn,permit,SubmissionResult('accepted','original-ref'),selected).state=='accepted'


def test_delivery_response_original_reference_joins_signed_callback_and_status_without_releasing_hold(response_case):
 from tests.test_delivery_callbacks_db import signed,endpoint,apply as callback
 from buyeros_api.providers.delivery import DeliveryStatusResult
 client,dsn,args,auth,original,execution,permit,selected=response_case;ref=str(uuid.uuid4());before=snapshot(dsn,original)
 apply(dsn,permit,SubmissionResult('accepted',ref),selected)
 data={'dsn':dsn,'message':original.message_id,'operation':original.operation_id,'reservation':original.reservation_id,'args':args}
 target=replace(endpoint(data),account_reference=auth.account_reference,reviewed_contract_hash=auth.reviewed_contract_hash)
 raw,headers=signed(ref,'email.delivered');first=callback(data,raw,headers,target);second=callback(data,raw,headers,target)
 observed=observe(dsn,original.message_id,DeliveryStatusResult('accepted',ref),selected)
 late=apply(dsn,permit,SubmissionResult('accepted',ref),selected);after=snapshot(dsn,original)
 assert first.event_id==second.event_id and second.replayed and first.state==observed.state==late.state=='delivered'
 assert after['original'][0][8:10]==('delivered',ref) and len(after['events'])==3 and len({event[1] for event in after['events']})==3
 assert any(event[1].startswith('submission:') for event in after['events']) and any(event[1].startswith('status:') for event in after['events']) and any(event[1]==headers['svix-id'] for event in after['events'])
 retained(before,after)
