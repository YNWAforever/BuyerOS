"""T21 quote preview: immutable eligibility and zero economic/provider side effects."""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import psycopg
import pytest

from buyeros_api.api.routes.quotes import selected_contact_quote_capability
from buyeros_api.db.icp import canonical_hash
from buyeros_api.providers.base import Money, ProviderCapability
from tests.test_api_projects_db import ADMIN, OPERATOR, REVIEWER, WORKSPACE_A, _h, api

PROJECT = "a0000000-0000-4000-8000-000000000001"
ICP = "d0000000-0000-4000-8000-000000000021"


def _capability(price="0.300000", version="fixture-price-v1"):
    return ProviderCapability(
        provider="fixture", adapter_version="contact-fixture-v1", service="contact",
        markets=frozenset({"US"}), languages=frozenset({"en"}),
        roles=frozenset({"Procurement manager"}), auth_model="fixture",
        pricing_version=version, max_liability=Money(Decimal(price)),
        idempotency="verified", status="verified", callback="unsupported", cancel="unsupported",
        retention="fixture-only", verified_at=datetime.now(timezone.utc),
        source_urls=("https://fixture.invalid/capability",),
    )


@pytest.fixture
def quote_case(api, seeded):
    content = {"markets": ["US"], "languages": ["en"], "buyer_types": ["distributor"]}
    with psycopg.connect(seeded, autocommit=True) as db:
        db.execute(
            "INSERT INTO icp_versions(id,workspace_id,project_id,number,basis_offer_revision,content,content_hash,approved_at,approved_by) "
            "VALUES (%s,%s,%s,1,1,%s::jsonb,%s,now(),%s)",
            (ICP, WORKSPACE_A, PROJECT, json.dumps(content), canonical_hash(content),
             str(uuid.uuid5(uuid.NAMESPACE_URL, REVIEWER))),
        )
        db.execute("UPDATE projects SET active_icp_version_id=%s WHERE id=%s", (ICP, PROJECT))
        db.execute(
            "INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,controller_scope_id,purpose,status,"
            "policy_version,basis_reference,provenance,countries,expires_at,retention_days,decision_author_id) "
            "VALUES (%s,%s,'project',%s,%s,'contact_research','permitted','fixture-v1','fixture','fixture',"
            "'{US}',now()+interval '1 day',1,%s)",
            (str(uuid.uuid4()), WORKSPACE_A, PROJECT, WORKSPACE_A,
             str(uuid.uuid5(uuid.NAMESPACE_URL, REVIEWER))),
        )
        buyers = []
        for number in (1, 2):
            company, buyer, fit, source, evidence = (str(uuid.uuid4()) for _ in range(5))
            db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name,domain) "
                       "VALUES (%s,%s,%s,%s,%s)",
                       (company, WORKSPACE_A, f"Fixture company {number}", f"Fixture company {number}",
                        f"fixture{number}.example"))
            db.execute("INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES (%s,%s,%s,%s)",
                       (buyer, WORKSPACE_A, PROJECT, company))
            db.execute(
                "INSERT INTO source_documents(id,workspace_id,project_id,permission_purpose,canonical_url,digest,"
                "retrieved_at,language,excerpt,retention_until) VALUES (%s,%s,%s,'account_research',%s,%s,"
                "now(),'en','Fixture cited source',now()+interval '1 day')",
                (source, WORKSPACE_A, PROJECT, f"https://fixture{number}.example/source", "a" * 64),
            )
            db.execute("INSERT INTO evidence(id,workspace_id,project_id,company_id,source_document_id,stance,excerpt) "
                       "VALUES (%s,%s,%s,%s,%s,'supports','Fixture cited source')",
                       (evidence, WORKSPACE_A, PROJECT, company, source))
            db.execute(
                "INSERT INTO fit_assessments(id,workspace_id,project_id,project_buyer_id,icp_version_id,"
                "evidence_set_hash,verdict,rationale,evidence_ids) VALUES (%s,%s,%s,%s,%s,%s,'match',"
                "'Fixture match',%s::jsonb)",
                (fit, WORKSPACE_A, PROJECT, buyer, ICP, canonical_hash({"evidence": [evidence]}),
                 json.dumps([evidence])),
            )
            db.execute(
                "INSERT INTO human_reviews(id,workspace_id,project_buyer_id,state,actor_user_id,fit_assessment_id) "
                "VALUES (%s,%s,%s,'accepted',%s,%s)",
                (str(uuid.uuid4()), WORKSPACE_A, buyer,
                 str(uuid.uuid5(uuid.NAMESPACE_URL, REVIEWER)), fit),
            )
            buyers.append((buyer, company))
        db.execute(
            "INSERT INTO suppressions(id,workspace_id,subject_key_hash,subject_type,subject_id,"
            "controller_scope_id,purpose,purposes,reason,active,actor_id) "
            "VALUES (%s,%s,%s,'company',%s,%s,'contact_research',ARRAY['contact_research'],"
            "'fixture suppression',true,%s)",
            (str(uuid.uuid4()), WORKSPACE_A, "b" * 64, buyers[1][1], WORKSPACE_A,
             str(uuid.uuid5(uuid.NAMESPACE_URL, REVIEWER))),
        )
    api.app.dependency_overrides[selected_contact_quote_capability] = lambda: (_capability(), "test")
    try:
        yield api, seeded, buyers
    finally:
        api.app.dependency_overrides.pop(selected_contact_quote_capability, None)
        with psycopg.connect(seeded, autocommit=True) as db:
            for table in ("outcome_events", "buyer_snapshot_items", "buyer_snapshots", "export_jobs", "approvals", "draft_revisions", "outreach_drafts", "async_job_items",
                          "provider_callback_routes", "provider_events", "outbox_events", "async_jobs",
                          "provider_operations", "enrichment_jobs",
                          "budget_reservation_allocations", "cost_events", "budget_reservations", "enrichment_quotes",
                          "suppressions", "policy_decisions", "human_reviews",
                          "fit_assessments", "evidence", "source_documents", "contact_points", "search_runs", "project_buyers", "companies"):
                db.execute(f"DELETE FROM {table} WHERE workspace_id=%s", (WORKSPACE_A,))
            db.execute("UPDATE projects SET active_icp_version_id=NULL WHERE id=%s", (PROJECT,))
            db.execute("DELETE FROM icp_versions WHERE id=%s", (ICP,))


