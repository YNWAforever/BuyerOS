import pytest
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

from buyeros_api.api.app import create_app
from buyeros_api.api.errors import ApiError
from buyeros_api.settings import get_settings

ORIGIN = "https://staff.example.test"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("BUYEROS_CORS_ORIGINS", '["https://staff.example.test"]')
    get_settings.cache_clear()
    app = create_app()

    @app.get("/_cors/stale")
    def stale():
        raise ApiError(412, "STALE_REVISION", "stale")

    @app.get("/_cors/ok")
    def ok():
        return JSONResponse({"ok": True}, headers={"ETag": '"v1"'})

    @app.get("/_cors/validate")
    def validate(required: int):
        return {"required": required}

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_preflight_allowed_origin(client):
    response = client.options(
        "/v1/workspaces",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type, idempotency-key, if-match, x-request-id",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert response.headers.get("access-control-allow-credentials") is None
    methods = response.headers["access-control-allow-methods"].lower()
    assert all(method in methods for method in ["get", "post", "patch", "delete", "options"])
    allowed = response.headers["access-control-allow-headers"].lower()
    assert all(header in allowed for header in ["authorization", "content-type", "idempotency-key", "if-match", "x-request-id"])


def test_success_exposes_etag_and_request_id(client):
    response = client.get("/_cors/ok", headers={"Origin": ORIGIN})
    assert response.status_code == 200
    assert response.headers["etag"] == '"v1"'
    assert response.headers["x-request-id"]
    exposed = response.headers["access-control-expose-headers"].lower()
    assert "x-request-id" in exposed and "etag" in exposed


def test_denied_origin_never_gets_allow_origin(client):
    response = client.options(
        "/v1/workspaces",
        headers={"Origin": "https://wrong.example.test", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers.get("access-control-allow-origin") is None
    response = client.get("/v1/workspaces", headers={"Origin": "https://wrong.example.test"})
    assert response.status_code == 401
    assert response.headers.get("access-control-allow-origin") is None


@pytest.mark.parametrize("path,status", [("/v1/workspaces", 401), ("/_cors/stale", 412), ("/_cors/validate?required=bad", 422)])
def test_error_responses_keep_cors_and_request_id(client, path, status):
    response = client.get(path, headers={"Origin": ORIGIN})
    assert response.status_code == status
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert response.headers["x-request-id"]
    assert response.json()["request_id"] == response.headers["x-request-id"]
    exposed = response.headers.get("access-control-expose-headers", "").lower()
    assert "x-request-id" in exposed and "etag" in exposed


@pytest.mark.parametrize("origin", ["*", "http://remote.example", "https://staff.example.test/extra", "https://user:pass@staff.example.test"])
def test_cors_configuration_rejects_wildcard_insecure_or_non_origin(origin):
    from pydantic import ValidationError
    from buyeros_api.settings import Settings

    with pytest.raises(ValidationError):
        Settings(cors_origins=[origin])


def test_cors_configuration_normalizes_explicit_origin():
    from buyeros_api.settings import Settings

    config = Settings(cors_origins=["https://staff.example.test/", "https://staff.example.test"])
    assert config.cors_origins == ["https://staff.example.test"]
