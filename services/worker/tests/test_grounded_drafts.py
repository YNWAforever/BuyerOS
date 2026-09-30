"""T24 grounded text generation never promotes an unsupported claim."""

import pytest

from buyeros_worker.handlers.draft_generate import render_grounded_template, validate_grounded_output

FACT = "e1000000-0000-4000-8000-000000000001"
EVIDENCE = "e2000000-0000-4000-8000-000000000001"


def _basis():
    return ([{"id": FACT, "value": "Industrial sensors", "approved": True}],
            [{"id": EVIDENCE, "excerpt": "The company distributes industrial equipment.",
              "version": 1, "stance": "supports"}])


def test_template_uses_only_approved_fact_and_cited_observation():
    facts, evidence = _basis()
    result = render_grounded_template(facts=facts, evidence=evidence,
                                      objective="Introduce our offer", tone="professional",
                                      language="en", kind="initial")
    assert "Industrial sensors" in result["body"]
    assert "The company distributes industrial equipment." in result["body"]
    assert result["recipient_contact_id"] is None
    assert result["route"] == "grounded-template.v1"
    assert {claim["text"] for claim in result["claims"]} == {
        "Industrial sensors", "The company distributes industrial equipment."}
    assert validate_grounded_output(result, facts=facts, evidence=evidence) == result


def test_unsupported_certification_or_savings_claim_is_rejected():
    facts, evidence = _basis()
    result = render_grounded_template(facts=facts, evidence=evidence,
                                      objective="Guarantee 50% savings and ISO certification", tone="warm",
                                      language="en", kind="initial")
    assert "50%" not in result["body"] and "ISO" not in result["body"]
    result["claims"].append({"text": "Guaranteed 50% savings", "kind": "offer_fact",
                             "offer_fact_ids": [FACT], "evidence_ids": []})
    with pytest.raises(ValueError, match="unsupported claim"):
        validate_grounded_output(result, facts=facts, evidence=evidence)


def test_zh_hk_follow_up_keeps_exact_source_citations():
    facts, evidence = _basis()
    result = render_grounded_template(facts=facts, evidence=evidence,
                                      objective="Follow up on the offer", tone="concise",
                                      language="zh-HK", kind="follow_up")
    assert result["subject"].startswith("跟進：")
    assert f"[offer_fact:{FACT}]" in result["body"]
    assert f"[evidence:{EVIDENCE}:v1]" in result["body"]
    assert result["recipient_contact_id"] is None
    assert validate_grounded_output(result, facts=facts, evidence=evidence) == result


