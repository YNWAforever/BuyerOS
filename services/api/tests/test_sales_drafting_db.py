"""Formal drafts require an explicit native eligible recipient."""
import importlib
import uuid
import pytest
import psycopg
from tests.test_api_projects_db import api
from tests.test_lookup_quotes_db import quote_case,WORKSPACE_A,PROJECT,ICP,OPERATOR,_h
from tests.test_draft_approval_context_db import _addressed_case,_review,_approve,_approval_payload
from tests.test_sales_core_journey_db import new_task
from tests.test_sales_tasks_api import SALES_ROOT
from tests.test_conversation_threads_api import headers
from tests.icp_fixtures import FACT_ID


@pytest.fixture
def seeded(isolated_seeded):
    return isolated_seeded


@pytest.fixture
def core_case(quote_case,monkeypatch):
    client,dsn,buyers=quote_case
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME','true')
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED','true')
    monkeypatch.setenv('BUYEROS_SALES_WORKSPACE_IDS',WORKSPACE_A)
    # The two-locale catalogue matrix deliberately makes more than sixty
    # fixture writes in one minute; retain the limiter with an explicit test cap.
    monkeypatch.setenv('BUYEROS_EXPENSIVE_WRITE_PER_MINUTE','300')
    from buyeros_api.settings import get_settings
    get_settings.cache_clear()
    from fastapi.testclient import TestClient
    from buyeros_api.api.app import create_app
    client=TestClient(create_app(),raise_server_exceptions=True)
    client.__enter__()  # One event loop/pool for the full bounded HTTP journey.
    _,contact=_addressed_case(client,dsn,buyers)
    from psycopg.types.json import Jsonb
    from buyeros_api.db.icp import canonical_hash
    with psycopg.connect(dsn) as db:
        content=db.execute('SELECT content FROM icp_versions WHERE id=%s',(ICP,)).fetchone()[0]
        content['requirements']=[{'id':str(uuid.uuid4()),'category':'must','text':'industrial sensors'}]
        db.execute('UPDATE icp_versions SET content=%s,content_hash=%s WHERE id=%s',(Jsonb(content),canonical_hash(content),ICP))
    from tests.policy_activation_fixtures import approve_research_fixture
    from tests.test_run_admission_integration_db import FIXTURE_SEARCH_BINDING,CAPABILITY
    from buyeros_api.api.routes.runs import selected_run_capability
    approve_research_fixture(dsn,WORKSPACE_A,PROJECT,domains=('fixture1.example','fixture2.example'),search=FIXTURE_SEARCH_BINDING)
    # Research designation expanded authority; reapprove the earlier provider
    # purposes against that current authority, without bypassing policy checks.
    from tests.policy_activation_fixtures import approve_provider_fixture
    from tests.test_api_projects_db import ADMIN
    with psycopg.connect(dsn) as db:
        sender=db.execute('SELECT active_sender_identity_version_id FROM projects WHERE id=%s',(PROJECT,)).fetchone()[0]
    provider={'provider_name':'resend','account_reference':'owned-delivery-budget-fixture','contract_sha256':'b'*64,
        'sender_identity_id':str(sender),'recipient_refs':[contact]}
    for purpose in ('outreach','draft_preparation'):
        approve_provider_fixture(dsn,WORKSPACE_A,PROJECT,uuid.uuid5(uuid.NAMESPACE_URL,ADMIN),purpose=purpose,
            scope=provider,domains=('fixture1.example',))
    client.app.dependency_overrides[selected_run_capability]=lambda:(CAPABILITY,'test')
    client.get(f'/v1/workspaces/{WORKSPACE_A}/budgets',headers=_h())
    with psycopg.connect(dsn) as db: db.execute('UPDATE budget_accounts SET approved_limit=5')
    yield client,dsn,buyers[0][0],contact
    client.__exit__(None,None,None)
    get_settings.cache_clear()
    with psycopg.connect(dsn) as db:
        db.execute("UPDATE sales_tasks SET state='cancelled'")
        db.execute('DELETE FROM conversation_threads')
        db.execute("DELETE FROM budget_accounts WHERE scope='run'")
        db.execute('DELETE FROM run_events')


