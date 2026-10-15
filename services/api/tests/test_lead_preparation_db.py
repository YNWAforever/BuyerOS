import copy
import json
import uuid
from datetime import datetime, timezone

import httpx
import psycopg
import pytest

from buyeros_api.db.icp import canonical_hash
from tests.lead_fixtures import (
    ACTORS, WORKSPACE, PROJECT, headers, prepare, apply, observation_payload, save_observation,
    lead_api, lead_case,
)
from tests.test_lead_progress_db import check_company, case_view


def ready_preparation(api, case):
    check_company(case)
    with psycopg.connect(case["dsn"], autocommit=True) as db:
        check = str(db.execute("SELECT id FROM buyer_source_checks WHERE buyer_id=%s", (case["buyer_id"],)).fetchone()[0])
        fact, icp = str(uuid.uuid4()), str(uuid.uuid4())
        content = {"offer_facts": [{"id": fact, "field": "product", "value": "Thai jasmine rice",
                                   "provenance": "user_entered", "approved": False}]}
        digest = canonical_hash(content)
        db.execute(
            "INSERT INTO icp_versions(id,workspace_id,project_id,number,basis_offer_revision,content,content_hash,"
            "approved_at,approved_by) VALUES (%s,%s,%s,1,1,%s::jsonb,%s,now(),%s)",
            (icp, WORKSPACE, PROJECT, json.dumps(content), digest, ACTORS["workspace_admin"]),
        )
        db.execute("UPDATE projects SET active_icp_version_id=%s WHERE id=%s", (icp, PROJECT))
    priority = prepare(api, case, "case.update", {
        "priority": True, "priority_reason": "Official UK wholesale rice range", "next_action": "Review preparation",
    }, version=case_view(api, case)["version"])
    assert priority.status_code == 201, priority.text
    assert apply(api, case, priority.json()["data"]).status_code == 200
    employment, _, _ = save_observation(api, case)
    person = employment["person_id"]
    procurement, _, _ = save_observation(api, case, observation_payload(
        claim="procurement_scope", person={"person_id": person},
    ))
    channel_payload = observation_payload(
        claim="channel_ownership", person={"person_id": person},
        channel={"type": "business_email", "value": "alex@rice.example.test", "person_id": person},
    )
    channel_payload["sources"][0]["excerpt"] = "Contact Alex Test, rice purchasing manager, at alex@rice.example.test."
    channel, _, _ = save_observation(api, case, channel_payload)
    ids = [employment["id"], procurement["id"], channel["id"]]
    review = prepare(api, case, "lead.review", {
        "person_id": person, "contact_id": channel["contact_id"], "employment": "accepted",
        "procurement_scope": "accepted", "channel_ownership": "accepted", "observation_ids": ids,
        "rationale": "Official staff, rice category and named business channel confirmed.",
    }, version=case_view(api, case)["version"])
    assert review.status_code == 201, review.text
    result = apply(api, case, review.json()["data"])
    assert result.status_code == 200, result.text
    payload = {
        "person_id": person, "contact_id": channel["contact_id"], "subject": "Rice supply discussion",
        "body": "Could we discuss Thai jasmine rice?", "language": "en",
        "product_fact_refs": [{"id": fact, "icp_version_id": icp, "icp_content_hash": digest, "offer_revision": 1}],
        "observation_ids": ids, "lead_review_id": result.json()["data"]["resource_id"],
        "company_source_check_ids": [check],
    }
    return payload


def create_preparation(api, case, payload):
    stage = prepare(api, case, "preparation.create", payload)
    assert stage.status_code == 201, stage.text
    intent = stage.json()["data"]
    response = apply(api, case, intent)
    assert response.status_code == 200, response.text
    identity = response.json()["data"]["resource_id"]
    view = api.get(f"{case['base']}/lead-preparations/{identity}", headers=headers())
    assert view.status_code == 200, view.text
    return view.json()["data"], intent


