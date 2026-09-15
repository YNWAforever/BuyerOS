import uuid

from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app

WORKSPACE = "11111111-1111-4111-8111-111111111111"
PROJECT = "22222222-2222-4222-8222-222222222222"
ICP = "33333333-3333-4333-8333-333333333333"


def test_unauthenticated_requests_are_rejected():
    client = TestClient(create_app(), raise_server_exceptions=False)
    requests = [
        ("GET", "/v1/workspaces"),
        ("GET", f"/v1/workspaces/{WORKSPACE}/projects"),
        ("POST", f"/v1/workspaces/{WORKSPACE}/projects"),
        ("GET", f"/v1/workspaces/{WORKSPACE}/projects/{PROJECT}"),
        ("GET", f"/v1/workspaces/{WORKSPACE}/projects/{PROJECT}/icp-versions"),
        ("POST", f"/v1/workspaces/{WORKSPACE}/projects/{PROJECT}/icp-versions"),
        ("POST", f"/v1/workspaces/{WORKSPACE}/icp-versions/{ICP}/approve"),
    ]
    for method, path in requests:
        response = client.request(method, path, json={})
        assert response.status_code == 401, (method, path)
        assert response.json()["code"] == "UNAUTHENTICATED"


def test_implemented_routes_match_openapi_operation_ids():
    import yaml
    from pathlib import Path

    spec = yaml.safe_load(Path("../../docs/buyeros/contracts/openapi.proposed.yaml").read_text(encoding="utf-8"))
    paths = spec["paths"]
    expected = (
        ("/v1/workspaces", "get", "listWorkspaces"),
        ("/v1/workspaces/{workspace_id}/projects", "get", "listProjects"),
        ("/v1/workspaces/{workspace_id}/projects", "post", "createProject"),
        ("/v1/workspaces/{workspace_id}/projects/{project_id}", "get", "getProject"),
        ("/v1/workspaces/{workspace_id}/projects/{project_id}/icp-versions", "get", "listICPVersions"),
        ("/v1/workspaces/{workspace_id}/projects/{project_id}/icp-versions", "post", "saveICPVersion"),
        ("/v1/workspaces/{workspace_id}/icp-versions/{icp_version_id}/approve", "post", "approveICPVersion"),
    )
    for path, method, operation_id in expected:
        assert path in paths, path
        assert method in paths[path], (path, method)
        assert paths[path][method]["operationId"] == operation_id


def test_the_app_actually_exposes_every_implemented_route():
    """The YAML-only check above passes even with no routes registered; this one does not."""
    client = TestClient(create_app(), raise_server_exceptions=False)
    expected = (
        ("GET", "/v1/workspaces"),
        ("GET", f"/v1/workspaces/{WORKSPACE}/projects"),
        ("POST", f"/v1/workspaces/{WORKSPACE}/projects"),
        ("GET", f"/v1/workspaces/{WORKSPACE}/projects/{PROJECT}"),
        ("GET", f"/v1/workspaces/{WORKSPACE}/projects/{PROJECT}/icp-versions"),
        ("POST", f"/v1/workspaces/{WORKSPACE}/projects/{PROJECT}/icp-versions"),
        ("POST", f"/v1/workspaces/{WORKSPACE}/icp-versions/{ICP}/approve"),
    )
    for method, path in expected:
        response = client.request(method, path, json={})
        assert response.status_code != 404, (method, path)


