"""BO-008 slice 1: buyer version, snapshots, reviews and evidence."""
import asyncio
import uuid
from pathlib import Path

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
PROJECT_A2 = "a0000000-0000-4000-8000-00000000000a"
PROJECT_B = "b0000000-0000-4000-8000-000000000002"
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
SERVICE_ROOT = Path(__file__).resolve().parents[1]
OPERATOR = "auth0|operator-a"
REVIEWER = "auth0|reviewer-a"
ADMIN = "auth0|admin-a"
VIEWER = "auth0|viewer-a"


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


def test_snapshot_selection_requires_excluded_ids():
    from pydantic import ValidationError

    from buyeros_api.api.schemas import SnapshotSelection

    with pytest.raises(ValidationError):
        SnapshotSelection.model_validate({"kind": "snapshot", "snapshot_id": str(uuid.uuid4())})
    parsed = SnapshotSelection.model_validate(
        {"kind": "snapshot", "snapshot_id": str(uuid.uuid4()), "excluded_ids": []}
    )
    assert parsed.excluded_ids == []


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
    for subject, roles in (
        (OPERATOR, ["operator"]),
        (REVIEWER, ["reviewer"]),
        (ADMIN, ["workspace_admin"]),
        (VIEWER, ["viewer"]),
    ):
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
        for subject in (OPERATOR, REVIEWER, ADMIN, VIEWER):
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
        fit_id = None
        if fit is not None:
            fit_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO fit_assessments(id, workspace_id, project_buyer_id, icp_version_id, evidence_set_hash, "
                "verdict, rationale, evidence_ids) VALUES (%s, %s, %s, %s, 'sha256:x', %s, 'because', '[]'::jsonb)",
                (fit_id, WORKSPACE_A, buyer_id, str(uuid.uuid4()), fit),
            )
        if review is not None:
            # A review is only contract-valid alongside its fit, so link it when both are seeded.
            conn.execute(
                "INSERT INTO human_reviews(id, workspace_id, project_buyer_id, state, actor_user_id, fit_assessment_id) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (str(uuid.uuid4()), WORKSPACE_A, buyer_id, review, str(uuid.uuid4()), fit_id),
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


def test_a_malformed_owner_membership_is_rejected_not_a_server_error(api):
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-snapshots",
        json={"filters": {"owner_membership_id": "not-a-uuid"}, "sort": "best_fit", "requested_limit": 10},
        headers=_h(key="snapshot-owner"),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"
    assert "owner_membership_id" in response.json()["message"]


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


def test_the_same_snapshot_key_on_another_project_is_not_a_replay(api, seeded):
    """The idempotency scope includes the project, so one key cannot replay across projects."""
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO projects(id, workspace_id, name, company_name, offer, markets, language_preferences, "
            "version) VALUES (%s, %s, 'ProjectA2', 'ProjectA2 Co', 'offer', '{US}', '{en}', 1) "
            "ON CONFLICT (id) DO NOTHING",
            (PROJECT_A2, WORKSPACE_A),
        )
    body = {"filters": {}, "sort": "name_asc", "requested_limit": 10}
    try:
        first = api.post(
            f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-snapshots",
            json=body, headers=_h(key="snapshot-scope"),
        )
        second = api.post(
            f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A2}/buyer-snapshots",
            json=body, headers=_h(key="snapshot-scope"),
        )
        assert first.status_code == second.status_code == 201, second.text
        assert first.json()["data"]["id"] != second.json()["data"]["id"]
        assert second.json()["data"]["project_id"] == PROJECT_A2
    finally:
        with psycopg.connect(seeded, autocommit=True) as conn:
            conn.execute("DELETE FROM projects WHERE id = %s", (PROJECT_A2,))


def _snapshot(api, *, limit=10, key="list-001"):
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-snapshots",
        json={"filters": {}, "sort": "name_asc", "requested_limit": limit},
        headers=_h(key=key),
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def test_list_buyers_pages_the_frozen_snapshot(api, seeded):
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("DELETE FROM project_buyers WHERE workspace_id = %s", (WORKSPACE_A,))
    first = _seed_buyer(seeded, name="Alpha Sensors", fit="match", review="accepted")
    _seed_buyer(seeded, name="Beta Sensors", fit="needs_review", review="awaiting_review")
    snapshot_id = _snapshot(api)

    response = api.get(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyers",
        params={"snapshot_id": snapshot_id, "offset": 0, "limit": 1},
        headers=_h(key="list-read"),
    )
    assert response.status_code == 200, response.text
    page = response.json()["data"]
    assert page["total"] == 2 and page["offset"] == 0 and page["limit"] == 1
    assert len(page["items"]) == 1
    item = page["items"][0]
    assert item["id"] == first
    assert item["version"] == 1
    assert item["fit"]["verdict"] == "match"
    assert item["review"]["status"] == "accepted"
    assert item["evidence_count"] == 0
    assert item["suppressed"] is False

    # a buyer created after the snapshot is not in it
    _seed_buyer(seeded, name="Gamma Sensors", fit="match")
    after = api.get(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyers",
        params={"snapshot_id": snapshot_id, "offset": 0, "limit": 10},
        headers=_h(key="list-read-2"),
    )
    assert after.json()["data"]["total"] == 2


