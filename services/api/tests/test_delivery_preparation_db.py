"""Real current approval bindings under tenant RLS; never creates or sends a message."""
import asyncio,importlib,uuid
from pathlib import Path
import psycopg,pytest
from buyeros_api.api.errors import ApiError
from buyeros_api.db.session import tenant_session
from buyeros_api.api.deps import get_engine
from tests.test_draft_approval_context_db import _addressed_case,_review,_approval_payload,_approve
from tests.test_api_tenant_isolation import WORKSPACE_B
from tests.test_api_projects_db import api
from tests.test_lookup_quotes_db import REVIEWER,OPERATOR,WORKSPACE_A,PROJECT,_h,quote_case

def service():
    assert Path(__file__).resolve().parents[1].joinpath('buyeros_api/services/delivery_service.py').is_file(),'current delivery preparation missing'
    return importlib.import_module('buyeros_api.services.delivery_service')

def approved(quote_case):
    api,dsn,buyers=quote_case;draft_id,contact_id=_addressed_case(api,dsn,buyers);review=_review(api,draft_id);assert review.status_code==200,review.text
    result=_approve(api,draft_id,_approval_payload(review));assert result.status_code==201,result.text
    data=result.json()['data']
    with psycopg.connect(dsn) as db:sender=str(db.execute('SELECT active_sender_identity_version_id FROM projects WHERE id=%s',(PROJECT,)).fetchone()[0])
    args=dict(workspace_id=uuid.UUID(WORKSPACE_A),actor_id=uuid.uuid5(uuid.NAMESPACE_URL,REVIEWER),draft_id=uuid.UUID(draft_id),draft_revision_id=uuid.UUID(data['draft_revision_id']),recipient_ref=uuid.UUID(contact_id),sender_identity_id=uuid.UUID(sender),approval_id=uuid.UUID(data['id']),key='delivery:exact-001')
    return api,dsn,buyers,args

def prepare(api,args):
    module=service()
    async def run():
        engine=get_engine()
        try:
            async with tenant_session(engine,args['workspace_id']) as session:return await module.prepare_delivery_intent(session,**args)
        finally:await engine.dispose()
    return asyncio.run(run())

def counts(dsn):
    with psycopg.connect(dsn) as db:return (db.execute('SELECT count(*) FROM outbox_events').fetchone()[0],db.execute('SELECT count(*) FROM provider_operations').fetchone()[0])

def test_delivery_preparation_resolves_exact_server_revision_and_retains_disabled_route(quote_case):
    module=service();api,dsn,buyers,args=approved(quote_case);before=counts(dsn)
    prepared=prepare(api,args)
    assert prepared.intent.draft_revision_id==args['draft_revision_id'] and prepared.intent.approval_id==args['approval_id']
    assert prepared.payload['recipient']=='recipient@fixture.example' and prepared.payload['subject']=='Introduction: Industrial sensors' and prepared.payload['body']=='We offer Industrial sensors.'
    assert module.delivery_payload_digest(prepared.payload)==prepared.intent.payload_digest
    response=api.post(f"/v1/workspaces/{WORKSPACE_A}/drafts/{args['draft_id']}/deliver",headers=_h(REVIEWER,key='delivery-still-disabled'))
    assert response.status_code==403 and response.json()['code']=='DELIVERY_DISABLED' and counts(dsn)==before

@pytest.mark.parametrize('binding',['draft_revision_id','recipient_ref','sender_identity_id','approval_id'])
def test_delivery_preparation_rejects_foreign_or_old_exact_binding(quote_case,binding):
    service();api,dsn,buyers,args=approved(quote_case);before=counts(dsn);args[binding]=uuid.uuid4()
    with pytest.raises(ApiError) as exc:prepare(api,args)
    assert exc.value.status_code==412 and exc.value.code=='STALE_REVISION' and counts(dsn)==before

@pytest.mark.parametrize('changed',['recipient','sender','policy','suppression','revision'])
def test_delivery_preparation_rechecks_current_policy_recipient_sender_and_revision(quote_case,changed):
    service();api,dsn,buyers,args=approved(quote_case)
    with psycopg.connect(dsn,autocommit=True) as db:
        if changed=='recipient':db.execute("UPDATE contact_points SET version=version+1 WHERE id=%s",(args['recipient_ref'],))
        elif changed=='sender':db.execute('UPDATE projects SET active_sender_identity_version_id=NULL WHERE id=%s',(PROJECT,))
        elif changed=='policy':db.execute("UPDATE policy_decisions SET status='blocked',version=version+1 WHERE workspace_id=%s AND purpose='outreach'",(WORKSPACE_A,))
        elif changed=='suppression':db.execute("INSERT INTO suppressions(id,workspace_id,subject_key_hash,subject_type,subject_id,controller_scope_id,purpose,purposes,reason,active,actor_id) VALUES (%s,%s,%s,'contact_point',%s,%s,'outreach',ARRAY['outreach'],'Fixture opt out',true,%s)",(uuid.uuid4(),WORKSPACE_A,'d'*64,args['recipient_ref'],WORKSPACE_A,args['actor_id']))
        elif changed=='revision':db.execute("UPDATE outreach_drafts SET state='draft',state_version=state_version+1 WHERE id=%s",(args['draft_id'],))
    before=counts(dsn)
    with pytest.raises(ApiError) as exc:prepare(api,args)
    assert exc.value.status_code in (403,412) and exc.value.code in ('STALE_REVISION','POLICY_BLOCKED') and counts(dsn)==before

def test_delivery_preparation_operator_cannot_use_reviewer_approval_to_send(quote_case):
    service();api,dsn,buyers,args=approved(quote_case);args['actor_id']=uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR);before=counts(dsn)
    with pytest.raises(ApiError) as exc:prepare(api,args)
    assert exc.value.status_code==403 and exc.value.code=='PERMISSION_DENIED' and counts(dsn)==before

def test_delivery_preparation_foreign_workspace_is_denied_with_owned_positive_control(quote_case):
    service();api,dsn,buyers,args=approved(quote_case);assert prepare(api,args).intent.workspace_id==uuid.UUID(WORKSPACE_A);args['workspace_id']=uuid.UUID(WORKSPACE_B);before=counts(dsn)
    with pytest.raises(ApiError) as exc:prepare(api,args)
    assert exc.value.status_code==403 and exc.value.code=='PERMISSION_DENIED' and counts(dsn)==before
