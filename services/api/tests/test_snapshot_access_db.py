"""T08 actor-bound buyer snapshots and stable, bounded page reads on disposable PostgreSQL."""
from datetime import datetime, timedelta, timezone

import psycopg

from tests.test_buyer_review_db import (
    PROJECT_A, PROJECT_A2, WORKSPACE_A, OPERATOR, REVIEWER, _h, _seed_buyer, _snapshot, api,
)


def _list(api, snapshot_id, *, subject=OPERATOR, offset=0, limit=20, **params):
    return api.get(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyers",
        params={"snapshot_id": snapshot_id, "offset": offset, "limit": limit, **params},
        headers=_h(subject=subject),
    )


def test_actor_expiry_filter_guard(api, seeded):
    _seed_buyer(seeded, name="Actor Bound Buyer")
    snapshot_id = _snapshot(api, key="t08-actor")
    assert _list(api, snapshot_id).status_code == 200
    assert _list(api, snapshot_id, subject=REVIEWER).status_code == 404
    denied_review = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews",
        json={"selection":{"kind":"snapshot","snapshot_id":snapshot_id,"excluded_ids":[]},
              "status":"accepted","reason":"reviewed by other actor"},
        headers=_h(subject=REVIEWER, key="t08-review-other-actor"),
    )
    assert denied_review.status_code == 404
    # A changed filter must not silently reuse the old snapshot.
    assert _list(api, snapshot_id, filters='{"q":"other"}').status_code == 422
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("UPDATE buyer_snapshots SET expires_at = %s WHERE id = %s",
                     (datetime.now(timezone.utc) - timedelta(seconds=1), snapshot_id))
    assert _list(api, snapshot_id).status_code in (404, 409)


def test_stable_pagination_while_new_results_arrive(api, seeded):
    ids = [_seed_buyer(seeded, name=f"Paged Buyer {i:02d}") for i in range(24)]
    snapshot_id = _snapshot(api, limit=24, key="t08-pages")
    first = _list(api, snapshot_id, offset=0, limit=12)
    assert first.status_code == 200, first.text
    _seed_buyer(seeded, name="Paged Buyer 00 Later")
    second = _list(api, snapshot_id, offset=12, limit=12)
    assert second.status_code == 200, second.text
    a, b = first.json()["data"], second.json()["data"]
    assert a["total"] == b["total"] == 24
    assert [item["id"] for item in a["items"] + b["items"]] == ids
    assert len({item["id"] for item in a["items"] + b["items"]}) == 24
    too_large = _list(api, snapshot_id, limit=101)
    assert too_large.status_code == 422


def test_historical_review_keeps_its_own_assessment_context_in_dossier_and_page(api, seeded):
    import uuid

    buyer_id = _seed_buyer(seeded, name="Historical fit buyer", fit="match", review="accepted")
    with psycopg.connect(seeded, autocommit=True) as conn:
        original_fit, original_icp = conn.execute(
            "SELECT f.id, f.icp_version_id FROM human_reviews r "
            "JOIN fit_assessments f ON f.id = r.fit_assessment_id "
            "WHERE r.project_buyer_id = %s", (buyer_id,),
        ).fetchone()
        successor_icp, successor_fit = uuid.uuid4(), uuid.uuid4()
        conn.execute(
            "INSERT INTO icp_versions(id, workspace_id, project_id, number, content, content_hash, "
            "basis_offer_revision) VALUES (%s, %s, %s, 2, '{}'::jsonb, %s, 1)",
            (successor_icp, WORKSPACE_A, PROJECT_A, "sha256:" + "1" * 64),
        )
        conn.execute(
            "INSERT INTO fit_assessments(id, workspace_id, project_id, project_buyer_id, "
            "icp_version_id, evidence_set_hash, verdict, rationale, evidence_ids, created_at) "
            "VALUES (%s, %s, %s, %s, %s, 'sha256:next', 'needs_review', "
            "'new assessment', '[]'::jsonb, now() + interval '1 second')",
            (successor_fit, WORKSPACE_A, PROJECT_A, buyer_id, successor_icp),
        )
    snapshot_id = _snapshot(api, key="t08-historical-fit")
    detail = api.get(f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}", headers=_h()).json()["data"]
    page = _list(api, snapshot_id).json()["data"]["items"][0]
    for row in (detail, page):
        assert row["fit"]["id"] == str(successor_fit)
        assert row["review"]["assessment_id"] == str(original_fit)
        assert row["review"]["icp_version_id"] == str(original_icp)


