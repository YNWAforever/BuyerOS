"""BO-004 acceptance tests: a verified actor reaches real data only through membership."""

import asyncio
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from buyeros_api.api import auth
from buyeros_api.api.app import create_app
from buyeros_api.api.jwks import JwksKeyCache
from buyeros_api.api.verifier import TokenVerifier
from tests import auth_fixtures as fx
from tests.conftest import runtime_role_dsn

WORKSPACE_A = "11111111-1111-4111-8111-111111111111"
WORKSPACE_B = "22222222-2222-4222-8222-222222222222"
PROJECT_B = "b0000000-0000-4000-8000-000000000002"
MEMBER = "auth0|member-a"
VIEWER = "auth0|viewer-a"


@pytest.fixture
def auth_env(seeded, monkeypatch):
    """Point the app at a local verifier and the runtime-role database."""
    monkeypatch.setenv("BUYEROS_DATABASE_URL", runtime_role_dsn(seeded))
    monkeypatch.setenv("BUYEROS_AUTH0_ISSUER", fx.ISSUER)
    monkeypatch.setenv("BUYEROS_AUTH0_AUDIENCE", fx.AUDIENCE)
    from buyeros_api.settings import get_settings

    get_settings.cache_clear()

    cache = JwksKeyCache(lambda: asyncio.sleep(0, result=fx.jwks_document()), cache_seconds=300)
    monkeypatch.setattr(
        auth, "_verifier_from_settings", lambda: TokenVerifier(cache, issuer=fx.ISSUER, audience=fx.AUDIENCE)
    )

    owner = psycopg.connect(seeded, autocommit=True)
    for subject, roles in ((MEMBER, ["operator"]), (VIEWER, ["viewer"])):
        user_id = uuid.uuid5(uuid.NAMESPACE_URL, subject)
        owner.execute("DELETE FROM memberships WHERE user_id = %s", (user_id,))
        owner.execute("DELETE FROM users WHERE id = %s", (user_id,))
        owner.execute("INSERT INTO users(id, issuer, subject) VALUES (%s, %s, %s)", (user_id, fx.ISSUER, subject))
        owner.execute(
            "INSERT INTO memberships(id, workspace_id, user_id, roles, active) VALUES (%s, %s, %s, %s, true)",
            (uuid.uuid4(), WORKSPACE_A, user_id, roles),
        )
    owner.close()
    yield
    get_settings.cache_clear()
    owner = psycopg.connect(seeded, autocommit=True)
    for subject in (MEMBER, VIEWER):
        user_id = uuid.uuid5(uuid.NAMESPACE_URL, subject)
        owner.execute("DELETE FROM memberships WHERE user_id = %s", (user_id,))
        owner.execute("DELETE FROM users WHERE id = %s", (user_id,))
    owner.close()


def _client():
    return TestClient(create_app(), raise_server_exceptions=False)


def _headers(subject=MEMBER, **kwargs):
    return {"Authorization": f"Bearer {fx.make_token(sub=subject, **kwargs)}"}


def test_valid_member_reaches_only_its_own_workspace(auth_env):
    client = _client()
    ok = client.get(f"/v1/workspaces/{WORKSPACE_A}/projects", headers=_headers())
    assert ok.status_code == 200, ok.text
    assert {item["name"] for item in ok.json()["data"]["items"]} == {"ProjectA"}

    foreign = client.get(f"/v1/workspaces/{WORKSPACE_B}/projects", headers=_headers())
    assert foreign.status_code == 404
    assert "ProjectB" not in foreign.text


def test_forged_expired_wrong_audience_and_malformed_are_denied(auth_env):
    """Every rejection is a 401 whose body reveals nothing about which check failed.

    The signature case uses a real keypair, so it fails at signature verification rather than
    at header parsing - a test that only sent garbage would pass even if signatures stopped
    being checked. The message assertion is what pins TEST-BO-004-03: without it, a regression
    that interpolated the reason ("expired", "bad issuer") would keep these cases green.
    """
    from cryptography.hazmat.primitives.asymmetric import rsa

    attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    client = _client()
    path = f"/v1/workspaces/{WORKSPACE_A}/projects"
    for headers in (
        _headers(iss="https://other.test/"),
        _headers(aud="other-api"),
        _headers(exp=100),
        _headers(key=attacker),  # correct header and kid, invalid signature
        {"Authorization": "Bearer not-a-jwt"},
    ):
        response = client.get(path, headers=headers)
        assert response.status_code == 401, headers
        body = response.json()
        assert body["code"] == "UNAUTHENTICATED"
        assert body["message"] == "token rejected"
        assert "oauth" not in response.text.lower()
        assert "expired" not in response.text.lower()
        assert "issuer" not in response.text.lower()


def test_unknown_actor_is_a_non_enumerating_404(auth_env):
    client = _client()
    response = client.get(f"/v1/workspaces/{WORKSPACE_A}/projects", headers=_headers(subject="auth0|nobody"))
    assert response.status_code == 404
    assert "ProjectA" not in response.text


def test_viewer_cannot_mutate(auth_env):
    client = _client()
    response = client.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects",
        headers={**_headers(VIEWER), "Idempotency-Key": "k-1"},
        json={"name": "Nope"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"


def test_foreign_project_id_is_hidden(auth_env):
    client = _client()
    response = client.get(f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_B}", headers=_headers())
    assert response.status_code == 404
    assert "ProjectB" not in response.text


def test_capabilities_and_errors_disclose_no_secrets(auth_env):
    client = _client()
    caps = client.get(f"/v1/workspaces/{WORKSPACE_A}/capabilities", headers=_headers())
    assert caps.status_code == 200
    body = caps.text.lower()
    for secret in ("password", "postgresql://", "bearer ", "auth0|"):
        assert secret not in body, secret

    denied = client.get(f"/v1/workspaces/{WORKSPACE_A}/projects", headers={"Authorization": "Bearer bogus"})
    assert denied.json()["message"] == "token rejected"
