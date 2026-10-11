"""Owned PG50 typed status observations; no network or vendor account selected."""
import asyncio,importlib,uuid
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
import psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.api.errors import ApiError
from buyeros_api.db.session import tenant_session
from buyeros_api.providers.delivery import DeliveryStatusResult
from tests.conftest import runtime_role_dsn
from tests.test_delivery_admission_db import admission_case,run as admit,snapshot as admission_snapshot
from tests.test_lookup_quotes_db import WORKSPACE_A
from tests.test_api_tenant_isolation import WORKSPACE_B
from tests.test_delivery_ledger_db import tenant

def module():
 path=Path(__file__).resolve().parents[1]/'buyeros_api/services/delivery_status.py'
 assert path.is_file(),'durable original delivery status service missing'
 return importlib.import_module('buyeros_api.services.delivery_status')

class DenySession:
 def __getattr__(self,name):raise AssertionError('status refusal must precede all database/provider I/O: '+name)

def authority(args,auth):
 return module().DeliveryStatusAuthority(workspace_id=args['workspace_id'],provider_name=auth.provider_name,account_reference=auth.account_reference,scope_hash=auth.scope_hash,reviewed_contract_hash=auth.reviewed_contract_hash,reviewed=True,valid_until=datetime.now(timezone.utc)+timedelta(hours=1))

def test_status_default_refuses_before_database_or_provider_IO():
 with pytest.raises(ApiError) as error:asyncio.run(module().record_delivery_status(DenySession(),message_id=uuid.uuid4(),result=DeliveryStatusResult('unknown','original-ref')))
 assert (error.value.status_code,error.value.code)==(503,'PROVIDER_UNAVAILABLE')

def submitted(dsn,result,*,state='unknown',ref='original-ref'):
 with tenant(dsn,WORKSPACE_A) as db:
  db.execute("UPDATE delivery_messages SET state='submitting' WHERE id=%s",(result.message_id,))
  db.execute('UPDATE delivery_messages SET state=%s,provider_ref=%s WHERE id=%s',(state,ref,result.message_id))
 with psycopg.connect(dsn) as db:db.execute("UPDATE provider_operations SET status='unknown',provider_ref=%s WHERE id=%s",(ref,result.operation_id))

def snapshot(dsn,admission):
 with psycopg.connect(dsn) as db:
  return {'original':admission_snapshot(dsn,admission),'events':db.execute('SELECT id,external_event_id,state,provider_ref,body_digest FROM delivery_events WHERE message_id=%s ORDER BY created_at,id',(admission.message_id,)).fetchall(),'operation':db.execute('SELECT status,provider_ref FROM provider_operations WHERE id=%s',(admission.operation_id,)).fetchone(),'cost':db.execute('SELECT count(*) FROM cost_events WHERE operation_id=%s',(admission.operation_id,)).fetchone()[0],'suppression':db.execute('SELECT count(*) FROM suppressions WHERE workspace_id=%s AND active',(WORKSPACE_A,)).fetchone()[0]}

def apply(dsn,message_id,result,auth,*,workspace=WORKSPACE_A,abort=False,catch=False):
 async def one():
  engine=create_async_engine(async_database_url(runtime_role_dsn(dsn)))
  try:
   async with tenant_session(engine,uuid.UUID(str(workspace))) as session:
    try:receipt=await module().record_delivery_status(session,message_id=message_id,result=result,authority=auth)
    except ApiError:
     if not catch:raise
     receipt=None
    if abort:raise RuntimeError('owned status caller abort')
    return receipt
  finally:await engine.dispose()
 return asyncio.run(one())

def assert_originals_retained(before,after):
 # State may advance, every canonical key/ref and economic field stays exact.
 assert before['original'][0][:8]==after['original'][0][:8]
 assert before['original'][0][9:]==after['original'][0][9:]
 assert before['original'][1:]==after['original'][1:]
 assert before['operation']==after['operation'] and before['cost']==after['cost']==0

def test_status_original_unknown_once_acceptance_is_distinct_from_delivery_and_never_resends(admission_case):
 client,dsn,args,auth=admission_case;original=admit(dsn,args,auth);submitted(dsn,original);selected=authority(args,auth);before=snapshot(dsn,original)
 unknown=apply(dsn,original.message_id,DeliveryStatusResult('unknown','original-ref'),selected)
 assert unknown.state=='unknown' and unknown.event_id is None and snapshot(dsn,original)==before
 accepted=DeliveryStatusResult('accepted','original-ref','observed_accepted')
 first=apply(dsn,original.message_id,accepted,selected);second=apply(dsn,original.message_id,accepted,selected)
 middle=snapshot(dsn,original);assert first.event_id==second.event_id and first.replayed is False and second.replayed is True
 assert first.state==second.state=='accepted' and middle['original'][0][8]=='accepted' and len(middle['events'])==1
 final=apply(dsn,original.message_id,DeliveryStatusResult('delivered','original-ref'),selected)
 late=apply(dsn,original.message_id,accepted,selected);after=snapshot(dsn,original)
 assert final.state==late.state=='delivered' and len(after['events'])==2
 assert all(e[1].startswith('status:') for e in after['events'])
 assert_originals_retained(before,after)

