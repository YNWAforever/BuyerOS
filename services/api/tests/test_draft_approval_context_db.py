"""T25 exact-context approval and permanent delivery kill boundary."""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest

from tests.test_api_projects_db import api
from tests.test_draft_persistence_db import _prepare, _seed_draft
from buyeros_api.services.draft_service import _digest
from tests.contract_validation import assert_contract_response
from tests.icp_fixtures import FACT_ID
from tests.test_lookup_quotes_db import OPERATOR, REVIEWER, WORKSPACE_A, PROJECT, ICP, _h, quote_case


def test_review_and_delivery_routes_are_real_and_delivery_never_dispatches(quote_case):
    api, dsn, buyers = quote_case
    evidence_id = _prepare(api, dsn, buyers[0][0])
    draft_id = _seed_draft(dsn, buyers[0][0], evidence_id)
    base = f"/v1/workspaces/{WORKSPACE_A}/drafts/{draft_id}"
    draft = api.get(base, headers=_h(OPERATOR)).json()["data"]
    review = api.post(base + "/review", json={
        "revision_id": draft["revision_id"], "content_hash": draft["content_hash"],
        "context_hash": draft["context_hash"]},
        headers=_h(OPERATOR, key="approval-review-red", **{"If-Match": '"1"'}))
    assert review.status_code != 501, review.text
    with psycopg.connect(dsn) as db:
        before = db.execute("SELECT count(*) FROM outbox_events WHERE workspace_id=%s",
                            (WORKSPACE_A,)).fetchone()[0]
    delivery = api.post(base + "/deliver", headers=_h(REVIEWER, key="delivery-red"))
    assert delivery.status_code == 403, delivery.text
    assert delivery.json()["code"] == "DELIVERY_DISABLED"
    with psycopg.connect(dsn) as db:
        after = db.execute("SELECT count(*) FROM outbox_events WHERE workspace_id=%s",
                           (WORKSPACE_A,)).fetchone()[0]
    assert after == before



def _addressed_case(api, dsn, buyers):
    buyer_id, company_id = buyers[0]
    evidence_id = _prepare(api, dsn, buyer_id)
    draft_id, revision_id, contact_id = (uuid.uuid4() for _ in range(3))
    with psycopg.connect(dsn, autocommit=True) as db:
        sender = db.execute("SELECT version_key FROM sender_identity_versions WHERE project_id=%s "
                            "AND retired=false", (PROJECT,)).fetchone()[0]
        fit_hash = db.execute("SELECT evidence_set_hash FROM fit_assessments WHERE project_buyer_id=%s",
                              (buyer_id,)).fetchone()[0]
        for purpose in ("outreach", "export_contacts"):
            db.execute("INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,"
                       "controller_scope_id,purpose,status,policy_version,basis_reference,provenance,"
                       "countries,expires_at,retention_days,decision_author_id) "
                       "VALUES (%s,%s,'project',%s,%s,%s,'permitted','fixture-v1','fixture',"
                       "'fixture',ARRAY['US'],now()+interval '1 day',1,%s)",
                       (uuid.uuid4(), WORKSPACE_A, PROJECT, WORKSPACE_A, purpose,
                        uuid.uuid5(uuid.NAMESPACE_URL, REVIEWER)))
        db.execute("INSERT INTO contact_points(id,workspace_id,company_id,type,normalized_value,"
                   "validity,checked_at,quarantined,retention_expires_at) VALUES (%s,%s,%s,'business_email',"
                   "'recipient@fixture.example','provider_marked_valid',now(),false,now()+interval '1 day')",
                   (contact_id, WORKSPACE_A, company_id))
        content = {
            "subject": "Introduction: Industrial sensors",
            "body": "We offer Industrial sensors.",
            "claims": [{"text": "Industrial sensors", "kind": "offer_fact",
                        "offer_fact_ids": [FACT_ID], "evidence_ids": []}],
            "recipient_contact_id": str(contact_id),
            "sender_identity_version": sender,
            "evidence_refs": [{"id": evidence_id, "version": 1}],
            "objective": "Introduce our offer", "tone": "professional",
            "language": "en", "kind": "initial", "parent_draft_id": None,
            "value_proposition_fact_ids": [FACT_ID], "icp_version_id": ICP,
            "evidence_set_hash": fit_hash, "policy_decision_ids": [],
            "grounding_status": "grounded",
        }
        context_keys = ("recipient_contact_id", "sender_identity_version", "evidence_refs",
                        "icp_version_id", "evidence_set_hash", "policy_decision_ids",
                        "objective", "tone", "language", "value_proposition_fact_ids")
        content["context_hash"] = _digest({key: content.get(key) for key in context_keys})
        db.execute("INSERT INTO outreach_drafts(id,workspace_id,project_id,buyer_id,current_revision,state) "
                   "VALUES (%s,%s,%s,%s,1,'draft')", (draft_id, WORKSPACE_A, PROJECT, buyer_id))
        db.execute("INSERT INTO draft_revisions(id,workspace_id,draft_id,revision_number,"
                   "content,content_hash,evidence_ids,offer_fact_ids) "
                   "VALUES (%s,%s,%s,1,%s::jsonb,%s,%s::jsonb,%s::jsonb)",
                   (revision_id, WORKSPACE_A, draft_id, json.dumps(content), _digest(content),
                    json.dumps([evidence_id]), json.dumps([FACT_ID])))
    return str(draft_id), str(contact_id)


