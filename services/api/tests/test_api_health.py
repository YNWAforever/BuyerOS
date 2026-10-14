from fastapi.testclient import TestClient
import pytest

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
    from buyeros_api.settings import Settings
    monkeypatch.setattr('buyeros_api.settings.get_settings', lambda: Settings(paid_admission_enabled=True))
    monkeypatch.setenv("BUYEROS_RESEARCH_PROVIDER_KEY", "fixture-only")
    page = capabilities_payload()
    assert next(x for x in page["items"] if x["name"] == "research")["status"] == "unconfigured"

def test_selected_but_invalid_provider_reports_its_current_blockers(monkeypatch):
    from buyeros_api.settings import Settings
    monkeypatch.setattr('buyeros_api.settings.get_settings', lambda: Settings(paid_admission_enabled=True))
    from buyeros_api.providers import registry
    from tests.test_provider_registry import fixture_registry
    selected,_=fixture_registry()
    monkeypatch.setattr(registry,'DEFAULT_REGISTRY',selected)
    research=next(x for x in capabilities_payload()['items'] if x['name']=='research')
    assert research['status']=='blocked'
    assert set(research['reason_codes'])=={'FIXTURE_IN_PRODUCTION','PROVIDER_UNSELECTED'}
    assert research['billable'] is False

@pytest.mark.parametrize('enabled', [False, True])
def test_capability_ready_state_uses_registry_without_starting_work(monkeypatch, enabled):
    from buyeros_api.providers import registry
    from buyeros_api.settings import Settings
    monkeypatch.setattr('buyeros_api.settings.get_settings', lambda: Settings(paid_admission_enabled=enabled))
    reads=[]
    def readiness(service,*,environment):
        reads.append((service,environment))
        return {'status':'ready','reason_codes':[],'actions':[]}
    monkeypatch.setattr(registry,'provider_readiness',readiness)
    items=capabilities_payload()['items']
    assert items[0]['status'] == ('ready' if enabled else 'disabled')
    assert items[0]['reason_codes'] == ([] if enabled else ['PAID_ADMISSION_DISABLED'])
    assert all(item['status']=='ready' and item['reason_codes']==[] for item in items[1:3])
    assert all(item['status']=='disabled' for item in items[3:])
    assert reads==[('search','production'),('contact','production'),('model','production')]


def test_paused_admission_preserves_provider_blockers_without_enabling_delivery(monkeypatch):
    from buyeros_api.providers import registry
    from buyeros_api.settings import Settings
    monkeypatch.setattr('buyeros_api.settings.get_settings', lambda: Settings(paid_admission_enabled=False))
    monkeypatch.setattr(registry, 'provider_readiness', lambda service, **kwargs: {
        'status': 'blocked', 'reason_codes': ['NO_SAFE_RECONCILIATION'], 'actions': [],
    })
    items = capabilities_payload()['items']
    assert items[0]['status'] == 'disabled'
    assert items[0]['reason_codes'] == ['PAID_ADMISSION_DISABLED', 'NO_SAFE_RECONCILIATION']
    assert all(item['status'] == 'disabled' for item in items[3:])
    assert all(item['billable'] is False for item in items)