def _body(buyers):
    return {"selection": {"kind": "explicit", "buyers": [
        {"id": buyer, "version": 1} for buyer, _ in buyers]},
        "purpose": "contact_research", "roles": ["Procurement manager"],
        "contact_type": "business_email"}


def _post(api, body, *, key="quote-fixture-0001", subject=OPERATOR):
    return api.post(f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/enrichment-quotes",
                    json=body, headers=_h(subject=subject, key=key))


def test_quote_is_actor_bound_partial_and_creates_no_hold_or_provider_intent(quote_case):
    client, dsn, buyers = quote_case
    first = _post(client, _body(buyers))
    assert first.status_code == 201, first.text
    data = first.json()["data"]
    assert data["status"] == "quoted" and data["actor_id"] == str(uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR))
    assert data["eligible_buyer_ids"] == [buyers[0][0]]
    by_buyer = {line["buyer_id"]: line for line in data["eligibility"]}
    assert by_buyer[buyers[0][0]]["eligible"] is True
    assert by_buyer[buyers[1][0]]["reason_codes"] == ["suppression_active"]
    assert data["max_cost"] == {"amount": "0.300000", "currency": "USD"}
    assert data["reservation_id"] is None and data["consumed_job_id"] is None
    assert len(data["quote_hash"]) == len(data["request_hash"]) == 64
    with psycopg.connect(dsn) as db:
        for table in ("budget_reservations", "provider_operations", "outbox_events", "enrichment_jobs"):
            assert db.execute(f"SELECT count(*) FROM {table} WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == 0
    replay = _post(client, _body(buyers))
    assert replay.status_code == 201 and replay.json()["data"]["id"] == data["id"]
    changed = _post(client, {**_body(buyers), "roles": ["Sales director"]})
    assert changed.status_code == 409 and changed.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_quote_read_cancel_and_stale_context_are_fail_closed(quote_case):
    client, dsn, buyers = quote_case
    quote = _post(client, _body(buyers), key="quote-fixture-0002").json()["data"]
    path = f"/v1/workspaces/{WORKSPACE_A}/enrichment-quotes/{quote['id']}"
    assert client.get(path, headers=_h()).json()["data"]["id"] == quote["id"]
    assert client.post(path + "/cancel", headers=_h(subject=ADMIN, key="quote-other-actor", **{"If-Match": '"1"'}), json={"reason":"No longer needed"}).status_code == 403
    cancelled = client.post(path + "/cancel", headers=_h(key="quote-cancel-0001", **{"If-Match": '"1"'}), json={"reason":"No longer needed"})
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert cancelled.json()["data"]["reservation_id"] is None
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE project_buyers SET version=2 WHERE id=%s", (buyers[0][0],))
    stale = _post(client, _body(buyers), key="quote-stale-0001")
    assert stale.status_code == 412 and stale.json()["code"] == "STALE_REVISION"


def test_quote_requires_selected_verified_pricing_and_operator_role(quote_case):
    client, _dsn, buyers = quote_case
    assert _post(client, _body(buyers), key="quote-reviewer-0001", subject=REVIEWER).status_code == 403
    client.app.dependency_overrides.pop(selected_contact_quote_capability)
    unavailable = _post(client, _body(buyers), key="quote-provider-0001")
    assert unavailable.status_code == 503 and unavailable.json()["code"] == "PROVIDER_UNAVAILABLE"



def test_quote_expiry_actor_scope_and_price_version_require_a_fresh_quote(quote_case):
    from tests import auth_fixtures as fx

    client, dsn, buyers = quote_case
    original = _post(client, _body(buyers), key="quote-price-old").json()["data"]
    other = "auth0|quote-operator-b"
    other_id = uuid.uuid5(uuid.NAMESPACE_URL, other)
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("INSERT INTO users(id,issuer,subject) VALUES (%s,%s,%s)", (other_id, fx.ISSUER, other))
        db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES (%s,%s,%s,%s,true)",
                   (uuid.uuid4(), WORKSPACE_A, other_id, ["operator"]))
    try:
        path = f"/v1/workspaces/{WORKSPACE_A}/enrichment-quotes/{original['id']}"
        assert client.get(path, headers=_h(subject=other)).status_code == 404
        assert client.get(path, headers=_h(subject=ADMIN)).status_code == 200
        assert client.post(path + "/cancel", headers=_h(
            subject=other, key="quote-other-cancel", **{"If-Match": '"1"'}), json={"reason":"No longer needed"}).status_code == 403
        client.app.dependency_overrides[selected_contact_quote_capability] = lambda: (_capability(
            price="0.400000", version="fixture-price-v2"), "test")
        changed = _post(client, _body(buyers), key="quote-price-new").json()["data"]
        assert changed["id"] != original["id"]
        assert changed["pricing_version"] == "fixture-price-v2"
        assert changed["quote_hash"] != original["quote_hash"]
        assert changed["max_cost"]["amount"] == "0.400000"
        with psycopg.connect(dsn, autocommit=True) as db:
            db.execute("UPDATE enrichment_quotes SET expires_at=now()-interval '1 minute' WHERE id=%s",
                       (original["id"],))
        assert client.get(path, headers=_h()).json()["data"]["status"] == "expired"
        replay = _post(client, _body(buyers), key="quote-price-old")
        assert replay.status_code == 201 and replay.json()["data"]["status"] == "expired"
        expired = client.post(path + "/cancel", headers=_h(
            key="quote-expired-cancel", **{"If-Match": '"1"'}), json={"reason":"No longer needed"})
        assert expired.status_code == 409 and expired.json()["code"] == "QUOTE_EXPIRED"
    finally:
        with psycopg.connect(dsn, autocommit=True) as db:
            db.execute("DELETE FROM memberships WHERE user_id=%s", (other_id,))
            db.execute("DELETE FROM users WHERE id=%s", (other_id,))