def review_preparation(api, case, view, *, role="workspace_admin"):
    payload = {"revision_id": view["revision_id"], "context_hash": view["context_hash"],
               "reason": "Checked this exact content against every selected source and product fact.",
               "confirmation": True}
    stage = prepare(api, case, "preparation.review", payload, role=role,
                    target_id=view["id"], version=view["version"])
    if stage.status_code != 201:
        return stage
    return apply(api, case, stage.json()["data"], role=role)


def test_preparation_public_channel_is_not_formal_recipient(lead_api, lead_case):
    payload = ready_preparation(lead_api, lead_case)
    view, intent = create_preparation(lead_api, lead_case, payload)
    assert view["state"] == "editing"
    assert view["content"]["body"] == payload["body"]
    assert review_preparation(lead_api, lead_case, view, role="operator").status_code == 403
    result = review_preparation(lead_api, lead_case, view)
    assert result.status_code == 200, result.text
    current = lead_api.get(f"{lead_case['base']}/lead-preparations/{view['id']}", headers=headers()).json()["data"]
    assert current["state"] == "reviewed"
    assert apply(lead_api, lead_case, intent).json()["data"]["resource_id"] == view["id"]
    with psycopg.connect(lead_case["dsn"]) as db:
        assert db.execute("SELECT validity,checked_at FROM contact_points WHERE id=%s",
                          (payload["contact_id"],)).fetchone() == ("unverified_public", None)
        assert db.execute("SELECT count(*) FROM outreach_drafts").fetchone() == (0,)
        assert db.execute("SELECT count(*) FROM approvals").fetchone() == (0,)
    progress = lead_api.get(f"{lead_case['base']}/lead-workflow", headers=headers()).json()["data"]
    assert progress["metrics"]["reviewed_preparation_companies"] == 1
    delivered = lead_api.post(f"/v1/workspaces/{WORKSPACE}/drafts/{view['id']}/deliver",
                              json={}, headers=headers("workspace_admin"))
    assert delivered.status_code == 403 and delivered.json()["code"] == "DELIVERY_DISABLED"


@pytest.mark.parametrize("change", ["body", "product", "person", "channel", "source_conflict", "expiry"])
def test_preparation_review_binds_revision_sources_and_product_facts(lead_api, lead_case, change):
    payload = ready_preparation(lead_api, lead_case)
    view, _ = create_preparation(lead_api, lead_case, payload)
    assert review_preparation(lead_api, lead_case, view).status_code == 200
    if change == "body":
        altered = dict(payload, body="Please review a different rice proposal.")
        stage = prepare(lead_api, lead_case, "preparation.revise", altered,
                        target_id=view["id"], version=2)
        assert stage.status_code == 201, stage.text
        assert apply(lead_api, lead_case, stage.json()["data"]).status_code == 200
    elif change == "source_conflict":
        save_observation(lead_api, lead_case, observation_payload(
            person={"person_id": payload["person_id"]}, stance="refutes"))
    else:
        with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
            if change == "product":
                db.execute("UPDATE projects SET offer_revision=offer_revision+1 WHERE id=%s", (PROJECT,))
            elif change == "person":
                db.execute("UPDATE people SET role='Finance Director' WHERE id=%s", (payload["person_id"],))
            elif change == "channel":
                db.execute("UPDATE contact_points SET normalized_value='replacement@rice.example.test',version=version+1 "
                           "WHERE id=%s", (payload["contact_id"],))
            else:
                db.execute("UPDATE lead_observations SET checked_at=now()-interval '7 days' "
                           "WHERE claim='channel_ownership' AND buyer_id=%s", (lead_case["buyer_id"],))
    current = lead_api.get(f"{lead_case['base']}/lead-preparations/{view['id']}", headers=headers()).json()["data"]
    assert current["state"] in {"editing", "needs_review"}
    assert lead_api.get(f"{lead_case['base']}/lead-workflow", headers=headers()).json()["data"]["metrics"]["reviewed_preparation_companies"] == 0


