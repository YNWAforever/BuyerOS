from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app


def test_error_envelope_shape():
    app = create_app()

    @app.get("/boom")
    async def boom():
        from buyeros_api.api.errors import ApiError

        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "conflict")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom")
    body = response.json()
    assert response.status_code == 409
    assert body["code"] == "IDEMPOTENCY_CONFLICT"
    assert body["retryable"] is False
    assert "request_id" in body


def test_request_id_header_is_contract_valid_and_correlated():
    import uuid

    client = TestClient(create_app())
    supplied = "c2bf90be-874c-45eb-a36e-16d06ec72151"
    kept = client.get("/health/live", headers={"X-Request-ID": supplied})
    assert kept.headers["X-Request-ID"] == supplied
    assert kept.json()["request_id"] == supplied
    invalid = client.get("/health/live", headers={"X-Request-ID": "abc"})
    normalized = invalid.headers["X-Request-ID"]
    assert normalized != "abc"
    assert str(uuid.UUID(normalized)) == normalized
    assert invalid.json()["request_id"] == normalized


def test_validation_errors_use_the_contract_envelope():
    app = create_app()

    @app.get("/needs-uuid/{value}")
    async def needs_uuid(value: int):
        return {"data": {"value": value}, "request_id": "x", "data_mode": "live"}

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/needs-uuid/not-an-int")
    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "INVALID_REQUEST"
    assert set(body) == {"code", "message", "request_id", "retryable"}
    assert "detail" not in body
    assert "not-an-int" not in response.text


def test_unknown_paths_use_the_contract_envelope():
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get("/definitely-not-a-route")
    body = response.json()
    assert response.status_code == 404
    assert body["code"] == "NOT_FOUND"
    assert set(body) == {"code", "message", "request_id", "retryable"}


def test_wrong_method_uses_the_contract_envelope():
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.delete("/health/live")
    body = response.json()
    assert response.status_code == 405
    assert set(body) == {"code", "message", "request_id", "retryable"}

def test_live_read_switch_preserves_health_and_returns_correlated_503(monkeypatch):
    from buyeros_api.settings import get_settings

    monkeypatch.setenv("BUYEROS_LIVE_READ_ENABLED", "false")
    get_settings.cache_clear()
    try:
        client = TestClient(create_app(), raise_server_exceptions=False)
        response = client.get(
            "/v1/workspaces/11111111-1111-4111-8111-111111111111/projects",
            headers={"X-Request-ID": "c2bf90be-874c-45eb-a36e-16d06ec72151"},
        )
        assert response.status_code == 503
        assert response.json()["code"] == "READ_DISABLED"
        assert response.headers["X-Request-ID"] == response.json()["request_id"]
        assert client.get("/health/live").status_code == 200
    finally:
        get_settings.cache_clear()


def test_internal_error_logs_only_type_and_request_id(caplog):
    import asyncio
    import logging
    from fastapi import Request
    from buyeros_api.api.errors import internal_error_handler

    request = Request({"type": "http", "method": "GET", "path": "/v1/test", "headers": []})
    request.state.request_id = "a393efc1-36a6-4edb-8727-8626f73ecfb6"
    with caplog.at_level(logging.ERROR, logger="buyeros_api.api.errors"):
        response = asyncio.run(internal_error_handler(request, ValueError("CANARY_PRIVATE_TOKEN")))
    assert response.status_code == 500
    assert b"CANARY_PRIVATE_TOKEN" not in response.body
    assert "ValueError" in caplog.text
    assert request.state.request_id in caplog.text
    assert "CANARY_PRIVATE_TOKEN" not in caplog.text