def _review(api, draft_id, *, subject=OPERATOR, key="approval-review-001"):
    base = f"/v1/workspaces/{WORKSPACE_A}/drafts/{draft_id}"
    draft = api.get(base, headers=_h(subject)).json()["data"]
    return api.post(base + "/review", json={
        "revision_id": draft["revision_id"], "content_hash": draft["content_hash"],
        "context_hash": draft["context_hash"]},
        headers=_h(subject, key=key, **{"If-Match": f'"{draft["version"]}"'}))


def _approval_payload(review):
    data = review.json()["data"]
    context = data["approval_review"]
    return {
        "revision_id": data["revision_id"], "content_hash": data["content_hash"],
        "context_hash": data["context_hash"],
        "recipient_contact_id": context["recipient"]["id"],
        "recipient_contact_version": context["recipient"]["version"],
        "evidence_set_hash": data["evidence_set_hash"],
        "icp_version_id": data["icp_version_id"],
        "policy_decision_ids": data["policy_decision_ids"],
        "sender_identity_version": data["sender_identity_version"],
        "confirmation": True,
    }


def _approve(api, draft_id, payload, *, subject=REVIEWER, key="approval-approve-001"):
    return api.post(f"/v1/workspaces/{WORKSPACE_A}/drafts/{draft_id}/approvals",
                    json=payload, headers=_h(subject, key=key, **{"If-Match": '"2"'}))


def test_exact_context_fixture_approval_and_disabled_delivery(quote_case):
    api, dsn, buyers = quote_case
    draft_id, contact_id = _addressed_case(api, dsn, buyers)
    review = _review(api, draft_id)
    assert review.status_code == 200, review.text
    assert_contract_response("DraftResponse", review.json())
    assert review.json()["data"]["status"] == "review_requested"
    assert review.json()["data"]["approval_review"]["recipient"]["value"] == "recipient@fixture.example"
    payload = _approval_payload(review)
    assert payload["recipient_contact_id"] == contact_id
    assert len(payload["policy_decision_ids"]) == 3
    assert _approve(api, draft_id, payload, subject=OPERATOR, key="operator-approval").status_code == 403
    approval = _approve(api, draft_id, payload)
    assert approval.status_code == 201, approval.text
    assert_contract_response("ApprovalResponse", approval.json())
    data = approval.json()["data"]
    assert data["valid"] is True and data["context_hash"] == payload["context_hash"]
    with psycopg.connect(dsn) as db:
        before = db.execute("SELECT count(*) FROM outbox_events WHERE workspace_id=%s",
                            (WORKSPACE_A,)).fetchone()[0]
    delivery = api.post(f"/v1/workspaces/{WORKSPACE_A}/drafts/{draft_id}/deliver",
                        headers=_h(REVIEWER, key="approved-deliver"))
    assert delivery.status_code == 403 and delivery.json()["code"] == "DELIVERY_DISABLED"
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT count(*) FROM outbox_events WHERE workspace_id=%s",
                          (WORKSPACE_A,)).fetchone()[0] == before


