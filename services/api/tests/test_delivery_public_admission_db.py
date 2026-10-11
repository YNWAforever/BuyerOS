"""New independent admission route; original /deliver kill boundary retained."""
import importlib,uuid
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
import psycopg,pytest
from tests.test_delivery_admission_db import admission_case,counts,snapshot
from tests.test_lookup_quotes_db import WORKSPACE_A,PROJECT,REVIEWER,OPERATOR,_h
from tests.test_api_tenant_isolation import WORKSPACE_B

def module():
    path=Path(__file__).resolve().parents[1]/'buyeros_api/api/routes/delivery.py'
    assert path.is_file(),'independent precise-revision delivery admission route missing'
    return importlib.import_module('buyeros_api.api.routes.delivery')

def body(args):return {key:str(args[key]) for key in ('draft_revision_id','recipient_ref','sender_identity_id','approval_id')}
def url(args,workspace=None,draft=None):return f"/v1/workspaces/{workspace or args['workspace_id']}/drafts/{draft or args['draft_id']}/delivery-intents"

def flags(monkeypatch,*,delivery=True,paid=True):
    from buyeros_api.settings import get_settings
    monkeypatch.setenv('BUYEROS_DELIVERY_ADMISSION_ENABLED','true' if delivery else 'false')
    monkeypatch.setenv('BUYEROS_PAID_ADMISSION_ENABLED','true' if paid else 'false')
    get_settings.cache_clear()

@pytest.fixture
def public_case(admission_case,monkeypatch):
    client,dsn,args,auth=admission_case;flags(monkeypatch)
    try:yield client,dsn,args,auth
    finally:
        from buyeros_api.settings import get_settings
        get_settings.cache_clear()

def selected(monkeypatch,auth):
    monkeypatch.setattr(module(),'selected_delivery_authorization',lambda **bindings:auth)

def test_new_delivery_admission_default_closed403_and_original_deliver403_have_zero_side_effects(admission_case,monkeypatch):
    client,dsn,args,auth=admission_case;flags(monkeypatch,delivery=False,paid=True);before=counts(dsn)
    try:
        reply=client.post(url(args),headers=_h(REVIEWER,key='new-default-delivery-off'),json=body(args))
        old=client.post(f"/v1/workspaces/{WORKSPACE_A}/drafts/{args['draft_id']}/deliver",headers=_h(REVIEWER,key='old-delivery-boundary'))
        assert (reply.status_code,reply.json()['code'])==(403,'DELIVERY_DISABLED')
        assert (old.status_code,old.json()['code'])==(403,'DELIVERY_DISABLED') and counts(dsn)==before
    finally:
        from buyeros_api.settings import get_settings
        get_settings.cache_clear()

def test_delivery_admission_unselected503_does_not_create_any_message_operation_hold_or_outbox(public_case):
    client,dsn,args,auth=public_case;module();before=counts(dsn)
    reply=client.post(url(args),headers=_h(REVIEWER,key='unselected-delivery-authority'),json=body(args))
    assert (reply.status_code,reply.json()['code'])==(503,'PROVIDER_UNAVAILABLE') and counts(dsn)==before

def test_delivery_admission_selected_precise_revision_once_replay_same_original_and_still_no_provider_IO(public_case,monkeypatch):
    client,dsn,args,auth=public_case;selected(monkeypatch,auth);before=counts(dsn)
    reply=client.post(url(args),headers=_h(REVIEWER,key=args['key']),json=body(args));assert reply.status_code==202,reply.text
    data=reply.json()['data'];assert set(data)=={'message_id','state','replayed'} and data['state']=='prepared' and data['replayed'] is False
    after=counts(dsn);assert tuple(a-b for a,b in zip(after,before))==(1,1,3,1,1,1,1,0)
    repeated=client.post(url(args),headers=_h(REVIEWER,key=args['key']),json=body(args));assert repeated.status_code==202
    assert repeated.json()['data']==dict(data,replayed=True) and counts(dsn)==after
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT intent_key,state,provider_ref,payload_digest FROM delivery_messages WHERE id=%s',(uuid.UUID(data['message_id']),)).fetchone()[:3]==(args['key'],'prepared',None)
        assert db.execute('SELECT remaining_hold,upper_bound,state FROM budget_reservations WHERE operation_id=(SELECT operation_id FROM delivery_messages WHERE id=%s)',(uuid.UUID(data['message_id']),)).fetchone()==(auth.upper_bound,auth.upper_bound,'active')
    old=client.post(f"/v1/workspaces/{WORKSPACE_A}/drafts/{args['draft_id']}/deliver",headers=_h(REVIEWER,key='old-still-off-after-native-admission'))
    assert (old.status_code,old.json()['code'])==(403,'DELIVERY_DISABLED') and counts(dsn)==after

