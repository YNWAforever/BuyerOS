"""T12 admin, preferences and audit acceptance against disposable PostgreSQL."""
import psycopg

from tests.contract_validation import assert_contract_response
from tests.test_buyer_review_db import ADMIN, OPERATOR, REVIEWER, VIEWER, WORKSPACE_A, WORKSPACE_B, _h, api

ROOT = f"/v1/workspaces/{WORKSPACE_A}"


def test_0017_preferences_rls_and_empty_rollback(migrated):
    from alembic import command
    from alembic.config import Config
    from tests.conftest import ALEMBIC_INI, SERVICE_ROOT
    with psycopg.connect(migrated) as conn:
        rows=conn.execute("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='workspace_preferences'").fetchall()
        assert rows == [(True,True)]
        version=conn.execute("SELECT column_default FROM information_schema.columns WHERE table_name='memberships' AND column_name='version'").fetchone()
        assert version and version[0] == '1'
    config=Config(str(ALEMBIC_INI));config.set_main_option('script_location',str(SERVICE_ROOT/'alembic'))
    command.downgrade(config,'0016_bulk_jobs')
    with psycopg.connect(migrated) as conn:
        assert conn.execute("SELECT to_regclass('workspace_preferences')").fetchone()[0] is None
    command.upgrade(config,'head')
    with psycopg.connect(migrated) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == '0033_api_rate_windows'


def _member_id(seeded, subject):
    with psycopg.connect(seeded) as conn:
        return str(conn.execute(
            "SELECT m.id FROM memberships m JOIN users u ON u.id=m.user_id "
            "WHERE m.workspace_id=%s AND u.subject=%s", (WORKSPACE_A, subject)
        ).fetchone()[0])


def test_admin_only_memberships_and_last_admin_guard(api, seeded):
    path = f"{ROOT}/memberships"
    for subject in (VIEWER, OPERATOR, REVIEWER):
        response = api.get(path, headers=_h(subject=subject))
        assert response.status_code == 403, response.text
    listed = api.get(path, headers=_h(subject=ADMIN))
    assert listed.status_code == 200, listed.text
    assert_contract_response("MembershipPageResponse", listed.json())
    own = _member_id(seeded, ADMIN)
    response = api.patch(f"{path}/{own}", json={"roles":["viewer"],"active":False,"reason":"Test sole admin guard"},
                         headers=_h(subject=ADMIN,key="t12-last-admin",**{"If-Match":'"1"'}))
    assert response.status_code in (409, 422), response.text
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT roles,active FROM memberships WHERE id=%s",(own,)).fetchone() == (['workspace_admin'],True)


def test_versioned_role_change_revokes_existing_session_immediately(api, seeded):
    member = _member_id(seeded, REVIEWER)
    path = f"{ROOT}/memberships/{member}"
    changed = api.patch(path,json={"roles":["viewer"],"active":True,"reason":"Duty rotation test"},
                        headers=_h(subject=ADMIN,key="t12-role-change",**{"If-Match":'"1"'}))
    assert changed.status_code == 200,changed.text
    assert_contract_response("MembershipResponse", changed.json())
    assert changed.json()['data']['version'] == 2
    denied = api.post(f"{ROOT}/projects/a0000000-0000-4000-8000-000000000001/buyer-reviews",
                      json={"selection":{"kind":"explicit","buyers":[{"id":"a7000000-0000-4000-8000-000000000001","version":1}]},"status":"accepted","reason":"Test review"},
                      headers=_h(subject=REVIEWER,key="t12-demoted-reviewer"))
    assert denied.status_code == 403,denied.text
    stale = api.patch(path,json={"roles":["operator"],"active":True,"reason":"Stale role test"},
                      headers=_h(subject=ADMIN,key="t12-stale-role",**{"If-Match":'"1"'}))
    assert stale.status_code == 412,stale.text
    replay = api.patch(path,json={"roles":["viewer"],"active":True,"reason":"Duty rotation test"},
                       headers=_h(subject=ADMIN,key="t12-role-change",**{"If-Match":'"1"'}))
    assert replay.status_code == 200 and replay.json()['data'] == changed.json()['data']


def test_preferences_zh_hk_persist_and_are_actor_workspace_scoped(api):
    path=f"{ROOT}/preferences"
    before=api.get(path,headers=_h(subject=VIEWER))
    assert before.status_code == 200,before.text
    assert_contract_response("PreferencesResponse",before.json())
    assert before.json()['data'] == {"locale":"en","default_markets":[],"version":1}
    updated=api.patch(path,json={"locale":"zh-HK","default_markets":["HK"]},
                      headers=_h(subject=VIEWER,key="t12-zh-preferences",**{"If-Match":'"1"'}))
    assert updated.status_code == 200,updated.text
    assert_contract_response("PreferencesResponse",updated.json())
    assert updated.json()['data']['version'] == 2
    assert api.get(path,headers=_h(subject=VIEWER)).json()['data']['locale'] == 'zh-HK'
    assert api.get(path,headers=_h(subject=OPERATOR)).json()['data']['locale'] == 'en'
    assert api.get(f"/v1/workspaces/{WORKSPACE_B}/preferences",headers=_h(subject=VIEWER)).status_code == 404


