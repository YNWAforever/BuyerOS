"""Scoped admin consumer of retained original GET; no actual account/provider send."""
import importlib,uuid
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import psycopg,pytest
from buyeros_api.providers.delivery import DeliveryStatusResult
from tests.test_delivery_admission_db import admission_case,run as admit,counts
from tests.test_delivery_status_db import authority,submitted,snapshot,assert_originals_retained
from tests.test_lookup_quotes_db import ADMIN,OPERATOR,REVIEWER,WORKSPACE_A,_h
from tests.test_api_tenant_isolation import WORKSPACE_B

def module():
    mod=importlib.import_module('buyeros_api.api.routes.delivery')
    assert callable(getattr(mod,'reconcile_message_delivery',None)),'public scoped retained delivery reconciliation consumer missing'
    return mod

def url(case,workspace=WORKSPACE_A,message=None):return f"/v1/workspaces/{workspace}/delivery-messages/{message or case[4].message_id}/reconciliation"

@pytest.fixture
def reconcile_case(admission_case,monkeypatch):
    client,dsn,args,auth=admission_case;original=admit(dsn,args,auth);submitted(dsn,original,ref='original-ref')
    from buyeros_api.settings import get_settings
    monkeypatch.setenv('BUYEROS_RECONCILIATION_ENABLED','true');get_settings.cache_clear()
    try:yield client,dsn,args,auth,original,authority(args,auth)
    finally:get_settings.cache_clear()

def select(monkeypatch,case,*,result=None,hook=None,error=None):
    module();service=importlib.import_module('buyeros_api.services.delivery_reconciliation');calls=[];built=[]
    class Reader:
        async def status(self):
            with psycopg.connect(case[1]) as db:
                assert db.execute('SELECT id FROM delivery_messages WHERE id=%s FOR UPDATE NOWAIT',(case[4].message_id,)).fetchone()
                assert db.execute('SELECT user_id FROM memberships WHERE workspace_id=%s AND user_id=%s FOR UPDATE NOWAIT',(WORKSPACE_A,uuid.uuid5(uuid.NAMESPACE_URL,ADMIN))).fetchone()
            calls.append('original-ref')
            if hook:hook()
            if error:raise error
            return result if result is not None else DeliveryStatusResult('accepted','original-ref')
    def factory(ref):assert ref=='original-ref';built.append(ref);return Reader()
    chosen=service.DeliveryReconciliationSelection(case[-1],factory)
    monkeypatch.setattr(service,'selected_delivery_reconciliation',lambda **bindings:chosen)
    return chosen,calls,built

def test_public_retained_reconciliation_unselected503_and_original_deliver403_have_no_provider_or_ledger_write(reconcile_case):
    case=reconcile_case;before=snapshot(case[1],case[4]);reply=case[0].post(url(case),headers=_h(ADMIN),json={})
    assert (reply.status_code,reply.json()['code'])==(503,'PROVIDER_UNAVAILABLE') and snapshot(case[1],case[4])==before
    old=case[0].post(f"/v1/workspaces/{WORKSPACE_A}/drafts/{case[2]['draft_id']}/deliver",headers=_h(ADMIN));assert (old.status_code,old.json()['code'])==(403,'DELIVERY_DISABLED')

def test_public_retained_reconciliation_gate_off503_before_any_factory_or_GET(reconcile_case,monkeypatch):
    case=reconcile_case;chosen,calls,built=select(monkeypatch,case)
    from buyeros_api.settings import get_settings
    monkeypatch.setenv('BUYEROS_RECONCILIATION_ENABLED','false');get_settings.cache_clear();before=snapshot(case[1],case[4]);reply=case[0].post(url(case),headers=_h(ADMIN),json={})
    assert (reply.status_code,reply.json()['code'])==(503,'CAPABILITY_DISABLED') and calls==built==[] and snapshot(case[1],case[4])==before

def test_public_retained_reconciliation_selected_admin_reads_only_original_metadata_and_deduplicates_event(reconcile_case,monkeypatch):
    case=reconcile_case;chosen,calls,built=select(monkeypatch,case);before=snapshot(case[1],case[4]);money=counts(case[1]);first=case[0].post(url(case),headers=_h(ADMIN),json={});assert first.status_code==200,first.text
    data=first.json()['data'];assert set(data)=={'message_id','state','event_id','replayed'} and data['message_id']==str(case[4].message_id) and data['state']=='accepted' and data['event_id'] and data['replayed'] is False
    assert first.headers['Cache-Control']=='private, no-store' and 'original-ref' not in first.text and case[-1].account_reference not in first.text
    second=case[0].post(url(case),headers=_h(ADMIN));assert second.status_code==200 and second.json()['data']==dict(data,replayed=True) and calls==built==['original-ref','original-ref']
    after=snapshot(case[1],case[4]);assert len(after['events'])==1 and counts(case[1])==money;assert_originals_retained(before,after)