def test_forged_hash_and_contact_change_fail_current_context(quote_case):
    api, dsn, buyers = quote_case
    draft_id, contact_id = _addressed_case(api, dsn, buyers)
    review = _review(api, draft_id)
    assert review.status_code == 200, review.text
    payload = _approval_payload(review)
    forged = _approve(api, draft_id, {**payload, "context_hash": "0" * 64},
                      key="forged-context")
    assert forged.status_code == 412 and forged.json()["code"] == "STALE_REVISION"
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE contact_points SET normalized_value='changed@fixture.example',version=version+1 "
                   "WHERE id=%s", (contact_id,))
    changed = _approve(api, draft_id, payload, key="changed-recipient")
    assert changed.status_code == 412 and changed.json()["code"] == "STALE_REVISION"
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT count(*) FROM approvals WHERE draft_id=%s", (draft_id,)).fetchone()[0] == 0



@pytest.mark.parametrize("changed_field", [
    "recipient_value", "contact_version", "recipient_expired", "sender", "icp", "evidence",
    "policy", "suppression", "review",
])
def test_material_change_since_review_blocks_approval(quote_case, changed_field):
    api, dsn, buyers = quote_case
    draft_id, contact_id = _addressed_case(api, dsn, buyers)
    review = _review(api, draft_id)
    assert review.status_code == 200, review.text
    payload = _approval_payload(review)
    with psycopg.connect(dsn, autocommit=True) as db:
        if changed_field == "recipient_value":
            db.execute("UPDATE contact_points SET normalized_value='new@fixture.example', "
                       "version=version+1 WHERE id=%s", (contact_id,))
        elif changed_field == "contact_version":
            db.execute("UPDATE contact_points SET version=version+1 WHERE id=%s", (contact_id,))
        elif changed_field == "recipient_expired":
            db.execute("UPDATE contact_points SET retention_expires_at=now()-interval '1 second' WHERE id=%s", (contact_id,))
        elif changed_field == "sender":
            db.execute("UPDATE projects SET active_sender_identity_version_id=NULL WHERE id=%s", (PROJECT,))
        elif changed_field == "icp":
            db.execute("UPDATE projects SET active_icp_version_id=NULL WHERE id=%s", (PROJECT,))
        elif changed_field == "evidence":
            db.execute("UPDATE evidence SET version=version+1 WHERE id=%s",
                       (review.json()["data"]["approval_review"]["evidence"][0]["id"],))
        elif changed_field == "policy":
            db.execute("UPDATE policy_decisions SET status='blocked',version=version+1 "
                       "WHERE workspace_id=%s AND purpose='outreach'", (WORKSPACE_A,))
        elif changed_field == "suppression":
            db.execute("INSERT INTO suppressions(id,workspace_id,subject_key_hash,subject_type,"
                       "subject_id,controller_scope_id,purpose,purposes,reason,active,actor_id) "
                       "VALUES (%s,%s,%s,'contact_point',%s,%s,'outreach',ARRAY['outreach'],"
                       "'Fixture opt out',true,%s)",
                       (uuid.uuid4(), WORKSPACE_A, "d" * 64, contact_id, WORKSPACE_A,
                        uuid.uuid5(uuid.NAMESPACE_URL, REVIEWER)))
        elif changed_field == "review":
            db.execute("INSERT INTO human_reviews(id,workspace_id,project_buyer_id,state,"
                       "actor_user_id,created_at) VALUES (%s,%s,%s,'rejected',%s,"
                       "now()+interval '1 second')",
                       (uuid.uuid4(), WORKSPACE_A, buyers[0][0],
                        uuid.uuid5(uuid.NAMESPACE_URL, REVIEWER)))
    response = _approve(api, draft_id, payload, key=f"stale-{changed_field}-001")
    assert response.status_code in {403, 412}, (changed_field, response.text)
    assert response.json()["code"] in {"STALE_REVISION", "EVIDENCE_STALE", "POLICY_BLOCKED"}
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT count(*) FROM approvals WHERE draft_id=%s", (draft_id,)).fetchone()[0] == 0


