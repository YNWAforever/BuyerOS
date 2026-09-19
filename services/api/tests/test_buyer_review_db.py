"""BO-008 slice 1: buyer version, snapshots, reviews and evidence."""
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
PROJECT_A = "a0000000-0000-4000-8000-000000000001"
PROJECT_B = "b0000000-0000-4000-8000-000000000002"
OPERATOR = "auth0|operator-a"
REVIEWER = "auth0|reviewer-a"
ADMIN = "auth0|admin-a"


def test_buyer_version_and_idempotency_response_columns_exist(migrated):
    with psycopg.connect(migrated) as conn:
        columns = {
            (r[0], r[1], r[2])
            for r in conn.execute(
                "SELECT table_name, column_name, is_nullable FROM information_schema.columns "
                "WHERE (table_name = 'project_buyers' AND column_name = 'version') "
                "OR (table_name = 'idempotency_records' AND column_name = 'response')"
            ).fetchall()
        }
    assert columns == {("project_buyers", "version", "NO"), ("idempotency_records", "response", "YES")}


def test_a_raw_project_buyer_insert_defaults_to_version_one(seeded):
    company_id = str(uuid.uuid4())
    buyer_id = str(uuid.uuid4())
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO companies(id, workspace_id, legal_name, display_name) VALUES (%s, %s, 'C', 'C Co')",
            (company_id, WORKSPACE_A),
        )
        conn.execute(
            "INSERT INTO project_buyers(id, workspace_id, project_id, company_id) VALUES (%s, %s, %s, %s)",
            (buyer_id, WORKSPACE_A, PROJECT_A, company_id),
        )
        version = conn.execute("SELECT version FROM project_buyers WHERE id = %s", (buyer_id,)).fetchone()[0]
        conn.execute("DELETE FROM project_buyers WHERE id = %s", (buyer_id,))
        conn.execute("DELETE FROM companies WHERE id = %s", (company_id,))
    assert version == 1


def test_buyer_update_rejects_an_empty_body_and_a_null_note():
    from pydantic import ValidationError

    from buyeros_api.api.schemas import BuyerUpdate

    with pytest.raises(ValidationError):
        BuyerUpdate.model_validate({})
    with pytest.raises(ValidationError):
        BuyerUpdate.model_validate({"note": None})
    # an explicit null owner is allowed (it clears the owner)
    assert BuyerUpdate.model_validate({"owner_membership_id": None}).owner_membership_id is None


def test_snapshot_create_rejects_unknown_keys_and_bounds():
    from pydantic import ValidationError

    from buyeros_api.api.schemas import SnapshotCreate

    base = {"filters": {}, "sort": "best_fit", "requested_limit": 10}
    # `filters` is required by the contract, but an empty object is a valid value.
    assert SnapshotCreate.model_validate(base).requested_limit == 10
    without_filters = {"sort": "best_fit", "requested_limit": 10}
    for bad in (
        {**base, "extra": 1},
        {**base, "sort": "newest"},
        {**base, "requested_limit": 0},
        {**base, "requested_limit": 1001},
        without_filters,
    ):
        with pytest.raises(ValidationError):
            SnapshotCreate.model_validate(bad)


def test_review_request_discriminates_the_selection_kind():
    from pydantic import ValidationError

    from buyeros_api.api.schemas import ReviewRequest

    explicit = {
        "selection": {"kind": "explicit", "buyers": [{"id": str(uuid.uuid4()), "version": 2}]},
        "status": "accepted",
        "reason": "reviewed",
    }
    assert ReviewRequest.model_validate(explicit).status == "accepted"
    for bad in (
        {**explicit, "status": "approved"},
        {**explicit, "reason": "no"},
        {"selection": {"kind": "other"}, "status": "accepted", "reason": "reviewed"},
    ):
        with pytest.raises(ValidationError):
            ReviewRequest.model_validate(bad)