@pytest.mark.parametrize('fault',['body','provider','account','upper_bound','actor','workspace_id','project_id','payload_digest'])
def test_delivery_admission_rejects_arbitrary_content_or_client_authority_fields_before_write(public_case,monkeypatch,fault):
    client,dsn,args,auth=public_case;selected(monkeypatch,auth);before=counts(dsn);payload=dict(body(args),**{fault:'untrusted-client-value'})
    reply=client.post(url(args),headers=_h(REVIEWER,key='invalid-client-delivery-'+fault),json=payload)
    assert (reply.status_code,reply.json()['code'])==(422,'INVALID_REQUEST') and counts(dsn)==before

@pytest.mark.parametrize('field',['draft_revision_id','recipient_ref','sender_identity_id','approval_id'])
def test_delivery_admission_stale_or_rebound_revision_context_has_exact412_and_no_money(public_case,monkeypatch,field):
    client,dsn,args,auth=public_case;selected(monkeypatch,auth);before=counts(dsn);payload=dict(body(args),**{field:str(uuid.uuid4())})
    reply=client.post(url(args),headers=_h(REVIEWER,key='rebound-delivery-'+field),json=payload)
    assert (reply.status_code,reply.json()['code'])==(412,'STALE_REVISION') and counts(dsn)==before

def test_delivery_admission_operator_role_denied_and_matching_reviewer_positive_control(public_case,monkeypatch):
    client,dsn,args,auth=public_case;selected(monkeypatch,auth);before=counts(dsn)
    denied=client.post(url(args),headers=_h(OPERATOR,key='operator-cannot-admit-delivery'),json=body(args))
    assert (denied.status_code,denied.json()['code'])==(403,'PERMISSION_DENIED') and counts(dsn)==before
    owned=client.post(url(args),headers=_h(REVIEWER,key=args['key']),json=body(args));assert owned.status_code==202

def test_delivery_admission_foreign_draft_404_has_matching_owned202_and_same_original_scope(public_case,monkeypatch):
    client,dsn,args,auth=public_case;selected(monkeypatch,auth);before=counts(dsn)
    foreign=uuid.uuid4();company=uuid.uuid4();buyer=uuid.uuid4()
    with psycopg.connect(dsn) as db:
        project=db.execute('SELECT id FROM projects WHERE workspace_id=%s',(WORKSPACE_B,)).fetchone()[0]
        db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name,domain) VALUES (%s,%s,'Foreign delivery company','Foreign delivery company','foreign-delivery.fixture.example')",(company,WORKSPACE_B))
        db.execute('INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES (%s,%s,%s,%s)',(buyer,WORKSPACE_B,project,company))
        db.execute("INSERT INTO outreach_drafts(id,workspace_id,project_id,buyer_id,current_revision,state) VALUES (%s,%s,%s,%s,1,'draft')",(foreign,WORKSPACE_B,project,buyer))
        assert db.execute('SELECT workspace_id FROM outreach_drafts WHERE id=%s',(foreign,)).fetchone()==(uuid.UUID(WORKSPACE_B),)
    denied=client.post(url(args,draft=foreign),headers=_h(REVIEWER,key='foreign-delivery-draft'),json=body(args))
    assert (denied.status_code,denied.json()['code'])==(404,'NOT_FOUND') and counts(dsn)==before
    owned=client.post(url(args),headers=_h(REVIEWER,key=args['key']),json=body(args));assert owned.status_code==202

