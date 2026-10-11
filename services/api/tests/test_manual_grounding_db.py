"""Q12 D01/D03/U09: actual guarded HTTP + persistent revisions, fictional inputs only."""
import copy
import json
import os
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
from tests.test_draft_approval_context_db import _addressed_case, _review, _approval_payload
from tests.test_lookup_quotes_db import quote_case, WORKSPACE_A, PROJECT, ICP, OPERATOR, REVIEWER, _h
from tests.test_api_projects_db import api
from tests.icp_fixtures import FACT_ID
from tests.contract_validation import assert_contract_response

SUBJECT = "邀請😀了解產品"
BODY = "您好👩‍💻\nIndustrial sensors\nFixture public catalog lists industrial sensors.\n謝謝！"


def _case(quote_case):
    api, dsn, buyers = quote_case
    draft_id, _ = _addressed_case(api, dsn, buyers)
    base = f"/v1/workspaces/{WORKSPACE_A}/drafts/{draft_id}"
    review = _review(api, draft_id)
    assert review.status_code == 200, review.text
    old = api.post(base + "/approvals", json=_approval_payload(review),
        headers=_h(REVIEWER, key="before-manual-approval", **{"If-Match": '"2"'}))
    assert old.status_code == 201, old.text
    edit = api.patch(base, json={"subject": SUBJECT, "body": BODY, "language": "zh-HK"},
        headers=_h(OPERATOR, key="manual-edit", **{"If-Match": '"3"'}))
    assert edit.status_code == 200, edit.text
    edited = edit.json()["data"]
    with psycopg.connect(dsn) as db:
        icp_hash = db.execute("SELECT content_hash FROM icp_versions WHERE id=%s", (ICP,)).fetchone()[0]
    segments = []
    for field, text in (("subject", SUBJECT), ("body", BODY)):
        offset = 0
        for line in text.splitlines(keepends=True):
            exact = line.rstrip("\n")
            factual = exact in {"Industrial sensors", "Fixture public catalog lists industrial sensors."}
            segments.append({"field": field, "start": offset, "end": offset + len(exact),
                "exact_text": exact, "classification": "factual" if factual else "non_factual",
                "evidence_refs": edited["evidence_refs"] if exact.startswith("Fixture") else [],
                "offer_fact_refs": [{"id": FACT_ID, "icp_version_id": ICP, "icp_content_hash": icp_hash.removeprefix("sha256:")}]
                    if exact == "Industrial sensors" else [],
                "reason": "Greeting or invitation; no factual assertion" if not factual else "Source read"})
            offset += len(line)
    return api, dsn, base, edited, {"revision_id": edited["revision_id"],
        "content_hash": edited["content_hash"], "segments": segments,
        "reason": "Read full original message and each cited source", "confirmation": True}


def _submit(api, base, edited, payload, key="grounding-001", actor=REVIEWER):
    return api.post(base + "/grounding-reviews", json=payload,
        headers=_h(actor, key=key, **{"If-Match": f'"{edited["version"]}"'}))


def _counts(dsn, base):
    with psycopg.connect(dsn) as db:
        return db.execute("SELECT current_revision,state_version,state FROM outreach_drafts WHERE id=%s",
            (base.split("/")[-1],)).fetchone(), db.execute(
            "SELECT count(*) FROM draft_revisions WHERE draft_id=%s", (base.split("/")[-1],)).fetchone()[0]


