from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app
from buyeros_api.api.routes.health import capabilities_payload, readiness_payload
from tests.contract_validation import assert_contract_response

WORKSPACE = "11111111-1111-4111-8111-111111111111"


def test_liveness_needs_no_auth():
    client = TestClient(create_app())
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"
    assert_contract_response("HealthResponse", response.json())


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


def test_expired_worker_heartbeat_degrades_readiness():
    state = readiness_payload(database="ready", queue="ready", worker="stale")
    assert state["worker"] == "stale"
    assert state["ready"] is False


def test_capabilities_never_become_ready_from_an_unverified_env_value(monkeypatch):
    monkeypatch.setenv("BUYEROS_RESEARCH_PROVIDER_KEY", "fixture-only")
    page = capabilities_payload()
    assert next(x for x in page["items"] if x["name"] == "research")["status"] == "unconfigured"


def test_capabilities_include_bounded_responsibility_and_next_action():
    """Staff can identify the activation owner/action without exposing credentials or granting access."""
    from datetime import datetime

    page = capabilities_payload()
    for item in page["items"]:
        assert item["owner_role"] == "Release owner"
        assert 1 <= len(item["owner_role"]) <= 80
        assert 1 <= len(item["next_action"]) <= 512
        assert datetime.fromisoformat(item["checked_at"]).tzinfo is not None
        if item["name"] in {"mailbox", "crm"}:
            assert item["status"] == "disabled"
            assert item["next_action"] == "Keep delivery disabled. Use authorized exports and manual outcomes."
        else:
            assert item["status"] == "unconfigured"
            assert item["next_action"] == "Select a provider and complete bounded verification before activation."
    assert_contract_response("CapabilityPage", page)
