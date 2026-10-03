"""Q08 actual manifest persistence; only existing guarded loopback PG fixtures."""
import uuid
import asyncio
import pytest
import psycopg
import os,subprocess,sys,json
from tests.test_buyer_review_db import WORKSPACE_A, PROJECT_A, _admin_membership, _h, api as buyer_api


@pytest.fixture
def api(buyer_api):
    # Exercise one actual ASGI lifespan/event loop, as the running HTTP server does.
    with buyer_api as client:
        yield client


def _seed_many(dsn,count,prefix="Q08"):
    with psycopg.connect(dsn) as conn:
        rows=conn.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) "
            "SELECT gen_random_uuid(),%s,%s||i::text,%s||lpad(i::text,5,'0') "
            "FROM generate_series(1,%s) i RETURNING id",(WORKSPACE_A,prefix,prefix,count)).fetchall()
        conn.cursor().executemany("INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES (%s,%s,%s,%s)",
            [(str(uuid.uuid4()),WORKSPACE_A,PROJECT_A,str(row[0])) for row in rows])


def test_manifest_freezes_1001_current_versions_without_widening_snapshot(api,seeded):
    _seed_many(seeded,1001)
    owner=_admin_membership(seeded)
    path=f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/bulk-manifests"
    response=api.post(path,json={"filters":{"q":"Q08"},"excluded_ids":[],
        "operation":"assignBuyerOwners","target":{"owner_membership_id":owner},"reason":"Bounded manifest review"},
        headers=_h(key="q08-preview-1001"))
    assert response.status_code==201,response.text
    data=response.json()["data"]
    assert data["count"]==1001 and data["status"]=="ready"
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT count(*),count(DISTINCT buyer_id),min(expected_version),max(expected_version) "
            "FROM bulk_manifest_items WHERE manifest_id=%s",(data["id"],)).fetchone()==(1001,1001,1,1)
        assert conn.execute("SELECT count(*) FROM async_jobs WHERE workspace_id=%s",(WORKSPACE_A,)).fetchone()[0]==0



ROOT=f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/bulk-manifests"


def _preview(api,owner,**patch):
    body={"filters":{"q":"Q08"},"excluded_ids":[],"operation":"assignBuyerOwners",
          "target":{"owner_membership_id":owner},"reason":"Bounded manifest review",**patch}
    response=api.post(ROOT,json=body,headers=_h(key=str(uuid.uuid4())))
    assert response.status_code==201,response.text
    from tests.contract_validation import assert_contract_response
    assert_contract_response("BulkManifestResponse",response.json())
    return response.json()["data"]


def _execute(api,manifest,key=None,**patch):
    return api.post(ROOT+f"/{manifest['id']}/execute",json={"digest":manifest["digest"],"confirmation":True,**patch},headers=_h(key=key or str(uuid.uuid4()),**{"If-Match":f'"{manifest["version"]}"'}))


@pytest.mark.parametrize("count",[100,101,1000,1001])
def test_manifest_sync_async_boundaries_and_replay_once(api,seeded,count):
    _seed_many(seeded,count);manifest=_preview(api,_admin_membership(seeded));key=str(uuid.uuid4())
    first=_execute(api,manifest,key);again=_execute(api,manifest,key)
    assert first.status_code==again.status_code==(200 if count==100 else 202),first.text
    from tests.contract_validation import assert_contract_response
    assert_contract_response('BulkResultResponse' if count==100 else 'AsyncJobResponse',first.json())
    assert first.json()["data"]==again.json()["data"]
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT count(*) FROM async_jobs WHERE manifest_id=%s",(manifest["id"],)).fetchone()[0]==(0 if count==100 else 1)
        assert conn.execute("SELECT count(*) FROM outbox_events WHERE event_type='bulk.mutate' AND payload->>'job_id'=%s",(first.json()["data"].get("id",""),)).fetchone()[0]==(0 if count==100 else 1)
        assert conn.execute("SELECT count(*) FROM project_buyers WHERE version=2 AND workspace_id=%s",(WORKSPACE_A,)).fetchone()[0]==(100 if count==100 else 0)
    assert _execute(api,manifest).status_code==409