def test_manual_review_preserves_unicode_text_appends_proof_then_exact_approval_export(quote_case):
    api, dsn, base, edited, payload = _case(quote_case)
    assert edited["claims"] == [] and edited["approval_id"] is None
    denied = _review(api, base.split("/")[-1], key="edited-not-grounded")
    assert denied.status_code == 412
    response = _submit(api, base, edited, payload)
    assert response.status_code == 200, response.text
    assert_contract_response("DraftResponse", response.json())
    grounded = response.json()["data"]
    assert (grounded["subject"], grounded["body"], grounded["language"]) == (SUBJECT, BODY, "zh-HK")
    assert grounded["revision_id"] != edited["revision_id"] and grounded["revision_number"] == 3
    proof = grounded["grounding_review"]
    assert proof["segments"] == payload["segments"]
    assert proof["reviewed_by"] == str(uuid.uuid5(uuid.NAMESPACE_URL, REVIEWER))
    assert proof["based_on_revision_id"] == edited["revision_id"]
    assert proof["based_on_content_hash"] == edited["content_hash"] and proof["reviewed_at"]
    replay = _submit(api, base, edited, payload)
    assert replay.status_code == 200 and replay.json()["data"]["revision_id"] == grounded["revision_id"]
    with psycopg.connect(dsn) as db:
        revisions = db.execute("SELECT content FROM draft_revisions WHERE draft_id=%s ORDER BY revision_number",
            (grounded["id"],)).fetchall()
        assert len(revisions) == 3 and revisions[1][0]["claims"] == []
        assert revisions[1][0]["body"] == BODY and revisions[0][0]["body"] == "We offer Industrial sensors."
        assert db.execute("SELECT invalidated_reason FROM approvals WHERE draft_id=%s", (grounded["id"],)).fetchone()[0] == "draft_edited"
        assert db.execute("SELECT count(*),min(actor_id::text) FROM audit_events WHERE action='reviewDraftGrounding' AND subject_id=%s", (grounded["revision_id"],)).fetchone() == (1, proof["reviewed_by"])
    review = _review(api, grounded["id"], key="manual-exact-review")
    assert review.status_code == 200, review.text
    approval = api.post(base + "/approvals", json=_approval_payload(review),
        headers=_h(REVIEWER, key="manual-approve", **{"If-Match": f'"{review.json()["data"]["version"]}"'}))
    assert approval.status_code == 201, approval.text
    approved = api.get(base, headers=_h(REVIEWER)).json()["data"]
    exported = api.post(base + "/exports", json={"revision_id": approved["revision_id"],
        "approval_id": approved["approval_id"], "format": "text"},
        headers=_h(REVIEWER, key="manual-export", **{"If-Match": f'"{approved["version"]}"'}))
    assert exported.status_code == 202, exported.text
    download = api.get(f"/v1/workspaces/{WORKSPACE_A}/exports/{exported.json()['data']['id']}/content", headers=_h(REVIEWER))
    assert download.status_code == 200 and BODY in download.text
    delivery = api.post(base + "/deliver", headers=_h(REVIEWER, key="manual-no-delivery"))
    assert delivery.status_code == 403 and delivery.json()["code"] == "DELIVERY_DISABLED"


