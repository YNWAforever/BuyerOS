"""Signed callback transaction on original retained delivery rows; no public route."""
import asyncio,base64,hashlib,hmac,importlib,json,time,uuid
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
import psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.api.errors import ApiError
from buyeros_api.db.session import tenant_session
from tests.conftest import runtime_role_dsn
from tests.test_api_projects_db import api
from tests.test_lookup_quotes_db import quote_case,WORKSPACE_A,_h,REVIEWER
from tests.test_delivery_ledger_db import ledger_case,tenant

SECRET='whsec_'+base64.b64encode(b'owned-callback-fixture-key-32byte!').decode()

def module():
    p=Path(__file__).resolve().parents[1]/'buyeros_api/services/delivery_callbacks.py'
    assert p.is_file(),'signed independent delivery callback transaction is missing'
    return importlib.import_module('buyeros_api.services.delivery_callbacks')

def endpoint(data):
    return module().DeliveryWebhookEndpoint(workspace_id=uuid.UUID(WORKSPACE_A),account_reference='owned-fake-account',reviewed_contract_hash='b'*64,signing_secret=SECRET,reviewed=True,valid_until=datetime.now(timezone.utc)+timedelta(hours=1))

def submitted(data,*,state='unknown',ref=None):
    ref=ref or str(uuid.uuid4())
    with tenant(data['dsn'],WORKSPACE_A) as db:
        db.execute("UPDATE delivery_messages SET state='submitting' WHERE id=%s",(data['message'],))
        db.execute('UPDATE delivery_messages SET state=%s,provider_ref=%s WHERE id=%s',(state,ref,data['message']))
    with psycopg.connect(data['dsn'],autocommit=True) as db:db.execute("UPDATE provider_operations SET status='unknown' WHERE id=%s",(data['operation'],))
    return ref

def signed(ref,event='email.sent',event_id=None,*,payload=None):
    event_id=event_id or 'evt_'+uuid.uuid4().hex
    value=payload or {'type':event,'created_at':datetime.now(timezone.utc).isoformat(),'data':{'email_id':ref,'from':'ignored@example.test','to':['ignored@example.test'],'subject':'not copied','workspace_id':str(uuid.uuid4()),'account_reference':'caller-cannot-select'}}
    raw=json.dumps(value,separators=(',',':')).encode();stamp=str(int(time.time()))
    signature=base64.b64encode(hmac.digest(base64.b64decode(SECRET[6:]),event_id.encode()+b'.'+stamp.encode()+b'.'+raw,'sha256')).decode()
    return raw,{'svix-id':event_id,'svix-timestamp':stamp,'svix-signature':'v1,'+signature}

def apply(data,raw,headers,authority,*,workspace=None,abort=False):
    async def one():
        engine=create_async_engine(async_database_url(runtime_role_dsn(data['dsn'])))
        try:
            async with tenant_session(engine,uuid.UUID(workspace or WORKSPACE_A)) as session:
                result=await module().record_resend_delivery_webhook(session,raw,headers,endpoint=authority)
                if abort:raise RuntimeError('owned caller abort callback')
                return result
        finally:await engine.dispose()
    return asyncio.run(one())

def snapshot(data):
    with psycopg.connect(data['dsn']) as db:
        return {'state':db.execute('SELECT state,provider_ref FROM delivery_messages WHERE id=%s',(data['message'],)).fetchone(),'events':db.execute('SELECT external_event_id,state,body_digest FROM delivery_events WHERE message_id=%s ORDER BY created_at,id',(data['message'],)).fetchall(),'hold':db.execute('SELECT remaining_hold,state FROM budget_reservations WHERE id=%s',(data['reservation'],)).fetchone(),'cost':db.execute('SELECT count(*) FROM cost_events WHERE operation_id=%s',(data['operation'],)).fetchone()[0],'outbox':db.execute('SELECT count(*) FROM outbox_events WHERE workspace_id=%s',(WORKSPACE_A,)).fetchone()[0],'suppression':db.execute("SELECT count(*) FROM suppressions WHERE workspace_id=%s AND subject_id=%s AND active",(WORKSPACE_A,data['args']['recipient_ref'])).fetchone()[0]}

