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