def ref(kind,id,version=1):
    return {'kind':kind,'id':id,'version':version,'locator':f'{kind}:{id}','retention_class':'durable'}


def test_material_draft_edit_invalidates_approval(core_case,monkeypatch):
    client,dsn,buyer,contact=core_case
    from tests.test_run_admission_db import LIMITS
    body={'icp_version_id':ICP,'target_companies':1,'max_cost':{'amount':'1.000000','currency':'USD'},
        'limits':{**LIMITS,'max_queries_per_run':1,'max_results':1,'max_pages':1,'provider_concurrency':1}}
    research=new_task(client,'sales-research',{'buyer_id':buyer,'research_question':'Review selected buyer'})
    guide=client.get(SALES_ROOT+'/'+research['id']+'/core-guidance',headers=headers()).json()['data']
    key=guide['action']['idempotency_key']
    path=f'/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/runs'
    admitted=client.post(path,headers=_h(key=key),json=body)
    assert admitted.status_code==202,admitted.text
    run=admitted.json()['data']
    assert client.post(path,headers=_h(key=key),json=body).json()['data']['id']==run['id']
    # Synthetic terminal native result, not a provider execution acceptance claim.
    with psycopg.connect(dsn) as db:
        db.execute("UPDATE search_runs SET status='completed' WHERE id=%s",(run['id'],))
        db.execute('UPDATE evidence SET run_id=%s WHERE company_id=(SELECT company_id FROM project_buyers WHERE id=%s)',(run['id'],buyer))
        db.execute('UPDATE source_documents SET run_id=%s WHERE id IN(SELECT source_document_id FROM evidence WHERE run_id=%s)',(run['id'],run['id']))
    refs=[ref('buyer',buyer),ref('profile',ICP),ref('run',run['id']),
        {**ref('project_fact',FACT_ID),'locator':f'fact:profile:{ICP}:{FACT_ID}'}]
    follow=client.post(SALES_ROOT+'/'+research['id']+'/followups',headers=headers(version=1),json={
        'user_message':'Use the reviewed native result','arguments':{},'source_refs':refs})
    assert follow.status_code==200,follow.text
    h=headers(version=follow.json()['data']['revision'],key='save-research-native')
    from buyeros_api.services import sales_outputs
    original=sales_outputs.get_output
    async def lost_save(*args,**kwargs): raise ValueError('synthetic failed output readback')
    monkeypatch.setattr(sales_outputs,'get_output',lost_save)
    failed=client.post(SALES_ROOT+'/'+research['id']+'/core-preparation',headers=h)
    assert failed.status_code==409,failed.text
    monkeypatch.setattr(sales_outputs,'get_output',original)
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT count(*) FROM sales_outputs').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM search_runs').fetchone()[0]==1
        assert any(r['id']==run['id'] for r in db.execute('SELECT source_refs FROM sales_tasks WHERE id=%s',(research['id'],)).fetchone()[0])
    saved=client.post(SALES_ROOT+'/'+research['id']+'/core-preparation',headers=h)
    assert saved.status_code==200,saved.text
    assert client.post(SALES_ROOT+'/'+research['id']+'/core-preparation',headers=h).json()['data']==saved.json()['data']
    research_output=saved.json()['data']
    prep=new_task(client,'sales-outreach',{'buyer_id':buyer,'profile_id':ICP,'objective':'Introduce the offer'},
        refs+[ref('output',research_output['id'])])
    saved=client.post(SALES_ROOT+'/'+prep['id']+'/core-preparation',headers=headers(version=1))
    assert saved.status_code==200,saved.text
    output=saved.json()['data']
    base=SALES_ROOT.replace('sales-tasks','sales-outputs')+'/'+output['id']
    denied=client.post(base+'/formal-draft',headers=headers(version=1,key='formal-invalid-recipient'),
        json={'recipient_id':str(uuid.uuid4()),'expected_revision':1})
    assert denied.status_code==412,denied.text
    formal=client.post(base+'/formal-draft',headers=headers(version=1,key='formal-native-create'),
        json={'recipient_id':contact,'expected_revision':1})
    assert formal.status_code==200,formal.text
    draft_id=formal.json()['data']['id']
    replay=client.post(base+'/formal-draft',headers=headers(version=1,key='formal-native-create'),
        json={'recipient_id':contact,'expected_revision':1})
    assert replay.json()['data']==formal.json()['data']
    native=f'/v1/workspaces/{WORKSPACE_A}/drafts/{draft_id}'
    assert client.get(native,headers=_h()).json()['data']['body']==output['content']['messages'][0]['body']
    review=_review(client,draft_id)
    assert review.status_code==200,review.text
    approval=_approve(client,draft_id,_approval_payload(review))
    assert approval.status_code==201,approval.text
    current=client.get(native,headers=_h()).json()['data']
    assert current['status']=='approved' and current['approval_id'] is not None
    edit=client.patch(native,headers=_h(key='material-core-edit',**{'If-Match':f'"{current["version"]}"'}),json={'body':'Material new text requires review'})
    assert edit.status_code==200,edit.text
    invalid=client.get(native,headers=_h()).json()['data']
    assert invalid['status']=='draft' and invalid['approval_id'] is None
    history=client.get(base+'/versions',headers=headers()).json()['data']['outputs']
    assert len(history)==2
    assert history[-1]['content']==output['content']
    # All Task11 catalogue entries are reachable, saved and read through the
    # same canonical owner; prospect/quick consume the same run, no rediscovery.
    cases=[('sales-research',{'buyer_id':buyer}),('sales-quick',{'buyer_id':buyer}),
        ('sales-outreach',{'buyer_id':buyer,'profile_id':ICP,'objective':'Discuss selected evidence'}),
        ('sales-prospect',{'buyer_id':buyer,'objective':'Review buyers'}),
        ('sales-qualify',{'buyer_id':buyer,'profile_id':ICP,'profile_version':1}),
        ('review-buyers',{'buyer_ids':[buyer],'profile_id':ICP,'profile_version':1}),
        ('sales-icp',{'offer_description':'Sensors','profile_id':ICP}),
        ('first-project',{'offer_description':'Sensors'}),
        ('sales-followup',{'buyer_id':buyer,'profile_id':ICP,'objective':'Discuss selected evidence',
            'scenario':'nurture','interaction_ref':ref('output',research_output['id'])})]
    for language in ('en','zh-HK'):
        for skill,args in cases:
            task=new_task(client,skill,{**args,'language':language},refs+[ref('output',research_output['id'])])
            response=client.post(SALES_ROOT+'/'+task['id']+'/core-preparation',headers=headers(version=1))
            assert response.status_code==200,(skill,language,response.text)
            value=response.json()['data']
            assert value['availability']=='available'
            reopen=client.get(SALES_ROOT.replace('sales-tasks','sales-outputs')+'/'+value['id'],headers=headers())
            assert reopen.json()['data']==value
            if skill=='sales-qualify': assert all(d['score'] is None for d in value['content']['dimensions'])
            if skill=='sales-icp': assert value['content']['approval_required'] is True
            if skill=='review-buyers': assert value['content']['review_required'] is True
            if skill=='sales-prospect':
                status=client.get(SALES_ROOT+'/'+task['id'],headers=headers()).json()['data']
                assert status['state']=='partially_completed'
    # Same-project authorization does not make buyer B's child relevant to A.
    with psycopg.connect(dsn) as db:
        other=str(db.execute('SELECT id FROM project_buyers WHERE project_id=%s AND id<>%s LIMIT 1',(PROJECT,buyer)).fetchone()[0])
    for child_buyer,accepted in ((other,False),(buyer,True)):
        child_refs=[ref('buyer',child_buyer) if r['kind']=='buyer' else r for r in refs]
        child_task=new_task(client,'sales-outreach',{'buyer_id':child_buyer,'profile_id':ICP,'objective':'Discuss'},child_refs)
        child=client.post(SALES_ROOT+'/'+child_task['id']+'/core-preparation',headers=headers(version=1))
        assert child.status_code==200,child.text
        child_output=child.json()['data']
        task=new_task(client,'sales-prospect',{'buyer_id':buyer,'objective':'Review'},refs+[ref('output',child_output['id'])])
        response=client.post(SALES_ROOT+'/'+task['id']+'/core-preparation',headers=headers(version=1))
        assert response.status_code==200,response.text
        missing=response.json()['data']['content']['unknowns']
        assert any('outreach_preparation' in item for item in missing) is (not accepted)
        assert client.get(SALES_ROOT+'/'+task['id'],headers=headers()).json()['data']['state']=='partially_completed'
        assert response.json()['data']['dependencies']==[{'id':child_output['id'],'revision':1}]
    # Revoked current sources invalidate all derived content and model context.
    with psycopg.connect(dsn) as db:
        db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE run_id=%s",(run['id'],))
    unavailable=client.get(SALES_ROOT.replace('sales-tasks','sales-outputs')+'/'+research_output['id'],headers=headers())
    assert unavailable.json()['data']['availability']=='unavailable'
    assert unavailable.json()['data']['content'] is None
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT count(*) FROM search_runs').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM model_receipts').fetchone()[0]==0
        assert db.execute("SELECT count(*) FROM outbox_events WHERE event_type LIKE 'delivery.%'").fetchone()[0]==0


