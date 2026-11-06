"""Reachable core preparation and native destination on owned PostgreSQL."""
import uuid
import pytest
from tests.test_sales_tasks_api import sales_api, SALES_ROOT
from tests.test_conversation_threads_api import create, headers
from tests.test_research_candidate_review_db import review_case,review,page_case,run_case,project_api,admission_case,migrated


def new_task(client,skill,arguments,refs=()):
    thread=create(client)
    response=client.post(SALES_ROOT,headers=headers(version=thread['version']),json={
        'thread_id':thread['id'],'skill_id':skill,'skill_version':'1','user_message':'Synthetic core request',
        'arguments':arguments,'source_refs':list(refs)})
    assert response.status_code==201,response.text
    return response.json()['data']


def test_first_project_has_persisted_canonical_output_and_history(sales_api):
    client,dsn=sales_api
    task=new_task(client,'first-project',{'offer_description':'Synthetic sensors'})
    path=SALES_ROOT+'/'+task['id']+'/core-preparation'
    h=headers(version=task['revision'],key='task11-project-prepare')
    response=client.post(path,headers=h)
    assert response.status_code==200,response.text
    output=response.json()['data']
    assert output['kind']=='project_setup' and output['availability']=='available'
    assert set(output['content']['missing_fields'])=={'approved_profile','reviewed_sender','unselected_recipient'}
    assert output['content']['setup_basis']['project_id']
    assert client.post(path,headers=h).json()['data']==output
    root=SALES_ROOT.replace('sales-tasks','sales-outputs')+'/'+output['id']
    assert client.get(root,headers=headers()).json()['data']==output
    assert client.get(root+'/versions',headers=headers()).json()['data']['outputs']==[output]


def test_missing_run_exposes_native_reviewed_destination(sales_api):
    client,dsn=sales_api
    task=new_task(client,'sales-research',{'research_question':'Find buyers'})
    response=client.get(SALES_ROOT+'/'+task['id']+'/core-guidance',headers=headers())
    assert response.status_code==200,response.text
    data=response.json()['data']
    assert data['action']['operation_id']=='startRun'
    assert data['action']['requires_human_review'] is True
    assert data['action']['idempotency_key']==f"sales-research:{task['id']}"
    assert data['work']['provider_calls']==0
    assert data['state']=='needs_input'


def test_actual_native_search_page_review_proof_reaches_saved_research(review_case,monkeypatch):
    import psycopg
    from fastapi.testclient import TestClient
    from buyeros_api.api.app import create_app
    c=review_case;native=review(c)
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME','true')
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED','true')
    monkeypatch.setenv('BUYEROS_SALES_WORKSPACE_IDS',str(c['workspace']))
    with psycopg.connect(c['dsn']) as db:
        # Native search dispatch, page retrieval and explicit review above are
        # real owners with synthetic transports. This freezes terminal metadata.
        db.execute("UPDATE search_runs SET status='completed' WHERE id=%s",(c['run'],))
        version=db.execute('SELECT version FROM search_runs WHERE id=%s',(c['run'],)).fetchone()[0]
    refs=[{'id':str(c['run']),'kind':'run','version':version,'locator':f'run:{c["run"]}','retention_class':'durable'}]
    try:
        with TestClient(create_app()) as client:
            task=new_task(client,'sales-research',{'research_question':'Review current native evidence'},refs)
            result=client.post(SALES_ROOT+'/'+task['id']+'/core-preparation',headers=headers(version=1))
            assert result.status_code==200,result.text
            data=result.json()['data']
            assert data['content']['findings'][0]['statement']==c['args']['excerpt']
            assert data['content']['findings'][0]['confidence']=='inference'
            assert len(c['calls'])==1 and c['transport'].calls==1
            with psycopg.connect(c['dsn']) as db:
                db.execute('UPDATE projects SET offer_revision=offer_revision+1 WHERE id=(SELECT project_id FROM search_runs WHERE id=%s)',(c['run'],))
            stale=client.get(SALES_ROOT.replace('sales-tasks','sales-outputs')+'/'+data['id'],headers=headers())
            assert stale.json()['data']['availability']=='unavailable'
            with psycopg.connect(c['dsn']) as db:
                db.execute('UPDATE projects SET offer_revision=offer_revision-1 WHERE id=(SELECT project_id FROM search_runs WHERE id=%s)',(c['run'],))
            with psycopg.connect(c['dsn']) as db:
                db.execute("UPDATE run_events SET payload=payload-'review_reason_hash' WHERE run_id=%s AND event_type='candidate.page_reviewed'",(c['run'],))
            gone=client.get(SALES_ROOT.replace('sales-tasks','sales-outputs')+'/'+data['id'],headers=headers())
            assert gone.json()['data']['availability']=='unavailable'
            assert len(c['calls'])==1 and c['transport'].calls==1
    finally:
        with psycopg.connect(c['dsn']) as db:
            db.execute("UPDATE sales_tasks SET state='cancelled'")
            db.execute('DELETE FROM conversation_threads')
