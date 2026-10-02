"""Machine credentials bind exact requests; staff tokens are never authority."""
import hashlib
import hmac
import importlib
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.cloudflare_fixtures import cloudflare_database as migrated

AUTH = Path(__file__).resolve().parents[1] / "buyeros_api/api/worker_auth.py"
NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)
SECRET = "fixture-only-worker-key-32-bytes-long"
PATH = "/v1/internal/worker/claim"
BODY = b'{"runtime_epoch":1}'


def auth_module():
    assert AUTH.is_file(), "CF02 request-bound worker authentication missing"
    return importlib.import_module("buyeros_api.api.worker_auth")


@pytest.fixture
def machine_keys(monkeypatch):
    from buyeros_api.settings import get_settings
    monkeypatch.setenv("BUYEROS_WORKER_CURRENT_KEY_ID", "fixture-current")
    monkeypatch.setenv("BUYEROS_WORKER_CURRENT_SECRET", SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def signed_headers(*, body=BODY, path=PATH, timestamp=None, nonce=None):
    timestamp = str(int(NOW.timestamp())) if timestamp is None else timestamp
    nonce = str(uuid.uuid4()) if nonce is None else nonce
    value = f"POST\n{path}\n{timestamp}\n{nonce}\n{hashlib.sha256(body).hexdigest()}"
    return {"x-buyeros-worker-key-id": "fixture-current", "x-buyeros-worker-timestamp": timestamp,
            "x-buyeros-worker-nonce": nonce,
            "x-buyeros-worker-signature": hmac.new(SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()}


def test_user_token_cannot_call_internal_worker():
    from buyeros_api.api.app import create_app
    with TestClient(create_app()) as client:
        for suffix in ("claim", "step", "status", "publication", "maintenance"):
            response = client.post(f"/v1/internal/worker/{suffix}", json={},
                                   headers={"Authorization": "Bearer fixture-user-token"})
            assert response.status_code == 401, (suffix, response.text)


@pytest.mark.parametrize("tamper", ["body", "path", "timestamp", "nonce", "method"])
def test_signature_binds_raw_body_path_timestamp_and_nonce(machine_keys, tamper):
    auth = auth_module()
    body, path, headers, method = BODY, PATH, signed_headers(), "POST"
    principal = auth.verify_worker_request(method, path, body, headers, NOW)
    assert principal.key_id == "fixture-current"
    if tamper == "body": body += b" "
    elif tamper == "path": path += "/"
    elif tamper == "timestamp": headers["x-buyeros-worker-timestamp"] = str(int(NOW.timestamp()) + 1)
    elif tamper == "nonce": headers["x-buyeros-worker-nonce"] = str(uuid.uuid4())
    else: method = "GET"
    with pytest.raises(Exception) as exc:
        auth.verify_worker_request(method, path, body, headers, NOW)
    assert exc.value.status_code == 401


def test_signature_expiry_body_limit_and_unknown_key_fail_closed(machine_keys):
    auth = auth_module()
    for now, body, headers in (
        (NOW + timedelta(seconds=61), BODY, signed_headers()),
        (NOW - timedelta(seconds=61), BODY, signed_headers()),
        (NOW, b"x" * 8193, signed_headers(body=b"x" * 8193)),
        (NOW, BODY, signed_headers() | {"x-buyeros-worker-key-id": "missing"}),
        (NOW, BODY, signed_headers(nonce="not-a-uuid")),
    ):
        with pytest.raises(Exception) as exc:
            auth.verify_worker_request("POST", PATH, body, headers, now)
        assert exc.value.status_code in {401, 413}


def test_authenticated_nonce_replay_and_unknown_fields_are_rejected(machine_keys, migrated, monkeypatch):
    import json
    import psycopg
    from urllib.parse import urlsplit, urlunsplit
    from buyeros_api.settings import get_settings
    from buyeros_api.api.app import create_app
    parts = urlsplit(migrated)
    host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
        epoch, enabled = db.execute("SELECT epoch,enabled FROM worker_runtime_control").fetchone()
        assert enabled is False  # fresh schema is disabled
    monkeypatch.setenv("BUYEROS_EXECUTION_DATABASE_URL", urlunsplit(parts._replace(
        netloc=f"buyeros_worker:test-only@{host}:{parts.port}")))
    get_settings.cache_clear()
    path = "/v1/internal/worker/maintenance"
    raw = json.dumps({"runtime_epoch": epoch}).encode()
    headers = signed_headers(body=raw, path=path, timestamp=str(int(datetime.now(timezone.utc).timestamp())))
    with TestClient(create_app()) as client:
        first = client.post(path, content=raw, headers=headers | {"Content-Type": "application/json"})
        assert first.status_code == 200, first.text
        assert first.json()["enabled"] is False
        replay = client.post(path, content=raw, headers=headers | {"Content-Type": "application/json"})
        assert replay.status_code == 409, replay.text
        bad = json.dumps({"runtime_epoch": epoch, "payload": "not allowed"}).encode()
        extra = client.post(path, content=bad, headers=signed_headers(body=bad, path=path,
            timestamp=str(int(datetime.now(timezone.utc).timestamp()))) | {"Content-Type": "application/json"})
        assert extra.status_code == 422, extra.text
        huge = b"x" * 8193
        assert client.post(path, content=huge, headers=signed_headers(body=huge, path=path,
            timestamp=str(int(datetime.now(timezone.utc).timestamp())))).status_code == 413


def test_explicit_previous_key_rotation_is_verified(machine_keys, monkeypatch):
    from buyeros_api.settings import get_settings
    auth = auth_module()
    old = signed_headers()
    monkeypatch.setenv("BUYEROS_WORKER_PREVIOUS_KEY_ID", "fixture-current")
    monkeypatch.setenv("BUYEROS_WORKER_PREVIOUS_SECRET", SECRET)
    monkeypatch.setenv("BUYEROS_WORKER_CURRENT_KEY_ID", "fixture-next")
    monkeypatch.setenv("BUYEROS_WORKER_CURRENT_SECRET", SECRET + "next")
    get_settings.cache_clear()
    assert auth.verify_worker_request("POST", PATH, BODY, old, NOW).key_id == "fixture-current"


def test_step_outcome_requires_all_four_protocol_fields():
    from pydantic import ValidationError
    from buyeros_api.api.worker_schemas import StepOutcome
    with pytest.raises(ValidationError):
        StepOutcome(state="done", code="OK")
    assert set(StepOutcome(state="done", code="OK", next_step_key=None,
                           retry_at=None).model_dump()) == {"state", "code", "next_step_key", "retry_at"}
