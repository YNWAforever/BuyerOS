"""Formal follow-up preserves selected authored content and current native parent."""
import psycopg
import uuid
from tests.test_sales_drafting_db import core_case,seeded,api,quote_case,ref
from tests.test_sales_core_journey_db import new_task
from tests.test_sales_tasks_api import SALES_ROOT
from tests.test_conversation_threads_api import headers
from tests.test_lookup_quotes_db import ICP,WORKSPACE_A,PROJECT,_h
from tests.icp_fixtures import FACT_ID
from tests.test_draft_approval_context_db import _review,_approval_payload


def test_positive_formal_followup_current_parent_exact_content_and_material_edit(core_case):
    client,dsn,buyer,contact=core_case
    refs=[ref('buyer',buyer),ref('profile',ICP),{**ref('project_fact',FACT_ID),'locator':f'fact:profile:{ICP}:{FACT_ID}'}]
    def prepare(skill,args,sources):
        task=new_task(client,skill,args,sources)
        result=client.post(SALES_ROOT+'/'+task['id']+'/core-preparation',headers=headers(version=1))
        assert result.status_code==200,result.text
        return result.json()['data']
    outputs=SALES_ROOT.replace('sales-tasks','sales-outputs')
    parent=prepare('sales-outreach',{'buyer_id':buyer,'profile_id':ICP,'objective':'Introduce offer'},refs)
    made=client.post(outputs+'/'+parent['id']+'/formal-draft',headers=headers(version=1),
        json={'recipient_id':contact,'expected_revision':1})
    assert made.status_code==200,made.text
    parent_draft=made.json()['data']
    selected=client.get(outputs+'/'+parent['id'],headers=headers()).json()['data']
    interaction=ref('output',parent['id'],selected['revision'])
    follow=prepare('sales-followup',{'buyer_id':buyer,'profile_id':ICP,'objective':'Continue discussion',
        'scenario':'nurture','interaction_ref':interaction},refs+[interaction])
    made=client.post(outputs+'/'+follow['id']+'/formal-draft',headers=headers(version=1),
        json={'recipient_id':contact,'expected_revision':1})
    assert made.status_code==200,made.text
    draft=made.json()['data'];url=f'/v1/workspaces/{WORKSPACE_A}/drafts/'+draft['id']
    current=client.get(url,headers=_h()).json()['data']
    assert current['parent_draft_id']==parent_draft['id']
    assert current['body']==follow['content']['messages'][0]['body']
    assert current['subject']==follow['content']['messages'][0]['subject']
    # Authored text is intentionally ungrounded until a human reviews its exact
    # revision. Exercise that native owner instead of granting template trust.
    from tests.test_lookup_quotes_db import REVIEWER
    with psycopg.connect(dsn) as db:
        icp_hash=db.execute('SELECT content_hash FROM icp_versions WHERE id=%s',(ICP,)).fetchone()[0]
    grounding={'revision_id':current['revision_id'],'content_hash':current['content_hash'],
        'confirmation':True,'reason':'Reviewed selected reference context and explicit unknown agreed actions',
        'segments':[{'field':field,'start':0,'end':len(current[field]),'exact_text':current[field],
            'classification':'non_factual' if field=='subject' else 'factual',
            'evidence_refs':[] if field=='subject' else current['evidence_refs'],
            'offer_fact_refs':[] if field=='subject' else [{'id':FACT_ID,'icp_version_id':ICP,'icp_content_hash':icp_hash.removeprefix('sha256:')}],
            'reason':'Invitation' if field=='subject' else 'Quoted selected source, no assertion of prior meeting'} for field in ('subject','body')]}
    grounded=client.post(url+'/grounding-reviews',headers=_h(REVIEWER,key='task14-grounding',
        **{'If-Match':f'"{current["version"]}"'}),json=grounding)
    assert grounded.status_code==200,grounded.text
    review=_review(client,draft['id'],key='task14-followup-review')
    assert review.status_code==200,review.text
    from tests.test_lookup_quotes_db import REVIEWER
    approved=client.post(url+'/approvals',headers=_h(REVIEWER,key='task14-approve',
        **{'If-Match':f'"{review.json()["data"]["version"]}"'}),json=_approval_payload(review))
    assert approved.status_code==201,approved.text
    current=client.get(url,headers=_h()).json()['data']
    assert current['approval_id'] is not None
    edited=client.patch(url,headers=_h(key='task14-material',**{'If-Match':f'"{current["version"]}"'}),
        json={'body':'Materially changed follow-up requires fresh approval'})
    assert edited.status_code==200,edited.text
    assert client.get(url,headers=_h()).json()['data']['approval_id'] is None
    assert client.get(outputs+'/'+follow['id'],headers=headers()).json()['data']['content'] is None
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT count(*) FROM outbox_events WHERE event_type LIKE 'delivery.%%'").fetchone()[0]==0