@pytest.mark.parametrize('fault',['account','provider','workspace','scope','contract','ref'])
def test_status_wrong_original_scope_has_exact_denial_and_no_state_or_hold_change(admission_case,fault):
 client,dsn,args,auth=admission_case;original=admit(dsn,args,auth);submitted(dsn,original);selected=authority(args,auth);before=snapshot(dsn,original);observation=DeliveryStatusResult('accepted','original-ref')
 if fault=='account':selected=replace(selected,account_reference='other-account')
 elif fault=='provider':selected=replace(selected,provider_name='other-provider')
 elif fault=='workspace':selected=replace(selected,workspace_id=uuid.UUID(WORKSPACE_B))
 elif fault=='scope':selected=replace(selected,scope_hash='c'*64)
 elif fault=='contract':selected=replace(selected,reviewed_contract_hash='c'*64)
 else:observation=DeliveryStatusResult('accepted','other-ref')
 with pytest.raises(ApiError) as error:apply(dsn,original.message_id,observation,selected)
 assert (error.value.status_code,error.value.code)==((404,'NOT_FOUND') if fault in {'account','provider','workspace'} else (409,'RETRY_UNSAFE'))
 assert snapshot(dsn,original)==before
 good=apply(dsn,original.message_id,DeliveryStatusResult('accepted','original-ref'),authority(args,auth));assert good.state=='accepted'

def test_status_foreign_tenant_denial_has_matching_owned_positive_control(admission_case):
 client,dsn,args,auth=admission_case;original=admit(dsn,args,auth);submitted(dsn,original);selected=authority(args,auth);before=snapshot(dsn,original)
 with pytest.raises(ApiError) as error:apply(dsn,original.message_id,DeliveryStatusResult('accepted','original-ref'),selected,workspace=WORKSPACE_B)
 assert (error.value.status_code,error.value.code)==(404,'NOT_FOUND') and snapshot(dsn,original)==before
 assert apply(dsn,original.message_id,DeliveryStatusResult('accepted','original-ref'),selected).state=='accepted'

def test_status_prepared_message_without_original_submit_reference_cannot_be_promoted(admission_case):
 client,dsn,args,auth=admission_case;original=admit(dsn,args,auth);before=snapshot(dsn,original)
 with pytest.raises(ApiError) as error:apply(dsn,original.message_id,DeliveryStatusResult('accepted','invented-ref'),authority(args,auth))
 assert (error.value.status_code,error.value.code)==(409,'RETRY_UNSAFE') and snapshot(dsn,original)==before

@pytest.mark.parametrize('fault',['unreviewed','expired','untyped'])
def test_status_unavailable_authority_refuses_before_IO(fault):
 selected=module().DeliveryStatusAuthority(workspace_id=uuid.uuid4(),provider_name='resend',account_reference='original-account',scope_hash='a'*64,reviewed_contract_hash='b'*64,reviewed=True,valid_until=datetime.now(timezone.utc)+timedelta(hours=1))
 if fault=='unreviewed':selected=replace(selected,reviewed=False)
 elif fault=='expired':selected=replace(selected,valid_until=datetime.now(timezone.utc)-timedelta(seconds=1))
 else:selected={}
 with pytest.raises(ApiError) as error:asyncio.run(module().record_delivery_status(DenySession(),message_id=uuid.uuid4(),result=DeliveryStatusResult('accepted','original-ref'),authority=selected))
 assert (error.value.status_code,error.value.code)==(503,'PROVIDER_UNAVAILABLE')

@pytest.mark.parametrize('fault',['untyped-result','mutated-result','nil-message','untyped-message'])
def test_status_malformed_observation_refuses_before_IO(fault):
 selected=module().DeliveryStatusAuthority(workspace_id=uuid.uuid4(),provider_name='resend',account_reference='original-account',scope_hash='a'*64,reviewed_contract_hash='b'*64,reviewed=True,valid_until=datetime.now(timezone.utc)+timedelta(hours=1));message_id=uuid.uuid4();observation=DeliveryStatusResult('accepted','original-ref')
 if fault=='untyped-result':observation={}
 elif fault=='mutated-result':object.__setattr__(observation,'state','prepared')
 elif fault=='nil-message':message_id=uuid.UUID(int=0)
 else:message_id='caller-string'
 with pytest.raises(ApiError) as error:asyncio.run(module().record_delivery_status(DenySession(),message_id=message_id,result=observation,authority=selected))
 assert (error.value.status_code,error.value.code)==(422,'INVALID_REQUEST')

