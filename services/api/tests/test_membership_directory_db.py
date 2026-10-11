"""Q02 U06/U07/U08/S06: disposable Postgres, runtime role, real JWT fixture."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import psycopg
import pytest
from fastapi.testclient import TestClient
from buyeros_api.api.app import create_app
from tests.contract_validation import assert_contract_response
from tests.test_buyer_review_db import ADMIN, OPERATOR, REVIEWER, VIEWER, WORKSPACE_A, WORKSPACE_B, _h, api
from tests import auth_fixtures as fx
ROOT=f"/v1/workspaces/{WORKSPACE_A}"

@pytest.fixture(autouse=True)
def clean_owned_directory(seeded):
    yield
    with psycopg.connect(seeded) as db:
        db.execute("DELETE FROM audit_events WHERE workspace_id=%s",(WORKSPACE_A,))
        db.execute("DELETE FROM memberships WHERE user_id IN (SELECT id FROM users WHERE subject LIKE 'directory-%' OR subject='auth0|q02-second-admin')")
        db.execute("DELETE FROM users WHERE subject LIKE 'directory-%' OR subject='auth0|q02-second-admin'")

@pytest.fixture
def directory(api,seeded):
    with psycopg.connect(seeded) as db:
        for i in range(246):
            user=uuid.uuid4() if i>=2 else uuid.UUID(f"7000000{i+1}-0000-4000-8000-000000c011de")
            db.execute("DELETE FROM users WHERE id=%s",(user,))
            name="Alex Chen" if i<2 else None if i==2 else "100%_safe" if i==3 else f"Fixture member {i:03d}"
            db.execute("INSERT INTO users(id,issuer,subject,display_name) VALUES (%s,%s,%s,%s)",(user,fx.ISSUER,f"directory-{user}",name))
            db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES (%s,%s,%s,'{viewer}',%s)",(uuid.UUID(f"10000000-0000-4000-8000-{i:012x}"),WORKSPACE_A,user,i!=245))
        ordered=db.execute("SELECT id,user_id FROM memberships WHERE workspace_id=%s ORDER BY id",(WORKSPACE_A,)).fetchall()
        target=ordered[100];db.execute("UPDATE users SET display_name='Search target 101' WHERE id=%s",(target[1],))
    return api,ordered,target

def test_u06_all_250_members_paged_and_search_target_101(directory):
    client,ordered,target=directory;ids=[]
    for offset in range(0,250,20):
        response=client.get(f"{ROOT}/memberships?offset={offset}&limit=20",headers=_h(subject=ADMIN))
        assert response.status_code==200,response.text
        assert_contract_response("MembershipPageResponse",response.json())
        page=response.json()["data"];assert (page["total"],page["offset"],page["limit"])==(250,offset,20)
        ids.extend(row["id"] for row in page["items"])
    assert ids==[str(row[0]) for row in ordered] and len(set(ids))==250
    for query in ("Search target 101",str(target[1]),str(target[0])):
        response=client.get(f"{ROOT}/memberships",params={"q":query,"limit":20},headers=_h(subject=ADMIN))
        assert response.status_code==200,response.text
        assert response.json()["data"]["total"]==1
        assert response.json()["data"]["items"][0]["user_id"]==str(target[1])
    assert client.get(f"{ROOT}/memberships",params={"q":"100%_safe"},headers=_h(subject=ADMIN)).json()["data"]["total"]==1
    empty=client.get(f"{ROOT}/memberships?q=absent",headers=_h(subject=ADMIN)).json()["data"]
    assert empty["total"]==0 and empty["items"]==[]
    for query in ("limit=101","q="+"x"*201,"offset=-1"):
        assert client.get(f"{ROOT}/memberships?{query}",headers=_h(subject=ADMIN)).status_code==422

def test_u07_duplicate_names_full_ids_and_no_identity_secrets(directory):
    client,_,_=directory
    response=client.get(f"{ROOT}/memberships?q=Alex",headers=_h(subject=ADMIN));assert response.status_code==200,response.text
    rows=response.json()["data"]["items"]
    assert len(rows)==2 and {r["display_name"] for r in rows}=={"Alex Chen"}
    assert len({r["user_id"] for r in rows})==2 and len({r["user_id"][-8:] for r in rows})==1
    rows2=client.get(f"{ROOT}/memberships?limit=100",headers=_h(subject=ADMIN)).json()["data"]["items"]
    fallback=next(r for r in rows2 if r["id"].endswith("000000000002"));assert fallback["display_name"]==fallback["user_id"]
    assert all(not ({"issuer","subject","email","token"}&set(row)) for row in rows)

def test_s06_directory_role_and_tenant_boundaries(directory):
    client,_,_=directory
    for subject in (VIEWER,REVIEWER,OPERATOR):
        assert client.get(f"{ROOT}/memberships",headers=_h(subject=subject)).status_code==403
    for path in ("memberships","eligible-assignees"):
        response=client.get(f"/v1/workspaces/{WORKSPACE_B}/{path}",headers=_h(subject=ADMIN))
        assert response.status_code==404 and "Alex" not in response.text
    assert client.get(f"{ROOT}/memberships").status_code==401

def test_s06_eligible_projection_and_revocation(directory,seeded):
    client,_,target=directory
    for subject in (ADMIN,OPERATOR):
        response=client.get(f"{ROOT}/eligible-assignees?q=Search target 101",headers=_h(subject=subject))
        assert response.status_code==200,response.text
        assert_contract_response("EligibleAssigneePageResponse",response.json())
        assert response.json()["data"]["total"]==1
        assert response.json()["data"]["items"]==[{"membership_id":str(target[0]),"user_id":str(target[1]),"display_name":"Search target 101","version":1}]
    for subject in (REVIEWER,VIEWER):
        assert client.get(f"{ROOT}/eligible-assignees",headers=_h(subject=subject)).status_code==403
    assert client.get(f"{ROOT}/eligible-assignees?limit=100",headers=_h(subject=OPERATOR)).json()["data"]["total"]==249
    with psycopg.connect(seeded) as db:db.execute("UPDATE memberships SET active=false,version=version+1 WHERE id=%s",(target[0],))
    assert client.get(f"{ROOT}/eligible-assignees?q=Search target 101",headers=_h(subject=OPERATOR)).json()["data"]["items"]==[]
    response=client.post(f"{ROOT}/projects/a0000000-0000-4000-8000-000000000001/buyer-owner-assignments",json={"selection":{"kind":"explicit","buyers":[{"id":"a7000000-0000-4000-8000-000000000001","version":1}]},"owner_membership_id":str(target[0]),"reason":"Fixture reassignment"},headers=_h(subject=OPERATOR,key="q02-revoked-owner"))
    assert response.status_code==422,response.text

def test_u08_two_admins_concurrent_self_demotions_leave_one_admin(api,seeded):
    second="auth0|q02-second-admin";user=uuid.uuid4();member=uuid.uuid4()
    with psycopg.connect(seeded) as db:
        db.execute("INSERT INTO users(id,issuer,subject) VALUES (%s,%s,%s)",(user,fx.ISSUER,second))
        db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES (%s,%s,%s,'{workspace_admin}',true)",(member,WORKSPACE_A,user))
        first=db.execute("SELECT m.id FROM memberships m JOIN users u ON u.id=m.user_id WHERE m.workspace_id=%s AND u.subject=%s",(WORKSPACE_A,ADMIN)).fetchone()[0]
    barrier=Barrier(2)
    def demote(subject,target):
        with TestClient(create_app(),raise_server_exceptions=False) as client:
            barrier.wait(timeout=10)
            return client.patch(f"{ROOT}/memberships/{target}",json={"roles":["viewer"],"active":True,"reason":"Fixture concurrent duty rotation"},headers=_h(subject=subject,key=f"q02-demote-{target}",**{"If-Match":'"1"'}))
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(demote,ADMIN,first),pool.submit(demote,second,member)];responses=[f.result(timeout=30) for f in futures]
    assert sorted(r.status_code for r in responses)==[200,409],[r.text for r in responses]
    assert next(r for r in responses if r.status_code==409).json()["code"]=="LAST_ADMIN"
    with psycopg.connect(seeded) as db:
        assert db.execute("SELECT count(*) FROM memberships WHERE workspace_id=%s AND active AND 'workspace_admin'=ANY(roles)",(WORKSPACE_A,)).fetchone()[0]==1
        assert db.execute("SELECT count(*) FROM audit_events WHERE workspace_id=%s AND action='membership.updated'",(WORKSPACE_A,)).fetchone()[0]==1


def test_s06_waiting_admin_write_rechecks_current_authority(api,seeded):
    import time
    from hashlib import sha256
    lock_id=int.from_bytes(sha256(f"membership-admin:{WORKSPACE_A}".encode()).digest()[:8],"big",signed=True)
    with psycopg.connect(seeded) as owner:
        target=owner.execute("SELECT m.id FROM memberships m JOIN users u ON u.id=m.user_id WHERE m.workspace_id=%s AND u.subject=%s",(WORKSPACE_A,REVIEWER)).fetchone()[0]
    with ThreadPoolExecutor(max_workers=1) as pool:
        with psycopg.connect(seeded) as blocker:
            blocker.execute("SELECT pg_advisory_xact_lock(%s)",(lock_id,))
            def mutate():
                with TestClient(create_app(),raise_server_exceptions=False) as client:
                    return client.patch(f"{ROOT}/memberships/{target}",json={"roles":["viewer"],"active":True,"reason":"Fixture waiting administrator"},headers=_h(subject=ADMIN,key="q02-waiting-admin",**{"If-Match":'"1"'}))
            pending=pool.submit(mutate)
            deadline=time.monotonic()+10
            with psycopg.connect(seeded,autocommit=True) as observer:
                while time.monotonic()<deadline:
                    if observer.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event='advisory'").fetchone()[0]:break
                    time.sleep(0.05)
                else:raise AssertionError('request did not reach the existing admin advisory lock')
            blocker.execute("UPDATE memberships SET roles='{viewer}',version=version+1 WHERE workspace_id=%s AND user_id=(SELECT id FROM users WHERE subject=%s)",(WORKSPACE_A,ADMIN))
        response=pending.result(timeout=20)
    assert response.status_code==403,response.text
    with psycopg.connect(seeded) as db:
        assert db.execute("SELECT roles,version FROM memberships WHERE id=%s",(target,)).fetchone()==(['reviewer'],1)
        assert db.execute("SELECT count(*) FROM audit_events WHERE workspace_id=%s AND action='membership.updated'",(WORKSPACE_A,)).fetchone()[0]==0


def test_u07_pre_q02_membership_replay_keeps_business_result_and_new_projection(api,seeded):
    with psycopg.connect(seeded) as db:
        target=db.execute("SELECT m.id FROM memberships m JOIN users u ON u.id=m.user_id WHERE m.workspace_id=%s AND u.subject=%s",(WORKSPACE_A,REVIEWER)).fetchone()[0]
    path=f"{ROOT}/memberships/{target}";headers=_h(subject=ADMIN,key="q02-legacy-replay",**{"If-Match":'"1"'})
    body={"roles":["viewer"],"active":True,"reason":"Fixture legacy response"}
    changed=api.patch(path,json=body,headers=headers);assert changed.status_code==200,changed.text
    original=changed.json()["data"]
    # Model an existing pre-Q02 idempotency response; do not migrate/rewrite history in production.
    with psycopg.connect(seeded) as db:
        db.execute("UPDATE idempotency_records SET response=response-'display_name' WHERE workspace_id=%s AND operation_id='updateMembership' AND key='q02-legacy-replay'",(WORKSPACE_A,))
    replay=api.patch(path,json=body,headers=headers);assert replay.status_code==200,replay.text
    assert_contract_response('MembershipResponse',replay.json())
    assert replay.json()['data']==original
    assert replay.headers['etag']=='"2"'
    with psycopg.connect(seeded) as db:
        assert db.execute("SELECT version FROM memberships WHERE id=%s",(target,)).fetchone()[0]==2
        assert db.execute("SELECT count(*) FROM audit_events WHERE workspace_id=%s AND action='membership.updated'",(WORKSPACE_A,)).fetchone()[0]==1
        assert 'display_name' not in db.execute("SELECT response FROM idempotency_records WHERE workspace_id=%s AND key='q02-legacy-replay'",(WORKSPACE_A,)).fetchone()[0]
