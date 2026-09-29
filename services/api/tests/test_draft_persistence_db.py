"""T24 durable grounded draft admission and immutable revisions."""

import json
import uuid

import psycopg

from buyeros_api.db.icp import canonical_hash
from tests.contract_validation import assert_contract_response
from tests.icp_fixtures import FACT_ID
from tests.test_api_projects_db import api
from tests.test_lookup_quotes_db import ICP, PROJECT, WORKSPACE_A, OPERATOR, REVIEWER, _h, quote_case


def _prepare(api, dsn, buyer_id):
    with psycopg.connect(dsn, autocommit=True) as db:
        content = {"markets": ["US"], "languages": ["en"], "buyer_types": ["distributor"],
                   "offer_facts": [{"id": FACT_ID, "field": "product", "value": "Industrial sensors",
                                    "provenance": "user_entered", "approved": False}]}
        db.execute("UPDATE icp_versions SET content=%s::jsonb,content_hash=%s WHERE id=%s",
                   (json.dumps(content), canonical_hash(content), ICP))
        evidence_id = db.execute("SELECT e.id FROM evidence e JOIN project_buyers b "
                                 "ON b.workspace_id=e.workspace_id AND b.company_id=e.company_id "
                                 "WHERE b.id=%s", (buyer_id,)).fetchone()[0]
        db.execute("INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,"
                   "controller_scope_id,purpose,status,policy_version,basis_reference,provenance,"
                   "countries,expires_at,retention_days,decision_author_id) "
                   "VALUES (%s,%s,'project',%s,%s,'draft_preparation','permitted','fixture-v1',"
                   "'fixture','fixture',ARRAY['US'],now()+interval '1 day',1,%s)",
                   (uuid.uuid4(), WORKSPACE_A, PROJECT, WORKSPACE_A,
                    uuid.uuid5(uuid.NAMESPACE_URL, REVIEWER)))
        result = str(evidence_id)
    sender = api.patch(f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}",
                       json={"sender_identity": {"display_name": "Alex Chan", "role_title": "Partner",
                            "organization": "ProjectA Co", "business_email": "alex@example.test",
                            "country": "US", "sender_confirmation": True,
                            "reason": "Approved draft preparation identity"}},
                       headers=_h(REVIEWER, key="draft-sender-001", **{"If-Match": '"1"'}))
    assert sender.status_code == 200, sender.text
    return result


def _request(buyer_id, evidence_id):
    return {"buyer_id": buyer_id, "buyer_version": 1, "objective": "Introduce our offer",
            "tone": "professional", "language": "en", "approved_offer_fact_ids": [FACT_ID],
            "evidence_refs": [{"id": evidence_id, "version": 1}], "kind": "initial",
            "max_cost": {"amount": "0.000000", "currency": "USD"}}


def test_zero_cost_grounded_draft_is_queued_without_provider_or_budget_hold(quote_case):
    api, dsn, buyers = quote_case
    buyer_id = buyers[0][0]
    evidence_id = _prepare(api, dsn, buyer_id)
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/drafts"
    response = api.post(path, json=_request(buyer_id, evidence_id),
                        headers=_h(OPERATOR, key="draft-generate-001"))
    assert response.status_code == 202, response.text
    assert_contract_response("AsyncJobResponse", response.json())
    job = response.json()["data"]
    assert job["kind"] == "draft_generation" and job["status"] == "queued"
    replay = api.post(path, json=_request(buyer_id, evidence_id),
                      headers=_h(OPERATOR, key="draft-generate-001"))
    assert replay.status_code == 202, replay.text
    assert replay.json()["data"]["id"] == job["id"]
    paid = _request(buyer_id, evidence_id)
    paid["max_cost"]["amount"] = "1.000000"
    unavailable = api.post(path, json=paid, headers=_h(OPERATOR, key="draft-paid-001"))
    assert unavailable.status_code == 503 and unavailable.json()["code"] == "PROVIDER_UNAVAILABLE"
    addressed = _request(buyer_id, evidence_id)
    addressed["recipient_contact_id"] = str(uuid.uuid4())
    unavailable = api.post(path, json=addressed, headers=_h(OPERATOR, key="draft-addressed-001"))
    assert unavailable.status_code == 503 and unavailable.json()["code"] == "PROVIDER_UNAVAILABLE"
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT count(*) FROM outbox_events WHERE event_type='draft.generate'").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM budget_reservations WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM provider_operations WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == 0