@pytest.mark.parametrize('state',['bounced','complained','unsubscribed'])
def test_status_adverse_observation_deduplicates_suppression_and_retains_original_full_hold(admission_case,state):
 client,dsn,args,auth=admission_case;original=admit(dsn,args,auth);submitted(dsn,original);selected=authority(args,auth);before=snapshot(dsn,original);observation=DeliveryStatusResult(state,'original-ref')
 first=apply(dsn,original.message_id,observation,selected);second=apply(dsn,original.message_id,observation,selected);after=snapshot(dsn,original)
 assert first.event_id==second.event_id and second.replayed is True and after['original'][0][8]==state and len(after['events'])==1 and after['suppression']==before['suppression']+1
 assert_originals_retained(before,after)
 with psycopg.connect(dsn) as db:assert db.execute('SELECT invalidated_reason FROM approvals WHERE id=%s',(args['approval_id'],)).fetchone()[0]=='delivery_adverse_event'

def test_status_caller_abort_rolls_back_observation_suppression_and_approval(admission_case):
 client,dsn,args,auth=admission_case;original=admit(dsn,args,auth);submitted(dsn,original);before=snapshot(dsn,original)
 with pytest.raises(RuntimeError,match='owned status caller abort'):apply(dsn,original.message_id,DeliveryStatusResult('bounced','original-ref'),authority(args,auth),abort=True)
 assert snapshot(dsn,original)==before
 with psycopg.connect(dsn) as db:assert db.execute('SELECT invalidated_reason FROM approvals WHERE id=%s',(args['approval_id'],)).fetchone()[0] is None

def test_status_expiry_after_writes_rolls_back_even_when_outer_caller_commits(admission_case,monkeypatch):
 client,dsn,args,auth=admission_case;original=admit(dsn,args,auth);submitted(dsn,original);before=snapshot(dsn,original);selected=authority(args,auth);check=module()._require_status_authority;calls=[]
 def expired(value):
  check(value);calls.append(1)
  if len(calls)==2:raise ApiError(503,'PROVIDER_UNAVAILABLE','owned expiry after actual writes')
 monkeypatch.setattr(module(),'_require_status_authority',expired)
 assert apply(dsn,original.message_id,DeliveryStatusResult('bounced','original-ref'),selected,catch=True) is None
 assert len(calls)==2 and snapshot(dsn,original)==before

def test_status_twelve_parallel_observations_commit_one_event_without_extra_cost(admission_case):
 client,dsn,args,auth=admission_case;original=admit(dsn,args,auth);submitted(dsn,original);before=snapshot(dsn,original);selected=authority(args,auth)
 async def race():
  engine=create_async_engine(async_database_url(runtime_role_dsn(dsn)),pool_size=12,max_overflow=0)
  try:
   async def one():
    async with tenant_session(engine,args['workspace_id']) as session:return await module().record_delivery_status(session,message_id=original.message_id,result=DeliveryStatusResult('accepted','original-ref'),authority=selected)
   return await asyncio.gather(*(one() for _ in range(12)))
  finally:await engine.dispose()
 results=asyncio.run(race());after=snapshot(dsn,original)
 assert len({x.event_id for x in results})==1 and sum(not x.replayed for x in results)==1 and len(after['events'])==1
 assert_originals_retained(before,after)

def test_status_reconciliation_survives_new_admission_role_and_approval_revocation(admission_case):
 client,dsn,args,auth=admission_case;original=admit(dsn,args,auth);submitted(dsn,original);before=snapshot(dsn,original)
 with psycopg.connect(dsn) as db:
  db.execute("UPDATE approvals SET invalidated_reason='owned-revocation',invalidated_at=now() WHERE id=%s",(args['approval_id'],))
  db.execute("UPDATE memberships SET active=false,version=version+1 WHERE workspace_id=%s AND user_id=%s",(args['workspace_id'],args['actor_id']))
 with pytest.raises(ApiError):admit(dsn,args,auth)
 receipt=apply(dsn,original.message_id,DeliveryStatusResult('accepted','original-ref'),authority(args,auth));assert receipt.state=='accepted'
 assert_originals_retained(before,snapshot(dsn,original))

@pytest.mark.parametrize('fault',['liability','operation-ref','hold'])
def test_status_missing_or_changed_original_liability_never_invents_receipts_or_releases_hold(admission_case,fault):
 client,dsn,args,auth=admission_case;original=admit(dsn,args,auth);submitted(dsn,original)
 with psycopg.connect(dsn) as db:
  if fault=='liability':db.execute('DELETE FROM delivery_liabilities WHERE message_id=%s',(original.message_id,))
  elif fault=='operation-ref':db.execute("UPDATE provider_operations SET provider_ref='different-ref' WHERE id=%s",(original.operation_id,))
  else:db.execute('UPDATE budget_reservations SET remaining_hold=0 WHERE id=%s',(original.reservation_id,))
 before=snapshot(dsn,original)
 with pytest.raises(ApiError) as error:apply(dsn,original.message_id,DeliveryStatusResult('accepted','original-ref'),authority(args,auth))
 assert (error.value.status_code,error.value.code)==(409,'RETRY_UNSAFE') and snapshot(dsn,original)==before
