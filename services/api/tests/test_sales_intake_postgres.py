"""Real owned PostgreSQL acceptance. BLOCKED until the isolated allocator can run."""
import uuid
import psycopg
import pytest
from concurrent.futures import ThreadPoolExecutor
from tests.test_sales_tasks_api import sales_api, SALES_ROOT
from tests.test_conversation_threads_api import create, grant, headers, member, ROOT
from tests.test_buyer_review_db import _h, OPERATOR, REVIEWER, VIEWER, ADMIN


def missing(client, thread):
    result=client.post(SALES_ROOT,headers=headers(version=thread['version']),json={
        'thread_id':thread['id'],'skill_id':'first-project','skill_version':'1',
        'user_message':'SYNTHETIC_ORIGINAL_INTAKE','arguments':{},'source_refs':[]})
    assert result.status_code==201,result.text
    data=result.json()['data']
    assert data['state']=='needs_input' and data['missing_inputs']==['offer_description']
    return data


def test_postgres_guided_intake_reload_replay_and_disabled_recovery(sales_api,monkeypatch):
    client,dsn=sales_api
    thread=create(client)
    task=missing(client,thread)
    path=SALES_ROOT+'/'+task['id']
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT count(*) FROM outbox_events WHERE event_type LIKE 'sales%'").fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM model_receipts').fetchone()[0]==0
    # Complete authored intake is recovery; disabled admission must not dispatch.
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED','false')
    monkeypatch.delenv('BUYEROS_SALES_WORKSPACE_IDS')
    data={'user_message':'SYNTHETIC_FOLLOWUP','arguments':{'offer_description':'Synthetic verified offer'}}
    h=headers(version=1,key='synthetic-guided-followup')
    result=client.post(path+'/followups',headers=h,json=data)
    assert result.status_code==200,result.text
    ready=result.json()['data']
    assert ready['id']==task['id'] and ready['revision']==2 and ready['state']=='ready_for_review'
    assert ready['missing_inputs']==[] and [x['revision'] for x in ready['intake']]==[1,2]
    assert client.post(path+'/followups',headers=h,json=data).json()['data']==ready
    assert client.get(path,headers=_h()).json()['data']==ready
    listing=client.get(SALES_ROOT+'?thread_id='+thread['id'],headers=_h()).json()['data']
    assert listing['items']==[ready] and listing['total']==1
    assert client.post(path+'/followups',headers=headers(version=1),json=data).status_code==409
    with psycopg.connect(dsn) as db:
        # Durable dedup survives native receipt expiry/removal, without another task revision.
        db.execute("DELETE FROM idempotency_records WHERE operation_id='followupSalesTask'")
    assert client.post(path+'/followups',headers=h,json=data).json()['data']==ready
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT count(*) FROM sales_tasks').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM sales_task_events').fetchone()[0]==2
        assert db.execute('SELECT count(*) FROM conversation_thread_messages').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM model_receipts').fetchone()[0]==0


def test_postgres_intake_share_revocation_and_private_discovery(sales_api):
    client,dsn=sales_api
    thread=grant(client,dsn,create(client),REVIEWER,'editor')
    thread=grant(client,dsn,thread,VIEWER,'viewer')
    task=missing(client,thread)
    path=SALES_ROOT+'/'+task['id']
    data={'user_message':'SYNTHETIC','arguments':{'offer_description':'Synthetic offer'}}
    h=headers(REVIEWER,1,'synthetic-editor-followup')
    assert client.post(path+'/followups',headers=headers(VIEWER),json=data).status_code==404
    assert client.get(SALES_ROOT+'?thread_id='+thread['id'],headers=_h(ADMIN)).status_code==404
    assert client.post(path+'/followups',headers=h,json=data).status_code==200
    current=client.get(ROOT+'/'+thread['id'],headers=_h()).json()['data']
    assert client.delete(ROOT+'/'+thread['id']+'/shares/'+member(dsn,REVIEWER),headers=headers(version=current['version'])).status_code==200
    assert client.post(path+'/followups',headers=h,json=data).status_code==404
    assert client.get(path,headers=_h(REVIEWER)).status_code==404
    assert client.get(SALES_ROOT+'?thread_id='+thread['id'],headers=_h(REVIEWER)).status_code==404


def test_postgres_followups_serialize_same_revision(sales_api):
    client,_=sales_api
    task=missing(client,create(client))
    path=SALES_ROOT+'/'+task['id']+'/followups'
    def submit(index):
        return client.post(path,headers=headers(version=1,key='synthetic-concurrent-'+str(index)),
            json={'user_message':'SYNTHETIC','arguments':{'offer_description':'Synthetic '+str(index)}}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(submit,range(2)))==[200,409]
    detail=client.get(SALES_ROOT+'/'+task['id'],headers=_h()).json()['data']
    assert detail['revision']==2 and len(detail['intake'])==2


def test_postgres_r4_oversized_merged_intake_preserves_original_row(sales_api):
    from tests.test_sales_intake import large_proposal_inputs
    client,dsn=sales_api
    thread=create(client)
    original,delta=large_proposal_inputs()
    created=client.post(SALES_ROOT,headers=headers(version=thread['version']),json={
        'thread_id':thread['id'],'skill_id':'sales-proposal','skill_version':'1',
        'user_message':'SYNTHETIC LARGE ORIGINAL','arguments':original,'source_refs':[]})
    assert created.status_code==201,created.text
    task=created.json()['data'];path=SALES_ROOT+'/'+task['id']
    def stored():
        with psycopg.connect(dsn) as db:
            row=db.execute('SELECT arguments,intake_history,revision,state,context_digest,source_refs,event_sequence,updated_at FROM sales_tasks WHERE id=%s',
                (task['id'],)).fetchone()
            counts=tuple(db.execute('SELECT count(*) FROM '+table+' WHERE task_id=%s',(task['id'],)).fetchone()[0]
                for table in ('sales_task_events','sales_task_dependencies'))
            receipts=db.execute("SELECT count(*) FROM idempotency_records WHERE operation_id='followupSalesTask'").fetchone()[0]
            return row,counts,receipts
    before=stored()
    result=client.post(path+'/followups',headers=headers(version=1,key='synthetic-oversized-merge'),
        json={'user_message':'SYNTHETIC DELTA','arguments':delta})
    assert result.status_code==422 and result.json()['code']=='INPUT_LIMIT',result.text
    assert result.headers['cache-control']=='no-store'
    assert stored()==before
    assert client.get(path,headers=_h()).json()['data']==task