def test_list_buyers_returns_the_second_page_with_the_full_total(api, seeded):
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("DELETE FROM project_buyers WHERE workspace_id = %s", (WORKSPACE_A,))
    _seed_buyer(seeded, name="Alpha Sensors", fit="match")
    second = _seed_buyer(seeded, name="Beta Sensors", fit="match")
    _seed_buyer(seeded, name="Gamma Sensors", fit="match")
    snapshot_id = _snapshot(api, key="list-page")

    response = api.get(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyers",
        params={"snapshot_id": snapshot_id, "offset": 1, "limit": 1},
        headers=_h(key="list-read-page-2"),
    )
    assert response.status_code == 200, response.text
    page = response.json()["data"]
    assert page["total"] == 3
    assert page["offset"] == 1 and page["limit"] == 1
    assert [item["id"] for item in page["items"]] == [second]

    # the contract default limit is 20 when the caller omits it
    defaulted = api.get(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyers",
        params={"snapshot_id": snapshot_id},
        headers=_h(key="list-read-default"),
    )
    assert defaulted.status_code == 200, defaulted.text
    assert defaulted.json()["data"]["limit"] == 20

    negative = api.get(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyers",
        params={"snapshot_id": snapshot_id, "offset": -1},
        headers=_h(key="list-read-negative"),
    )
    assert negative.status_code == 422
    assert negative.json()["code"] == "INVALID_REQUEST"


def test_an_expired_snapshot_is_not_found(api, seeded):
    _seed_buyer(seeded, name="Alpha Sensors", fit="match")
    snapshot_id = _snapshot(api, key="list-expired")
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute(
            "UPDATE buyer_snapshots SET expires_at = now() - interval '1 hour' WHERE id = %s",
            (snapshot_id,),
        )
    response = api.get(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyers",
        params={"snapshot_id": snapshot_id},
        headers=_h(key="list-expired-read"),
    )
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_a_foreign_or_unknown_snapshot_is_a_404(api):
    response = api.get(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyers",
        params={"snapshot_id": str(uuid.uuid4()), "offset": 0, "limit": 10},
        headers=_h(key="list-404"),
    )
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_get_buyer_returns_the_contract_subset_and_404s_foreign(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors", fit="match")
    own = api.get(f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}", headers=_h(key="get-01"))
    assert own.status_code == 200, own.text
    assert own.json()["data"]["id"] == buyer_id
    foreign = api.get(f"/v1/workspaces/{WORKSPACE_B}/buyers/{buyer_id}", headers=_h(key="get-02"))
    assert foreign.status_code == 404
    assert "Alpha" not in foreign.text


def _admin_membership(seeded, subject=ADMIN):
    user_id = uuid.uuid5(uuid.NAMESPACE_URL, subject)
    with psycopg.connect(seeded, autocommit=True) as conn:
        return str(conn.execute(
            "SELECT id FROM memberships WHERE workspace_id = %s AND user_id = %s",
            (WORKSPACE_A, user_id),
        ).fetchone()[0])


def test_update_buyer_bumps_the_version_and_sets_the_etag(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors", fit="match")
    response = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}",
        json={"note": "Reviewed scope."},
        headers=_h(key="update-01", **{"If-Match": '"1"'}),
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["note"] == "Reviewed scope."
    assert data["version"] == 2
    assert response.headers["ETag"] == '"2"'


def test_update_buyer_rejects_stale_and_missing_if_match(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors")
    stale = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}",
        json={"note": "x"},
        headers=_h(key="update-10", **{"If-Match": '"9"'}),
    )
    assert stale.status_code == 412 and stale.json()["code"] == "STALE_REVISION"
    missing = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}",
        json={"note": "x"}, headers=_h(key="update-11"),
    )
    assert missing.status_code == 400


