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


def test_unimplemented_paths_match_openapi_spec():
    import yaml
    from pathlib import Path

    spec = yaml.safe_load(Path("../../docs/buyeros/contracts/openapi.proposed.yaml").read_text(encoding="utf-8"))
    paths = spec["paths"]
    for operation_id, (method, path) in UNIMPLEMENTED_OPERATIONS.items():
        assert path in paths, (operation_id, path)
        assert method in paths[path], (operation_id, method)
        assert paths[path][method]["operationId"] == operation_id


def test_unimplemented_declared_path_fails_closed_then_501():
    client = TestClient(create_app(), raise_server_exceptions=False)
    # Unconfigured auth: fail closed before any 501 is reachable.
    response = client.post(f"/v1/workspaces/{WORKSPACE}/projects/{PROJECT}/runs", json={})
    assert response.status_code == 401
