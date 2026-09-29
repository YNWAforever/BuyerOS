"""T02: malformed ICP requests fail before any immutable version is written."""

import psycopg
import pytest

from tests.icp_fixtures import valid_icp_payload
from tests.test_api_projects_db import WORKSPACE_A, _create, _h, api


def _count_versions(dsn, project_id):
    with psycopg.connect(dsn) as owner:
        return owner.execute(
            "SELECT count(*) FROM icp_versions WHERE workspace_id = %s AND project_id = %s",
            (WORKSPACE_A, project_id),
        ).fetchone()[0]


@pytest.mark.parametrize(
    "change",
    [
        lambda p: {},
        lambda p: {**p, "requirements": "invalid-string"},
        lambda p: {**p, "markets": 123},
        lambda p: {**p, "extra": "ignored before"},
        lambda p: {**p, "offer_facts": [{**p["offer_facts"][0], "id": "bad-uuid"}]},
        lambda p: {**p, "offer_facts": []},
        lambda p: {**p, "requirements": []},
        lambda p: {**p, "requirements": [{**p["requirements"][0], "category": "unknown"}]},
        lambda p: {**p, "offer_facts": [{**p["offer_facts"][0], "value": "x" * 20001}]},
        lambda p: {**p, "basis_offer_revision": 0},
    ],
)
def test_invalid_icp_never_writes(api, seeded, change):
    project_id = _create(api, "create-invalid-icp")
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}/icp-versions"
    response = api.post(path, json=change(valid_icp_payload()), headers=_h(key="save-invalid-icp"))
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "INVALID_REQUEST"
    assert _count_versions(seeded, project_id) == 0


def test_short_idempotency_key_never_writes(api, seeded):
    project_id = _create(api, "create-short-icp-key")
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}/icp-versions"
    response = api.post(path, json=valid_icp_payload(), headers=_h(key="k"))
    assert response.status_code == 400, response.text
    assert response.json()["code"] == "INVALID_REQUEST"
    assert _count_versions(seeded, project_id) == 0


def test_malformed_json_envelope(api, seeded):
    project_id = _create(api, "create-malformed-json")
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}/icp-versions"
    response = api.post(
        path,
        content='{"offer_facts":',
        headers={**_h(key="save-malformed"), "Content-Type": "application/json"},
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "INVALID_REQUEST"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    assert _count_versions(seeded, project_id) == 0


def test_unexpected_error_is_sanitized():
    from fastapi.testclient import TestClient
    from buyeros_api.api.app import create_app

    app = create_app()

    @app.get("/__test_unexpected_failure")
    def fail():
        raise RuntimeError("private-secret-marker")

    response = TestClient(app, raise_server_exceptions=False).get("/__test_unexpected_failure")
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert response.json()["retryable"] is True
    assert response.json()["request_id"]
    assert "private-secret-marker" not in response.text
