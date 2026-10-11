"""Workspace listing must work through a real non-owner DB connection."""

import uuid

import psycopg
from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app
from buyeros_api.api.auth import Principal, get_principal
from buyeros_api.settings import get_settings
from tests.conftest import runtime_role_dsn


WORKSPACE_ID = "11111111-1111-4111-8111-111111111111"
USER_ID = uuid.UUID("c0000000-0000-4000-8000-000000000001")
MEMBERSHIP_ID = uuid.UUID("c0000000-0000-4000-8000-000000000002")


def test_list_workspaces_reads_a_real_membership_under_runtime_role(seeded, monkeypatch):
    with psycopg.connect(seeded, autocommit=True) as owner:
        owner.execute(
            "INSERT INTO users(id, issuer, subject) VALUES (%s, 'urn:buyeros:test', 'workspace-list')",
            (USER_ID,),
        )
        owner.execute(
            "INSERT INTO memberships(id, workspace_id, user_id, roles, active) "
            "VALUES (%s, %s, %s, %s, true)",
            (MEMBERSHIP_ID, WORKSPACE_ID, USER_ID, ["operator"]),
        )

    monkeypatch.setenv("BUYEROS_DATABASE_URL", runtime_role_dsn(seeded))
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_principal] = lambda: Principal(
        issuer="urn:buyeros:test", subject="workspace-list"
    )
    try:
        response = TestClient(app, raise_server_exceptions=False).get("/v1/workspaces")
        assert response.status_code == 200, response.text
        assert response.json()["data"]["items"] == [
            {
                "id": WORKSPACE_ID,
                "name": "A",
                "roles": ["operator"],
                "membership_id": str(MEMBERSHIP_ID),
                "data_mode": "live",
            }
        ]
    finally:
        get_settings.cache_clear()
        with psycopg.connect(seeded, autocommit=True) as owner:
            owner.execute("DELETE FROM memberships WHERE id = %s", (MEMBERSHIP_ID,))
            owner.execute("DELETE FROM users WHERE id = %s", (USER_ID,))


def test_list_workspaces_paginates_authorized_memberships(seeded, monkeypatch):
    second_membership = uuid.UUID("c0000000-0000-4000-8000-000000000003")
    with psycopg.connect(seeded, autocommit=True) as owner:
        owner.execute(
            "INSERT INTO users(id, issuer, subject) VALUES (%s, 'urn:buyeros:test', 'workspace-pages')",
            (USER_ID,),
        )
        owner.execute(
            "INSERT INTO memberships(id, workspace_id, user_id, roles, active) "
            "VALUES (%s, %s, %s, %s, true), (%s, %s, %s, %s, true)",
            (MEMBERSHIP_ID, WORKSPACE_ID, USER_ID, ["operator"], second_membership,
             "22222222-2222-4222-8222-222222222222", USER_ID, ["reviewer"]),
        )

    monkeypatch.setenv("BUYEROS_DATABASE_URL", runtime_role_dsn(seeded))
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_principal] = lambda: Principal(
        issuer="urn:buyeros:test", subject="workspace-pages"
    )
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            first = client.get("/v1/workspaces?offset=0&limit=1")
            second = client.get("/v1/workspaces?offset=1&limit=1")
            empty = client.get("/v1/workspaces?offset=2&limit=1")
            invalid = client.get("/v1/workspaces?limit=0")
        assert first.status_code == second.status_code == empty.status_code == 200
        assert first.json()["data"] == {
            "items": [{"id": WORKSPACE_ID, "name": "A", "roles": ["operator"], "membership_id": str(MEMBERSHIP_ID), "data_mode": "live"}],
            "offset": 0, "limit": 1, "total": 2,
        }
        assert second.json()["data"] == {
            "items": [{"id": "22222222-2222-4222-8222-222222222222", "name": "B",
                       "roles": ["reviewer"], "membership_id": str(second_membership), "data_mode": "live"}],
            "offset": 1, "limit": 1, "total": 2,
        }
        assert empty.json()["data"] == {"items": [], "offset": 2, "limit": 1, "total": 2}
        assert invalid.status_code == 422
        assert invalid.json()["code"] == "INVALID_REQUEST"
    finally:
        get_settings.cache_clear()
        with psycopg.connect(seeded, autocommit=True) as owner:
            owner.execute("DELETE FROM memberships WHERE id IN (%s, %s)", (MEMBERSHIP_ID, second_membership))
            owner.execute("DELETE FROM users WHERE id = %s", (USER_ID,))

