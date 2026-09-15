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


def test_approve_declares_the_required_if_match_precondition():
    import yaml
    from pathlib import Path

    spec = yaml.safe_load(Path("../../docs/buyeros/contracts/openapi.proposed.yaml").read_text(encoding="utf-8"))
    operation = spec["paths"]["/v1/workspaces/{workspace_id}/icp-versions/{icp_version_id}/approve"]["post"]
    parameters = {p.get("$ref", "").rsplit("/", 1)[-1]: p for p in operation["parameters"]}
    assert "IfMatch" in parameters
    assert spec["components"]["parameters"]["IfMatch"]["required"] is True
    assert operation["x-version-precondition"] == "If-Match"


def test_approve_rejects_a_missing_or_malformed_if_match():
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