def _seed_draft(dsn, buyer_id, evidence_id, *, body="We offer: Industrial sensors"):
    draft_id, revision_id = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(dsn, autocommit=True) as db:
        sender = db.execute("SELECT version_key FROM sender_identity_versions WHERE project_id=%s "
                            "AND retired=false", (PROJECT,)).fetchone()[0]
        content = {"subject": "Introduction: Industrial sensors", "body": body,
                   "claims": [{"text": "Industrial sensors", "kind": "offer_fact",
                               "offer_fact_ids": [FACT_ID], "evidence_ids": []}],
                   "recipient_contact_id": None, "sender_identity_version": sender,
                   "evidence_refs": [{"id": evidence_id, "version": 1}],
                   "objective": "Introduce our offer", "tone": "professional", "language": "en",
                   "kind": "initial", "parent_draft_id": None,
                   "value_proposition_fact_ids": [FACT_ID], "icp_version_id": ICP,
                   "evidence_set_hash": "a"*64, "policy_decision_ids": [],
                   "context_hash": "b"*64, "grounding_status": "grounded"}
        db.execute("INSERT INTO outreach_drafts(id,workspace_id,project_id,buyer_id,current_revision,state) "
                   "VALUES (%s,%s,%s,%s,1,'draft')", (draft_id, WORKSPACE_A, PROJECT, buyer_id))
        db.execute("INSERT INTO draft_revisions(id,workspace_id,draft_id,revision_number,"
                   "content,content_hash,evidence_ids,offer_fact_ids) "
                   "VALUES (%s,%s,%s,1,%s::jsonb,%s,%s::jsonb,%s::jsonb)",
                   (revision_id, WORKSPACE_A, draft_id, json.dumps(content), "c"*64,
                    json.dumps([evidence_id]), json.dumps([FACT_ID])))
    return str(draft_id)


def test_draft_read_list_and_versioned_edit_preserve_prior_revision(quote_case):
    api, dsn, buyers = quote_case
    buyer_id = buyers[0][0]
    evidence_id = _prepare(api, dsn, buyer_id)
    draft_id = _seed_draft(dsn, buyer_id, evidence_id)
    path = f"/v1/workspaces/{WORKSPACE_A}/drafts/{draft_id}"
    first = api.get(path, headers=_h(OPERATOR))
    assert first.status_code == 200, first.text
    assert_contract_response("DraftResponse", first.json())
    assert first.json()["data"]["body"] == "We offer: Industrial sensors"
    assert first.json()["data"]["delivery_enabled"] is False
    listed = api.get(f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/drafts?offset=0&limit=1",
                     headers=_h(OPERATOR))
    assert listed.status_code == 200, listed.text
    assert_contract_response("DraftPageResponse", listed.json())
    assert listed.json()["data"]["total"] == 1
    assert listed.json()["data"]["items"][0]["id"] == draft_id
    edited = api.patch(path, json={"body": "Revised human text"},
                       headers=_h(OPERATOR, key="draft-edit-001", **{"If-Match": '"1"'}))
    assert edited.status_code == 200, edited.text
    assert_contract_response("DraftResponse", edited.json())
    assert edited.json()["data"]["revision_number"] == 2
    assert edited.json()["data"]["body"] == "Revised human text"
    assert edited.json()["data"]["status"] == "draft"
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT count(*) FROM draft_revisions WHERE draft_id=%s",
                          (draft_id,)).fetchone()[0] == 2
        assert db.execute("SELECT content->>'body' FROM draft_revisions WHERE draft_id=%s "
                          "AND revision_number=1", (draft_id,)).fetchone()[0] == "We offer: Industrial sensors"
    replay = api.patch(path, json={"body": "Revised human text"},
                       headers=_h(OPERATOR, key="draft-edit-001", **{"If-Match": '"1"'}))
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"] == edited.json()["data"]
    stale = api.patch(path, json={"body": "Third edit"},
                      headers=_h(OPERATOR, key="draft-edit-002", **{"If-Match": '"1"'}))
    assert stale.status_code == 412, stale.text


def test_draft_edit_rejects_explicit_null_for_required_content(quote_case):
    api, dsn, buyers = quote_case
    buyer_id = buyers[0][0]
    evidence_id = _prepare(api, dsn, buyer_id)
    draft_id = _seed_draft(dsn, buyer_id, evidence_id)
    path = f"/v1/workspaces/{WORKSPACE_A}/drafts/{draft_id}"
    for index, field in enumerate(("subject", "body", "language", "tone", "objective",
                                   "sender_identity_version", "evidence_refs",
                                   "value_proposition_fact_ids")):
        response = api.patch(path, json={field: None},
            headers=_h(OPERATOR, key=f"null-draft-{index}", **{"If-Match": '"1"'}))
        assert response.status_code == 422, (field, response.text)
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT count(*) FROM draft_revisions WHERE draft_id=%s",
                          (draft_id,)).fetchone()[0] == 1


def test_draft_list_uses_bounded_real_database_pages(quote_case):
    api, dsn, buyers = quote_case
    buyer_id = buyers[0][0]
    evidence_id = _prepare(api, dsn, buyer_id)
    expected = {_seed_draft(dsn, buyer_id, evidence_id) for _ in range(3)}
    base = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/drafts"
    first = api.get(base + "?offset=0&limit=2", headers=_h(OPERATOR))
    second = api.get(base + "?offset=2&limit=2", headers=_h(OPERATOR))
    assert first.status_code == second.status_code == 200
    assert_contract_response("DraftPageResponse", first.json())
    assert_contract_response("DraftPageResponse", second.json())
    first_page, second_page = first.json()["data"], second.json()["data"]
    assert (first_page["total"], second_page["total"]) == (3, 3)
    assert (len(first_page["items"]), len(second_page["items"])) == (2, 1)
    assert {row["id"] for row in first_page["items"] + second_page["items"]} == expected
