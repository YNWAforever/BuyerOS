"""Stage 4 real HTTP/runtime-role DB proof with an owned read-only Drive fixture."""
import uuid
import psycopg
import pytest
from fastapi.testclient import TestClient
from buyeros_api.api.app import create_app
from buyeros_api.services import drive_mcp
from tests.test_buyer_review_db import api, _h, OPERATOR, REVIEWER, VIEWER, ADMIN, WORKSPACE_A, WORKSPACE_B, PROJECT_A, PROJECT_B
from tests.test_conversation_threads_api import BODY

ROOT=f'/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}'
PATH=ROOT+'/conversation-connections/google-drive'
PRIVATE='SYNTHETIC_DRIVE_BODY_DO_NOT_PERSIST'


class FixtureDrive:
    folder_ids=['folder_one','folder_two']
    parent='folder_one'
    revoked=False
    reads=0

    async def status(self, *_):
        if self.revoked:
            raise drive_mcp.unavailable()

    async def folders(self, *args):
        await self.status();return self.folder_ids

    async def items(self, ws, project, folders):
        await self.status()
        return [{'id':'file_one','folder_id':self.parent}] if self.parent in folders else []

    async def read(self, ws, project, folders, item_id):
        await self.status();self.reads+=1
        assert self.parent in folders and item_id=='file_one'
        return PRIVATE


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME','true')


@pytest.fixture
def connection_api(enabled,api,seeded,monkeypatch):
    gateway=FixtureDrive()
    monkeypatch.setattr(drive_mcp,'adapter',lambda:gateway)
    monkeypatch.setattr(drive_mcp,'configured',lambda:True)
    yield api,seeded,gateway
    with psycopg.connect(seeded) as db:
        db.execute('DELETE FROM conversation_threads')
        db.execute('DELETE FROM conversation_drive_connections')


def headers(subject=ADMIN,version=1,key=None):
    return {**_h(subject),'X-BuyerOS-If-Match':f'"{version}"','Idempotency-Key':key or str(uuid.uuid4())}


def connected(client):
    response=client.post(PATH,headers=headers(),json={})
    assert response.status_code==200,response.text
    response=client.put(PATH+'/folders',headers=headers(version=2),json={'folder_ids':['folder_one']})
    assert response.status_code==200,response.text
    return response.json()['data']


def selected(client):
    row=connected(client)
    source=client.get(PATH+'/items',headers=_h(VIEWER)).json()['data']['items'][0]
    return row,source


@pytest.mark.parametrize('flag',[None,'false','TRUE','1',''])
def test_flag_off_all_paths_fail_closed_before_auth_or_validation(monkeypatch,flag):
    if flag is None:monkeypatch.delenv('NEXT_PUBLIC_CONVERSATION_HOME',raising=False)
    else:monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME',flag)
    client=TestClient(create_app())
    for method,suffix in [('GET',''),('GET','/folders'),('GET','/items'),('POST',''),('PUT','/folders'),('DELETE','')]:
        response=client.request(method,PATH+suffix,json={'token':PRIVATE})
        assert response.status_code==404 and response.json()['code']=='NOT_FOUND'
        assert response.headers['cache-control']=='no-store' and PRIVATE not in response.text


@pytest.mark.parametrize('actor',[ADMIN,OPERATOR,REVIEWER,VIEWER])
def test_admin_controls_and_member_read_matrix(connection_api,actor):
    client,_,_=connection_api
    status=client.get(PATH,headers=_h(actor));assert status.status_code==200
    assert status.json()['data']['can_manage']==(actor==ADMIN)
    response=client.post(PATH,headers=headers(actor),json={})
    assert response.status_code==(200 if actor==ADMIN else 404)
    if actor!=ADMIN:connected(client)
    else:assert client.put(PATH+'/folders',headers=headers(actor,2),json={'folder_ids':['folder_one']}).status_code==200
    assert client.get(PATH+'/items',headers=_h(actor)).status_code==200
    assert client.get(PATH+'/folders',headers=_h(actor)).status_code==(200 if actor==ADMIN else 404)
    assert client.put(PATH+'/folders',headers=headers(actor,3),json={'folder_ids':[]}).status_code==(200 if actor==ADMIN else 404)
    assert client.delete(PATH,headers=headers(actor,4 if actor==ADMIN else 3)).status_code==(200 if actor==ADMIN else 404)