@pytest.mark.parametrize('principal',[OPERATOR,REVIEWER])
def test_public_retained_reconciliation_current_nonadmin_role_denied_before_GET_with_admin_positive_control(reconcile_case,monkeypatch,principal):
    case=reconcile_case;chosen,calls,built=select(monkeypatch,case);before=snapshot(case[1],case[4]);denied=case[0].post(url(case),headers=_h(principal),json={})
    assert (denied.status_code,denied.json()['code'])==(403,'PERMISSION_DENIED') and calls==built==[] and snapshot(case[1],case[4])==before
    owned=case[0].post(url(case),headers=_h(ADMIN),json={});assert owned.status_code==200

def test_public_retained_reconciliation_foreign_workspace404_has_matching_owned_admin_control(reconcile_case,monkeypatch):
    case=reconcile_case;chosen,calls,built=select(monkeypatch,case);before=snapshot(case[1],case[4]);denied=case[0].post(url(case,workspace=WORKSPACE_B),headers=_h(ADMIN),json={})
    assert (denied.status_code,denied.json()['code'])==(404,'NOT_FOUND') and calls==built==[] and snapshot(case[1],case[4])==before
    assert case[0].post(url(case),headers=_h(ADMIN),json={}).status_code==200

def test_public_retained_reconciliation_real_foreign_message404_with_current_foreign_workspace_membership_and_owned200(reconcile_case,monkeypatch):
    case=reconcile_case;chosen,calls,built=select(monkeypatch,case);service=importlib.import_module('buyeros_api.services.delivery_reconciliation')
    with psycopg.connect(case[1]) as db:
        db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES (%s,%s,%s,ARRAY['workspace_admin'],true)",(uuid.uuid4(),WORKSPACE_B,uuid.uuid5(uuid.NAMESPACE_URL,ADMIN)))
        assert db.execute('SELECT workspace_id FROM delivery_messages WHERE id=%s',(case[4].message_id,)).fetchone()==(uuid.UUID(WORKSPACE_A),)
    foreign=replace(chosen,authority=replace(chosen.authority,workspace_id=uuid.UUID(WORKSPACE_B)))
    monkeypatch.setattr(service,'selected_delivery_reconciliation',lambda **bindings:foreign);before=snapshot(case[1],case[4]);denied=case[0].post(url(case,workspace=WORKSPACE_B),headers=_h(ADMIN),json={})
    assert (denied.status_code,denied.json()['code'])==(404,'NOT_FOUND') and calls==built==[] and snapshot(case[1],case[4])==before
    monkeypatch.setattr(service,'selected_delivery_reconciliation',lambda **bindings:chosen);assert case[0].post(url(case),headers=_h(ADMIN),json={}).status_code==200

@pytest.mark.parametrize('field',['body','provider_ref','intent_key','provider','account','scope_hash','authority','amount'])
def test_public_retained_reconciliation_forbids_client_ref_key_scope_body_and_economics_fields(reconcile_case,monkeypatch,field):
    case=reconcile_case;chosen,calls,built=select(monkeypatch,case);before=snapshot(case[1],case[4]);reply=case[0].post(url(case),headers=_h(ADMIN),json={field:'untrusted-client-value'})
    assert (reply.status_code,reply.json()['code'])==(422,'INVALID_REQUEST') and calls==built==[] and snapshot(case[1],case[4])==before

@pytest.mark.parametrize('fault',['unreviewed','expired','scope','contract'])
def test_public_retained_reconciliation_rejects_invalid_server_review_without_factory_or_GET(reconcile_case,monkeypatch,fault):
    case=reconcile_case;chosen,calls,built=select(monkeypatch,case);service=importlib.import_module('buyeros_api.services.delivery_reconciliation')
    changes={'reviewed':False} if fault=='unreviewed' else {'valid_until':datetime.now(timezone.utc)-timedelta(seconds=1)} if fault=='expired' else {'scope_hash':'c'*64} if fault=='scope' else {'reviewed_contract_hash':'c'*64}
    monkeypatch.setattr(service,'selected_delivery_reconciliation',lambda **bindings:replace(chosen,authority=replace(chosen.authority,**changes)));before=snapshot(case[1],case[4]);reply=case[0].post(url(case),headers=_h(ADMIN),json={})
    assert (reply.status_code,reply.json()['code'])==((503,'PROVIDER_UNAVAILABLE') if fault in {'unreviewed','expired'} else (409,'RETRY_UNSAFE')) and calls==built==[] and snapshot(case[1],case[4])==before

def test_public_retained_reconciliation_original_without_saved_ref_is409_without_key_lookup_or_GET(admission_case,monkeypatch):
    client,dsn,args,auth=admission_case;original=admit(dsn,args,auth);submitted(dsn,original,ref=None);case=client,dsn,args,auth,original,authority(args,auth);chosen,calls,built=select(monkeypatch,case);before=snapshot(dsn,original)
    reply=client.post(url(case),headers=_h(ADMIN),json={});assert (reply.status_code,reply.json()['code'])==(409,'RETRY_UNSAFE') and calls==built==[] and snapshot(dsn,original)==before