def test_formal_draft_owner_is_separate_from_authored_preparation():
    assert importlib.util.find_spec('buyeros_api.sales.drafting'), 'formal draft producer missing'
    module=importlib.import_module('buyeros_api.sales.drafting')
    assert callable(module.save_formal_draft)
    assert callable(module.prepare_draft)


def test_configured_setup_and_current_invalidation(core_case):
    client,dsn,buyer,contact=core_case
    def prepare(args):
        task=new_task(client,'first-project',{'offer_description':'Sensors',**args})
        guide=client.get(SALES_ROOT+'/'+task['id']+'/core-guidance',headers=headers()).json()['data']
        result=client.post(SALES_ROOT+'/'+task['id']+'/core-preparation',headers=headers(version=1))
        assert result.status_code==200,result.text
        value=result.json()['data']
        assert guide['missing_inputs']==value['content']['missing_fields']
        return value
    unselected=prepare({})
    assert unselected['content']['missing_fields']==['unselected_recipient']
    configured=prepare({'buyer_id':buyer,'recipient_id':contact})
    assert configured['content']['missing_fields']==[]
    unavailable=prepare({'buyer_id':buyer,'recipient_id':str(uuid.uuid4())})
    assert unavailable['content']['missing_fields']==['ineligible_recipient']
    with psycopg.connect(dsn) as db:
        db.execute('UPDATE sender_identity_versions SET retired=true WHERE id=(SELECT active_sender_identity_version_id FROM projects WHERE id=%s)',(PROJECT,))
    read=client.get(SALES_ROOT.replace('sales-tasks','sales-outputs')+'/'+configured['id'],headers=headers())
    assert read.json()['data']['availability']=='unavailable'
    assert 'reviewed_sender' in prepare({})['content']['missing_fields']


