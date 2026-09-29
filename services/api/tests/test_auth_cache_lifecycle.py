"""T04: bounded JWKS failure, live membership checks, and engine lifecycle."""

import asyncio
import uuid
from unittest.mock import AsyncMock

import psycopg
import pytest
from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app
from buyeros_api.api.deps import permission_for_roles
from buyeros_api.api.jwks import JwksError, JwksKeyCache
from tests.test_jwks_cache import Clock, Fetcher, _doc
from tests.test_auth_routes_db import WORKSPACE_A, MEMBER, _headers, auth_env


def test_jwks_stale_ceiling_and_unknown_kid_fail_closed():
    clock = Clock()
    fetcher = Fetcher(_doc("k1"))
    cache = JwksKeyCache(fetcher, cache_seconds=300, max_stale_seconds=3600, now=clock)
    assert asyncio.run(cache.get_key("k1")) is not None
    fetcher.error = RuntimeError("offline")
    clock.t += 301
    assert asyncio.run(cache.get_key("k1")) is not None
    with pytest.raises(JwksError):
        asyncio.run(cache.get_key("unknown"))
    clock.t += 3299  # exactly 3600 seconds since the last successful fetch
    with pytest.raises(JwksError):
        asyncio.run(cache.get_key("k1"))


def test_unknown_operation_denies_admin_by_default():
    assert permission_for_roles(["workspace_admin"], "notAContractOperation") is False


def test_app_shutdown_disposes_pool(monkeypatch):
    from buyeros_api.api import deps

    dispose = AsyncMock()
    monkeypatch.setattr(deps, "dispose_engines", dispose)
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        assert client.get("/health/live").status_code == 200
    dispose.assert_awaited_once()


def test_revoked_membership_is_rechecked_on_next_request(auth_env, seeded):
    client = TestClient(create_app(), raise_server_exceptions=False)
    before = client.get(f"/v1/workspaces/{WORKSPACE_A}/projects", headers=_headers())
    assert before.status_code == 200, before.text
    user_id = uuid.uuid5(uuid.NAMESPACE_URL, MEMBER)
    with psycopg.connect(seeded, autocommit=True) as owner:
        owner.execute("UPDATE memberships SET active = false WHERE user_id = %s", (user_id,))
    after = client.get(f"/v1/workspaces/{WORKSPACE_A}/projects", headers=_headers())
    assert after.status_code == 404, after.text
    assert after.json()["code"] == "NOT_FOUND"