@pytest.fixture
def draft_job(worker_database_url, pg_dsn):
    import json
    import uuid
    from datetime import datetime, timezone

    import psycopg

    from buyeros_api.db.icp import canonical_hash
    from buyeros_api.services.outbox_service import build_intent
    from tests.conftest import ICP_A, PROJECT_A, WS_A

    actor, sender, company, buyer, source, evidence_id, fit, review, policy, job = [uuid.uuid4() for _ in range(10)]
    content = {"markets": ["US"], "languages": ["en"], "buyer_types": ["distributor"],
               "offer_facts": [{"id": FACT, "field": "product", "value": "Industrial sensors",
                                "provenance": "user_entered", "approved": False}]}
    evidence_hash = canonical_hash({"evidence": [str(evidence_id)]})
    command = {"buyer_id": str(buyer), "buyer_version": 1,
               "icp_id": ICP_A, "icp_hash": canonical_hash(content), "offer_revision": 1,
               "fit_id": str(fit), "review_id": str(review), "sender_id": str(sender),
               "sender_version": f"sender:{sender}:1", "offer_fact_ids": [FACT],
               "evidence_refs": [{"id": str(evidence_id), "version": 1}],
               "evidence_set_hash": evidence_hash, "policy_decision_ids": [str(policy)],
               "objective": "Introduce our offer", "tone": "professional", "language": "en",
               "kind": "initial", "parent_draft_id": None, "route": "grounded-template.v1",
               "max_cost": "0.000000"}
    payload = {"job_id": str(job)}
    intent_key = build_intent("draft.generate", payload, 0)
    with psycopg.connect(pg_dsn, autocommit=True) as db:
        db.execute("INSERT INTO users(id,issuer,subject) VALUES (%s,'fixture',%s)",
                   (actor, f"draft-{actor}"))
        db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES (%s,%s,%s,'{operator}',true)",
                   (uuid.uuid4(), WS_A, actor))
        db.execute("UPDATE icp_versions SET content=%s::jsonb, content_hash=%s, "
                   "basis_offer_revision=1, approved_at=now(), approved_by=%s WHERE id=%s",
                   (json.dumps(content), canonical_hash(content), actor, ICP_A))
        db.execute("UPDATE projects SET active_icp_version_id=%s WHERE id=%s", (ICP_A, PROJECT_A))
        db.execute("INSERT INTO sender_identity_versions(id,workspace_id,project_id,version_key,"
                   "display_name,organization,business_email,country,reviewed_by,reviewed_at) "
                   "VALUES (%s,%s,%s,%s,'Alex','ProjectA Co','alex@example.test','US',%s,now())",
                   (sender, WS_A, PROJECT_A, f"sender:{sender}:1", actor))
        db.execute("UPDATE projects SET active_sender_identity_version_id=%s,sender_identity_epoch=1 WHERE id=%s",
                   (sender, PROJECT_A))
        db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name,domain) "
                   "VALUES (%s,%s,'Fixture buyer','Fixture buyer','fixture.example')", (company, WS_A))
        db.execute("INSERT INTO project_buyers(id,workspace_id,project_id,company_id) "
                   "VALUES (%s,%s,%s,%s)", (buyer, WS_A, PROJECT_A, company))
        db.execute("INSERT INTO source_documents(id,workspace_id,project_id,permission_purpose,"
                   "canonical_url,digest,retrieved_at,language,excerpt,retention_until) "
                   "VALUES (%s,%s,%s,'account_research','https://fixture.example/source',%s,"
                   "now(),'en','The company distributes industrial equipment.',now()+interval '1 day')",
                   (source, WS_A, PROJECT_A, 'a'*64))
        db.execute("INSERT INTO evidence(id,workspace_id,project_id,company_id,source_document_id,"
                   "stance,excerpt) VALUES (%s,%s,%s,%s,%s,'supports',%s)",
                   (evidence_id, WS_A, PROJECT_A, company, source,
                    'The company distributes industrial equipment.'))
        db.execute("INSERT INTO fit_assessments(id,workspace_id,project_id,project_buyer_id,"
                   "icp_version_id,evidence_set_hash,verdict,rationale,evidence_ids) "
                   "VALUES (%s,%s,%s,%s,%s,%s,'match','Fixture match',%s::jsonb)",
                   (fit, WS_A, PROJECT_A, buyer, ICP_A, evidence_hash, json.dumps([str(evidence_id)])))
        db.execute("INSERT INTO human_reviews(id,workspace_id,project_buyer_id,state,actor_user_id,"
                   "fit_assessment_id) VALUES (%s,%s,%s,'accepted',%s,%s)",
                   (review, WS_A, buyer, actor, fit))
        db.execute("INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,"
                   "controller_scope_id,purpose,status,policy_version,basis_reference,provenance,"
                   "countries,expires_at,retention_days,decision_author_id) "
                   "VALUES (%s,%s,'project',%s,%s,'draft_preparation','permitted','fixture-v1',"
                   "'fixture','fixture',ARRAY['US'],now()+interval '1 day',1,%s)",
                   (policy, WS_A, PROJECT_A, WS_A, actor))
        db.execute("INSERT INTO async_jobs(id,workspace_id,project_id,actor_user_id,kind,operation,"
                   "command,status,requested,processed,updated,unchanged,blocked,conflicts) "
                   "VALUES (%s,%s,%s,%s,'draft_generation','generateDraft',%s::jsonb,'queued',1,0,0,0,0,0)",
                   (job, WS_A, PROJECT_A, actor, json.dumps(command)))
        db.execute("INSERT INTO async_job_items(id,workspace_id,job_id,buyer_id,ordinal,expected_version,status) "
                   "VALUES (%s,%s,%s,%s,0,1,'pending')", (uuid.uuid4(), WS_A, job, buyer))
        db.execute("INSERT INTO outbox_events(id,workspace_id,intent_key,event_type,payload,state,"
                   "fencing_generation) VALUES (%s,%s,%s,'draft.generate',%s::jsonb,'dispatched',1)",
                   (uuid.uuid4(), WS_A, intent_key, json.dumps(payload)))
    try:
        yield {"dsn": pg_dsn, "workspace": WS_A, "job": job, "buyer": buyer,
               "company": company, "intent_key": intent_key, "policy": policy,
               "actor": actor}
    finally:
        with psycopg.connect(pg_dsn, autocommit=True) as db:
            for table in ("approvals", "draft_revisions", "outreach_drafts", "async_job_items",
                          "outbox_events", "async_jobs", "suppressions", "policy_decisions", "contact_points",
                          "human_reviews", "fit_assessments", "evidence", "source_documents",
                          "project_buyers", "companies"):
                db.execute(f"DELETE FROM {table} WHERE workspace_id=%s", (WS_A,))
            db.execute("UPDATE projects SET active_sender_identity_version_id=NULL,"
                       "sender_identity_epoch=0,active_icp_version_id=NULL WHERE id=%s", (PROJECT_A,))
            db.execute("DELETE FROM sender_identity_versions WHERE id=%s", (sender,))
            db.execute("UPDATE icp_versions SET content='{}'::jsonb,content_hash='hash',"
                       "basis_offer_revision=NULL,approved_at=NULL,approved_by=NULL WHERE id=%s", (ICP_A,))
            db.execute("DELETE FROM memberships WHERE user_id=%s", (actor,))
            db.execute("DELETE FROM users WHERE id=%s", (actor,))