@pytest.mark.parametrize('fault',['reviewed','selected','sender_verified','expired','scope-workspace'])
def test_delivery_admission_unreviewed_or_expired_server_scope_cannot_create_hold(public_case,monkeypatch,fault):
    client,dsn,args,auth=public_case
    if fault=='expired':auth=replace(auth,valid_until=datetime.now(timezone.utc)-timedelta(seconds=1))
    elif fault=='scope-workspace':auth=replace(auth,workspace_id=uuid.UUID(WORKSPACE_B))
    else:auth=replace(auth,**{fault:False})
    selected(monkeypatch,auth);before=counts(dsn)
    reply=client.post(url(args),headers=_h(REVIEWER,key='invalid-selected-scope-'+fault),json=body(args))
    assert (reply.status_code,reply.json()['code'])==(503,'PROVIDER_UNAVAILABLE') and counts(dsn)==before

def test_delivery_admission_paid_flag_disabled_requires503_even_if_delivery_flag_and_selection_present(public_case,monkeypatch):
    client,dsn,args,auth=public_case;selected(monkeypatch,auth);flags(monkeypatch,delivery=True,paid=False);before=counts(dsn)
    reply=client.post(url(args),headers=_h(REVIEWER,key=args['key']),json=body(args))
    assert (reply.status_code,reply.json()['code'])==(503,'CAPABILITY_DISABLED') and counts(dsn)==before

def test_delivery_admission_requires_key_before_any_delivery_write(public_case,monkeypatch):
    client,dsn,args,auth=public_case;selected(monkeypatch,auth);before=counts(dsn);headers=_h(REVIEWER);headers.pop('Idempotency-Key',None)
    reply=client.post(url(args),headers=headers,json=body(args));assert (reply.status_code,reply.json()['code'])==(400,'INVALID_REQUEST') and counts(dsn)==before

@pytest.mark.parametrize('fault',['policy','approval','role'])
def test_delivery_admission_current_revocation_before_request_denies_and_keeps_zero_side_effects(public_case,monkeypatch,fault):
    client,dsn,args,auth=public_case;selected(monkeypatch,auth)
    with psycopg.connect(dsn) as db:
        if fault=='policy':db.execute("UPDATE policy_decisions SET status='blocked',version=version+1 WHERE workspace_id=%s AND purpose='outreach'",(WORKSPACE_A,))
        elif fault=='approval':db.execute("UPDATE approvals SET invalidated_reason='owned public revocation',invalidated_at=now() WHERE id=%s",(args['approval_id'],))
        else:db.execute('UPDATE memberships SET active=false,version=version+1 WHERE workspace_id=%s AND user_id=%s',(WORKSPACE_A,args['actor_id']))
    before=counts(dsn);reply=client.post(url(args),headers=_h(REVIEWER,key=args['key']),json=body(args))
    expected=(403,'POLICY_BLOCKED') if fault=='policy' else (412,'STALE_REVISION') if fault=='approval' else (404,'NOT_FOUND')
    assert (reply.status_code,reply.json()['code'])==expected and counts(dsn)==before


@pytest.mark.parametrize('key',['short','x'*129,'space key','unicode-字','bad.key','bad?key','bad%key','bad\\nkey'],ids=['short','too-long','space','unicode','period','query','percent','newline'])
def test_delivery_admission_key_contract_rejects_before_money_and_never_surfaces500(public_case,monkeypatch,key):
    client,dsn,args,auth=public_case;selected(monkeypatch,auth);before=counts(dsn)
    headers=[(k.encode('ascii'),v.encode('utf-8')) for k,v in _h(REVIEWER,key=key).items()]
    reply=client.post(url(args),headers=headers,json=body(args))
    assert (reply.status_code,reply.json()['code'])==(400,'INVALID_REQUEST') and counts(dsn)==before

@pytest.mark.parametrize('field',['draft_revision_id','recipient_ref','sender_identity_id','approval_id'])
def test_delivery_admission_zero_UUID_is_invalid_request_without_write(public_case,monkeypatch,field):
    client,dsn,args,auth=public_case;selected(monkeypatch,auth);before=counts(dsn)
    reply=client.post(url(args),headers=_h(REVIEWER,key='delivery-zero-'+field),json=dict(body(args),**{field:str(uuid.UUID(int=0))}))
    assert (reply.status_code,reply.json()['code'])==(422,'INVALID_REQUEST') and counts(dsn)==before

