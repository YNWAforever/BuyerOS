"""Authenticated HTTP on the real API role, synthetic user notes only."""
import uuid
import psycopg
import pytest
from psycopg.types.json import Jsonb
from fastapi.testclient import TestClient
from buyeros_api.api.app import create_app
from tests.test_buyer_review_db import api, _h, OPERATOR, VIEWER, REVIEWER, ADMIN, WORKSPACE_A, WORKSPACE_B, PROJECT_A, PROJECT_B

ROOT = f'/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/conversation-threads'
BODY = {'confirmed':True, 'template_id':'custom', 'title':'Synthetic note', 'messages':[{'text':'SYNTHETIC_USER_NOTE'}], 'sources':[], 'runs':[]}


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME','true')


@pytest.fixture
def thread_api(enabled, api, seeded):
    yield api, seeded
    with psycopg.connect(seeded) as db:
        db.execute('DELETE FROM conversation_threads')


def headers(subject=OPERATOR, version=1, key=None):
    return {**_h(subject), 'If-Match':f'"{version}"', 'Idempotency-Key':key or str(uuid.uuid4())}


def create(client, **changes):
    response = client.post(ROOT, headers=headers(), json={**BODY,**changes})
    assert response.status_code == 201, response.text
    return response.json()['data']


def member(dsn, subject):
    with psycopg.connect(dsn) as db:
        return str(db.execute('SELECT id FROM memberships WHERE workspace_id=%s AND user_id=%s', (WORKSPACE_A,uuid.uuid5(uuid.NAMESPACE_URL,subject))).fetchone()[0])


def grant(client, dsn, row, subject, role):
    response=client.put(f"{ROOT}/{row['id']}/shares/{member(dsn,subject)}", headers=headers(version=row['version']), json={'role':role})
    assert response.status_code==200,response.text
    return response.json()['data']


@pytest.mark.parametrize('flag',[None,'false','TRUE','1',''])
def test_flag_off_is_404_without_database_access(monkeypatch,flag):
    if flag is None:monkeypatch.delenv('NEXT_PUBLIC_CONVERSATION_HOME',raising=False)
    else:monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME',flag)
    client=TestClient(create_app())
    for method,suffix in [('GET',''),('POST',''),('GET','/'+str(uuid.uuid4()))]:
        response=client.request(method,ROOT+suffix,json=BODY if method=='POST' else None)
        assert response.status_code==404
        assert response.json()['code']=='NOT_FOUND'
        assert response.headers['cache-control']=='no-store'


def test_create_replay_version_and_no_content_copies_in_idempotency(thread_api):
    client,dsn=thread_api
    h=headers(key='synthetic-import-key')
    first=client.post(ROOT,headers=h,json=BODY)
    replay=client.post(ROOT,headers=h,json=BODY)
    assert first.status_code==replay.status_code==201
    row=first.json()['data'];assert row==replay.json()['data']
    assert row['access']=='owner' and row['shareCount']==0
    path=f"{ROOT}/{row['id']}/messages";h=headers(key='synthetic-append-key')
    first=client.post(path,headers=h,json={'text':'SECOND_SYNTHETIC_NOTE'})
    assert first.status_code==200,first.text
    assert client.post(path,headers=h,json={'text':'SECOND_SYNTHETIC_NOTE'}).json()['data']==first.json()['data']
    stale=client.post(path,headers=headers(),json={'text':'must not overwrite'})
    assert stale.status_code==409 and stale.json()['code']=='STALE_REVISION'
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT count(*) FROM conversation_threads').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM conversation_thread_messages').fetchone()[0]==2
        records=db.execute("SELECT response FROM idempotency_records WHERE operation_id LIKE '%ConversationThread%'").fetchall()
        assert all(response is None for response, in records)


@pytest.mark.parametrize('actor,access',[(OPERATOR,'owner'),(REVIEWER,'editor'),(VIEWER,'viewer'),(ADMIN,None)])
def test_acl_matrix_and_owner_only_controls(thread_api,actor,access):
    client,dsn=thread_api;row=create(client)
    row=grant(client,dsn,row,REVIEWER,'editor');row=grant(client,dsn,row,VIEWER,'viewer')
    path=f"{ROOT}/{row['id']}"
    read=client.get(path,headers=_h(actor));assert read.status_code==(200 if access else 404),read.text
    if access:assert read.json()['data']['access']==access
    write=client.post(path+'/messages',headers=headers(actor,row['version']),json={'text':'role note'})
    assert write.status_code==(200 if access in {'owner','editor'} else 404),write.text
    version=write.json()['data']['version'] if write.status_code==200 else row['version']
    for method,suffix,body in [('PATCH','',{'title':'Renamed'}),('GET','/shares',None),('GET','/share-recipients',None),('DELETE','',None)]:
        response=client.request(method,path+suffix,headers=headers(actor,version),json=body)
        assert response.status_code==(200 if access=='owner' else 404),(method,response.text)
        if method=='PATCH' and access=='owner':version=response.json()['data']['version']