def test_delivery_callback_same_signed_intent_once_preserves_original_unknown_hold(quote_case):
    module()
    with ledger_case(quote_case) as data:
        ref=submitted(data);auth=endpoint(data);raw,headers=signed(ref);before=snapshot(data)
        first=apply(data,raw,headers,auth);second=apply(data,raw,headers,auth);after=snapshot(data)
        assert first.message_id==second.message_id==data['message'] and first.event_id==second.event_id
        assert first.replayed is False and second.replayed is True and after['state']==('accepted',ref)
        assert len(after['events'])==1 and after['events'][0]==(headers['svix-id'],'accepted',hashlib.sha256(raw).hexdigest())
        assert after['hold']==before['hold']==(Decimal('0.010000'),'active') and after['cost']==before['cost']==0 and after['outbox']==before['outbox']
        disabled=data['client'].post(f"/v1/workspaces/{WORKSPACE_A}/drafts/{data['args']['draft_id']}/deliver",headers=_h(REVIEWER,key='callback-keeps-disabled'))
        assert disabled.status_code==403 and disabled.json()['code']=='DELIVERY_DISABLED'

def test_delivery_callback_bounce_duplicate_and_late_acceptance_keep_independent_suppression(quote_case):
    module()
    with ledger_case(quote_case) as data:
        ref=submitted(data);auth=endpoint(data);raw,headers=signed(ref,'email.bounced');before=snapshot(data)
        first=apply(data,raw,headers,auth);second=apply(data,raw,headers,auth)
        late,h=signed(ref,'email.sent');apply(data,late,h,auth);after=snapshot(data)
        assert first.event_id==second.event_id and second.replayed is True
        assert after['state']==('bounced',ref) and len(after['events'])==2 and after['suppression']==before['suppression']+1
        assert after['hold']==before['hold']==(Decimal('0.010000'),'active') and after['cost']==0 and after['outbox']==before['outbox']
        with psycopg.connect(data['dsn']) as db:
            row=db.execute("SELECT subject_type,subject_id,controller_scope_id,purposes,source_reference,actor_id FROM suppressions WHERE workspace_id=%s AND subject_id=%s AND active",(WORKSPACE_A,data['args']['recipient_ref'])).fetchone()
            assert row[0]=='contact_point' and row[1]==data['args']['recipient_ref'] and row[2]==uuid.UUID(WORKSPACE_A) and 'outreach' in row[3] and row[4]=='delivery-event:'+str(first.event_id) and row[5]==data['args']['actor_id']

def signed_raw(raw,event_id=None,stamp=None):
    event_id=event_id or 'evt_'+uuid.uuid4().hex;stamp=str(int(time.time())) if stamp is None else str(stamp)
    signature=base64.b64encode(hmac.digest(base64.b64decode(SECRET[6:]),event_id.encode()+b'.'+stamp.encode()+b'.'+raw,'sha256')).decode()
    return raw,{'svix-id':event_id,'svix-timestamp':stamp,'svix-signature':'v1,'+signature}

@pytest.mark.parametrize('fault',['tampered-body','forged-signature','past-window','future-window','wrong-key'])
def test_delivery_callback_invalid_signature_or_attempt_time_never_writes(quote_case,fault):
    module()
    with ledger_case(quote_case) as data:
        ref=submitted(data);auth=endpoint(data);raw,h=signed(ref);before=snapshot(data)
        if fault=='tampered-body':raw+=b' '
        elif fault=='forged-signature':h={**h,'svix-signature':'v1,'+base64.b64encode(b'0'*32).decode()}
        elif fault in ('past-window','future-window'):raw,h=signed_raw(raw,stamp=int(time.time())+(-301 if fault=='past-window' else 601))
        else:auth=replace(auth,signing_secret='whsec_'+base64.b64encode(b'other-owned-32-byte-fixture-key!!').decode())
        with pytest.raises(ApiError) as error:apply(data,raw,h,auth)
        assert (error.value.status_code,error.value.code)==(403,'PERMISSION_DENIED') and snapshot(data)==before

@pytest.mark.parametrize('fault',['missing','unreviewed','expired','account','workspace'])
def test_delivery_callback_endpoint_is_server_owned_and_fail_closed(quote_case,fault):
    from tests.test_api_tenant_isolation import WORKSPACE_B
    module()
    with ledger_case(quote_case) as data:
        ref=submitted(data);auth=endpoint(data);raw,h=signed(ref);before=snapshot(data)
        if fault=='missing':auth=None
        elif fault=='unreviewed':auth=replace(auth,reviewed=False)
        elif fault=='expired':auth=replace(auth,valid_until=datetime.now(timezone.utc)-timedelta(seconds=1))
        elif fault=='account':auth=replace(auth,account_reference='another-original-account')
        else:auth=replace(auth,workspace_id=uuid.UUID(WORKSPACE_B))
        with pytest.raises(ApiError) as error:apply(data,raw,h,auth)
        assert (error.value.status_code,error.value.code)==((503,'PROVIDER_UNAVAILABLE') if fault in ('missing','unreviewed','expired') else (404,'NOT_FOUND')) and snapshot(data)==before