def test_idempotency_stale_and_missing_preconditions_no_silent_overwrite(connection_api):
    client,dsn,_=connection_api;h=headers(key='connect-once')
    first=client.post(PATH,headers=h,json={});second=client.post(PATH,headers=h,json={})
    assert first.status_code==second.status_code==200 and first.json()=={**second.json(),'request_id':first.json()['request_id']}
    h=headers(version=2,key='approve-once');body={'folder_ids':['folder_one']}
    first=client.put(PATH+'/folders',headers=h,json=body)
    assert first.status_code==200 and client.put(PATH+'/folders',headers=h,json=body).json()['data']==first.json()['data']
    assert client.put(PATH+'/folders',headers=h,json={'folder_ids':[]}).json()['code']=='IDEMPOTENCY_CONFLICT'
    stale=client.delete(PATH,headers=headers(version=2));assert stale.status_code==409 and stale.json()['code']=='STALE_REVISION'
    assert client.delete(PATH,headers=_h(ADMIN)).status_code==400
    assert client.delete(PATH,headers={**_h(ADMIN),'Idempotency-Key':'no-version'}).status_code==400
    assert client.delete(PATH,headers={**headers(version=3),'If-Match':'"3"'}).status_code==400
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT count(*),max(version) FROM conversation_drive_connections').fetchone()==(1,3)
        rows=db.execute("SELECT response FROM idempotency_records WHERE operation_id LIKE '%ConversationDrive%'").fetchall()
        assert rows and all(row[0] is None for row in rows)


@pytest.mark.parametrize('payload',[
    {'folder_ids':['not-approved']},{'folder_ids':['folder_one']*2},{'folder_ids':['x']*21},
    {'folder_ids':[42]},{'folder_ids':['https://private.invalid']},{'folder_ids':['x'*129]},
    {'folder_ids':[], 'token':PRIVATE},{'folder_ids':[], 'filename':PRIVATE},{'folder_ids':[], 'text':PRIVATE},
    {'folder_ids':[], 'residency':'US'},{'folder_ids':[], 'retention_seconds':3600},
])
def test_validation_caps_approved_ids_and_no_reflected_private_fields(connection_api,payload):
    client,_,_=connection_api;connected(client)
    response=client.put(PATH+'/folders',headers=headers(version=3),json=payload)
    assert response.status_code==(404 if payload=={'folder_ids':['not-approved']} else 422),response.text
    assert PRIVATE not in response.text


@pytest.mark.parametrize('case',['workspace','project','inactive','role','moved','revoke','disconnect','reapprove','reconnect'])
def test_current_permission_and_revocation_invalidate_selected_sources(connection_api,case):
    client,dsn,gateway=connection_api;row,source=selected(client)
    path=ROOT+'/conversation-reply'
    body={'question':'Review selected evidence','source_ids':[source['id']],'language':'en'}
    assert client.post(path,headers=_h(),json=body).json()['code']=='CONVERSATION_MODEL_UNAVAILABLE'
    if case=='workspace':path=path.replace(WORKSPACE_A,WORKSPACE_B).replace(PROJECT_A,PROJECT_B)
    elif case=='project':path=path.replace(PROJECT_A,PROJECT_B)
    elif case in {'inactive','role'}:
        with psycopg.connect(dsn) as db:
            db.execute('UPDATE memberships SET '+('active=false' if case=='inactive' else "roles=ARRAY['viewer']")+' WHERE workspace_id=%s AND user_id=%s',(WORKSPACE_A,uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR)))
    elif case=='moved':gateway.parent='unapproved-folder'
    elif case=='revoke':gateway.revoked=True
    elif case=='reapprove':assert client.put(PATH+'/folders',headers=headers(version=3),json={'folder_ids':['folder_one']}).status_code==200
    else:
        assert client.delete(PATH,headers=headers(version=3)).status_code==200
        if case=='reconnect':
            assert client.post(PATH,headers=headers(version=4),json={}).status_code==200
            assert client.put(PATH+'/folders',headers=headers(version=5),json={'folder_ids':['folder_one']}).status_code==200
    response=client.post(path,headers=_h(),json=body)
    assert response.status_code in {403,404,422,503} and response.json()['code']!='CONVERSATION_MODEL_UNAVAILABLE',response.text
    assert PRIVATE not in response.text
    if case in {'workspace','project'}:
        foreign=PATH.replace(PROJECT_A,PROJECT_B)
        if case=='workspace':foreign=foreign.replace(WORKSPACE_A,WORKSPACE_B)
        for suffix in ['', '/folders', '/items']:
            denied=client.get(foreign+suffix,headers=_h(ADMIN))
            assert denied.status_code==404 and denied.headers['cache-control']=='no-store'
        assert client.post(foreign,headers=headers(),json={}).status_code==404