@pytest.mark.parametrize('change',['revoke','inactive','role_removed','foreign_workspace','foreign_project','deleted'])
def test_access_loss_and_foreign_ids_are_no_leak_404(thread_api,change):
    client,dsn=thread_api;row=create(client);row=grant(client,dsn,row,VIEWER,'viewer');path=f"{ROOT}/{row['id']}"
    assert client.get(path,headers=_h(VIEWER)).status_code==200
    if change=='revoke':
        assert client.delete(path+'/shares/'+member(dsn,VIEWER),headers=headers(version=row['version'])).status_code==200
    elif change in {'inactive','role_removed'}:
        with psycopg.connect(dsn) as db:
            db.execute('UPDATE memberships SET '+('active=false' if change=='inactive' else "roles=ARRAY['policy_admin']")+' WHERE id=%s',(member(dsn,VIEWER),))
    elif change=='foreign_workspace':path=path.replace(WORKSPACE_A,WORKSPACE_B).replace(PROJECT_A,PROJECT_B)
    elif change=='foreign_project':path=path.replace(PROJECT_A,PROJECT_B)
    elif change=='deleted':assert client.delete(path,headers=headers(version=row['version'])).status_code==200
    result=client.get(path,headers=_h(VIEWER));assert result.status_code==404,result.text
    listed=client.get(ROOT,headers=_h(VIEWER));assert listed.status_code==404 or not listed.json()['data']['items'] or change in {'foreign_workspace','foreign_project'}


@pytest.mark.parametrize('changes',[
    {'confirmed':False},{'confirmed':1},{'template_id':'unknown'},{'title':'x'*81},{'messages':[]},
    {'messages':[{'text':'x'*4001}]},{'messages':[{'text':'   '}]},{'messages':[{'text':42}]},
    {'messages':[{'text':'AI','kind':'ai'}]},{'messages':[{'text':'note','citations':[]}]},
    {'messages':[{'text':'note','draft_body':'private'}]},{'document_text':'private'},{'buyer_email':'private'},
    {'live_ai_reply':'private'},{'filenames':['private.txt']},{'fact_values':['private']},
    {'sources':[{'id':'document:one','label':'private.pdf'}]}, {'sources':[{'id':'https://private','label':'Offer document'}]},
    {'sources':[{'id':'document:one','label':'Offer document','text':'private'}]},
    {'sources':[{'id':'document:one','label':'Offer document'}]*2},
    {'runs':[{'id':str(uuid.uuid4()),'label':'private','status':'queued'}]},
    {'runs':[{'id':str(uuid.uuid4()),'label':'Research run','status':'invented'}]},
    {'runs':[{'id':str(uuid.uuid4()),'label':'Research run','status':'queued','text':'private'}]},
])
def test_strict_validation_and_forbidden_payload_classes(thread_api,changes):
    client,_=thread_api
    result=client.post(ROOT,headers=headers(),json={**BODY,**changes})
    assert result.status_code==422,result.text
    assert 'private' not in result.text


def test_recipient_search_is_scoped_minimal_and_role_change_revoke_audit_ids_only(thread_api):
    client,dsn=thread_api;row=create(client);path=f"{ROOT}/{row['id']}"
    result=client.get(path+'/share-recipients',headers=_h());assert result.status_code==200,result.text
    assert len(result.json()['data']['items'])==3
    assert all(set(item)=={'member_id','display_name'} for item in result.json()['data']['items'])
    row=grant(client,dsn,row,VIEWER,'viewer');row=grant(client,dsn,row,VIEWER,'editor')
    assert client.get(path+'/shares',headers=_h()).json()['data']['items'][0]['role']=='editor'
    result=client.delete(path+'/shares/'+member(dsn,VIEWER),headers=headers(version=row['version']));assert result.status_code==200
    assert client.delete(path,headers=headers(version=result.json()['data']['version'])).status_code==200
    with psycopg.connect(dsn) as db:
        rows=db.execute("SELECT action,subject_id,reason,detail_digest FROM audit_events WHERE action LIKE 'conversation_thread.%' ORDER BY created_at").fetchall()
        assert {row[0] for row in rows}=={'conversation_thread.imported','conversation_thread.shared','conversation_thread.role_changed','conversation_thread.revoked','conversation_thread.deleted'}
        assert all(uuid.UUID(entity) and reason is None and digest is None for _,entity,reason,digest in rows)
        assert 'SYNTHETIC_USER_NOTE' not in str(rows)
        assert db.execute('SELECT count(*) FROM conversation_thread_messages').fetchone()[0]==0