def test_preparation_calls_no_provider_worker_or_delivery(lead_api, lead_case, monkeypatch):
    payload = ready_preparation(lead_api, lead_case)
    calls = []
    original = httpx.Client.send

    def guard(client, request, *args, **kwargs):
        if request.url.host != "testserver":
            calls.append(str(request.url))
            raise AssertionError("external HTTP is forbidden")
        return original(client, request, *args, **kwargs)

    async def forbidden(*args, **kwargs):
        calls.append("async HTTP")
        raise AssertionError("external HTTP is forbidden")

    monkeypatch.setattr(httpx.Client, "send", guard)
    monkeypatch.setattr(httpx.AsyncClient, "send", forbidden)
    view, _ = create_preparation(lead_api, lead_case, dict(payload, subject="", body=""))
    assert "Thai jasmine rice" in view["content"]["body"]
    assert "MOQ" not in view["content"]["body"]
    assert review_preparation(lead_api, lead_case, view).status_code == 200
    assert calls == []
    with psycopg.connect(lead_case["dsn"]) as db:
        for table in ("provider_operations", "outbox_events", "async_jobs", "budget_reservations"):
            assert db.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,)


def test_preparation_retention_redacts_history_and_original_intent(lead_api, lead_case):
    payload = ready_preparation(lead_api, lead_case)
    view, intent = create_preparation(lead_api, lead_case, dict(payload, body="Hello Alex Test, could we discuss rice?"))
    with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
        db.execute("UPDATE people SET retention_expires_at=now()-interval '1 day' WHERE id=%s", (payload["person_id"],))
        db.execute("SELECT set_config('app.workspace_id',%s,false)", (WORKSPACE,))
        db.execute("SELECT buyeros_redact_lead_subject(%s,'person',%s)", (WORKSPACE, payload["person_id"]))
    result = lead_api.get(f"{lead_case['base']}/lead-preparations/{view['id']}", headers=headers())
    assert result.status_code == 200 and result.json()["data"]["redacted"] is True
    assert "Alex Test" not in result.text
    replay = apply(lead_api, lead_case, intent)
    assert replay.status_code == 200 and replay.json()["data"]["redacted"] is True


def test_unlinked_expired_payload_has_narrow_retention_boundary(lead_case):
    identity = uuid.uuid4()
    with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
        db.execute(
            "INSERT INTO lead_private_payloads(id,workspace_id,project_id,contents,content_hash,retention_expires_at)"
            "VALUES (%s,%s,%s,'{\"body\":\"Unlinked private preparation\"}','sha256:fixture',now()-interval '1 day')",
            (identity, WORKSPACE, PROJECT),
        )
        db.execute("SELECT set_config('app.workspace_id',%s,false)", (WORKSPACE,))
        assert db.execute("SELECT buyeros_redact_lead_subject(%s,'lead_payload',%s)", (WORKSPACE, identity)).fetchone() == (1,)
        assert db.execute("SELECT contents FROM lead_private_payloads WHERE id=%s", (identity,)).fetchone() == (None,)


def test_contact_specific_policy_blocks_recovered_preparation_payload(lead_api, lead_case):
    payload = ready_preparation(lead_api, lead_case)
    payload["body"] = "Hello Alex Test, could we discuss rice?"
    staged = prepare(lead_api, lead_case, "preparation.create", payload)
    assert staged.status_code == 201, staged.text
    intent = staged.json()["data"]
    with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
        db.execute(
            "INSERT INTO policy_decisions"
            "(id,workspace_id,subject_type,subject_id,controller_scope_id,purpose,status,policy_version,"
            "basis_reference,provenance,countries,expires_at,retention_days,decision_author_id)"
            "VALUES (%s,%s,'contact_point',%s,%s,'contact_research','blocked','fixture-block',"
            "'test revocation','test',ARRAY['GB'],now()+interval '90 days',90,%s)",
            (uuid.uuid4(), WORKSPACE, payload["contact_id"], WORKSPACE, ACTORS["workspace_admin"]),
        )
    recovered = lead_api.get(f"{lead_case['base']}/lead-intents/{intent['id']}", headers=headers())
    assert recovered.status_code == 200
    assert recovered.json()["data"]["redacted"] is True
    assert recovered.json()["data"]["payload"] is None
    assert "Alex Test" not in recovered.text
    assert apply(lead_api, lead_case, intent).status_code == 403