# C61-06 reuses the peer's actual signed-fixture observations, without its RLS policy.
import asyncio
import httpx
import pytest
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from buyeros_api.api import auth, deps
from buyeros_api.api.jwks import JwksKeyCache
from buyeros_api.api.verifier import TokenVerifier
from tests import auth_fixtures as fx
from tests.contract_validation import assert_contract_response


@pytest.fixture
def directory_case(migrated, monkeypatch):
    users = [uuid.uuid4(), uuid.uuid4()]
    subjects = [f"q13-fixture-{user}" for user in users]
    workspaces, memberships = [], []
    with psycopg.connect(migrated, autocommit=True) as owner:
        owner.execute("ALTER ROLE buyeros_api LOGIN PASSWORD 'test-only'")
        owner.execute("GRANT USAGE ON SCHEMA public TO buyeros_api")
        for user, subject in zip(users, subjects):
            owner.execute("INSERT INTO users(id,issuer,subject) VALUES (%s,%s,%s)", (user, fx.ISSUER, subject))
    monkeypatch.setenv("BUYEROS_DATABASE_URL", runtime_role_dsn(migrated))
    monkeypatch.setenv("BUYEROS_AUTH0_ISSUER", fx.ISSUER)
    monkeypatch.setenv("BUYEROS_AUTH0_AUDIENCE", fx.AUDIENCE)
    get_settings.cache_clear()
    cache = JwksKeyCache(lambda: asyncio.sleep(0, result=fx.jwks_document()), cache_seconds=3600)
    monkeypatch.setattr(auth, "_verifier_from_settings", lambda: TokenVerifier(cache, issuer=fx.ISSUER, audience=fx.AUDIENCE))

    def add_workspace(actor=None, active=True):
        workspace, member = uuid.uuid4(), uuid.uuid4()
        with psycopg.connect(migrated, autocommit=True) as owner:
            owner.execute("INSERT INTO workspaces(id,name,data_mode) VALUES (%s,'Q13 fixture','live')", (workspace,))
            workspaces.append(workspace)
            if actor is not None:
                owner.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES (%s,%s,%s,'{operator}',%s)", (member,workspace,users[actor],active))
                memberships.append(member)
        return workspace, member

    try:
        yield dict(dsn=migrated, users=users, subjects=subjects, add=add_workspace,
                   headers=[{"Authorization":f"Bearer {fx.make_token(sub=s)}"} for s in subjects])
    finally:
        with psycopg.connect(migrated, autocommit=True) as owner:
            owner.execute("DELETE FROM memberships WHERE user_id=ANY(%s)", (users,))
            owner.execute("DELETE FROM workspaces WHERE id=ANY(%s)", (workspaces,))
            owner.execute("DELETE FROM users WHERE id=ANY(%s)", (users,))
        get_settings.cache_clear()