def test_quote_rechecks_profile_policy_and_actual_eligible_ceiling(quote_case):
    client, dsn, buyers = quote_case
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE suppressions SET active=false WHERE workspace_id=%s", (WORKSPACE_A,))
    both = _post(client, _body(buyers), key="quote-two-eligible").json()["data"]
    assert set(both["eligible_buyer_ids"]) == {buyer for buyer, _ in buyers}
    assert both["max_cost"]["amount"] == "0.600000"
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("DELETE FROM policy_decisions WHERE workspace_id=%s", (WORKSPACE_A,))
    unknown = _post(client, _body(buyers), key="quote-policy-unknown").json()["data"]
    assert unknown["eligible_buyer_ids"] == []
    assert unknown["max_cost"]["amount"] == "0.000000"
    assert all("policy_unknown" in line["reason_codes"] for line in unknown["eligibility"])
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE projects SET offer_revision=2 WHERE id=%s", (PROJECT,))
    stale = _post(client, _body(buyers), key="quote-profile-stale")
    assert stale.status_code == 412 and stale.json()["code"] == "STALE_REVISION"


def test_quote_blocks_a_buyer_with_an_active_contact_job(quote_case):
    client, dsn, buyers = quote_case
    first = _post(client, _body(buyers), key="quote-active-base").json()["data"]
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("INSERT INTO enrichment_jobs(id,workspace_id,quote_id,state) VALUES (%s,%s,%s,'reserved')",
                   (str(uuid.uuid4()), WORKSPACE_A, first["id"]))
    second = _post(client, _body(buyers), key="quote-active-next").json()["data"]
    lines = {line["buyer_id"]: line for line in second["eligibility"]}
    assert "lookup_in_progress" in lines[buyers[0][0]]["reason_codes"]
    assert second["eligible_buyer_ids"] == []
    assert second["max_cost"]["amount"] == "0.000000"