def test_update_buyer_replays_and_validates_the_owner(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors")
    body = {"owner_membership_id": _admin_membership(seeded)}
    first = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}",
        json=body, headers=_h(key="update-replay", **{"If-Match": '"1"'}),
    )
    assert first.status_code == 200, first.text
    assert first.json()["data"]["owner_membership_id"] == body["owner_membership_id"]
    replay = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}",
        json=body, headers=_h(key="update-replay", **{"If-Match": '"1"'}),
    )
    assert replay.json()["data"]["version"] == 2  # a replay, not a second bump
    bad = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}",
        json={"owner_membership_id": str(uuid.uuid4())},
        headers=_h(key="update-bad-owner", **{"If-Match": '"2"'}),
    )
    assert bad.status_code == 422


def test_update_buyer_404s_a_foreign_buyer_and_conflicts_on_reuse(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors")
    foreign = api.patch(
        f"/v1/workspaces/{WORKSPACE_B}/buyers/{buyer_id}",
        json={"note": "x"}, headers=_h(key="update-f", **{"If-Match": '"1"'}),
    )
    assert foreign.status_code == 404
    assert api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}",
        json={"note": "one"}, headers=_h(key="update-conflict", **{"If-Match": '"1"'}),
    ).status_code == 200
    conflict = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}",
        json={"note": "two"}, headers=_h(key="update-conflict", **{"If-Match": '"2"'}),
    )
    assert conflict.status_code == 409 and conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_update_buyer_rejects_a_malformed_owner_not_a_server_error(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors")
    response = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}",
        json={"owner_membership_id": "not-a-uuid"},
        headers=_h(key="update-malformed-owner", **{"If-Match": '"1"'}),
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "INVALID_REQUEST"
    assert "owner_membership_id" in response.json()["message"]


def test_update_buyer_clears_the_owner_with_an_explicit_null(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors")
    membership_id = _admin_membership(seeded)
    set_owner = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}",
        json={"owner_membership_id": membership_id},
        headers=_h(key="clear-owner-set", **{"If-Match": '"1"'}),
    )
    assert set_owner.status_code == 200, set_owner.text
    assert set_owner.json()["data"]["owner_membership_id"] == membership_id
    assert set_owner.json()["data"]["version"] == 2
    cleared = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}",
        json={"owner_membership_id": None},
        headers=_h(key="clear-owner-null", **{"If-Match": '"2"'}),
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["owner_membership_id"] is None
    assert cleared.json()["data"]["version"] == 3
    assert cleared.headers["ETag"] == '"3"'


def test_update_buyer_denies_a_viewer(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors")
    response = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}",
        json={"note": "viewer cannot write"},
        headers=_h(subject=VIEWER, key="update-viewer", **{"If-Match": '"1"'}),
    )
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "PERMISSION_DENIED"


def test_review_updates_only_the_explicit_selection(api, seeded):
    first = _seed_buyer(seeded, name="Alpha Sensors", fit="match")
    second = _seed_buyer(seeded, name="Beta Sensors", fit="match")
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews",
        json={"selection": {"kind": "explicit", "buyers": [{"id": first, "version": 1}]},
              "status": "accepted", "reason": "reviewed evidence"},
        headers=_h(subject=REVIEWER, key="review-01"),
    )
    assert response.status_code == 200, response.text
    result = response.json()["data"]
    assert (result["requested"], result["updated"], result["blocked"], result["conflicts"]) == (1, 1, 0, 0)
    assert result["results"][0]["version"] == 2
    assert api.get(f"/v1/workspaces/{WORKSPACE_A}/buyers/{first}", headers=_h(key="r-get-1")).json()["data"]["version"] == 2
    assert api.get(f"/v1/workspaces/{WORKSPACE_A}/buyers/{second}", headers=_h(key="r-get-2")).json()["data"]["version"] == 1


def test_a_stale_review_version_conflicts_and_preserves_the_prior_record(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors", fit="match", review="accepted")
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews",
        json={"selection": {"kind": "explicit", "buyers": [{"id": buyer_id, "version": 9}]},
              "status": "rejected", "reason": "changed mind"},
        headers=_h(subject=REVIEWER, key="review-conflict"),
    )
    result = response.json()["data"]
    assert result["conflicts"] == 1 and result["updated"] == 0
    assert result["results"][0] == {"id": buyer_id, "status": "conflict", "reason_code": "version_conflict", "version": 1}
    assert api.get(f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}", headers=_h(key="r-get-3")).json()["data"]["review"]["status"] == "accepted"