@pytest.mark.parametrize('fault',['json','duplicate-type','unknown-event','unsubscribed-not-documented','nil-ref','naive-time','missing-ref'])
def test_delivery_callback_signed_unsupported_metadata_never_invents_a_state(quote_case,fault):
    module()
    with ledger_case(quote_case) as data:
        ref=submitted(data);auth=endpoint(data);before=snapshot(data)
        value={'type':'email.sent','created_at':datetime.now(timezone.utc).isoformat(),'data':{'email_id':ref}}
        if fault=='unknown-event':value['type']='email.opened'
        elif fault=='unsubscribed-not-documented':value['type']='email.unsubscribed'
        elif fault=='nil-ref':value['data']['email_id']=str(uuid.UUID(int=0))
        elif fault=='naive-time':value['created_at']='2026-10-09T02:00:00'
        elif fault=='missing-ref':value['data']={}
        raw=json.dumps(value,separators=(',',':')).encode()
        if fault=='json':raw=b'{'
        elif fault=='duplicate-type':raw=raw.replace(b'"type":"email.sent"',b'"type":"email.delivered","type":"email.sent"')
        raw,h=signed_raw(raw)
        with pytest.raises(ApiError) as error:apply(data,raw,h,auth)
        assert (error.value.status_code,error.value.code)==(422,'INVALID_REQUEST') and snapshot(data)==before

@pytest.mark.parametrize('fault',['different-state','different-bytes'])
def test_delivery_callback_same_external_identity_cannot_change_authenticated_body(quote_case,fault):
    module()
    with ledger_case(quote_case) as data:
        ref=submitted(data);auth=endpoint(data);raw,h=signed(ref);apply(data,raw,h,auth);before=snapshot(data)
        changed=raw.replace(b'email.sent',b'email.delivered') if fault=='different-state' else raw+b' '
        changed,h=signed_raw(changed,event_id=h['svix-id'])
        with pytest.raises(ApiError) as error:apply(data,changed,h,auth)
        assert (error.value.status_code,error.value.code)==(409,'IDEMPOTENCY_CONFLICT') and snapshot(data)==before

@pytest.mark.parametrize('event,expected,adverse',[('email.sent','accepted',False),('email.delivered','delivered',False),('email.bounced','bounced',True),('email.complained','complained',True),('email.failed','failed',False),('email.suppressed','failed',True)])
def test_delivery_callback_official_event_mapping_retains_financial_hold(quote_case,event,expected,adverse):
    module()
    with ledger_case(quote_case) as data:
        ref=submitted(data);auth=endpoint(data);raw,h=signed(ref,event);before=snapshot(data);receipt=apply(data,raw,h,auth);after=snapshot(data)
        assert receipt.state==expected and after['state']==(expected,ref) and len(after['events'])==1
        assert after['suppression']==before['suppression']+int(adverse) and after['hold']==before['hold']==(Decimal('0.010000'),'active') and after['cost']==0 and after['outbox']==before['outbox']

def test_delivery_callback_twelve_parallel_duplicates_commit_one_event_and_overlay(quote_case):
    target=module()
    with ledger_case(quote_case) as data:
        ref=submitted(data);auth=endpoint(data);raw,h=signed(ref,'email.complained');before=snapshot(data)
        async def race():
            engine=create_async_engine(async_database_url(runtime_role_dsn(data['dsn'])),pool_size=12,max_overflow=0)
            async def one():
                async with tenant_session(engine,uuid.UUID(WORKSPACE_A)) as session:return await target.record_resend_delivery_webhook(session,raw,h,endpoint=auth)
            try:return await asyncio.gather(*(one() for _ in range(12)))
            finally:await engine.dispose()
        receipts=asyncio.run(race());after=snapshot(data)
        assert len(receipts)==12 and len({item.event_id for item in receipts})==1 and sum(not item.replayed for item in receipts)==1
        assert after['state']==('complained',ref) and len(after['events'])==1 and after['suppression']==before['suppression']+1 and after['hold']==before['hold'] and after['cost']==0