def test_durable_worker_creates_one_immutable_draft_and_never_calls_provider(draft_job):
    import psycopg
    from buyeros_worker.tasks import execute_intent_sync

    case = draft_job
    with psycopg.connect(case["dsn"]) as db:
        before = {table: db.execute(f"SELECT count(*) FROM {table} WHERE workspace_id=%s",
                                    (case["workspace"],)).fetchone()[0]
                  for table in ("provider_operations", "budget_reservations")}
    assert execute_intent_sync(case["intent_key"], case["workspace"], 1) == "done"
    with psycopg.connect(case["dsn"]) as db:
        row = db.execute("SELECT d.state,r.content,r.content_hash FROM outreach_drafts d "
                         "JOIN draft_revisions r ON r.workspace_id=d.workspace_id AND r.draft_id=d.id "
                         "WHERE d.buyer_id=%s", (case["buyer"],)).fetchone()
        assert row is not None and row[0] == "draft"
        assert row[1]["grounding_status"] == "grounded"
        assert "Industrial sensors" in row[1]["body"]
        assert "The company distributes industrial equipment." in row[1]["body"]
        assert row[1]["recipient_contact_id"] is None
        assert db.execute("SELECT status,processed,updated FROM async_jobs WHERE id=%s",
                          (case["job"],)).fetchone() == ("completed", 1, 1)
        assert db.execute("SELECT count(*) FROM provider_operations WHERE workspace_id=%s",
                          (case["workspace"],)).fetchone()[0] == before["provider_operations"]
        assert db.execute("SELECT count(*) FROM budget_reservations WHERE workspace_id=%s",
                          (case["workspace"],)).fetchone()[0] == before["budget_reservations"]
    assert execute_intent_sync(case["intent_key"], case["workspace"], 1) == "duplicate"


def test_suppression_before_worker_prevents_draft_materialization(draft_job):
    import psycopg
    from buyeros_worker.tasks import execute_intent_sync

    case = draft_job
    with psycopg.connect(case["dsn"], autocommit=True) as db:
        db.execute("INSERT INTO suppressions(id,workspace_id,subject_key_hash,subject_type,subject_id,"
                   "controller_scope_id,purpose,purposes,reason,active,actor_id) "
                   "VALUES (%s,%s,%s,'company',%s,%s,'draft_preparation',"
                   "ARRAY['draft_preparation'],'Fixture suppression',true,%s)",
                   (__import__('uuid').uuid4(), case["workspace"], 'b'*64,
                    case["company"], case["workspace"], case["actor"]))
    assert execute_intent_sync(case["intent_key"], case["workspace"], 1) == "done"
    with psycopg.connect(case["dsn"]) as db:
        assert db.execute("SELECT status,blocked FROM async_jobs WHERE id=%s",
                          (case["job"],)).fetchone() == ("failed", 1)
        assert db.execute("SELECT count(*) FROM outreach_drafts WHERE workspace_id=%s",
                          (case["workspace"],)).fetchone()[0] == 0