def test_a_snapshot_review_expands_excluding_removed_ids(api, seeded):
    first = _seed_buyer(seeded, name="Alpha Sensors", fit="match")
    second = _seed_buyer(seeded, name="Beta Sensors", fit="match")
    snapshot_id = _snapshot(api, key="review-snap")
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews",
        json={"selection": {"kind": "snapshot", "snapshot_id": snapshot_id, "excluded_ids": [second]},
              "status": "accepted", "reason": "batch reviewed"},
        headers=_h(subject=REVIEWER, key="review-snap-key"),
    )
    result = response.json()["data"]
    assert result["requested"] == 1 and result["updated"] == 1
    assert {row["id"] for row in result["results"]} == {first}


def test_review_requires_a_reviewer_and_replays(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors", fit="match")
    body = {"selection": {"kind": "explicit", "buyers": [{"id": buyer_id, "version": 1}]},
            "status": "needs_information", "reason": "ask for detail"}
    denied = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews",
        json=body, headers=_h(subject=OPERATOR, key="review-denied"),
    )
    assert denied.status_code == 403
    first = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews",
        json=body, headers=_h(subject=REVIEWER, key="review-replay"),
    )
    assert first.status_code == 200 and first.json()["data"]["updated"] == 1
    replay = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews",
        json=body, headers=_h(subject=REVIEWER, key="review-replay"),
    )
    assert replay.json()["data"] == first.json()["data"]  # the stored result, not a re-apply
    assert api.get(f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}", headers=_h(key="r-get-4")).json()["data"]["version"] == 2