def test_approved_drive_grounds_fixture_in_memory_never_db_receipts_audit_or_logs(connection_api,monkeypatch,caplog):
    from buyeros_api.api.routes import conversation
    from buyeros_api.services.conversation_reply import reply_from_grounding
    client,dsn,gateway=connection_api;_,source=selected(client)
    def fixture(grounding):
        assert grounding.excerpts==[PRIVATE] and not grounding.paid_eligible
        return reply_from_grounding(grounding,fixture_candidate={'text':'Review the approved Drive source.',
            'citations':grounding.citations,'status':'needs_review','fixture':True})
    monkeypatch.setattr(conversation,'reply_from_grounding',fixture)
    result=client.post(ROOT+'/conversation-reply',headers=_h(),json={'question':'Review?','source_ids':[source['id']],'language':'zh-HK'})
    assert result.status_code==200,result.text
    assert result.json()['data']['citations'][0]['id']==source['id'] and PRIVATE not in result.text
    assert gateway.reads==1 and PRIVATE not in caplog.text
    from buyeros_api.services import conversation_admission
    monkeypatch.setattr(conversation_admission,'selected_configuration',lambda *args:object())
    blocked=client.post(ROOT+'/conversation-reply',headers=_h(),json={'question':'Review?','source_ids':[source['id']],'language':'en'})
    assert blocked.status_code==409 and blocked.json()['code']=='POLICY_BLOCKED'
    with psycopg.connect(dsn) as db:
        record=db.execute('SELECT row_to_json(c)::text FROM conversation_drive_connections c').fetchone()[0]
        assert PRIVATE not in record and 'token' not in record and 'filename' not in record
        rows=db.execute("SELECT subject_id,reason,detail_digest FROM audit_events WHERE action LIKE 'conversation_drive.%'").fetchall()
        assert rows and all(uuid.UUID(ident) and reason is None and digest is None for ident,reason,digest in rows)
        for table in ['model_receipts','budget_reservations','outbox_events','async_jobs']:
            assert db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]==0


def test_thread_import_and_source_selection_only_approved_ids_replay_and_revoke(connection_api):
    client,_,_=connection_api;_,source=selected(client)
    body={**BODY,'sources':[source]}
    result=client.post(ROOT+'/conversation-threads',headers=headers(OPERATOR),json=body)
    assert result.status_code==201,result.text
    thread=result.json()['data'];path=ROOT+'/conversation-threads/'+thread['id']+'/sources';h=headers(OPERATOR,key='select-once')
    first=client.put(path,headers=h,json={'sources':[source]});assert first.status_code==200,first.text
    assert client.put(path,headers=h,json={'sources':[source]}).json()['data']==first.json()['data']
    assert client.delete(PATH,headers=headers(version=3)).status_code==200
    assert client.put(path,headers=h,json={'sources':[source]}).status_code==422
    assert client.post(ROOT+'/conversation-threads',headers=headers(OPERATOR),json=body).status_code==422


def test_disconnect_works_during_gateway_outage_and_runtime_flag_kills_all_paths(connection_api,monkeypatch):
    from buyeros_api.settings import get_settings
    client,_,gateway=connection_api;connected(client);gateway.revoked=True
    response=client.get(PATH,headers=_h(ADMIN));assert response.status_code==200
    assert response.json()['data']['connected'] and not response.json()['data']['available']
    assert client.delete(PATH,headers=headers(version=3)).status_code==200
    assert client.get(PATH+'/items',headers=_h(VIEWER)).json()['data']['items']==[]
    monkeypatch.setenv('BUYEROS_LIVE_READ_ENABLED','false');get_settings.cache_clear()
    assert client.post(PATH,headers=headers(version=4),json={}).status_code==503
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME','TRUE')
    assert client.put(PATH+'/folders',json={'unknown':PRIVATE}).status_code==404


def test_concurrent_admin_updates_admit_once(connection_api):
    from concurrent.futures import ThreadPoolExecutor
    client,_,_=connection_api;connected(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:client.put(PATH+'/folders',headers=headers(version=3),json={'folder_ids':[]}),range(2)))
    assert sorted(row.status_code for row in results)==[200,409]


@pytest.mark.parametrize('case',['bytes','deadline'])
def test_drive_grounding_total_bytes_and_deadline_are_bounded(connection_api,monkeypatch,case):
    import asyncio
    from buyeros_api.services import conversation_connections
    client,_,gateway=connection_api;_,source=selected(client)
    async def read(*args):
        if case=='deadline':await asyncio.sleep(1)
        return 'x'*12001
    monkeypatch.setattr(gateway,'read',read)
    if case=='deadline':monkeypatch.setattr(conversation_connections,'SOURCE_DEADLINE_SECONDS',.01)
    result=client.post(ROOT+'/conversation-reply',headers=_h(),json={'question':'Review?','source_ids':[source['id']],'language':'en'})
    assert result.status_code==(503 if case=='deadline' else 422),result.text