def _address_job(case):
    import hashlib
    import json
    import uuid
    import psycopg
    from tests.conftest import PROJECT_A

    contact_id = uuid.uuid4()
    with psycopg.connect(case["dsn"], autocommit=True) as db:
        checked, retention = db.execute("INSERT INTO contact_points(id,workspace_id,company_id,type,normalized_value,"
            "validity,checked_at,quarantined,retention_expires_at) VALUES (%s,%s,%s,'business_email',"
            "'recipient@fixture.example.test','provider_marked_valid',now(),false,now()+interval '1 day') RETURNING checked_at,retention_expires_at",
            (contact_id, case["workspace"], case["company"])).fetchone()
        for purpose in ("outreach", "export_contacts"):
            db.execute("INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,"
                "controller_scope_id,purpose,status,policy_version,basis_reference,provenance,countries,"
                "expires_at,retention_days,decision_author_id) VALUES (%s,%s,'project',%s,%s,%s,"
                "'permitted','fixture-v1','fixture','fixture',ARRAY['US'],now()+interval '1 day',1,%s)",
                (uuid.uuid4(), case["workspace"], PROJECT_A, case["workspace"], purpose, case["actor"]))
        policies = [{"id":str(row[0]), "version":row[1], "purpose":row[2], "status":row[3],
                     "expires_at":row[4].isoformat()} for row in db.execute(
            "SELECT id,version,purpose,status,expires_at FROM policy_decisions "
            "WHERE workspace_id=%s ORDER BY id", (case["workspace"],))]
        context = {"contact":{"id":str(contact_id), "version":1, "type":"business_email",
            "validity":"provider_marked_valid", "value_hash":hashlib.sha256(b'recipient@fixture.example.test').hexdigest(),
            "checked_at":checked.isoformat(), "retention_until":retention.isoformat()}, "policies":policies}
        db.execute("UPDATE async_jobs SET command=command || %s::jsonb WHERE id=%s",
                   (json.dumps({"recipient_context":context}), case["job"]))
    return contact_id


def test_worker_materializes_addressed_grounded_template_without_provider(draft_job):
    import psycopg
    from buyeros_worker.tasks import execute_intent_sync

    contact_id = _address_job(draft_job)
    with psycopg.connect(draft_job["dsn"]) as db:
        before = tuple(db.execute(f"SELECT count(*) FROM {table} WHERE workspace_id=%s",
                                  (draft_job["workspace"],)).fetchone()[0]
                       for table in ("provider_operations", "budget_reservations"))
    assert execute_intent_sync(draft_job["intent_key"], draft_job["workspace"], 1) == "done"
    with psycopg.connect(draft_job["dsn"]) as db:
        content = db.execute("SELECT content FROM draft_revisions WHERE workspace_id=%s",
                             (draft_job["workspace"],)).fetchone()[0]
        assert content["recipient_contact_id"] == str(contact_id)
        assert content["grounding_status"] == "grounded" and content["claims"]
        after = tuple(db.execute(f"SELECT count(*) FROM {table} WHERE workspace_id=%s",
                                 (draft_job["workspace"],)).fetchone()[0]
                      for table in ("provider_operations", "budget_reservations"))
        assert after == before


@pytest.mark.parametrize("changed", ["value", "validity", "policy", "membership"])
def test_worker_rechecks_addressed_contact_and_policy_after_admission(draft_job, changed):
    import psycopg
    from buyeros_worker.tasks import execute_intent_sync

    contact_id = _address_job(draft_job)
    with psycopg.connect(draft_job["dsn"], autocommit=True) as db:
        if changed == "value":
            db.execute("UPDATE contact_points SET normalized_value='other@fixture.example.test' WHERE id=%s", (contact_id,))
        elif changed == "validity":
            db.execute("UPDATE contact_points SET validity='catch_all' WHERE id=%s", (contact_id,))
        elif changed == "policy":
            db.execute("UPDATE policy_decisions SET status='blocked' WHERE purpose='outreach'")
        else:
            db.execute("UPDATE memberships SET active=false WHERE user_id=%s", (draft_job["actor"],))
    assert execute_intent_sync(draft_job["intent_key"], draft_job["workspace"], 1) == "done"
    with psycopg.connect(draft_job["dsn"]) as db:
        assert db.execute("SELECT status,blocked FROM async_jobs WHERE id=%s", (draft_job["job"],)).fetchone() == ("failed", 1)
        assert db.execute("SELECT count(*) FROM outreach_drafts WHERE workspace_id=%s",
                          (draft_job["workspace"],)).fetchone()[0] == 0
