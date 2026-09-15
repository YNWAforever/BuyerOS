# services/api/tests/test_api_tenant_isolation.py
import psycopg
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
    with psycopg.connect(runtime_role_dsn(seeded), autocommit=True) as conn:
        conn.execute("SELECT set_config('app.workspace_id', %s, false)", (WORKSPACE_B,))
        names = {row[0] for row in conn.execute("SELECT name FROM projects").fetchall()}
    assert names == {"ProjectB"}
