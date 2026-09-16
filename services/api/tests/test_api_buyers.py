from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app
from buyeros_api.api.unimplemented import UNIMPLEMENTED_OPERATIONS

WORKSPACE = "11111111-1111-4111-8111-111111111111"
PROJECT = "22222222-2222-4222-8222-222222222222"
RUN = "44444444-4444-4444-8444-444444444444"


def test_buyers_list_requires_auth():
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get(f"/v1/workspaces/{WORKSPACE}/projects/{PROJECT}/buyers")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_unimplemented_registry_uses_declared_contract_paths():
    assert UNIMPLEMENTED_OPERATIONS["startRun"] == (
        "post",
        "/v1/workspaces/{workspace_id}/projects/{project_id}/runs",
    )
    for method, path in UNIMPLEMENTED_OPERATIONS.values():
        assert method in {"get", "post", "patch", "delete"}
        assert path.startswith("/v1/")


def _contract_operations() -> dict:
    import yaml
    from pathlib import Path

    spec = yaml.safe_load(Path("../../docs/buyeros/contracts/openapi.proposed.yaml").read_text(encoding="utf-8"))
    operations = {}
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            if method in {"get", "post", "patch", "put", "delete"}:
                operations[operation["operationId"]] = (method, path)
    return operations


def test_unimplemented_paths_match_openapi_spec():
    paths = _contract_operations()
    for operation_id, (method, path) in UNIMPLEMENTED_OPERATIONS.items():
        assert operation_id in paths, operation_id
        assert paths[operation_id] == (method, path), operation_id


def test_registry_covers_every_unimplemented_contract_operation():
    """Regression guard: an out-of-slice operation must never silently 404."""
    implemented = {
        "getLiveness",
        "listWorkspaces",
        "listProjects",
        "createProject",
        "getProject",
        "listICPVersions",
        "saveICPVersion",
        "approveICPVersion",
        "getReadiness",
        "getCapabilities",
        "listBuyers",
        "getBuyer",
    }
    out_of_slice = set(_contract_operations()) - implemented
    assert out_of_slice, "contract parse produced no out-of-slice operations"
    assert out_of_slice == set(UNIMPLEMENTED_OPERATIONS)


def test_unimplemented_declared_path_fails_closed_then_501():
    client = TestClient(create_app(), raise_server_exceptions=False)
    # Unconfigured auth: fail closed before any 501 is reachable.
    response = client.post(f"/v1/workspaces/{WORKSPACE}/projects/{PROJECT}/runs", json={})
    assert response.status_code == 401


def test_every_registry_route_is_registered_on_its_declared_path():
    """A 405 here would mean a declared path exists but its method was never registered."""
    client = TestClient(create_app(), raise_server_exceptions=False)
    for operation_id, (method, path) in UNIMPLEMENTED_OPERATIONS.items():
        concrete = path.replace("{workspace_id}", WORKSPACE).replace("{project_id}", PROJECT)
        for placeholder in ("{run_id}", "{quote_id}", "{job_id}", "{draft_id}", "{export_id}",
                            "{outcome_id}", "{buyer_id}", "{list_id}", "{evidence_id}",
                            "{suppression_id}", "{budget_id}", "{document_id}", "{provider}"):
            concrete = concrete.replace(placeholder, "44444444-4444-4444-8444-444444444444")
        response = client.request(method, concrete, json={})
        assert response.status_code == 401, (operation_id, method, concrete)


def test_list_buyers_declares_the_required_snapshot_id():
    """Auth precedes validation, so assert the contract requirement in the app's schema."""
    from buyeros_api.api.app import create_app as _create_app

    schema = _create_app().openapi()
    operation = schema["paths"]["/v1/workspaces/{workspace_id}/projects/{project_id}/buyers"]["get"]
    query = [p for p in operation["parameters"] if p["in"] == "query"]
    snapshot = [p for p in query if p["name"] == "snapshot_id"]
    assert snapshot, "snapshot_id query parameter is not declared"
    assert snapshot[0]["required"] is True


def test_unimplemented_handler_actually_returns_501(monkeypatch):
    """The 401 test cannot prove 501; this drives the handler with a satisfied principal."""
    from buyeros_api.api import auth
    from buyeros_api.api.app import create_app as _create_app
    from buyeros_api.settings import get_settings

    monkeypatch.setenv("BUYEROS_AUTH0_ISSUER", "https://issuer.test/")
    monkeypatch.setenv("BUYEROS_AUTH0_AUDIENCE", "buyeros-api")
    get_settings.cache_clear()

    class _StubVerifier:
        async def verify(self, token):
            return auth.Principal(issuer="https://issuer.test/", subject="auth0|1")

    monkeypatch.setattr(auth, "_verifier_from_settings", lambda: _StubVerifier())
    try:
        client = TestClient(_create_app(), raise_server_exceptions=False)
        response = client.post(
            f"/v1/workspaces/{WORKSPACE}/projects/{PROJECT}/runs",
            json={},
            headers={"Authorization": "Bearer t"},
        )
        assert response.status_code == 501
        assert response.json()["code"] == "NOT_IMPLEMENTED"
    finally:
        get_settings.cache_clear()
