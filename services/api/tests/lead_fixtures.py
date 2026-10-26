"""Offline, disposable lead fixtures. No real contact or provider is used."""
import asyncio
import copy
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient

from buyeros_api.api import auth
from buyeros_api.api.app import create_app
from buyeros_api.api.jwks import JwksKeyCache
from buyeros_api.api.verifier import TokenVerifier
from tests import auth_fixtures as fx
from tests.conftest import runtime_role_dsn

WORKSPACE = "11111111-1111-4111-8111-111111111111"
PROJECT = "a0000000-0000-4000-8000-000000000001"
OTHER_WORKSPACE = "22222222-2222-4222-8222-222222222222"
OTHER_PROJECT = "b0000000-0000-4000-8000-000000000002"
SUBJECTS = {role: f"auth0|lead-suite-{role}" for role in ("operator", "reviewer", "workspace_admin", "viewer")}
ACTORS = {role: uuid.uuid5(uuid.NAMESPACE_URL, subject) for role, subject in SUBJECTS.items()}


def headers(role="operator", *, key=None, version=None):
    result = {"Authorization": f"Bearer {fx.make_token(sub=SUBJECTS[role])}"}
    if key is not None:
        result["Idempotency-Key"] = key
    if version is not None:
        result["If-Match"] = f'"{version}"'
    return result


def observation_payload(**changes):
    value = {
        "claim": "employment", "stance": "supports",
        "person": {"full_name": "Alex Test", "role": "Food Purchasing Manager"},
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "sources": [{
            "title": "Official team page", "url": "https://rice.example.test/team",
            "excerpt": "Alex Test is our Food Purchasing Manager.",
            "source_kind": "official", "published_on": None, "published_precision": None,
        }],
        "rationale": "Official staff page identifies the current purchasing manager.",
        "limitations": "No purchase intent is established.",
    }
    value.update(changes)
    return value


@pytest.fixture
def lead_case(isolated_seeded):
    now = datetime.now(timezone.utc)
    buyer, company, other_buyer, other_company = (uuid.uuid4() for _ in range(4))
    with psycopg.connect(isolated_seeded, autocommit=True) as db:
        for role, actor in ACTORS.items():
            db.execute("INSERT INTO users(id,issuer,subject) VALUES (%s,%s,%s)", (actor, fx.ISSUER, SUBJECTS[role]))
            db.execute(
                "INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES (%s,%s,%s,%s,true)",
                (uuid.uuid4(), WORKSPACE, actor, [role]),
            )
        for cid, bid, wid, pid in (
            (company, buyer, WORKSPACE, PROJECT),
            (other_company, other_buyer, OTHER_WORKSPACE, OTHER_PROJECT),
        ):
            db.execute(
                "INSERT INTO companies(id,workspace_id,legal_name,display_name,domain) "
                "VALUES (%s,%s,'Fixture rice wholesaler','Fixture rice wholesaler','rice.example.test')",
                (cid, wid),
            )
            db.execute(
                "INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES (%s,%s,%s,%s)",
                (bid, wid, pid, cid),
            )
    from tests.policy_activation_fixtures import approve_native_fixture
    approve_native_fixture(isolated_seeded, WORKSPACE, PROJECT, ACTORS["workspace_admin"])
    return {
        "dsn": isolated_seeded, "workspace_id": WORKSPACE, "project_id": PROJECT,
        "buyer_id": str(buyer), "company_id": str(company), "other_buyer_id": str(other_buyer),
        "other_company_id": str(other_company),
        "base": f"/v1/workspaces/{WORKSPACE}/projects/{PROJECT}",
    }


@pytest.fixture
def lead_api(lead_case, monkeypatch):
    from buyeros_api.settings import get_settings
    monkeypatch.setenv("BUYEROS_DATABASE_URL", runtime_role_dsn(lead_case["dsn"]))
    monkeypatch.setenv("BUYEROS_AUTH_MODE", "auth0")
    monkeypatch.setenv("BUYEROS_AUTH0_ISSUER", fx.ISSUER)
    monkeypatch.setenv("BUYEROS_AUTH0_AUDIENCE", fx.AUDIENCE)
    monkeypatch.setenv("BUYEROS_PAID_ADMISSION_ENABLED", "false")
    monkeypatch.setenv("BUYEROS_DELIVERY_ADMISSION_ENABLED", "false")
    monkeypatch.setenv("BUYEROS_CLOUDFLARE_EXECUTION_ENABLED", "false")
    get_settings.cache_clear()
    cache = JwksKeyCache(lambda: asyncio.sleep(0, result=fx.jwks_document()), cache_seconds=300)
    monkeypatch.setattr(auth, "_verifier_from_settings",
                        lambda: TokenVerifier(cache, issuer=fx.ISSUER, audience=fx.AUDIENCE))
    try:
        with TestClient(create_app(), raise_server_exceptions=True) as client:
            yield client
    finally:
        get_settings.cache_clear()


def prepare(api, case, action, payload, *, role="operator", buyer=True, target_id=None, version=None, key=None):
    body = {"action": action, "payload": copy.deepcopy(payload)}
    if buyer:
        body["buyer_id"] = case["buyer_id"]
    if target_id is not None:
        body["target_id"] = target_id
    if version is not None:
        body["expected_version"] = version
    return api.post(
        f"{case['base']}/lead-intents", json=body,
        headers=headers(role, key=key or str(uuid.uuid4())),
    )


def apply(api, case, intent, *, role="operator"):
    return api.post(
        f"{case['base']}/lead-intents/{intent['id']}/apply", json={},
        headers=headers(role, key=intent["submission_key"], version=intent.get("expected_version")),
    )


def save_observation(api, case, payload=None, *, role="operator"):
    prepared = prepare(api, case, "observation.append", payload or observation_payload(), role=role)
    assert prepared.status_code == 201, prepared.text
    intent = prepared.json()["data"]
    applied = apply(api, case, intent, role=role)
    assert applied.status_code == 200, applied.text
    receipt = applied.json()["data"]
    page = api.get(f"{case['base']}/buyers/{case['buyer_id']}/lead-evidence", headers=headers(role))
    assert page.status_code == 200, page.text
    record = next(row for row in page.json()["data"]["items"] if row["id"] == receipt["resource_id"])
    return record, intent, receipt