def test_removed_reviewer_membership_is_denied(quote_case):
    api, dsn, buyers = quote_case
    draft_id, _ = _addressed_case(api, dsn, buyers)
    review = _review(api, draft_id)
    payload = _approval_payload(review)
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE memberships SET active=false WHERE workspace_id=%s AND user_id=%s",
                   (WORKSPACE_A, uuid.uuid5(uuid.NAMESPACE_URL, REVIEWER)))
    response = _approve(api, draft_id, payload, key="removed-reviewer-001")
    assert response.status_code in {403, 404}, response.text
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT count(*) FROM approvals WHERE draft_id=%s", (draft_id,)).fetchone()[0] == 0


def test_edit_and_approval_share_one_state_precondition_winner(quote_case):
    api, dsn, buyers = quote_case
    draft_id, _ = _addressed_case(api, dsn, buyers)
    review = _review(api, draft_id)
    payload = _approval_payload(review)
    base = f"/v1/workspaces/{WORKSPACE_A}/drafts/{draft_id}"

    def approve():
        return _approve(api, draft_id, payload, key="race-approval-001")

    def edit():
        return api.patch(base, json={"body": "A translated successor message"},
                         headers=_h(OPERATOR, key="race-edit-001", **{"If-Match": '"2"'}))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [task.result() for task in [pool.submit(approve), pool.submit(edit)]]
    codes = sorted(row.status_code for row in results)
    assert codes in ([200, 412], [201, 412]), [row.text for row in results]
    with psycopg.connect(dsn) as db:
        active = db.execute("SELECT count(*) FROM approvals WHERE draft_id=%s AND "
                            "invalidated_reason IS NULL", (draft_id,)).fetchone()[0]
        revisions = db.execute("SELECT count(*) FROM draft_revisions WHERE draft_id=%s",
                               (draft_id,)).fetchone()[0]
    assert active + (revisions - 1) == 1


def test_translation_creates_revision_and_invalidates_review(quote_case):
    api, dsn, buyers = quote_case
    draft_id, _ = _addressed_case(api, dsn, buyers)
    review = _review(api, draft_id)
    payload = _approval_payload(review)
    base = f"/v1/workspaces/{WORKSPACE_A}/drafts/{draft_id}"
    edit = api.patch(base, json={"body": "Translated successor text", "language": "zh-HK"},
                     headers=_h(OPERATOR, key="translation-edit-001", **{"If-Match": '"2"'}))
    assert edit.status_code == 200, edit.text
    assert edit.json()["data"]["revision_number"] == 2
    assert edit.json()["data"]["version"] == 3
    assert edit.json()["data"]["status"] == "draft"
    stale = _approve(api, draft_id, payload, key="translation-stale-001")
    assert stale.status_code == 412 and stale.json()["code"] == "STALE_REVISION"



def test_detail_and_idempotent_replay_hide_stale_recipient_after_contact_change(quote_case):
    api, dsn, buyers = quote_case
    draft_id, contact_id = _addressed_case(api, dsn, buyers)
    original = api.get(f"/v1/workspaces/{WORKSPACE_A}/drafts/{draft_id}",
                       headers=_h(OPERATOR)).json()["data"]
    review = _review(api, draft_id)
    payload = _approval_payload(review)
    approval = _approve(api, draft_id, payload, key="approval-replay-current")
    assert approval.status_code == 201, approval.text
    replay = _approve(api, draft_id, payload, key="approval-replay-current")
    assert replay.status_code == 201 and replay.json()["data"]["id"] == approval.json()["data"]["id"]
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE contact_points SET normalized_value='revoked@fixture.example',"
                   "version=version+1 WHERE id=%s", (contact_id,))
    detail = api.get(f"/v1/workspaces/{WORKSPACE_A}/drafts/{draft_id}", headers=_h(REVIEWER))
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["status"] == "stale"
    assert "approval_review" not in detail.json()["data"]
    assert detail.json()["data"]["approval_id"] is None
    stale_replay = _approve(api, draft_id, payload, key="approval-replay-current")
    assert stale_replay.status_code == 412 and stale_replay.json()["code"] == "STALE_REVISION"
    review_replay = api.post(f"/v1/workspaces/{WORKSPACE_A}/drafts/{draft_id}/review",
        json={"revision_id": original["revision_id"], "content_hash": original["content_hash"],
              "context_hash": original["context_hash"]},
        headers=_h(OPERATOR, key="approval-review-001", **{"If-Match": '"1"'}))
    assert review_replay.status_code == 412
