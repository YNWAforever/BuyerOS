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