def test_delivery_admission_same_key_different_body_conflicts_without_rebind_or_extra_hold(public_case,monkeypatch):
    client,dsn,args,auth=public_case;selected(monkeypatch,auth)
    first=client.post(url(args),headers=_h(REVIEWER,key=args['key']),json=body(args));assert first.status_code==202
    before=counts(dsn)
    changed=client.post(url(args),headers=_h(REVIEWER,key=args['key']),json=dict(body(args),recipient_ref=str(uuid.uuid4())))
    assert (changed.status_code,changed.json()['code'])==(409,'IDEMPOTENCY_CONFLICT') and counts(dsn)==before

@pytest.mark.parametrize('state',['unknown','accepted'])
def test_delivery_admission_original_unknown_or_accepted_replay_never_resends_under_new_key(public_case,monkeypatch,state):
    client,dsn,args,auth=public_case;selected(monkeypatch,auth)
    first=client.post(url(args),headers=_h(REVIEWER,key=args['key']),json=body(args));assert first.status_code==202
    message=uuid.UUID(first.json()['data']['message_id']);ref=str(uuid.uuid4()) if state=='accepted' else None
    with psycopg.connect(dsn) as db:
        db.execute("UPDATE delivery_messages SET state='submitting' WHERE id=%s",(message,))
        db.execute('UPDATE delivery_messages SET state=%s,provider_ref=%s WHERE id=%s',(state,ref,message))
        db.execute('UPDATE provider_operations SET status=%s WHERE id=(SELECT operation_id FROM delivery_messages WHERE id=%s)',('accepted' if state=='accepted' else 'unknown_acceptance',message))
    before=counts(dsn)
    replay=client.post(url(args),headers=_h(REVIEWER,key=args['key']),json=body(args))
    assert replay.status_code==202 and replay.json()['data']=={'message_id':str(message),'state':state,'replayed':True}
    new=client.post(url(args),headers=_h(REVIEWER,key='public-fresh-key-after-'+state),json=body(args))
    assert (new.status_code,new.json()['code'])==(409,'RETRY_UNSAFE') and counts(dsn)==before
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT provider_ref FROM delivery_messages WHERE id=%s',(message,)).fetchone()==(ref,)
        assert db.execute('SELECT remaining_hold,upper_bound,state FROM budget_reservations WHERE operation_id=(SELECT operation_id FROM delivery_messages WHERE id=%s)',(message,)).fetchone()==(auth.upper_bound,auth.upper_bound,'active')

@pytest.mark.parametrize('fault',['policy','approval','role'])
def test_delivery_admission_replay_rechecks_current_permission_instead_of_returning_cached202(public_case,monkeypatch,fault):
    client,dsn,args,auth=public_case;selected(monkeypatch,auth)
    first=client.post(url(args),headers=_h(REVIEWER,key=args['key']),json=body(args));assert first.status_code==202
    with psycopg.connect(dsn) as db:
        if fault=='policy':db.execute("UPDATE policy_decisions SET status='blocked',version=version+1 WHERE workspace_id=%s AND purpose='outreach'",(WORKSPACE_A,))
        elif fault=='approval':db.execute("UPDATE approvals SET invalidated_reason='owned replay revocation',invalidated_at=now() WHERE id=%s",(args['approval_id'],))
        else:db.execute('UPDATE memberships SET active=false,version=version+1 WHERE workspace_id=%s AND user_id=%s',(WORKSPACE_A,args['actor_id']))
    before=counts(dsn);replay=client.post(url(args),headers=_h(REVIEWER,key=args['key']),json=body(args))
    expected=(403,'POLICY_BLOCKED') if fault=='policy' else (412,'STALE_REVISION') if fault=='approval' else (404,'NOT_FOUND')
    assert (replay.status_code,replay.json()['code'])==expected and counts(dsn)==before

def test_delivery_admission_foreign_workspace_is_non_enumerating404_with_owned202_control(public_case,monkeypatch):
    client,dsn,args,auth=public_case;selected(monkeypatch,auth);before=counts(dsn)
    denied=client.post(url(args,workspace=WORKSPACE_B),headers=_h(REVIEWER,key='foreign-workspace-delivery'),json=body(args))
    assert (denied.status_code,denied.json()['code'])==(404,'NOT_FOUND') and counts(dsn)==before
    owned=client.post(url(args),headers=_h(REVIEWER,key=args['key']),json=body(args));assert owned.status_code==202