def test_10001_is_explicitly_rejected_and_no_partial_preview_or_job(api,seeded):
    _seed_many(seeded,10001)
    response=api.post(ROOT,json={"filters":{"q":"Q08"},"excluded_ids":[],"operation":"assignBuyerOwners","target":{"owner_membership_id":None},"reason":"Reject overflow"},headers=_h(key="q08-overflow-10001"))
    assert response.status_code==422 and "10000" in response.text,response.text
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT count(*) FROM bulk_manifests").fetchone()[0]==0
        assert conn.execute("SELECT count(*) FROM bulk_manifest_items").fetchone()[0]==0
        assert conn.execute("SELECT count(*) FROM async_jobs").fetchone()[0]==0


def test_10000_committed_crash_recovery_exact_results_and_failed_child_preview(api,seeded):
    from buyeros_api.api.deps import tenant_scoped
    from buyeros_api.services.bulk_service import apply_bulk_chunk
    _seed_many(seeded,10000);owner=_admin_membership(seeded);manifest=_preview(api,owner)
    assert manifest["count"]==10000
    with psycopg.connect(seeded) as conn:
        stale=conn.execute("SELECT buyer_id FROM bulk_manifest_items WHERE manifest_id=%s ORDER BY ordinal LIMIT 50",(manifest["id"],)).fetchall()
        conn.cursor().executemany("UPDATE project_buyers SET version=version+1 WHERE id=%s",stale)
    response=_execute(api,manifest);assert response.status_code==202,response.text
    job=response.json()["data"];job_id=uuid.UUID(job["id"])
    async def run():
        async with tenant_scoped(uuid.UUID(WORKSPACE_A)) as session:await apply_bulk_chunk(session,job_id)
        try:
            async with tenant_scoped(uuid.UUID(WORKSPACE_A)) as session:
                await apply_bulk_chunk(session,job_id)
                raise RuntimeError("crash before chunk commit")
        except RuntimeError:pass
        with psycopg.connect(seeded) as conn:
            assert conn.execute("SELECT processed FROM async_jobs WHERE id=%s",(job_id,)).fetchone()[0]==50
            assert conn.execute("SELECT count(*) FROM project_buyers WHERE owner_user_id IS NOT NULL AND workspace_id=%s",(WORKSPACE_A,)).fetchone()[0]==0
        restart_script = """import asyncio,json,sys,os,uuid
if sys.platform=='win32':asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from buyeros_api.api.deps import tenant_scoped,dispose_engines
from buyeros_api.services.bulk_service import apply_bulk_chunk
async def resume():
 try:
  async with tenant_scoped(uuid.UUID(sys.argv[2])) as session:
   result=await apply_bulk_chunk(session,uuid.UUID(sys.argv[1]))
  print(json.dumps({'pid':os.getpid(),'processed':result['processed']}))
 finally:await dispose_engines()
asyncio.run(resume())
"""
        restarted=subprocess.run([sys.executable,"-c",restart_script,str(job_id),WORKSPACE_A],capture_output=True,text=True,check=True)
        receipt=json.loads(restarted.stdout);assert receipt["pid"]!=os.getpid() and receipt["processed"]==50
        with psycopg.connect(seeded) as conn:
            assert conn.execute("SELECT processed FROM async_jobs WHERE id=%s",(job_id,)).fetchone()[0]==100
        for _ in range(198):
            async with tenant_scoped(uuid.UUID(WORKSPACE_A)) as session:
                result=await apply_bulk_chunk(session,job_id)
                assert result["processed"]<=50
        async with tenant_scoped(uuid.UUID(WORKSPACE_A)) as session:assert (await apply_bulk_chunk(session,job_id))["processed"]==0
    asyncio.run(run())
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT requested,processed,updated,conflicts,status FROM async_jobs WHERE id=%s",(job_id,)).fetchone()==(10000,10000,9950,50,"completed")
        assert conn.execute("SELECT count(*),count(DISTINCT buyer_id) FROM async_job_items WHERE job_id=%s",(job_id,)).fetchone()==(10000,10000)
    ids=[]
    for offset in range(0,10000,100):
        read=api.get(f"/v1/workspaces/{WORKSPACE_A}/jobs/{job_id}?offset={offset}&limit=100",headers=_h())
        assert read.status_code==200,read.text
        page=read.json()["data"]["result_page"]
        assert page["total"]==10000 and len(page["items"])==100;ids.extend(i["id"] for i in page["items"])
    assert len(ids)==len(set(ids))==10000
    old_retry=api.post(f"/v1/workspaces/{WORKSPACE_A}/jobs/{job_id}/retry-failed",json={},headers=_h(key="q08-no-blind-retry"))
    assert old_retry.status_code==409 and old_retry.json()["code"]=="MANIFEST_REVIEW_REQUIRED"
    child=_preview(api,owner,filters={},source_job_id=str(job_id));assert child["count"]==50 and child["digest"]!=manifest["digest"]
    retried=_execute(api,child);assert retried.status_code==200 and retried.json()["data"]["updated"]==50,retried.text
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT count(*) FROM project_buyers WHERE version=2 AND workspace_id=%s",(WORKSPACE_A,)).fetchone()[0]==9950
        assert conn.execute("SELECT count(*) FROM project_buyers WHERE version=3 AND workspace_id=%s",(WORKSPACE_A,)).fetchone()[0]==50


