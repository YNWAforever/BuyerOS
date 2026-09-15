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


def test_request_id_header_is_returned():
    app = create_app()

    @app.get("/ok")
    async def ok():
        return {"data": {"ok": True}, "request_id": "x", "data_mode": "live"}

    client = TestClient(app)
    response = client.get("/ok", headers={"X-Request-ID": "abc"})
    assert response.headers["X-Request-ID"] == "abc"


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
