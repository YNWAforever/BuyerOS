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
    assert SnapshotCreate.model_validate(base).requested_limit == 10
    for bad in (
        {**base, "extra": 1},
        {**base, "sort": "newest"},
        {**base, "requested_limit": 0},
        {**base, "requested_limit": 1001},
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