@pytest.mark.parametrize("bad",[{"digest":"0"*64},{"confirmation":False},{"confirmation":1},{"actor_user_id":str(uuid.uuid4())}])
def test_exact_manifest_confirmation_is_required_and_denial_atomic(api,seeded,bad):
    _seed_many(seeded,2);manifest=_preview(api,_admin_membership(seeded));response=_execute(api,manifest,**bad)
    assert response.status_code in {412,422},response.text
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT status,version FROM bulk_manifests WHERE id=%s",(manifest["id"],)).fetchone()==("ready",1)
        assert conn.execute("SELECT count(*) FROM project_buyers WHERE version>1").fetchone()[0]==0


def test_other_actor_scope_current_roles_owner_and_expiry_cannot_execute(api,seeded,monkeypatch):
    from tests.test_buyer_review_db import ADMIN,OPERATOR,VIEWER
    import buyeros_api.services.bulk_manifest as service
    from datetime import datetime,timezone,timedelta
    _seed_many(seeded,2);owner=_admin_membership(seeded);manifest=_preview(api,owner)
    assert api.get(ROOT+f"/{manifest['id']}",headers=_h(subject=ADMIN)).status_code==404
    assert api.post(ROOT,json={"filters":{},"excluded_ids":[],"operation":"assignBuyerOwners","target":{"owner_membership_id":None},"reason":"Viewer cannot attest"},headers=_h(subject=VIEWER)).status_code==403
    with psycopg.connect(seeded) as conn:conn.execute("UPDATE memberships SET active=false WHERE id=%s",(owner,))
    assert _execute(api,manifest).status_code==422
    with psycopg.connect(seeded) as conn:
        conn.execute("UPDATE memberships SET active=true WHERE id=%s",(owner,))
        conn.execute("UPDATE memberships SET roles='{viewer}' WHERE user_id=%s",(str(uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR)),))
    assert _execute(api,manifest).status_code==403
    with psycopg.connect(seeded) as conn:conn.execute("UPDATE memberships SET roles='{operator}' WHERE user_id=%s",(str(uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR)),))
    class Expired(datetime):
        @classmethod
        def now(cls,tz=None):return datetime.now(timezone.utc)+timedelta(hours=1)
    monkeypatch.setattr(service,'datetime',Expired)
    assert _execute(api,manifest).status_code==412


def test_exclusions_and_one_statement_snapshot_keep_exact_versions(api,seeded,monkeypatch):
    import buyeros_api.services.bulk_manifest as service
    _seed_many(seeded,1001)
    with psycopg.connect(seeded) as db:
        excluded=[str(r[0]) for r in db.execute('SELECT id FROM project_buyers WHERE workspace_id=%s ORDER BY id LIMIT 2',(WORKSPACE_A,)).fetchall()]
    original=service.add_digest;changed=False
    def concurrent_version_change(digest,ordinal,buyer_id,version):
        nonlocal changed
        if ordinal==249 and not changed:
            changed=True
            with psycopg.connect(seeded) as db:db.execute('UPDATE project_buyers SET version=2 WHERE workspace_id=%s',(WORKSPACE_A,))
        original(digest,ordinal,buyer_id,version)
    monkeypatch.setattr(service,'add_digest',concurrent_version_change)
    manifest=_preview(api,_admin_membership(seeded),excluded_ids=excluded)
    assert manifest['count']==999 and changed
    with psycopg.connect(seeded) as db:
        assert db.execute('SELECT count(*),min(expected_version),max(expected_version) FROM bulk_manifest_items WHERE manifest_id=%s',(manifest['id'],)).fetchone()==(999,1,1)
        assert db.execute('SELECT count(*) FROM bulk_manifest_items WHERE manifest_id=%s AND buyer_id=ANY(%s::uuid[])',(manifest['id'],excluded)).fetchone()[0]==0
        assert db.execute('SELECT min(version),max(version) FROM project_buyers WHERE workspace_id=%s',(WORKSPACE_A,)).fetchone()==(2,2)