def test_three_real_prospect_children_are_saved_and_recursively_revoked(core_case,monkeypatch):
    from types import SimpleNamespace
    from buyeros_api.sales.contracts import Scope
    from tests.test_buyer_review_db import ADMIN
    from tests.test_xverum_dispatch_db import dispatch_case
    from tests.test_xverum_enrichment_db import journey,propose
    from tests.xverum_fixtures import pg
    from tests.test_run_admission_db import LIMITS
    from tests.policy_activation_fixtures import approve_research_fixture
    client,dsn,buyer,contact=core_case
    c=SimpleNamespace(client=client,dsn=dsn,ws=uuid.UUID(WORKSPACE_A),project=uuid.UUID(PROJECT),
        buyer=uuid.UUID(buyer),id=uuid.uuid4(),account=uuid.uuid4())
    c.scope=Scope(workspace_id=c.ws,project_id=c.project,actor_id=uuid.uuid5(uuid.NAMESPACE_URL,ADMIN))
    with psycopg.connect(dsn) as db:
        db.execute("INSERT INTO xverum_credit_accounts(id,workspace_id,account_ref,credit_limit) VALUES(%s,%s,'synthetic-account',100)",(c.account,c.ws))
        db.execute("INSERT INTO xverum_connections(id,workspace_id,generation,version,account_ref,tariff_version,secret_ref,status,configured_by) VALUES(%s,%s,1,1,'synthetic-account','fixture-v1',%s,'connected',%s)",(c.id,c.ws,uuid.uuid4(),c.scope.actor_id))
        db.execute('INSERT INTO xverum_project_assignments(id,workspace_id,connection_id,project_id) VALUES(%s,%s,%s,%s)',(uuid.uuid4(),c.ws,c.id,c.project))
        db.execute('INSERT INTO xverum_credit_limits(id,workspace_id,project_id,credit_limit) VALUES(%s,%s,NULL,100),(%s,%s,%s,100)',(uuid.uuid4(),c.ws,uuid.uuid4(),c.ws,c.project))
        db.execute("INSERT INTO xverum_tariffs(id,workspace_id,account_id,version,usd_per_credit) VALUES(%s,%s,%s,'fixture-v1',.01)",(uuid.uuid4(),c.ws,c.account))
    async def budgets(factory):
        from buyeros_api.services.budget_service import ensure_period_accounts
        async with factory() as s:await ensure_period_accounts(s,c.ws,c.project,None,'contact_lookup')
    pg(c,budgets)
    with psycopg.connect(dsn) as db:db.execute('UPDATE budget_accounts SET approved_limit=100 WHERE workspace_id=%s',(c.ws,))
    generator=dispatch_case.__wrapped__(c,monkeypatch)
    next(generator)
    try:
        c=journey.__wrapped__(c,monkeypatch,SimpleNamespace(param='en'))
        producer=propose(c)
        with psycopg.connect(dsn) as db:
            enrichment=str(db.execute('SELECT id FROM sales_outputs WHERE task_id=%s',(c.task,)).fetchone()[0])
        # This composition uses a historical native result fixture. The separate
        # native-lifecycle test proves new admission/worker/reconciliation completion.
        response=client.post(f'/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/runs',headers=_h(key='task14-composition-run'),json={
            'icp_version_id':ICP,'target_companies':1,'max_cost':{'amount':'1.000000','currency':'USD'},
            'limits':{**LIMITS,'max_queries_per_run':1,'max_results':1,'max_pages':1,'provider_concurrency':1}})
        assert response.status_code==202,response.text
        run=response.json()['data']['id']
        with psycopg.connect(dsn) as db:
            db.execute("UPDATE search_runs SET status='completed' WHERE id=%s",(run,))
            db.execute('UPDATE evidence SET run_id=%s WHERE company_id=(SELECT company_id FROM project_buyers WHERE id=%s)',(run,buyer))
            db.execute('UPDATE source_documents SET run_id=%s WHERE id IN(SELECT source_document_id FROM evidence WHERE run_id=%s)',(run,run))
        refs=[ref('buyer',buyer),ref('profile',ICP),ref('run',run),{**ref('project_fact',FACT_ID),'locator':f'fact:profile:{ICP}:{FACT_ID}'}]
        from tests.test_conversation_threads_api import ROOT,BODY
        def prepare(skill,args,sources):
            thread=client.post(ROOT,headers=headers(ADMIN),json=BODY).json()['data']
            created=client.post(SALES_ROOT,headers=headers(ADMIN,thread['version']),json={
                'thread_id':thread['id'],'skill_id':skill,'skill_version':'1','user_message':'Synthetic Task14 composition',
                'arguments':args,'source_refs':sources})
            assert created.status_code==201,created.text
            task=created.json()['data']
            output=client.post(SALES_ROOT+'/'+task['id']+'/core-preparation',headers=headers(ADMIN,1))
            assert output.status_code==200,output.text
            return task,output.json()['data']
        _,competitive=prepare('sales-competitors',{'buyer_id':buyer,'profile_id':ICP,'competitor_names':['Fixture']},refs)
        _,outreach=prepare('sales-outreach',{'buyer_id':buyer,'profile_id':ICP,'objective':'Introduce offer'},refs)
        selected=[ref('output',enrichment),ref('output',competitive['id']),ref('output',outreach['id'])]
        task,parent=prepare('sales-prospect',{'buyer_id':buyer,'objective':'Review all children'},refs+selected)
        current=client.get(SALES_ROOT+'/'+task['id'],headers=headers(ADMIN)).json()['data']
        assert current['state']=='completed'
        assert len(parent['dependencies'])==3
        assert not any(any(kind in missing for kind in ('enrichment_proposal','competitive_document','outreach_preparation')) for missing in parent['content']['unknowns'])
        from buyeros_api.services.sales_retention import purge_sales_content
        async def purge(factory):
            async with factory() as s:await purge_sales_content(s,c.scope,c.task)
        pg(c,purge)
        output_url=SALES_ROOT.replace('sales-tasks','sales-outputs')+'/'+parent['id']
        assert client.get(output_url,headers=headers(ADMIN)).json()['data']['content'] is None
        provider_root=f'/v1/workspaces/{c.ws}/projects/{c.project}/xverum'
        assert client.get(provider_root+f'/tasks/{c.task}/stages',headers=headers(ADMIN)).status_code==404
        assert client.get(provider_root+f'/receipts/{c.detail.id}/candidates',headers=headers(ADMIN)).status_code in {404,409}
        with psycopg.connect(dsn) as db:
            assert db.execute("SELECT count(*) FROM outbox_events WHERE event_type LIKE 'delivery.%%'").fetchone()[0]==0
    finally:
        generator.close()
        # Retain financial rows until the owned DB is dropped, while allowing the
        # pre-existing core fixture's private-thread cleanup to run.
        with psycopg.connect(dsn) as db:
            db.execute('UPDATE xverum_enrichments SET task_id=NULL,thread_id=NULL WHERE task_id=%s',(getattr(c,'task',None),))
            db.execute('UPDATE xverum_stages SET task_id=NULL,thread_id=NULL,task_revision=NULL,context_digest=NULL,intake_hash=NULL WHERE task_id=%s',(getattr(c,'task',None),))
            db.execute('DELETE FROM worker_steps WHERE outbox_id IN(SELECT outbox_id FROM xverum_receipts WHERE workspace_id=%s)',(c.ws,))
            db.execute('UPDATE xverum_quotes SET source_receipt_id=NULL,source_digest=NULL WHERE workspace_id=%s',(c.ws,))
            for table in ('xverum_enrichments','xverum_tool_receipts','xverum_stages','xverum_reconciliations',
                'xverum_credit_settlements','xverum_receipts','xverum_credit_reservations','xverum_quotes',
                'xverum_project_assignments','xverum_connections','xverum_tariffs','xverum_credit_limits',
                'xverum_credit_accounts','sales_content_tombstones'):
                db.execute(f'DELETE FROM {table} WHERE workspace_id=%s',(c.ws,))