def test_1001_explicit_buyers_are_rejected_without_a_review_write(api, seeded):
    import uuid

    requested = [{"id": str(uuid.uuid4()), "version": 1} for _ in range(1001)]
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews",
        json={"selection": {"kind": "explicit", "buyers": requested},
              "status": "accepted", "reason": "above bounded selection"},
        headers=_h(subject=REVIEWER, key="t08-over-selection"),
    )
    assert response.status_code == 422, response.text
    with psycopg.connect(seeded) as conn:
        count = conn.execute("SELECT count(*) FROM human_reviews WHERE workspace_id = %s",
                             (WORKSPACE_A,)).fetchone()[0]
    assert count == 0


def test_snapshot_name_ties_use_buyer_id_and_page_reads_are_query_bounded(api, seeded, monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession

    buyer_ids = [_seed_buyer(seeded, name="Same Name") for _ in range(24)]
    snapshot_id = _snapshot(api, limit=24, key="t08-tie-page")
    count = 0
    original = AsyncSession.execute

    async def counted(self, *args, **kwargs):
        nonlocal count
        count += 1
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "execute", counted)
    response = _list(api, snapshot_id, offset=0, limit=24)
    assert response.status_code == 200, response.text
    observed = [item["id"] for item in response.json()["data"]["items"]]
    assert observed == sorted(buyer_ids)
    assert count <= 12, f"listBuyers dispatched {count} SQL queries for one 24-row page"


def test_snapshot_rejects_cross_project_and_revoked_current_membership(api, seeded):
    _seed_buyer(seeded, name="Scoped buyer")
    snapshot_id = _snapshot(api, key="t08-project-scope")
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO projects(id, workspace_id, name, company_name, offer, markets, "
            "language_preferences, version) VALUES (%s, %s, 'Other Project', "
            "'Other Seller', 'offer', '{US}', '{en}', 1)", (PROJECT_A2, WORKSPACE_A),
        )
    try:
        cross = api.get(
            f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A2}/buyers",
            params={"snapshot_id": snapshot_id}, headers=_h(),
        )
        assert cross.status_code == 404
        with psycopg.connect(seeded, autocommit=True) as conn:
            conn.execute(
                "UPDATE memberships SET active = false WHERE workspace_id = %s AND user_id = "
                "(SELECT id FROM users WHERE subject = %s)", (WORKSPACE_A, OPERATOR),
            )
        assert _list(api, snapshot_id).status_code == 404
    finally:
        with psycopg.connect(seeded, autocommit=True) as conn:
            conn.execute("DELETE FROM projects WHERE id = %s", (PROJECT_A2,))


def test_t08_http_operations_emit_the_checked_in_response_contract(api, seeded):
    from tests.contract_validation import assert_contract_response
    from tests.test_buyer_review_db import _seed_evidence

    buyer_id = _seed_buyer(seeded, name="Contract Buyer", fit="match")
    with psycopg.connect(seeded) as conn:
        company_id = conn.execute(
            "SELECT company_id FROM project_buyers WHERE id = %s", (buyer_id,)
        ).fetchone()[0]
    evidence_id = _seed_evidence(seeded, buyer_id, company_id)

    snapshot = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-snapshots",
        json={"filters": {}, "sort": "name_asc", "requested_limit": 10},
        headers=_h(key="t08-contract"),
    )
    assert snapshot.status_code == 201, snapshot.text
    assert_contract_response("BuyerSnapshotResponse", snapshot.json())
    snapshot_id = snapshot.json()["data"]["id"]

    operations = (
        ("BuyerPageResponse", _list(api, snapshot_id)),
        ("BuyerResponse", api.get(
            f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}", headers=_h())),
        ("EvidencePageResponse", api.get(
            f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}/evidence", headers=_h())),
        ("EvidenceResponse", api.get(
            f"/v1/workspaces/{WORKSPACE_A}/evidence/{evidence_id}", headers=_h())),
    )
    for schema_name, response in operations:
        assert response.status_code == 200, (schema_name, response.text)
        assert_contract_response(schema_name, response.json())