@pytest.mark.parametrize('case',['message','source','run','thread','share'])
def test_bounded_server_caps(thread_api,case):
    client,dsn=thread_api;row=create(client);path=f"{ROOT}/{row['id']}"
    with psycopg.connect(dsn) as db:
        owner=uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR)
        if case=='message':
            db.execute("INSERT INTO conversation_thread_messages(id,workspace_id,project_id,thread_id,owner_user_id,author_user_id,text) SELECT gen_random_uuid(),%s,%s,%s,%s,%s,'bounded' FROM generate_series(1,99)",(WORKSPACE_A,PROJECT_A,row['id'],owner,owner))
        elif case=='run':db.execute('UPDATE conversation_threads SET runs=%s WHERE id=%s',(Jsonb([{'id':str(uuid.uuid4()),'label':'Research run','status':'queued'} for _ in range(100)]),row['id']))
        elif case=='thread':db.execute("INSERT INTO conversation_threads(id,workspace_id,project_id,owner_user_id,template_id,title) SELECT gen_random_uuid(),%s,%s,%s,'custom','bounded' FROM generate_series(1,199)",(WORKSPACE_A,PROJECT_A,owner))
        elif case=='share':
            for _ in range(25):
                user=uuid.uuid4();db.execute("INSERT INTO users(id,issuer,subject) VALUES(%s,'fixture',%s)",(user,str(user)))
                db.execute("INSERT INTO conversation_thread_shares(id,workspace_id,project_id,thread_id,owner_user_id,grantee_user_id,granted_by,role) VALUES(gen_random_uuid(),%s,%s,%s,%s,%s,%s,'viewer')",(WORKSPACE_A,PROJECT_A,row['id'],owner,user,owner))
    if case=='message':response=client.post(path+'/messages',headers=headers(),json={'text':'too many'})
    elif case=='source':response=client.put(path+'/sources',headers=headers(),json={'sources':[{'id':f'document:{i}','label':'Offer document'} for i in range(101)]})
    elif case=='run':response=client.post(path+'/runs',headers=headers(),json={'id':str(uuid.uuid4()),'label':'Research run','status':'queued'})
    elif case=='thread':response=client.post(ROOT,headers=headers(),json=BODY)
    else:response=client.put(path+'/shares/'+member(dsn,VIEWER),headers=headers(),json={'role':'viewer'})
    assert response.status_code==(422 if case=='source' else 409),response.text


def test_missing_preconditions_share_replay_and_immediate_replay_revocation(thread_api):
    client,dsn=thread_api;row=create(client);path=f"{ROOT}/{row['id']}";recipient=member(dsn,VIEWER)
    assert client.post(ROOT,headers={'Authorization':_h()['Authorization']},json=BODY).status_code==400
    assert client.patch(path,headers=_h(),json={'title':'next'}).status_code==400
    h=headers(key='share-replay-key')
    first=client.put(path+'/shares/'+recipient,headers=h,json={'role':'editor'})
    second=client.put(path+'/shares/'+recipient,headers=h,json={'role':'editor'})
    assert first.status_code==second.status_code==200
    assert first.json()['data']==second.json()['data']
    h=headers(VIEWER,2,key='editor-note-key')
    assert client.post(path+'/messages',headers=h,json={'text':'editor note'}).status_code==200
    assert client.delete(path+'/shares/'+recipient,headers=headers(version=3)).status_code==200
    assert client.post(path+'/messages',headers=h,json={'text':'editor note'}).status_code==404


def test_two_concurrent_writers_cannot_silently_overwrite(thread_api):
    from concurrent.futures import ThreadPoolExecutor
    client,dsn=thread_api;row=create(client);path=f"{ROOT}/{row['id']}/messages"
    row=grant(client,dsn,row,REVIEWER,'editor')
    def append(subject):
        return client.post(path,headers=headers(subject,row['version']),json={'text':'concurrent '+subject})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(append,[OPERATOR,REVIEWER]))
    assert sorted(result.status_code for result in results)==[200,409]
    assert next(result for result in results if result.status_code==409).json()['code']=='STALE_REVISION'
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT count(*) FROM conversation_thread_messages').fetchone()[0]==2


def test_runtime_flag_and_read_kill_switch_rechecked_on_existing_app(thread_api,monkeypatch):
    from buyeros_api.settings import get_settings
    client,_=thread_api;row=create(client);path=f"{ROOT}/{row['id']}"
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME','TRUE')
    assert client.get(path,headers=_h()).status_code==404
    assert client.post(path+'/messages',headers=headers(),json={'unknown':'blocked before validation'}).status_code==404
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME','true')
    monkeypatch.setenv('BUYEROS_LIVE_READ_ENABLED','false');get_settings.cache_clear()
    assert client.post(path+'/messages',headers=headers(),json={'text':'note'}).status_code==503