def test_concurrent_same_preview_and_execute_key_produces_one_job_outbox(api,seeded):
    from concurrent.futures import ThreadPoolExecutor
    _seed_many(seeded,101);owner=_admin_membership(seeded)
    body={'filters':{'q':'Q08'},'excluded_ids':[],'operation':'assignBuyerOwners','target':{'owner_membership_id':owner},'reason':'Concurrent exact review'}
    preview_headers=_h(key='q08-concurrent-preview')  # initialize fictional signing key before concurrent requests
    with ThreadPoolExecutor(max_workers=2) as pool:
        previews=list(pool.map(lambda _:api.post(ROOT,json=body,headers=preview_headers),range(2)))
    assert [r.status_code for r in previews]==[201,201];assert previews[0].json()['data']==previews[1].json()['data'];manifest=previews[0].json()['data']
    with ThreadPoolExecutor(max_workers=2) as pool:executions=list(pool.map(lambda _:_execute(api,manifest,'q08-concurrent-execute'),range(2)))
    assert [r.status_code for r in executions]==[202,202];assert executions[0].json()['data']==executions[1].json()['data']
    with psycopg.connect(seeded) as db:
        assert db.execute('SELECT count(*) FROM bulk_manifests').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM async_jobs WHERE manifest_id=%s',(manifest['id'],)).fetchone()[0]==1
        assert db.execute("SELECT count(*) FROM outbox_events WHERE event_type='bulk.mutate'").fetchone()[0]==1
        assert db.execute("SELECT count(*) FROM audit_events WHERE action='executeBulkManifest'").fetchone()[0]==1


def test_cancel_manifest_retains_committed_chunk_and_cancels_only_pending(api,seeded):
    from buyeros_api.api.deps import tenant_scoped
    from buyeros_api.services.bulk_service import apply_bulk_chunk
    _seed_many(seeded,101);manifest=_preview(api,_admin_membership(seeded));job_id=uuid.UUID(_execute(api,manifest).json()['data']['id'])
    async def chunk():
        async with tenant_scoped(uuid.UUID(WORKSPACE_A)) as session:return await apply_bulk_chunk(session,job_id)
    assert asyncio.run(chunk())['processed']==50
    response=api.post(f'/v1/workspaces/{WORKSPACE_A}/jobs/{job_id}/cancel',json={},headers=_h(key='q08-cancel'))
    assert response.status_code==200,response.text
    assert asyncio.run(chunk())['processed']==50
    assert asyncio.run(chunk())['processed']==1
    assert asyncio.run(chunk())['processed']==0
    with psycopg.connect(seeded) as db:
        assert db.execute('SELECT status,processed,updated FROM async_jobs WHERE id=%s',(job_id,)).fetchone()==('cancelled',101,50)
        assert db.execute('SELECT count(*) FROM project_buyers WHERE version=2').fetchone()[0]==50
        assert db.execute('SELECT count(*) FROM async_job_items WHERE job_id=%s AND status=\'cancelled\'',(job_id,)).fetchone()[0]==51


def test_manifest_forced_rls_frozen_basis_and_digest_tamper_denies_execute(api,seeded):
    from tests.test_buyer_review_db import WORKSPACE_B
    _seed_many(seeded,2);manifest=_preview(api,_admin_membership(seeded))
    with psycopg.connect(seeded) as db:
        for table in ['bulk_manifests','bulk_manifest_items']:
            assert db.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname=%s',(table,)).fetchone()==(True,True)
            assert db.execute("SELECT has_table_privilege('buyeros_worker',%s,'INSERT,UPDATE,DELETE')",(table,)).fetchone()==(False,)
        with pytest.raises(psycopg.errors.RaiseException):
            with db.transaction():db.execute("UPDATE bulk_manifests SET specification=specification||'{\"reason\":\"tamper\"}'::jsonb WHERE id=%s",(manifest['id'],))
        db.execute('SET LOCAL ROLE buyeros_api');db.execute("SELECT set_config('app.workspace_id',%s,true)",(WORKSPACE_B,))
        assert db.execute('SELECT count(*) FROM bulk_manifests').fetchone()[0]==0
        db.execute("SELECT set_config('app.workspace_id',%s,true)",(WORKSPACE_A,))
        assert db.execute('SELECT count(*) FROM bulk_manifest_items WHERE manifest_id=%s',(manifest['id'],)).fetchone()[0]==2
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with db.transaction():db.execute('UPDATE bulk_manifest_items SET expected_version=2 WHERE manifest_id=%s',(manifest['id'],))
    # Owner-only corruption rehearsal: digest revalidation must still fail closed.
    with psycopg.connect(seeded) as db:db.execute('UPDATE bulk_manifest_items SET expected_version=2 WHERE manifest_id=%s',(manifest['id'],))
    response=_execute(api,manifest);assert response.status_code==412,response.text
    with psycopg.connect(seeded) as db:assert db.execute('SELECT count(*) FROM async_jobs').fetchone()[0]==0