@pytest.mark.parametrize("mutation", ["missing", "overlap", "utf16", "text", "uncited", "reason", "confirmation", "numeric_confirmation", "foreign_evidence", "foreign_company", "fact_version", "hash", "evidence_version", "expiry", "stance", "inference", "source_purpose", "policy", "recipient", "offer", "membership"])
def test_bad_or_stale_review_rolls_back_without_grounded_successor(quote_case, mutation):
    api, dsn, base, edited, original = _case(quote_case)
    payload = copy.deepcopy(original)
    if mutation == "missing": payload["segments"].pop()
    elif mutation == "overlap": payload["segments"].append(payload["segments"][0])
    elif mutation == "utf16": payload["segments"][0]["end"] += 1
    elif mutation == "text": payload["segments"][0]["exact_text"] += "!"
    elif mutation == "uncited": payload["segments"][2]["offer_fact_refs"] = []
    elif mutation == "reason": payload["segments"][0]["reason"] = " "
    elif mutation == "confirmation": payload["confirmation"] = False
    elif mutation == "numeric_confirmation": payload["confirmation"] = 1
    elif mutation == "foreign_evidence": payload["segments"][3]["evidence_refs"][0]["id"] = str(uuid.uuid4())
    elif mutation == "fact_version": payload["segments"][2]["offer_fact_refs"][0]["icp_content_hash"] = "0" * 64
    elif mutation == "hash": payload["content_hash"] = "0" * 64
    else:
        with psycopg.connect(dsn, autocommit=True) as db:
            if mutation == "foreign_company": db.execute("UPDATE evidence SET company_id=%s WHERE id=%s", (quote_case[2][1][1], edited["evidence_refs"][0]["id"]))
            elif mutation == "evidence_version": db.execute("UPDATE evidence SET version=version+1 WHERE id=%s", (edited["evidence_refs"][0]["id"],))
            elif mutation == "expiry": db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE project_id=%s", (PROJECT,))
            elif mutation == "stance": db.execute("UPDATE evidence SET stance='contradicts' WHERE id=%s", (edited["evidence_refs"][0]["id"],))
            elif mutation == "inference": db.execute("UPDATE evidence SET is_inference=true WHERE id=%s", (edited["evidence_refs"][0]["id"],))
            elif mutation == "source_purpose": db.execute("UPDATE source_documents SET permission_purpose='contact_research' WHERE project_id=%s", (PROJECT,))
            elif mutation == "policy": db.execute("UPDATE policy_decisions SET status='blocked' WHERE purpose='outreach' AND workspace_id=%s", (WORKSPACE_A,))
            elif mutation == "recipient": db.execute("UPDATE contact_points SET retention_expires_at=now()-interval '1 second' WHERE id=%s", (edited["recipient_contact_id"],))
            elif mutation == "offer": db.execute("UPDATE projects SET offer_revision=offer_revision+1 WHERE id=%s", (PROJECT,))
            elif mutation == "membership": db.execute("UPDATE memberships SET active=false WHERE workspace_id=%s AND user_id=%s", (WORKSPACE_A, uuid.uuid5(uuid.NAMESPACE_URL, REVIEWER)))
    before = _counts(dsn, base)
    response = _submit(api, base, edited, payload)
    assert response.status_code in {403, 404, 412, 422}, (mutation, response.text)
    assert _counts(dsn, base) == before
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT count(*) FROM audit_events WHERE action='reviewDraftGrounding'").fetchone()[0] == 0


def test_operator_cannot_attest_and_key_cannot_bind_changed_body(quote_case):
    api, dsn, base, edited, payload = _case(quote_case)
    denied = _submit(api, base, edited, payload, actor=OPERATOR)
    assert denied.status_code == 403, denied.text
    good = _submit(api, base, edited, payload)
    assert good.status_code == 200, good.text
    changed = _submit(api, base, edited, {**payload, "reason": "Different intent"})
    assert changed.status_code == 409 and changed.json()["code"] == "IDEMPOTENCY_CONFLICT"
    assert _counts(dsn, base)[1] == 3


def test_two_same_key_requests_create_one_revision_and_restart_reads_proof(quote_case):
    api, dsn, base, edited, payload = _case(quote_case)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _submit(api, base, edited, payload), range(2)))
    assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
    assert len({r.json()["data"]["revision_id"] for r in results}) == 1
    assert _counts(dsn, base)[1] == 3
    with psycopg.connect(dsn) as db:
        stored = db.execute("SELECT content FROM draft_revisions WHERE draft_id=%s AND revision_number=3", (edited["id"],)).fetchone()[0]
    from tests.conftest import _require_disposable_test_dsn
    _require_disposable_test_dsn(os.environ["BUYEROS_DATABASE_URL"])
    # A separate interpreter creates a fresh app, verifier, engine and HTTP client. No in-memory proof.
    child = """
import asyncio, json, sys
from tests.test_api_projects_db import _h, REVIEWER
from tests import auth_fixtures as fx
from buyeros_api.api import auth
from buyeros_api.api.app import create_app
from buyeros_api.api.jwks import JwksKeyCache
from buyeros_api.api.verifier import TokenVerifier
from fastapi.testclient import TestClient
cache=JwksKeyCache(lambda: asyncio.sleep(0,result=fx.jwks_document()),cache_seconds=300)
auth._verifier_from_settings=lambda:TokenVerifier(cache,issuer=fx.ISSUER,audience=fx.AUDIENCE)
with TestClient(create_app(),raise_server_exceptions=False) as client:
 response=client.get(sys.argv[1],headers=_h(REVIEWER))
 assert response.status_code==200,response.text
 print(json.dumps(response.json()["data"]))
"""
    restarted = subprocess.run([sys.executable, "-c", child, base], capture_output=True,
        text=True, encoding="utf-8", timeout=30, check=True)
    fresh = json.loads(restarted.stdout)
    assert fresh["grounding_review"] == stored["grounding_review"]
    assert fresh["subject"] == SUBJECT and fresh["body"] == BODY