def test_audit_archive_reason_is_redacted_and_tenant_scoped(api, seeded):
    # Existing project archive mutation is the representative T01-T11 audit producer.
    target = _member_id(seeded, OPERATOR)
    changed=api.patch(f"{ROOT}/memberships/{target}",json={"roles":["operator"],"active":False,"reason":"Operator left pilot"},
                      headers=_h(subject=ADMIN,key="t12-archive-member",**{"If-Match":'"1"'}))
    assert changed.status_code == 200,changed.text
    page=api.get(f"{ROOT}/audit-events?offset=0&limit=20",headers=_h(subject=ADMIN))
    assert page.status_code == 200,page.text
    assert_contract_response("AuditEventPageResponse",page.json())
    assert any(e['action']=='membership.updated' and e.get('reason_code')=='operator_left_pilot' for e in page.json()['data']['items'])
    text=str(page.json()).lower()
    assert 'bearer ' not in text and 'auth0|' not in text and 'contact@' not in text
    assert api.get(f"{ROOT}/audit-events",headers=_h(subject=VIEWER)).status_code == 403
    assert api.get(f"/v1/workspaces/{WORKSPACE_B}/audit-events",headers=_h(subject=ADMIN)).status_code == 404


def test_readiness_uses_observed_worker_heartbeat_not_environment_flag(api, seeded):
    from datetime import datetime, timedelta, timezone
    path=f"{ROOT}/readiness"
    with psycopg.connect(seeded,autocommit=True) as owner:
        owner.execute("DELETE FROM worker_heartbeats")
        try:
            none=api.get(path,headers=_h(subject=ADMIN))
            assert none.status_code==200,none.text
            assert_contract_response("ReadinessResponse", none.json())
            assert none.json()['data']['database']=='ready'
            assert none.json()['data']['worker']=='unavailable'
            assert none.json()['data']['ready'] is False
            owner.execute("INSERT INTO worker_heartbeats(worker_id,observed_at,broker_state) VALUES (%s,%s,'ready')",
                          ('test-sweeper',datetime.now(timezone.utc)-timedelta(minutes=5)))
            stale=api.get(path,headers=_h(subject=ADMIN))
            assert stale.json()['data']['worker']=='stale'
            assert stale.json()['data']['queue']=='unavailable'
            owner.execute("UPDATE worker_heartbeats SET observed_at=%s WHERE worker_id='test-sweeper'",
                          (datetime.now(timezone.utc),))
            fresh=api.get(path,headers=_h(subject=ADMIN))
            assert fresh.json()['data']['worker']=='ready'
            assert fresh.json()['data']['queue']=='ready'
            assert fresh.json()['data']['ready'] is True
            assert api.get(path,headers=_h(subject=VIEWER)).status_code==403
        finally:
            owner.execute("DELETE FROM worker_heartbeats")


def test_capability_page_is_contract_valid_and_never_secret_bearing(api):
    response=api.get(f"{ROOT}/capabilities",headers=_h(subject=VIEWER))
    assert response.status_code==200,response.text
    assert_contract_response("CapabilityPageResponse",response.json())
    assert "fixture-only" not in str(response.json())


def test_operations_list_jobs_is_actor_scoped_and_paged(api, seeded):
    import uuid
    reviewer_user=uuid.uuid5(uuid.NAMESPACE_URL,REVIEWER)
    admin_user=uuid.uuid5(uuid.NAMESPACE_URL,ADMIN)
    with psycopg.connect(seeded,autocommit=True) as owner:
        for number,actor,status in ((1,reviewer_user,'failed'),(2,admin_user,'queued'),(3,reviewer_user,'completed')):
            owner.execute("INSERT INTO async_jobs(id,workspace_id,project_id,actor_user_id,kind,operation,command,status,requested) "
                          "VALUES (%s,%s,'a0000000-0000-4000-8000-000000000001',%s,'bulk_mutation','reviewBuyers','{}'::jsonb,%s,101)",
                          (f'a9000000-0000-4000-8000-{number:012x}',WORKSPACE_A,actor,status))
    path=f"{ROOT}/jobs"
    reviewer=api.get(path+'?offset=0&limit=1',headers=_h(subject=REVIEWER))
    assert reviewer.status_code==200,reviewer.text
    assert_contract_response('AsyncJobPageResponse',reviewer.json())
    assert reviewer.json()['data']['total']==2
    assert len(reviewer.json()['data']['items'])==1
    assert api.get(path+'?offset=1&limit=1',headers=_h(subject=REVIEWER)).json()['data']['total']==2
    admin=api.get(path+'?status=failed',headers=_h(subject=ADMIN))
    assert admin.status_code==200,admin.text
    assert admin.json()['data']['total']==1
    assert admin.json()['data']['items'][0]['status']=='failed'
    assert api.get(path,headers=_h(subject=VIEWER)).json()['data']['total']==0
    assert api.get(f"/v1/workspaces/{WORKSPACE_B}/jobs",headers=_h(subject=ADMIN)).status_code==404


def test_existing_project_write_adds_one_redacted_audit_event_on_replay(api):
    from tests.test_api_projects_db import CREATE
    request_id = "c2bf90be-874c-45eb-a36e-16d06ec72151"
    headers = _h(subject=OPERATOR, key="t12-project-audit", **{"X-Request-ID": request_id})
    created = api.post(f"{ROOT}/projects", json=CREATE, headers=headers)
    assert created.status_code == 201, created.text
    replay = api.post(f"{ROOT}/projects", json=CREATE, headers=headers)
    assert replay.status_code == 201, replay.text
    events = api.get(f"{ROOT}/audit-events?limit=100", headers=_h(subject=ADMIN))
    assert events.status_code == 200, events.text
    project_id = created.json()["data"]["id"]
    matches = [event for event in events.json()["data"]["items"]
               if event["action"] == "project.created" and event.get("entity_id") == project_id]
    assert len(matches) == 1
    assert matches[0]["request_id"] == request_id
    assert "Industrial sensing" not in str(events.json())
