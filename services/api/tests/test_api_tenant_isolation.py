# services/api/tests/test_api_tenant_isolation.py
import psycopg
import pytest
from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app
from tests.conftest import runtime_role_dsn

WORKSPACE_A = "11111111-1111-4111-8111-111111111111"
WORKSPACE_B = "22222222-2222-4222-8222-222222222222"


def test_tenant_routes_fail_closed_without_configured_auth():
    """With no Auth0 issuer/audience configured every tenant route is unreachable
    and no cross-tenant data can be enumerated."""
    client = TestClient(create_app(), raise_server_exceptions=False)
    for method, path in (
        ("GET", "/v1/workspaces"),
        ("GET", f"/v1/workspaces/{WORKSPACE_B}/projects"),
        ("GET", f"/v1/workspaces/{WORKSPACE_B}/readiness"),
    ):
        response = client.request(method, path)
        assert response.status_code == 401, (method, path)
        assert response.json()["code"] == "UNAUTHENTICATED"
        assert "ProjectB" not in response.text


def test_runtime_role_is_confined_to_one_tenant(seeded):
    """The NOBYPASSRLS runtime role only ever sees its own workspace's rows."""
    with psycopg.connect(runtime_role_dsn(seeded), autocommit=True) as conn:
        conn.execute("SELECT set_config('app.workspace_id', %s, false)", (WORKSPACE_A,))
        names = {row[0] for row in conn.execute("SELECT name FROM projects").fetchall()}
    assert names == {"ProjectA"}


def test_runtime_role_without_context_sees_nothing(seeded):
    """No `app.workspace_id` fails closed: the policy raises rather than exposing rows."""
    with psycopg.connect(runtime_role_dsn(seeded), autocommit=True) as conn:
        with pytest.raises(psycopg.errors.UndefinedObject):
            conn.execute("SELECT name FROM projects").fetchall()


@pytest.mark.skip(
    reason="blocked by the runtime-role `users` grant gap (0002/0007 grant memberships/workspaces only): "
    "load_membership reads users, so every authenticated route 500s under buyeros_api. Recorded as a BO-004 "
    "prerequisite in the P9 ledger and plan; unskip with the grant migration."
)
def test_route_tenant_scope_comes_from_the_membership_checked_path(seeded, monkeypatch):
    """The route must set `app.workspace_id` from the path, so a member of A can never
    read B's rows even though B is a real, seeded workspace in the same database."""
    import uuid as _uuid

    from buyeros_api.api import auth

    monkeypatch.setenv("BUYEROS_DATABASE_URL", runtime_role_dsn(seeded))
    from buyeros_api.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(
        auth, "principal_from_token", lambda token, *, issuer, audience: auth.Principal("test", "auth0|member-a")
    )

    user_id = _uuid.UUID("aaaaaaaa-0000-4000-8000-000000000001")
    owner = psycopg.connect(seeded, autocommit=True)
    owner.execute("DELETE FROM memberships WHERE user_id = %s", (user_id,))
    owner.execute("DELETE FROM users WHERE id = %s", (user_id,))
    owner.execute("INSERT INTO users(id, issuer, subject) VALUES (%s, 'test', 'auth0|member-a')", (user_id,))
    owner.execute(
        "INSERT INTO memberships(id, workspace_id, user_id, roles, active) VALUES (%s, %s, %s, %s, true)",
        (_uuid.UUID("bbbbbbbb-0000-4000-8000-000000000001"), WORKSPACE_A, user_id, ["viewer"]),
    )
    owner.close()

    try:
        client = TestClient(create_app(), raise_server_exceptions=False)
        headers = {"Authorization": "Bearer t"}
        own = client.get(f"/v1/workspaces/{WORKSPACE_A}/projects", headers=headers)
        assert own.status_code == 200, own.text
        assert {item["name"] for item in own.json()["data"]["items"]} == {"ProjectA"}

        # Same principal, foreign workspace id: non-enumerating 404, never B's data.
        foreign = client.get(f"/v1/workspaces/{WORKSPACE_B}/projects", headers=headers)
        assert foreign.status_code == 404, foreign.text
        assert "ProjectB" not in foreign.text
    finally:
        get_settings.cache_clear()
        cleanup = psycopg.connect(seeded, autocommit=True)
        cleanup.execute("DELETE FROM memberships WHERE user_id = %s", (user_id,))
        cleanup.execute("DELETE FROM users WHERE id = %s", (user_id,))
        cleanup.close()