def test_delivery_callback_caller_abort_rolls_back_event_state_suppression_and_approval_invalidation(quote_case):
    module()
    with ledger_case(quote_case) as data:
        ref=submitted(data);auth=endpoint(data);raw,h=signed(ref,'email.bounced');before=snapshot(data)
        with psycopg.connect(data['dsn']) as db:
            approval_before=db.execute('SELECT invalidated_at,invalidated_reason FROM approvals WHERE id=%s',(data['args']['approval_id'],)).fetchone()
            contact_before=db.execute('SELECT quarantined FROM contact_points WHERE id=%s',(data['args']['recipient_ref'],)).fetchone()
        with pytest.raises(RuntimeError,match='owned caller abort callback'):apply(data,raw,h,auth,abort=True)
        assert snapshot(data)==before
        with psycopg.connect(data['dsn']) as db:
            assert db.execute('SELECT invalidated_at,invalidated_reason FROM approvals WHERE id=%s',(data['args']['approval_id'],)).fetchone()==approval_before
            assert db.execute('SELECT quarantined FROM contact_points WHERE id=%s',(data['args']['recipient_ref'],)).fetchone()==contact_before

def test_delivery_callback_after_current_policy_revocation_still_records_original_status_only(quote_case):
    module()
    with ledger_case(quote_case) as data:
        ref=submitted(data);auth=endpoint(data);raw,h=signed(ref,'email.delivered');before=snapshot(data)
        with psycopg.connect(data['dsn'],autocommit=True) as db:
            db.execute("UPDATE policy_decisions SET status='blocked',version=version+1 WHERE workspace_id=%s AND purpose='outreach'",(WORKSPACE_A,))
            db.execute("UPDATE approvals SET invalidated_reason='owned revoked before callback',invalidated_at=now() WHERE id=%s",(data['args']['approval_id'],))
        receipt=apply(data,raw,h,auth);after=snapshot(data)
        assert receipt.state=='delivered' and len(after['events'])==1 and after['hold']==before['hold'] and after['cost']==0 and after['outbox']==before['outbox']

def test_delivery_callback_foreign_tenant_denial_has_matching_owned_positive_control(quote_case):
    from tests.test_api_tenant_isolation import WORKSPACE_B
    module()
    with ledger_case(quote_case) as data:
        ref=submitted(data);auth=endpoint(data);raw,h=signed(ref);owned=apply(data,raw,h,auth);before=snapshot(data)
        with pytest.raises(ApiError) as error:apply(data,raw,h,auth,workspace=WORKSPACE_B)
        assert (error.value.status_code,error.value.code,error.value.message)==(404,'NOT_FOUND','original delivery message not found') and snapshot(data)==before
        assert apply(data,raw,h,auth).event_id==owned.event_id

@pytest.mark.parametrize('fault',['no-ref','prepared-with-ref','missing-liability'])
def test_delivery_callback_cannot_create_missing_original_submit_or_liability(quote_case,fault):
    module()
    with ledger_case(quote_case) as data:
        auth=endpoint(data);ref=str(uuid.uuid4())
        if fault=='prepared-with-ref':
            # Existing0048 guard already refuses a ref before submit. Accept that
            # actual protection; no fixture may bypass it to manufacture a row.
            initial=snapshot(data)
            with pytest.raises(psycopg.errors.CheckViolation,match='delivery acceptance requires original provider reference'):
                with tenant(data['dsn'],WORKSPACE_A) as db:db.execute('UPDATE delivery_messages SET provider_ref=%s WHERE id=%s',(ref,data['message']))
            assert snapshot(data)==initial
        elif fault=='missing-liability':
            submitted(data,ref=ref)
            with psycopg.connect(data['dsn'],autocommit=True) as db:db.execute('DELETE FROM delivery_liabilities WHERE id=%s',(data['liability'],))
        before=snapshot(data);raw,h=signed(ref)
        with pytest.raises(ApiError) as error:apply(data,raw,h,auth)
        assert (error.value.status_code,error.value.code)==((404,'NOT_FOUND') if fault in ('no-ref','prepared-with-ref') else (409,'RETRY_UNSAFE')) and snapshot(data)==before

def test_delivery_callback_expired_after_actual_writes_rolls_back_when_outer_caller_catches(quote_case,monkeypatch):
    target=module()
    with ledger_case(quote_case) as data:
        ref=submitted(data);auth=endpoint(data);raw,h=signed(ref,'email.bounced');before=snapshot(data)
        with psycopg.connect(data['dsn']) as db:
            approval_before=db.execute('SELECT invalidated_at,invalidated_reason FROM approvals WHERE id=%s',(data['args']['approval_id'],)).fetchone()
            contact_before=db.execute('SELECT quarantined FROM contact_points WHERE id=%s',(data['args']['recipient_ref'],)).fetchone()
        class ExpiryClock(datetime):
            calls=0
            @classmethod
            def now(cls,tz=None):
                cls.calls+=1
                return datetime.now(timezone.utc) if cls.calls==1 else auth.valid_until+timedelta(seconds=1)
        monkeypatch.setattr(target,'datetime',ExpiryClock)
        async def one():
            engine=create_async_engine(async_database_url(runtime_role_dsn(data['dsn'])))
            try:
                async with tenant_session(engine,uuid.UUID(WORKSPACE_A)) as session:
                    try:
                        await target.record_resend_delivery_webhook(session,raw,h,endpoint=auth)
                        result='ACCEPTED'
                    except ApiError as error:
                        assert error.status_code==503;result=error.code
                    # Outer caller deliberately catches refusal and commits.
                    return result
            finally:await engine.dispose()
        assert asyncio.run(one())=='PROVIDER_UNAVAILABLE' and ExpiryClock.calls==2 and snapshot(data)==before
        with psycopg.connect(data['dsn']) as db:
            assert db.execute('SELECT invalidated_at,invalidated_reason FROM approvals WHERE id=%s',(data['args']['approval_id'],)).fetchone()==approval_before
            assert db.execute('SELECT quarantined FROM contact_points WHERE id=%s',(data['args']['recipient_ref'],)).fetchone()==contact_before