def test_followup_interaction_and_scenario_are_not_generic(core_case):
    client,dsn,buyer,contact=core_case
    refs=[ref('buyer',buyer),ref('profile',ICP),{**ref('project_fact',FACT_ID),'locator':f'fact:profile:{ICP}:{FACT_ID}'}]
    bodies=[]
    for interaction in (refs[0],refs[2]):
        for scenario in ('nurture','post_meeting','post_demo','recovery'):
            task=new_task(client,'sales-followup',{'buyer_id':buyer,'profile_id':ICP,'objective':'Discuss',
                'interaction_ref':interaction,'scenario':scenario},refs)
            response=client.post(SALES_ROOT+'/'+task['id']+'/core-preparation',headers=headers(version=1))
            if scenario!='nurture':
                assert response.status_code==409,response.text
                assert response.json()['code']=='NEEDS_INPUT'
                assert scenario in response.json()['message']
            else:
                assert response.status_code==200,response.text
                value=response.json()['data']['content']
                assert any('agreed actions' in item for item in value['unknowns'])
                bodies.append(value['messages'][0]['body'])
    assert bodies[0]!=bodies[1]


@pytest.mark.parametrize('loss',['buyer','evidence'])
@pytest.mark.parametrize('extra_sources',[False,True])
def test_final_real_native_component_same_buyer_transition(core_case,loss,extra_sources):
    import json,subprocess
    from pathlib import Path
    client,dsn,buyer,contact=core_case
    task=new_task(client,'review-buyers',{'buyer_ids':[str(buyer)],'profile_id':ICP,'profile_version':1},[ref('buyer',buyer),ref('profile',ICP)])
    prepared=client.post(SALES_ROOT+'/'+task['id']+'/core-preparation',headers=headers(version=1))
    assert prepared.status_code==200,prepared.text
    original=prepared.json()['data']
    probe=subprocess.run(['node','tests/sales-native-action-probe.mjs'],cwd=Path(__file__).resolve().parents[3],
        input=json.dumps(original),capture_output=True,text=True,timeout=30)
    assert probe.returncode==0,probe.stderr
    request=json.loads(probe.stdout);payload=request['payload']
    if extra_sources:payload['source_versions']+=original['citations']
    assert any(r['kind']=='output' and r['id']==original['id'] and r['version']==original['revision'] for r in payload['source_versions'])
    path=SALES_ROOT.replace('sales-tasks','sales-outputs')
    h=headers(version=request['version'],key='final-real-ui-native')
    for _ in range(2):
        response=client.post(path+'/native-actions',headers=h,json=payload)
        assert response.status_code==200,response.text
        assert response.json()['data']['revision']==2
    latest=client.get(path+'/'+original['id'],headers=headers()).json()['data']
    assert latest['availability']=='available' and latest['revision']==2
    assert latest['content']['assessments'][0]['evidence'][0]['version']==2
    assert latest['citations'][0]['version']==2
    # A new action cannot reuse the now-obsolete saved output, unlike exact replay.
    assert client.post(path+'/native-actions',headers=headers(version=request['version'],key='final-stale-ui-native'),json=payload).status_code in {403,404,409,412,422}
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT note,version FROM project_buyers WHERE id=%s',(buyer,)).fetchone()==('Reviewed same-buyer note',2)
        old=db.execute('SELECT candidate FROM sales_output_versions WHERE output_id=%s AND revision=1',(original['id'],)).fetchone()[0]
        assert old['content']==original['content']
        if loss=='buyer':db.execute('UPDATE project_buyers SET version=version+1 WHERE id=%s',(buyer,))
        else:db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second'")
    assert client.post(path+'/native-actions',headers=h,json=payload).status_code in {403,404,409,412}
    assert client.get(path+'/'+original['id'],headers=headers()).json()['data']['availability']=='unavailable'


def test_final_browser_same_buyer_native_save(core_case):
    from tests.sales_final_browser import run_browser
    client,dsn,buyer,_=core_case
    task=new_task(client,'review-buyers',{'buyer_ids':[str(buyer)],'profile_id':ICP,'profile_version':1},[ref('buyer',buyer),ref('profile',ICP)])
    response=client.post(SALES_ROOT+'/'+task['id']+'/core-preparation',headers=headers(version=1))
    assert response.status_code==200,response.text
    output=response.json()['data']
    run_browser(client,{'phase':'native','workspace':WORKSPACE_A,'project':PROJECT,
        'output':output['id'],'buyer':str(buyer)},headers())
    latest=client.get(SALES_ROOT.replace('sales-tasks','sales-outputs')+'/'+output['id'],headers=headers()).json()['data']
    assert latest['revision']==2 and latest['availability']=='available'
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT note,version FROM project_buyers WHERE id=%s',(buyer,)).fetchone()==('Browser reviewed buyer note',2)