def test_a_long_review_reason_is_persisted(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors", fit="match")
    reason = "r" * 500
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews",
        json={"selection": {"kind": "explicit", "buyers": [{"id": buyer_id, "version": 1}]},
              "status": "accepted", "reason": reason},
        headers=_h(subject=REVIEWER, key="review-long-reason"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["updated"] == 1
    stored = api.get(f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}", headers=_h(key="r-get-long")).json()["data"]
    assert stored["review"]["reason"] == reason


def test_a_malformed_snapshot_id_is_rejected_not_a_server_error(api):
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews",
        json={"selection": {"kind": "snapshot", "snapshot_id": "not-a-uuid", "excluded_ids": []},
              "status": "accepted", "reason": "batch reviewed"},
        headers=_h(subject=REVIEWER, key="review-bad-snapshot"),
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "INVALID_REQUEST"
    assert "snapshot_id" in response.json()["message"]


def test_a_malformed_excluded_id_is_rejected_not_a_server_error(api, seeded):
    _seed_buyer(seeded, name="Alpha Sensors", fit="match")
    snapshot_id = _snapshot(api, key="review-bad-excluded-snap")
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews",
        json={"selection": {"kind": "snapshot", "snapshot_id": snapshot_id, "excluded_ids": ["not-a-uuid"]},
              "status": "accepted", "reason": "batch reviewed"},
        headers=_h(subject=REVIEWER, key="review-bad-excluded"),
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "INVALID_REQUEST"
    assert "excluded_ids" in response.json()["message"]


def test_a_malformed_explicit_id_is_rejected_not_a_server_error(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors", fit="match")
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews",
        json={"selection": {"kind": "explicit", "buyers": [
            {"id": buyer_id, "version": 1}, {"id": "not-a-uuid", "version": 1}]},
              "status": "accepted", "reason": "batch reviewed"},
        headers=_h(subject=REVIEWER, key="review-bad-item"),
    )
    # A malformed id never lands in the uuid-typed result; it is rejected up front.
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "INVALID_REQUEST"
    assert "buyer id" in response.json()["message"]


def test_a_review_without_a_fit_is_stored_but_not_emitted(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors")
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews",
        json={"selection": {"kind": "explicit", "buyers": [{"id": buyer_id, "version": 1}]},
              "status": "accepted", "reason": "no fit to anchor"},
        headers=_h(subject=REVIEWER, key="review-no-fit"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["updated"] == 1
    stored = api.get(f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}", headers=_h(key="r-get-no-fit")).json()["data"]
    assert "review" not in stored
    with psycopg.connect(seeded) as conn:
        count = conn.execute(
            "SELECT count(*) FROM human_reviews WHERE workspace_id = %s AND project_buyer_id = %s",
            (WORKSPACE_A, buyer_id),
        ).fetchone()[0]
    assert count == 1


def test_a_duplicate_explicit_id_is_processed_once(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors", fit="match")
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews",
        json={"selection": {"kind": "explicit", "buyers": [
            {"id": buyer_id, "version": 1}, {"id": buyer_id, "version": 1}]},
              "status": "accepted", "reason": "reviewed once"},
        headers=_h(subject=REVIEWER, key="review-dupe"),
    )
    assert response.status_code == 200, response.text
    result = response.json()["data"]
    assert result["requested"] == 1 and result["updated"] == 1
    assert result["results"] == [
        {"id": buyer_id, "status": "updated", "reason_code": "accepted", "version": 2}
    ]


def _seed_evidence(seeded, buyer_id, company_id):
    source_id = str(uuid.uuid4())
    evidence_id = str(uuid.uuid4())
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO source_documents(id, workspace_id, canonical_url, digest, retrieved_at, language) "
            "VALUES (%s, %s, 'https://example.test/a', 'sha256:x', now(), 'en')",
            (source_id, WORKSPACE_A),
        )
        conn.execute(
            "INSERT INTO evidence(id, workspace_id, project_id, company_id, source_document_id, stance, excerpt) "
            "VALUES (%s, %s, %s, %s, %s, 'supports', 'supports the requirement')",
            (evidence_id, WORKSPACE_A, PROJECT_A, company_id, source_id),
        )
    return evidence_id


def test_buyer_evidence_is_scoped_and_404s_foreign(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Alpha Sensors", fit="match")
    with psycopg.connect(seeded) as conn:
        company_id = conn.execute("SELECT company_id FROM project_buyers WHERE id = %s", (buyer_id,)).fetchone()[0]
    evidence_id = _seed_evidence(seeded, buyer_id, company_id)

    page = api.get(f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}/evidence", headers=_h(key="ev-01"))
    assert page.status_code == 200, page.text
    body = page.json()["data"]
    assert body["total"] == 1 and body["items"][0]["id"] == evidence_id
    assert body["items"][0]["relationship"] == "supports"
    assert body["items"][0]["source_url"] == "https://example.test/a"

    one = api.get(f"/v1/workspaces/{WORKSPACE_A}/evidence/{evidence_id}", headers=_h(key="ev-02"))
    assert one.status_code == 200 and one.json()["data"]["id"] == evidence_id

    foreign = api.get(f"/v1/workspaces/{WORKSPACE_B}/evidence/{evidence_id}", headers=_h(key="ev-03"))
    assert foreign.status_code == 404
    assert evidence_id not in foreign.text


def test_0011_downgrade_truncates_a_long_review_reason(migrated):
    """0011's downgrade narrows `reason` without failing on a stored >400-char value."""
    import os

    from alembic import command
    from alembic.config import Config

    from buyeros_api.settings import get_settings

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))

    workspace_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    company_id = str(uuid.uuid4())
    buyer_id = str(uuid.uuid4())
    reason = "r" * 500
    os.environ["BUYEROS_DATABASE_URL"] = migrated
    get_settings.cache_clear()
    try:
        with psycopg.connect(migrated, autocommit=True) as conn:
            conn.execute("INSERT INTO workspaces(id, name, data_mode) VALUES (%s, 'mig', 'live')", (workspace_id,))
            conn.execute(
                "INSERT INTO projects(id, workspace_id, name, company_name, offer, markets, language_preferences, "
                "version) VALUES (%s, %s, 'P', 'C', 'o', '{US}', '{en}', 1)",
                (project_id, workspace_id),
            )
            conn.execute(
                "INSERT INTO companies(id, workspace_id, legal_name, display_name) VALUES (%s, %s, 'C', 'C Co')",
                (company_id, workspace_id),
            )
            conn.execute(
                "INSERT INTO project_buyers(id, workspace_id, project_id, company_id) VALUES (%s, %s, %s, %s)",
                (buyer_id, workspace_id, project_id, company_id),
            )
            conn.execute(
                "INSERT INTO human_reviews(id, workspace_id, project_buyer_id, state, reason, actor_user_id) "
                "VALUES (%s, %s, %s, 'accepted', %s, %s)",
                (str(uuid.uuid4()), workspace_id, buyer_id, reason, str(uuid.uuid4())),
            )

        command.downgrade(config, "0010_widen_idempotency_key")
        command.upgrade(config, "head")

        with psycopg.connect(migrated) as conn:
            stored = conn.execute(
                "SELECT reason FROM human_reviews WHERE workspace_id = %s", (workspace_id,)
            ).fetchone()
        assert stored is not None
        assert stored[0] == reason[:400]
    finally:
        command.upgrade(config, "head")
        with psycopg.connect(migrated, autocommit=True) as conn:
            conn.execute("DELETE FROM human_reviews WHERE workspace_id = %s", (workspace_id,))
            conn.execute("DELETE FROM project_buyers WHERE workspace_id = %s", (workspace_id,))
            conn.execute("DELETE FROM companies WHERE workspace_id = %s", (workspace_id,))
            conn.execute("DELETE FROM projects WHERE workspace_id = %s", (workspace_id,))
            conn.execute("DELETE FROM workspaces WHERE id = %s", (workspace_id,))