def test_delivery_callback_external_event_cannot_move_to_another_original_message(quote_case):
    module()
    with ledger_case(quote_case) as data:
        other_message,other_operation,other_reservation,other_liability=(uuid.uuid4() for _ in range(4));other_key='delivery:other:'+uuid.uuid4().hex;other_ref=str(uuid.uuid4())
        try:
            # Own an independently bound second original intent; preserve all
            # approval/RLS/operation/liability triggers rather than bypassing.
            with psycopg.connect(data['dsn'],autocommit=True) as db:
                db.execute("INSERT INTO provider_operations(id,workspace_id,intent_key,capability,input_hash,status,provider_name,account_reference) SELECT %s,workspace_id,%s,capability,input_hash,'intent',provider_name,account_reference FROM provider_operations WHERE id=%s",(other_operation,other_key,data['operation']))
                db.execute("INSERT INTO budget_reservations(id,workspace_id,account_id,operation_id,intent_key,price_version,currency,origin_period_start,upper_bound,remaining_hold,state) SELECT %s,workspace_id,account_id,%s,%s,price_version,currency,origin_period_start,upper_bound,remaining_hold,'active' FROM budget_reservations WHERE id=%s",(other_reservation,other_operation,str(other_operation),data['reservation']))
                db.execute("INSERT INTO delivery_messages(id,workspace_id,project_id,draft_id,draft_revision_id,revision_number,recipient_ref,sender_identity_id,approval_id,actor_id,operation_id,intent_key,provider_name,account_reference,payload_digest,state) SELECT %s,workspace_id,project_id,draft_id,draft_revision_id,revision_number,recipient_ref,sender_identity_id,approval_id,actor_id,%s,%s,provider_name,account_reference,payload_digest,'prepared' FROM delivery_messages WHERE id=%s",(other_message,other_operation,other_key,data['message']))
                db.execute("INSERT INTO delivery_liabilities(id,workspace_id,message_id,operation_id,reservation_id,max_liability,currency,pricing_version) SELECT %s,workspace_id,%s,%s,%s,max_liability,currency,pricing_version FROM delivery_liabilities WHERE id=%s",(other_liability,other_message,other_operation,other_reservation,data['liability']))
            other={**data,'message':other_message,'operation':other_operation,'reservation':other_reservation,'liability':other_liability,'key':other_key}
            original_ref=submitted(data);submitted(other,ref=other_ref);auth=endpoint(data);raw,h=signed(original_ref);first=apply(data,raw,h,auth);before=snapshot(data);other_before=snapshot(other)
            moved,headers=signed(other_ref,event_id=h['svix-id'])
            with pytest.raises(ApiError) as error:apply(other,moved,headers,auth)
            assert (error.value.status_code,error.value.code)==(409,'IDEMPOTENCY_CONFLICT') and snapshot(data)==before and snapshot(other)==other_before
            assert apply(data,raw,h,auth).event_id==first.event_id
            own,headers=signed(other_ref);second=apply(other,own,headers,auth)
            assert second.message_id==other_message and second.event_id!=first.event_id and snapshot(other)['hold']==other_before['hold']
        finally:
            with psycopg.connect(data['dsn'],autocommit=True) as db:
                db.execute('DELETE FROM delivery_events WHERE message_id=%s',(other_message,));db.execute('DELETE FROM delivery_liabilities WHERE id=%s',(other_liability,));db.execute('DELETE FROM delivery_messages WHERE id=%s',(other_message,));db.execute('DELETE FROM budget_reservations WHERE id=%s',(other_reservation,));db.execute('DELETE FROM provider_operations WHERE id=%s',(other_operation,))