@pytest.fixture
def api(seeded, monkeypatch):
    """An authenticated client on the runtime role with operator, reviewer and admin members."""
    monkeypatch.setenv("BUYEROS_DATABASE_URL", runtime_role_dsn(seeded))
    monkeypatch.setenv("BUYEROS_AUTH0_ISSUER", fx.ISSUER)
    monkeypatch.setenv("BUYEROS_AUTH0_AUDIENCE", fx.AUDIENCE)
    from buyeros_api.settings import get_settings

    get_settings.cache_clear()
    cache = JwksKeyCache(lambda: asyncio.sleep(0, result=fx.jwks_document()), cache_seconds=300)
    monkeypatch.setattr(auth, "_verifier_from_settings", lambda: TokenVerifier(cache, issuer=fx.ISSUER, audience=fx.AUDIENCE))

    owner = psycopg.connect(seeded, autocommit=True)
    for subject, roles in ((OPERATOR, ["operator"]), (REVIEWER, ["reviewer"]), (ADMIN, ["workspace_admin"])):
        user_id = uuid.uuid5(uuid.NAMESPACE_URL, subject)
        owner.execute("DELETE FROM memberships WHERE user_id = %s", (user_id,))
        owner.execute("DELETE FROM users WHERE id = %s", (user_id,))
        owner.execute("INSERT INTO users(id, issuer, subject) VALUES (%s, %s, %s)", (user_id, fx.ISSUER, subject))
        owner.execute(
            "INSERT INTO memberships(id, workspace_id, user_id, roles, active) VALUES (%s, %s, %s, %s, true)",
            (uuid.uuid4(), WORKSPACE_A, user_id, roles),
        )
    owner.close()
    try:
        yield TestClient(create_app(), raise_server_exceptions=False)
    finally:
        get_settings.cache_clear()
        owner = psycopg.connect(seeded, autocommit=True)
        for subject in (OPERATOR, REVIEWER, ADMIN):
            user_id = uuid.uuid5(uuid.NAMESPACE_URL, subject)
            owner.execute("DELETE FROM memberships WHERE user_id = %s", (user_id,))
            owner.execute("DELETE FROM users WHERE id = %s", (user_id,))
        for statement in (
            "DELETE FROM buyer_snapshot_items WHERE workspace_id = %s",
            "DELETE FROM buyer_snapshots WHERE workspace_id = %s",
            "DELETE FROM human_reviews WHERE workspace_id = %s",
            "DELETE FROM fit_assessments WHERE workspace_id = %s",
            "DELETE FROM list_memberships WHERE workspace_id = %s",
            "DELETE FROM project_buyers WHERE workspace_id = %s",
            "DELETE FROM evidence WHERE workspace_id = %s",
            "DELETE FROM source_documents WHERE workspace_id = %s",
            "DELETE FROM companies WHERE workspace_id = %s",
            "DELETE FROM idempotency_records WHERE workspace_id = %s",
        ):
            owner.execute(statement, (WORKSPACE_A,))
        owner.close()


def _seed_buyer(seeded, *, name, fit=None, review=None, owner_user_id=None, domain=None):
    company_id = str(uuid.uuid4())
    buyer_id = str(uuid.uuid4())
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO companies(id, workspace_id, legal_name, display_name, domain) VALUES (%s, %s, %s, %s, %s)",
            (company_id, WORKSPACE_A, name, name, domain),
        )
        conn.execute(
            "INSERT INTO project_buyers(id, workspace_id, project_id, company_id, owner_user_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (buyer_id, WORKSPACE_A, PROJECT_A, company_id, owner_user_id),
        )
        if fit is not None:
            conn.execute(
                "INSERT INTO fit_assessments(id, workspace_id, project_buyer_id, icp_version_id, evidence_set_hash, "
                "verdict, rationale, evidence_ids) VALUES (%s, %s, %s, %s, 'sha256:x', %s, 'because', '[]'::jsonb)",
                (str(uuid.uuid4()), WORKSPACE_A, buyer_id, str(uuid.uuid4()), fit),
            )
        if review is not None:
            conn.execute(
                "INSERT INTO human_reviews(id, workspace_id, project_buyer_id, state, actor_user_id) "
                "VALUES (%s, %s, %s, %s, %s)",
                (str(uuid.uuid4()), WORKSPACE_A, buyer_id, review, str(uuid.uuid4())),
            )
    return buyer_id


def _h(subject=OPERATOR, key="snapshot-01", **extra):
    headers = {"Authorization": f"Bearer {fx.make_token(sub=subject)}", "Idempotency-Key": key}
    headers.update(extra)
    return headers


def test_create_snapshot_orders_filters_and_bounds(api, seeded):
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("DELETE FROM project_buyers WHERE workspace_id = %s", (WORKSPACE_A,))
    _seed_buyer(seeded, name="Zeta Sensors", fit="match")
    _seed_buyer(seeded, name="Alpha Sensors", fit="needs_review")
    _seed_buyer(seeded, name="Mid Sensors", fit="match")
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-snapshots",
        json={"filters": {"fit": ["match"]}, "sort": "name_asc", "requested_limit": 1},
        headers=_h(),
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["result_limit_reached"] is True
    assert data["sort"] == "name_asc"
    assert data["snapshot_version"] == 1
    assert response.headers.get("ETag") is None


def test_a_deferred_filter_is_rejected_loudly(api):
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-snapshots",
        json={"filters": {"markets": ["DE"]}, "sort": "best_fit", "requested_limit": 10},
        headers=_h(key="snapshot-f"),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"
    assert "markets" in response.json()["message"]


def test_a_snapshot_replays_for_the_same_key_and_body(api):
    body = {"filters": {}, "sort": "best_fit", "requested_limit": 10}
    first = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-snapshots",
        json=body, headers=_h(key="snapshot-replay"),
    )
    second = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-snapshots",
        json=body, headers=_h(key="snapshot-replay"),
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
