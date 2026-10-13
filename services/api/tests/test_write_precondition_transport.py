"""The hosting-safe carrier must preserve the existing strict route precondition."""
import pytest
from fastapi import Header, Request, Response
from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app
from buyeros_api.api.errors import ApiError, envelope
from buyeros_api.api.idempotency import if_match_version, request_fingerprint


@pytest.fixture
def api():
    app = create_app()
    state = {"version": 1, "writes": 0, "fingerprint": None}

    @app.patch("/v1/transport-fixture")
    async def guarded_write(request: Request, response: Response,
                            if_match: str | None = Header(default=None, alias="If-Match")):
        expected = if_match_version(if_match)
        if expected != state["version"]:
            raise ApiError(412, "STALE_REVISION", "fixture version changed")
        state["fingerprint"] = request_fingerprint("updateProject", {"project_id": "fixture"},
                                                   if_match, {"name": "Revised"})
        state["version"] += 1
        state["writes"] += 1
        response.headers["ETag"] = f'"{state["version"]}"'
        return envelope({"version": state["version"]}, request.state.request_id)

    return TestClient(app), state


def test_transport_carrier_reaches_existing_version_guard_and_fingerprint(api):
    client, state = api
    response = client.patch("/v1/transport-fixture", headers={"X-BuyerOS-If-Match": '"1"'})
    assert response.status_code == 200, response.text
    assert response.json()["data"] == {"version": 2}
    assert response.headers["ETag"] == '"2"'
    assert state["writes"] == 1
    assert state["fingerprint"] == request_fingerprint(
        "updateProject", {"project_id": "fixture"}, '"1"', {"name": "Revised"})
    stale = client.patch("/v1/transport-fixture", headers={"X-BuyerOS-If-Match": '"1"'})
    assert stale.status_code == 412
    assert stale.json()["code"] == "STALE_REVISION"
    assert stale.headers["X-Request-ID"] == stale.json()["request_id"]
    assert state["writes"] == 1


@pytest.mark.parametrize("value", ['*', 'W/"1"', '"01"', '1', '"1", "2"', ''])
def test_transport_carrier_cannot_weaken_strong_version_validation(api, value):
    client, state = api
    response = client.patch("/v1/transport-fixture", headers={"X-BuyerOS-If-Match": value})
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_REQUEST"
    assert state["writes"] == 0


@pytest.mark.parametrize("headers", [
    [("If-Match", '"1"'), ("X-BuyerOS-If-Match", '"1"')],
    [("If-Match", '"1"'), ("X-BuyerOS-If-Match", '"2"')],
    [("X-BuyerOS-If-Match", '"1"'), ("X-BuyerOS-If-Match", '"2"')],
])
def test_ambiguous_precondition_carriers_fail_before_the_route(api, headers):
    client, state = api
    response = client.patch("/v1/transport-fixture", headers=headers)
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_REQUEST"
    assert response.headers["X-Request-ID"] == response.json()["request_id"]
    assert state["writes"] == 0


def test_standard_if_match_remains_supported(api):
    client, state = api
    response = client.patch("/v1/transport-fixture", headers={"If-Match": '"1"'})
    assert response.status_code == 200
    assert state["writes"] == 1


def test_transport_carrier_is_allowed_by_cors(monkeypatch):
    from buyeros_api.settings import get_settings

    monkeypatch.setenv("BUYEROS_CORS_ORIGINS", '["https://app.example"]')
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        response = client.options("/v1/transport-fixture", headers={
            "Origin": "https://app.example", "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "authorization, content-type, idempotency-key, x-buyeros-if-match",
        })
        assert response.status_code == 200, response.text
        assert response.headers["Access-Control-Allow-Origin"] == "https://app.example"
    finally:
        get_settings.cache_clear()