def test_edit_and_grounding_review_have_one_precondition_winner(quote_case):
    api, dsn, base, edited, payload = _case(quote_case)
    def edit():
        return api.patch(base, json={"body": "A concurrent edit"}, headers=_h(OPERATOR,
            key="grounding-race-edit", **{"If-Match": f'"{edited["version"]}"'}))
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(_submit, api, base, edited, payload)
        b = pool.submit(edit)
        results = [a.result(), b.result()]
    assert sorted(r.status_code for r in results) == [200, 412], [r.text for r in results]
    assert _counts(dsn, base)[1] == 3


@pytest.mark.parametrize("change", ["source_digest", "evidence_hash", "expiry", "edited_again"])
def test_current_source_guard_applies_to_replay_and_exact_review_and_next_edit_clears_proof(quote_case, change):
    api, dsn, base, edited, payload = _case(quote_case)
    grounded = _submit(api, base, edited, payload)
    assert grounded.status_code == 200, grounded.text
    data = grounded.json()["data"]
    if change == "edited_again":
        changed = api.patch(base, json={"subject": "Next manual edit"}, headers=_h(OPERATOR,
            key="after-grounding-edit", **{"If-Match": f'"{data["version"]}"'}))
        assert changed.status_code == 200 and "grounding_review" not in changed.json()["data"]
        assert changed.json()["data"]["claims"] == []
    else:
        with psycopg.connect(dsn, autocommit=True) as db:
            if change == "source_digest": db.execute("UPDATE source_documents SET digest=%s WHERE project_id=%s", ("b"*64, PROJECT))
            elif change == "evidence_hash": db.execute("UPDATE evidence SET content_hash=%s WHERE id=%s", ("c"*64, data["evidence_refs"][0]["id"]))
            else: db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE project_id=%s", (PROJECT,))
    before = _counts(dsn, base)
    replay = _submit(api, base, edited, payload)
    assert replay.status_code == 412, replay.text
    review = _review(api, data["id"], key="stale-manual-source-review")
    assert review.status_code == 412, review.text
    assert _counts(dsn, base) == before


def test_other_workspace_cannot_attest_foreign_draft(quote_case):
    api, dsn, base, edited, payload = _case(quote_case)
    with psycopg.connect(dsn) as db:
        other = db.execute("SELECT id FROM workspaces WHERE id<>%s ORDER BY id LIMIT 1", (WORKSPACE_A,)).fetchone()
    assert other is not None, "the guarded fixture must include its second tenant"
    denied = _submit(api, base.replace(WORKSPACE_A,str(other[0])), edited, payload)
    assert denied.status_code in {403,404}, denied.text
    assert _counts(dsn, base)[1] == 2


def test_current_workspace_admin_can_review_but_client_cannot_choose_actor(quote_case):
    api, dsn, base, edited, payload = _case(quote_case)
    from tests.test_api_projects_db import ADMIN
    spoofed = _submit(api, base, edited, {**payload, "reviewed_by": str(uuid.uuid4())}, key="forged-actor", actor=ADMIN)
    assert spoofed.status_code == 422 and _counts(dsn, base)[1] == 2
    reviewed = _submit(api, base, edited, payload, actor=ADMIN)
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["data"]["grounding_review"]["reviewed_by"] == str(uuid.uuid5(uuid.NAMESPACE_URL, ADMIN))