def test_preparation_history_reads_exact_prior_revision_without_reapproving_it(lead_api, lead_case):
    payload = ready_preparation(lead_api, lead_case)
    first, _ = create_preparation(lead_api, lead_case, payload)
    altered = dict(payload, body="A new, separately reviewed proposal.")
    stage = prepare(lead_api, lead_case, "preparation.revise", altered, target_id=first["id"], version=1)
    assert stage.status_code == 201, stage.text
    assert apply(lead_api, lead_case, stage.json()["data"]).status_code == 200
    history = lead_api.get(f"{lead_case['base']}/lead-preparations/{first['id']}/revisions", headers=headers())
    assert history.status_code == 200, history.text
    rows = history.json()["data"]
    assert rows["total"] == 2
    assert [row["revision_number"] for row in rows["items"]] == [2, 1]
    assert rows["items"][1]["content"]["body"] == payload["body"]
    assert all(row["historical"] is True for row in rows["items"])


def test_deleted_product_attachment_cannot_reappear_in_preparation_or_intent(lead_api, lead_case):
    payload = ready_preparation(lead_api, lead_case)
    document = str(uuid.uuid4())
    excerpt = "Private supplier attachment quotation"
    with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
        db.execute(
            "INSERT INTO offer_documents"
            "(id,workspace_id,project_id,kind,filename,media_type,status,version,sha256,retention_until,extraction_metadata)"
            "VALUES (%s,%s,%s,'upload','fixture.pdf','application/pdf','ready',1,%s,now()+interval '90 days',"
            "'{\"classification\":\"text\"}')", (document, WORKSPACE, PROJECT, "b"*64),
        )
        icp = payload["product_fact_refs"][0]["icp_version_id"]
        content = db.execute("SELECT content FROM icp_versions WHERE id=%s", (icp,)).fetchone()[0]
        content["offer_document_ids"] = [document]
        content["offer_facts"][0].update(provenance="document_excerpt", source_document_id=document, excerpt=excerpt)
        digest = canonical_hash(content)
        db.execute("UPDATE icp_versions SET content=%s::jsonb,content_hash=%s WHERE id=%s",
                   (json.dumps(content), digest, icp))
    payload["product_fact_refs"][0]["icp_content_hash"] = digest
    payload["body"] = excerpt
    view, intent = create_preparation(lead_api, lead_case, payload)
    deleted = lead_api.request("DELETE", f"/v1/workspaces/{WORKSPACE}/offer-documents/{document}",
        json={"reason": "Remove the disposable fixture attachment"},
        headers=headers(key=str(uuid.uuid4()), version=1))
    assert deleted.status_code == 202, deleted.text
    current = lead_api.get(f"{lead_case['base']}/lead-preparations/{view['id']}", headers=headers())
    assert current.status_code == 200
    assert current.json()["data"]["redacted"] is True
    assert excerpt not in current.text
    assert apply(lead_api, lead_case, intent).json()["data"]["redacted"] is True
    with psycopg.connect(lead_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM lead_private_payloads WHERE contents::text LIKE %s",
                          (f"%{excerpt}%",)).fetchone() == (0,)


@pytest.mark.parametrize("subject,want", [("Rice supply discussion", 200), ("", 412)], ids=["complete", "missing_subject"])
def test_operator_can_request_content_review_only_for_complete_preparation(lead_api, lead_case, subject, want):
    payload = ready_preparation(lead_api, lead_case)
    view, _ = create_preparation(lead_api, lead_case, dict(payload, subject=subject))
    stage = prepare(lead_api, lead_case, "preparation.request_review",
        {"reason": "Please review these exact cited facts"}, target_id=view["id"], version=view["version"])
    assert stage.status_code == 201, stage.text
    result = apply(lead_api, lead_case, stage.json()["data"])
    assert result.status_code == want, result.text
    if want == 200:
        current = lead_api.get(f"{lead_case['base']}/lead-preparations/{view['id']}", headers=headers()).json()["data"]
        assert current["state"] == "review_requested"