def test_directory_queries_bounded_with_unrelated_workspaces(directory_case):
    case = directory_case
    visible, member = case['add'](0)
    statements, maxima = [], []
    def observed(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(Engine, 'before_cursor_execute', observed)
    try:
        with TestClient(create_app(), raise_server_exceptions=False) as client:
            previous = 1
            for total in (1,10,100,1000):
                for _ in range(previous,total):
                    case['add']()
                statements.clear()
                result = client.get('/v1/workspaces?limit=1',headers=case['headers'][0])
                assert result.status_code == 200, result.text
                assert_contract_response('WorkspacePageResponse',result.json())
                assert result.json()['data'] == dict(items=[dict(id=str(visible),name='Q13 fixture',membership_id=str(member),roles=['operator'],data_mode='live')],offset=0,limit=1,total=1)
                maxima.append(len(statements))
                previous=total
        assert max(maxima)<=6, f"P09 SQL budget: observed {maxima} for W=1/10/100/1000"
        assert len(set(maxima))==1, f"P10 unrelated-workspace scan: {maxima}"
    finally:
        event.remove(Engine,'before_cursor_execute',observed)


def test_verified_subject_scope_revocation_and_real_pages(directory_case):
    case=directory_case
    own=[case['add'](0) for _ in range(21)]
    case['add'](1)
    case['add'](0,active=False)
    expected=sorted(str(row[0]) for row in own)
    with TestClient(create_app(),raise_server_exceptions=False) as client:
        first=client.get('/v1/workspaces?limit=20',headers=case['headers'][0])
        second=client.get('/v1/workspaces?offset=20&limit=20',headers=case['headers'][0])
        empty=client.get('/v1/workspaces?offset=21&limit=20',headers=case['headers'][0])
        assert first.status_code==second.status_code==empty.status_code==200
        assert [r['id'] for r in first.json()['data']['items']+second.json()['data']['items']]==expected
        assert first.json()['data']['total']==second.json()['data']['total']==21
        assert empty.json()['data']['items']==[] and empty.json()['data']['total']==21
        unknown=client.get('/v1/workspaces',headers={'Authorization':f"Bearer {fx.make_token(sub='not-mapped')}"})
        assert unknown.status_code==200 and unknown.json()['data']['total']==0
        wrong=client.get('/v1/workspaces',headers={'Authorization':f"Bearer {fx.make_token(iss='https://another.fixture.invalid/',sub=case['subjects'][0])}"})
        assert wrong.status_code==401
        with psycopg.connect(case['dsn'],autocommit=True) as owner:
            owner.execute('UPDATE memberships SET active=false WHERE id=%s',(own[0][1],))
        revoked=client.get('/v1/workspaces',headers=case['headers'][0])
        assert revoked.status_code==200 and revoked.json()['data']['total']==20
        assert str(own[0][0]) not in [r['id'] for r in revoked.json()['data']['items']]


def test_pooled_member_nonmember_revoked_member_clears_actor_and_tenant(directory_case):
    case=directory_case
    own,member=case['add'](0)
    foreign,_=case['add'](1)
    async def exercise():
        app=create_app()
        pids=[]
        async with app.router.lifespan_context(app), httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://q13.fixture.invalid') as client:
            engine=deps.get_engine()
            for actor,expected in ((0,[own]),(1,[foreign]),(0,[own])):
                result=await client.get('/v1/workspaces',headers=case['headers'][actor])
                assert result.status_code==200
                assert [r['id'] for r in result.json()['data']['items']]==[str(r) for r in expected]
                async with engine.connect() as conn:
                    pid,actor_context,tenant_context=(await conn.execute(text("SELECT pg_backend_pid(),current_setting('app.user_id',true),current_setting('app.workspace_id',true)"))).one()
                    pids.append(pid)
                    assert actor_context in (None,'') and tenant_context in (None,'')
            assert len(set(pids))==1, 'same pooled backend must actually be reused'
            with psycopg.connect(case['dsn'],autocommit=True) as owner:
                owner.execute('UPDATE memberships SET active=false WHERE id=%s',(member,))
            result=await client.get('/v1/workspaces',headers=case['headers'][0])
            assert result.json()['data']['total']==0
        print(f'Q13 pool reuse observed: pids={pids}; actor/workspace reset; revocation visible')
    asyncio.run(exercise())


@pytest.mark.parametrize('count',[21,101])
def test_directory_real_twenty_row_pages_read_every_visible_workspace_once(directory_case,count):
    case=directory_case
    expected=sorted(str(case['add'](0)[0]) for _ in range(count))
    case['add'](1)
    actual=[]
    with TestClient(create_app(),raise_server_exceptions=False) as client:
        for offset in range(0,count+20,20):
            result=client.get(f'/v1/workspaces?offset={offset}&limit=20&user_id={case["users"][1]}',headers=case['headers'][0])
            assert result.status_code==200
            assert_contract_response('WorkspacePageResponse',result.json())
            page=result.json()['data']
            assert page['total']==count and page['offset']==offset and page['limit']==20
            actual.extend(row['id'] for row in page['items'])
    assert actual==expected and len(set(actual))==count



def test_directory_oversized_offset_is_empty_instead_of_database_overflow(directory_case):
    case=directory_case;case['add'](0)
    offset=2**100
    with TestClient(create_app(),raise_server_exceptions=False) as client:
        result=client.get(f'/v1/workspaces?offset={offset}&limit=1',headers=case['headers'][0])
        assert result.status_code==200,result.text
        assert result.json()['data']=={'items':[],'offset':offset,'limit':1,'total':1}
