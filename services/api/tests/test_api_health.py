from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app
from buyeros_api.api.routes.health import capabilities_payload, readiness_payload

WORKSPACE = "11111111-1111-4111-8111-111111111111"


def test_liveness_needs_no_auth():
    client = TestClient(create_app())
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"


def test_readiness_and_capabilities_require_auth():
    client = TestClient(create_app(), raise_server_exceptions=False)
    for path in (f"/v1/workspaces/{WORKSPACE}/readiness", f"/v1/workspaces/{WORKSPACE}/capabilities"):
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.json()["code"] == "UNAUTHENTICATED"


def test_readiness_payload_matches_contract_without_secrets():
    data = readiness_payload()
    assert set(data) == {"ready", "database", "queue", "worker", "checked_at"}
    assert "password" not in str(data).lower()
    assert "postgresql://" not in str(data)


def test_readiness_payload_reflects_a_reachable_database_but_stays_unready():
    reachable = readiness_payload(database="ready")
    assert reachable["database"] == "ready"
    assert reachable["queue"] == "unavailable"
    assert reachable["worker"] == "unavailable"
    assert reachable["ready"] is False
    assert all(reachable[k] in {"ready", "unavailable"} for k in ("database", "queue"))
    assert reachable["worker"] in {"ready", "stale", "unavailable"}


def test_readiness_payload_reports_ready_only_when_every_dependency_is_ready():
    assert readiness_payload(database="ready", queue="ready", worker="ready")["ready"] is True


def test_capabilities_payload_matches_contract_without_secrets():
    page = capabilities_payload()
    assert set(page) == {"items", "offset", "limit", "total"}
    assert {item["name"] for item in page["items"]} == {
        "research", "contact_enrichment", "draft_generation", "mailbox", "crm",
    }
    for item in page["items"]:
        assert item["status"] in {"unconfigured", "blocked", "ready", "degraded", "disabled"}
        assert "password" not in str(item).lower()