def test_implemented_response_fields_are_declared_by_the_contract():
    """P9 returns a *documented subset* of each contract entity (see the plan's deliberate gaps:
    the ORM models do not yet carry every filtered/sensitive field). This guard pins the shape we
    do return: every emitted key must be declared by the contract schema, so a renamed or invented
    field fails here instead of drifting silently. It does NOT assert full required-field coverage —
    that is the recorded BO-004/next-phase deferral."""
    import yaml
    from pathlib import Path

    spec = yaml.safe_load(Path("../../docs/buyeros/contracts/openapi.proposed.yaml").read_text(encoding="utf-8"))
    schemas = spec["components"]["schemas"]

    def properties(name: str) -> set[str]:
        return set(schemas[name].get("properties", {}))

    readiness_keys = properties("Readiness")
    capability_keys = properties("Capability")
    workspace_keys = properties("Workspace")
    project_keys = properties("Project")
    icp_keys = properties("ICPVersion")
    buyer_keys = properties("Buyer")

    from buyeros_api.api.routes.buyers import _buyer_data
    from buyeros_api.api.routes.health import capabilities_payload, readiness_payload
    from buyeros_api.api.routes.icp import _icp_data
    from buyeros_api.api.routes.projects import _project_data

    assert set(readiness_payload()) <= readiness_keys

    page_keys = properties("CapabilityPage")
    page = capabilities_payload()
    assert set(page) <= page_keys
    for item in page["items"]:
        assert set(item) <= capability_keys, set(item) - capability_keys

    # Every page wrapper the routes build inline must also use contract `*Page` keys.
    for schema in ("WorkspacePage", "ProjectPage", "ICPVersionPage", "BuyerPage"):
        assert {"items", "offset", "limit", "total"} <= properties(schema), schema
    assert properties("BuyerPage") >= {"snapshot_id", "expires_at"}

    class _Project:
        id = workspace_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
        name = "P"
        status = "active"

    assert set(_project_data(_Project())) <= project_keys

    class _Icp:
        id = workspace_id = project_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
        number = 1
        content_hash = "sha256:x"
        approved_at = None
        approved_by = None
        content: dict = {}

    assert set(_icp_data(_Icp())) <= icp_keys

    class _Buyer:
        id = workspace_id = project_id = company_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
        note = None

    class _Company:
        display_name = "C"

    assert set(_buyer_data(_Buyer(), _Company())) <= buyer_keys
    assert {"id", "name", "roles", "data_mode"} <= workspace_keys

    import yaml
    from pathlib import Path

    spec = yaml.safe_load(Path("../../docs/buyeros/contracts/openapi.proposed.yaml").read_text(encoding="utf-8"))
    operation = spec["paths"]["/v1/workspaces/{workspace_id}/icp-versions/{icp_version_id}/approve"]["post"]
    parameters = {p.get("$ref", "").rsplit("/", 1)[-1]: p for p in operation["parameters"]}
    assert "IfMatch" in parameters
    assert spec["components"]["parameters"]["IfMatch"]["required"] is True
    assert operation["x-version-precondition"] == "If-Match"


def test_approve_checks_auth_before_preconditions():
    client = TestClient(create_app(), raise_server_exceptions=False)
    path = f"/v1/workspaces/{WORKSPACE}/icp-versions/{ICP}/approve"

    absent = client.post(path, json={"content_hash": "sha256:x", "confirmation": True}, headers={"Idempotency-Key": "k"})
    assert absent.status_code == 401  # auth is checked before preconditions

    weak = client.post(
        path,
        json={"content_hash": "sha256:x", "confirmation": True},
        headers={"Idempotency-Key": "k", "If-Match": "4"},
    )
    assert weak.status_code == 401


def _approve_client_with_principal(monkeypatch):
    """A client whose auth succeeds, so the route's own precondition logic runs."""
    from fastapi import Depends

    from buyeros_api.api import auth
    from buyeros_api.api.app import create_app

    monkeypatch.setattr(
        auth, "principal_from_token", lambda token, *, issuer, audience: auth.Principal("test", "auth0|1")
    )
    app = create_app()

    @app.middleware("http")
    async def _accept_bearer(request, call_next):
        return await call_next(request)

    return TestClient(app, raise_server_exceptions=False)


def test_approve_rejects_a_missing_or_malformed_if_match(monkeypatch):
    """Regression guard: with auth satisfied, If-Match must be enforced (it was once absent)."""
    client = _approve_client_with_principal(monkeypatch)
    path = f"/v1/workspaces/{WORKSPACE}/icp-versions/{ICP}/approve"
    body = {"content_hash": "sha256:x", "confirmation": True}

    absent = client.post(path, json=body, headers={"Idempotency-Key": "k", "Authorization": "Bearer t"})
    assert absent.status_code == 400
    assert absent.json()["code"] == "INVALID_REQUEST"

    for weak in ("4", 'W/"4"', '"x"', '""'):
        response = client.post(
            path,
            json=body,
            headers={"Idempotency-Key": "k", "Authorization": "Bearer t", "If-Match": weak},
        )
        assert response.status_code == 400, weak
        assert response.json()["code"] == "INVALID_REQUEST"