def test_public_retained_reconciliation_new_delivery_admission_off_does_not_block_retained_scope(reconcile_case,monkeypatch):
    case=reconcile_case;chosen,calls,built=select(monkeypatch,case)
    from buyeros_api.settings import get_settings
    monkeypatch.setenv('BUYEROS_DELIVERY_ADMISSION_ENABLED','false');monkeypatch.setenv('BUYEROS_PAID_ADMISSION_ENABLED','false');get_settings.cache_clear()
    reply=case[0].post(url(case),headers=_h(ADMIN),json={});assert reply.status_code==200 and calls==['original-ref']

def test_public_retained_reconciliation_inactive_admin_is404_before_GET(reconcile_case,monkeypatch):
    case=reconcile_case;chosen,calls,built=select(monkeypatch,case)
    with psycopg.connect(case[1]) as db:db.execute('UPDATE memberships SET active=false,version=version+1 WHERE workspace_id=%s AND user_id=%s',(WORKSPACE_A,uuid.uuid5(uuid.NAMESPACE_URL,ADMIN)))
    before=snapshot(case[1],case[4]);reply=case[0].post(url(case),headers=_h(ADMIN),json={});assert (reply.status_code,reply.json()['code'])==(404,'NOT_FOUND') and calls==built==[] and snapshot(case[1],case[4])==before

@pytest.mark.parametrize('fault',['inactive','downgraded'])
def test_public_retained_reconciliation_revoked_admin_after_GET_keeps_observation_but_denies_response(reconcile_case,monkeypatch,fault):
    case=reconcile_case
    def revoke():
        with psycopg.connect(case[1]) as db:
            if fault=='inactive':db.execute('UPDATE memberships SET active=false,version=version+1 WHERE workspace_id=%s AND user_id=%s',(WORKSPACE_A,uuid.uuid5(uuid.NAMESPACE_URL,ADMIN)))
            else:db.execute("UPDATE memberships SET roles=ARRAY['viewer'],version=version+1 WHERE workspace_id=%s AND user_id=%s",(WORKSPACE_A,uuid.uuid5(uuid.NAMESPACE_URL,ADMIN)))
    chosen,calls,built=select(monkeypatch,case,hook=revoke);before=snapshot(case[1],case[4]);reply=case[0].post(url(case),headers=_h(ADMIN),json={});after=snapshot(case[1],case[4])
    assert (reply.status_code,reply.json()['code'])==((404,'NOT_FOUND') if fault=='inactive' else (403,'PERMISSION_DENIED')) and calls==['original-ref'] and after['original'][0][8]=='accepted' and len(after['events'])==1;assert_originals_retained(before,after)

def test_public_retained_reconciliation_malformed_foreign_ref_never_rebinds_original_or_records_event(reconcile_case,monkeypatch):
    case=reconcile_case;chosen,calls,built=select(monkeypatch,case,result=DeliveryStatusResult('accepted','foreign-ref'));before=snapshot(case[1],case[4]);reply=case[0].post(url(case),headers=_h(ADMIN),json={})
    assert (reply.status_code,reply.json()['code'])==(422,'INVALID_REQUEST') and calls==['original-ref'] and snapshot(case[1],case[4])==before

def test_public_retained_reconciliation_network_loss_returns_original_unknown_with_no_event_money_or_resend(reconcile_case,monkeypatch):
    case=reconcile_case;chosen,calls,built=select(monkeypatch,case,error=RuntimeError('owned mock transport loss'));before=snapshot(case[1],case[4]);reply=case[0].post(url(case),headers=_h(ADMIN),json={})
    assert reply.status_code==200 and reply.json()['data']=={'message_id':str(case[4].message_id),'state':'unknown','event_id':None,'replayed':False} and calls==['original-ref'] and snapshot(case[1],case[4])==before


def test_retained_public_reconciliation_classifies_as_expensive_write():
    from buyeros_api.services.api_rate_limit import classify_request
    assert classify_request('POST','/v1/workspaces/selector/delivery-messages/original/reconciliation')=='expensive_write'

def test_retained_public_reconciliation_rate_limit_admission_occurs_once_before_GET_and_never_after_receipt(reconcile_case,monkeypatch):
    case=reconcile_case;chosen,calls,built=select(monkeypatch,case)
    from buyeros_api.settings import get_settings
    monkeypatch.setenv('BUYEROS_EXPENSIVE_WRITE_PER_MINUTE','1');get_settings.cache_clear()
    with psycopg.connect(case[1]) as db:db.execute('DELETE FROM api_rate_windows WHERE workspace_id=%s AND actor_id=%s',(WORKSPACE_A,uuid.uuid5(uuid.NAMESPACE_URL,ADMIN)))
    first=case[0].post(url(case),headers=_h(ADMIN),json={});assert first.status_code==200,first.text
    before=snapshot(case[1],case[4]);second=case[0].post(url(case),headers=_h(ADMIN),json={})
    assert (second.status_code,second.json()['code'])==(429,'RATE_LIMITED') and calls==built==['original-ref'] and snapshot(case[1],case[4])==before