def test_0037_empty_roundtrip_and_data_preserving_downgrade_refusal(api,seeded,monkeypatch):
    from alembic import command
    from alembic.config import Config
    from tests.test_buyer_review_db import ALEMBIC_INI,SERVICE_ROOT
    monkeypatch.setenv('BUYEROS_DATABASE_URL',seeded)
    from buyeros_api.settings import get_settings
    get_settings.cache_clear()
    config=Config(str(ALEMBIC_INI));config.set_main_option('script_location',str(SERVICE_ROOT/'alembic'))
    command.downgrade(config,'0036_checkpoint_schema_grants')
    with psycopg.connect(seeded) as db:
        assert db.execute("SELECT to_regclass('bulk_manifests')").fetchone()[0] is None
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0036_checkpoint_schema_grants'
    command.upgrade(config,'head')
    from buyeros_api.settings import get_settings
    from tests.test_buyer_review_db import runtime_role_dsn
    monkeypatch.setenv('BUYEROS_DATABASE_URL',runtime_role_dsn(seeded));get_settings.cache_clear()
    _seed_many(seeded,2);manifest=_preview(api,_admin_membership(seeded));monkeypatch.setenv('BUYEROS_DATABASE_URL',seeded);get_settings.cache_clear()
    with pytest.raises(RuntimeError,match='durable manifests'):command.downgrade(config,'0036_checkpoint_schema_grants')
    with psycopg.connect(seeded) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0037_bulk_manifests'
        assert db.execute('SELECT count(*) FROM bulk_manifest_items WHERE manifest_id=%s',(manifest['id'],)).fetchone()[0]==2
    monkeypatch.setenv('BUYEROS_DATABASE_URL',runtime_role_dsn(seeded));get_settings.cache_clear()


@pytest.mark.parametrize("operation",["reviewBuyers","changeListMemberships"])
def test_manifest_other_operations_use_current_canonical_review_and_lists(api,seeded,operation):
    from tests.test_buyer_review_db import _seed_buyer,REVIEWER
    from tests.test_buyer_management_db import _new_list
    buyers=[_seed_buyer(seeded,name=f'Q08 Other {i}',fit='match') for i in range(2)]
    if operation=='reviewBuyers':
        target={'status':'accepted'};subject=REVIEWER
    else:
        target={'list_id':_new_list(api,key='q08-new-target'),'operation':'add'};subject=None
    body={'filters':{'q':'Q08 Other'},'excluded_ids':[],'operation':operation,'target':target,'reason':'Exact domain operation review'}
    headers=_h(subject=subject) if subject else _h()
    if operation=='reviewBuyers':assert api.post(ROOT,json=body,headers=_h(key='q08-review-denial')).status_code==403
    response=api.post(ROOT,json=body,headers=headers);assert response.status_code==201,response.text;manifest=response.json()['data']
    execute_headers={**headers,'Idempotency-Key':'q08-other-execute','If-Match':'"1"'}
    result=api.post(ROOT+f"/{manifest['id']}/execute",json={'digest':manifest['digest'],'confirmation':True},headers=execute_headers)
    assert result.status_code==200 and result.json()['data']['updated']==2,result.text
    with psycopg.connect(seeded) as db:
        if operation=='reviewBuyers':assert db.execute('SELECT count(*) FROM human_reviews WHERE project_buyer_id=ANY(%s::uuid[]) AND state=%s',(buyers,'accepted')).fetchone()[0]==2
        else:assert db.execute('SELECT count(*) FROM list_memberships WHERE list_id=%s AND buyer_id=ANY(%s::uuid[])',(target['list_id'],buyers)).fetchone()[0]==2
