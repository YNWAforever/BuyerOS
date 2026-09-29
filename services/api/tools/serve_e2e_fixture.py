"""Run a loopback API against disposable Postgres with a clearly fake identity.

For browser harnesses only. This does not verify Auth0 or represent a live login.
The default database is a fresh Docker container removed when this process ends.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from fastapi import Request

import psycopg
import uvicorn
from alembic import command
from alembic.config import Config

from buyeros_api.api.app import create_app
from buyeros_api.api.auth import Principal, get_principal
from buyeros_api.api.errors import ApiError
from buyeros_api.settings import get_settings
from tests.conftest import (
    _docker,
    _require_disposable_test_dsn,
    _start_container,
    runtime_role_dsn,
)


WORKSPACE_ID = "e0000000-0000-4000-8000-000000000001"
USER_ID = "e0000000-0000-4000-8000-000000000002"
MEMBERSHIP_ID = "e0000000-0000-4000-8000-000000000003"
ISSUER = "urn:buyeros:e2e"
SUBJECT = "tester"


def seed(owner_dsn: str) -> None:
    """Seed only the isolated E2E identity and workspace."""
    with psycopg.connect(owner_dsn, autocommit=True) as conn:
        conn.execute("ALTER ROLE buyeros_api LOGIN PASSWORD 'test-only'")
        conn.execute("GRANT USAGE ON SCHEMA public TO buyeros_api")
        conn.execute(
            "INSERT INTO workspaces(id, name, data_mode) VALUES (%s, %s, 'live')",
            (WORKSPACE_ID, "E2E fixture workspace"),
        )
        conn.execute(
            "INSERT INTO users(id, issuer, subject) VALUES (%s, %s, %s)",
            (USER_ID, ISSUER, SUBJECT),
        )
        conn.execute(
            "INSERT INTO memberships(id, workspace_id, user_id, roles, active) "
            "VALUES (%s, %s, %s, %s, true)",
            (MEMBERSHIP_ID, WORKSPACE_ID, USER_ID, ["operator"]),
        )
        conn.execute("INSERT INTO users(id, issuer, subject) VALUES "
                     "('e0000000-0000-4000-8000-000000000004', %s, 'reviewer'), "
                     "('e0000000-0000-4000-8000-000000000006', %s, 'viewer'), "
                     "('e0000000-0000-4000-8000-000000000008', %s, 'admin')", (ISSUER, ISSUER, ISSUER))
        conn.execute("INSERT INTO memberships(id, workspace_id, user_id, roles, active) VALUES "
                     "('e0000000-0000-4000-8000-000000000005', %s, "
                     "'e0000000-0000-4000-8000-000000000004', '{reviewer}', true), "
                     "('e0000000-0000-4000-8000-000000000007', %s, "
                     "'e0000000-0000-4000-8000-000000000006', '{viewer}', true), "
                     "('e0000000-0000-4000-8000-000000000009', %s, "
                     "'e0000000-0000-4000-8000-000000000008', '{workspace_admin}', true)",
                     (WORKSPACE_ID, WORKSPACE_ID, WORKSPACE_ID))
        if os.environ.get("BUYEROS_E2E_SEED_BUYERS") == "1":
            _seed_buyers(conn)
        if os.environ.get("BUYEROS_E2E_SEED_QUOTES") == "1":
            if os.environ.get("BUYEROS_E2E_SEED_BUYERS") != "1":
                raise RuntimeError("quote browser fixture requires fictional buyers")
            _seed_quote_context(conn)
            if os.environ.get("BUYEROS_E2E_SEED_CONFIRM") == "1":
                _seed_contact_budget(conn)
        if os.environ.get("BUYEROS_E2E_SEED_DRAFTS") == "1":
            if os.environ.get("BUYEROS_E2E_SEED_BUYERS") != "1":
                raise RuntimeError("draft browser fixture requires fictional buyers")
            _seed_draft_context(conn)
            if os.environ.get('BUYEROS_E2E_SEED_DRAFT_APPROVAL') == '1':
                _seed_draft_approval_context(conn)
        if os.environ.get("BUYEROS_E2E_SEED_EXPORTS") == "1":
            if os.environ.get("BUYEROS_E2E_SEED_BUYERS") != "1":
                raise RuntimeError("export browser fixture requires fictional buyers")
            _seed_export_context(conn)
        if os.environ.get("BUYEROS_E2E_SEED_RUNS") == "1":
            _seed_runs(conn)


def _seed_buyers(conn) -> None:
    """Only the disposable browser fixture gets these clearly fictional rows."""
    project = "e1000000-0000-4000-8000-000000000001"
    icp = "e6000000-0000-4000-8000-000000000001"
    conn.execute(
        "INSERT INTO projects(id, workspace_id, name, company_name, offer, markets, "
        "language_preferences, version) VALUES (%s, %s, 'Buyer Fixture Project', "
        "'Fictional Seller', 'Fixture product\nFixture value', '{US}', '{en}', 1)",
        (project, WORKSPACE_ID),
    )
    conn.execute(
        "INSERT INTO icp_versions(id, workspace_id, project_id, number, content, content_hash, "
        "basis_offer_revision) VALUES (%s, %s, %s, 1, '{}'::jsonb, %s, 1)",
        (icp, WORKSPACE_ID, project, "sha256:" + "1" * 64),
    )
    conn.execute(
        "UPDATE projects SET active_icp_version_id=%s WHERE workspace_id=%s AND id=%s",
        (icp, WORKSPACE_ID, project),
    )
    buyer_count = int(os.environ.get("BUYEROS_E2E_BUYER_COUNT", "24"))
    if not 1 <= buyer_count <= 1000:
        raise RuntimeError("E2E buyer fixture count must be 1..1000")
    for index in range(1, buyer_count + 1):
        company = f"e3000000-0000-4000-8000-{index:012x}"
        buyer = f"e2000000-0000-4000-8000-{index:012x}"
        name = f"Buyer Fixture {index:02d}"
        conn.execute(
            "INSERT INTO companies(id, workspace_id, legal_name, display_name, domain) "
            "VALUES (%s, %s, %s, %s, %s)",
            (company, WORKSPACE_ID, name, name, f"fixture-{index:02d}.example.test"),
        )
        conn.execute(
            "INSERT INTO project_buyers(id, workspace_id, project_id, company_id) "
            "VALUES (%s, %s, %s, %s)", (buyer, WORKSPACE_ID, project, company),
        )
        if index <= 2:
            evidence_ids = "[]"
            if index in (1, 2):
                source = f"e4000000-0000-4000-8000-{index:012x}"
                evidence = f"e5000000-0000-4000-8000-{index:012x}"
                excerpt = ("Fixture public catalog lists industrial sensors." if index == 1
                           else "Fixture outdated catalog listed unverified parts.")
                conn.execute(
                    "INSERT INTO source_documents(id, workspace_id, project_id, permission_purpose, "
                    "canonical_url, digest, retrieved_at, language, storage_mode, excerpt, retention_until) "
                    "VALUES (%s, %s, %s, 'account_research', %s, %s, now(), 'en', 'excerpt_only', %s, "
                    "now() + (%s * interval '1 day'))",
                    (source, WORKSPACE_ID, project, f"https://example.test/fictional-buyer-{index:02d}",
                     "2" * 64, excerpt, 30 if index == 1 else -1),
                )
                conn.execute(
                    "INSERT INTO evidence(id, workspace_id, project_id, company_id, "
                    "source_document_id, stance, excerpt, is_inference, observed_at, content_hash) "
                    "VALUES (%s, %s, %s, %s, %s, 'supports', %s, false, now(), %s)",
                    (evidence, WORKSPACE_ID, project, company, source, excerpt, "3" * 64),
                )
                evidence_ids = '["' + evidence + '"]'
            fit = f"e7000000-0000-4000-8000-{index:012x}"
            verdict = "match" if index == 1 else "needs_review"
            conn.execute(
                "INSERT INTO fit_assessments(id, workspace_id, project_id, project_buyer_id, "
                "icp_version_id, evidence_set_hash, verdict, rationale, evidence_ids) "
                "VALUES (%s, %s, %s, %s, %s, 'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc', %s, %s, %s::jsonb)",
                (fit, WORKSPACE_ID, project, buyer, icp, verdict, "Fictional fixture assessment.", evidence_ids),
            )
            if index == 1:
                conn.execute(
                    "INSERT INTO human_reviews(id, workspace_id, project_buyer_id, "
                    "fit_assessment_id, state, reason, actor_user_id) "
                    "VALUES (%s, %s, %s, %s, 'accepted', 'Fixture review', %s)",
                    ("e8000000-0000-4000-8000-000000000001", WORKSPACE_ID, buyer, fit,
                     "e0000000-0000-4000-8000-000000000004"),
                )



def _seed_quote_context(conn) -> None:
    """Disposable fictional approval/policy only; no real owner decision or provider."""
    from buyeros_api.db.icp import canonical_hash

    project = "e1000000-0000-4000-8000-000000000001"
    icp = "e6000000-0000-4000-8000-000000000001"
    content = {"markets": ["US"], "languages": ["en"], "buyer_types": ["distributor"]}
    conn.execute(
        "UPDATE icp_versions SET content=%s::jsonb,content_hash=%s,approved_at=now(),approved_by=%s "
        "WHERE id=%s AND workspace_id=%s",
        (json.dumps(content), canonical_hash(content),
         "e0000000-0000-4000-8000-000000000004", icp, WORKSPACE_ID),
    )
    conn.execute(
        "INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,controller_scope_id,"
        "purpose,status,policy_version,basis_reference,provenance,countries,expires_at,retention_days,decision_author_id) "
        "VALUES (%s,%s,'project',%s,%s,'contact_research','permitted','fixture-only',"
        "'fictional-browser-policy','fixture-only','{US}',now()+interval '1 day',1,%s)",
        ("e9900000-0000-4000-8000-000000000001", WORKSPACE_ID, project, WORKSPACE_ID,
         "e0000000-0000-4000-8000-000000000004"),
    )


def _seed_draft_context(conn) -> None:
    """Fictional approved context and draft for disposable browser journeys only."""
    from buyeros_api.db.icp import canonical_hash

    project = "e1000000-0000-4000-8000-000000000001"
    icp = "e6000000-0000-4000-8000-000000000001"
    buyer = "e2000000-0000-4000-8000-000000000001"
    evidence = "e5000000-0000-4000-8000-000000000001"
    sender = "ea000000-0000-4000-8000-000000000001"
    fact = "eb000000-0000-4000-8000-000000000001"
    draft = "ec000000-0000-4000-8000-000000000001"
    content = {"markets": ["US"], "languages": ["en"], "buyer_types": ["distributor"],
               "offer_facts": [{"id": fact, "field": "product", "value": "Fictional industrial sensors",
                                "provenance": "user_entered", "approved": True}]}
    conn.execute("UPDATE icp_versions SET content=%s::jsonb,content_hash=%s,approved_at=now(),"
                 "approved_by=%s WHERE id=%s", (json.dumps(content), canonical_hash(content),
                 "e0000000-0000-4000-8000-000000000004", icp))
    conn.execute("INSERT INTO sender_identity_versions(id,workspace_id,project_id,version_key,"
                 "display_name,role,organization,business_email,country,reviewed_by,reviewed_at,review_reason) "
                 "VALUES (%s,%s,%s,%s,'Fixture Alex','Partner','Fictional Seller',"
                 "'alex@example.test','US',%s,now(),'Fictional browser fixture')",
                 (sender, WORKSPACE_ID, project, f"sender:{sender}:1",
                  "e0000000-0000-4000-8000-000000000004"))
    conn.execute("UPDATE projects SET active_sender_identity_version_id=%s,sender_identity_epoch=1 "
                 "WHERE id=%s", (sender, project))
    conn.execute("INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,controller_scope_id,"
                 "purpose,status,policy_version,basis_reference,provenance,countries,expires_at,"
                 "retention_days,decision_author_id) VALUES "
                 "('ed000000-0000-4000-8000-000000000001',%s,'project',%s,%s,"
                 "'draft_preparation','permitted','fixture-v1','fictional-browser-policy',"
                 "'fixture-only','{US}',now()+interval '1 day',1,%s)",
                 (WORKSPACE_ID, project, WORKSPACE_ID,
                  "e0000000-0000-4000-8000-000000000004"))
    draft_content = {"subject": "Introduction: Fictional industrial sensors",
                     "body": "We offer fictional industrial sensors [offer:eb000000-0000-4000-8000-000000000001].",
                     "claims": [{"text": "Fictional industrial sensors", "kind": "offer_fact",
                                 "offer_fact_ids": [fact], "evidence_ids": []}],
                     "recipient_contact_id": None, "sender_identity_version": f"sender:{sender}:1",
                     "evidence_refs": [{"id": evidence, "version": 1}],
                     "objective": "Introduce the approved offer", "tone": "professional", "language": "en",
                     "kind": "initial", "parent_draft_id": None, "value_proposition_fact_ids": [fact],
                     "icp_version_id": icp, "evidence_set_hash": "c" * 64,
                     "policy_decision_ids": ["ed000000-0000-4000-8000-000000000001"],
                     "context_hash": "b" * 64, "grounding_status": "grounded"}
    conn.execute("INSERT INTO outreach_drafts(id,workspace_id,project_id,buyer_id,current_revision,state) "
                 "VALUES (%s,%s,%s,%s,1,'draft')", (draft, WORKSPACE_ID, project, buyer))
    conn.execute("INSERT INTO draft_revisions(id,workspace_id,draft_id,revision_number,content,"
                 "content_hash,evidence_ids,offer_fact_ids) VALUES "
                 "('ee000000-0000-4000-8000-000000000001',%s,%s,1,%s::jsonb,%s,%s::jsonb,%s::jsonb)",
                 (WORKSPACE_ID, draft, json.dumps(draft_content), "a" * 64,
                  json.dumps([evidence]), json.dumps([fact])))



def _seed_draft_approval_context(conn) -> None:
    """An addressed, fictional review fixture; not a provider or mailbox result."""
    from buyeros_api.services.draft_service import _digest

    project = "e1000000-0000-4000-8000-000000000001"
    buyer = "e2000000-0000-4000-8000-000000000001"
    company = "e3000000-0000-4000-8000-000000000001"
    icp = "e6000000-0000-4000-8000-000000000001"
    evidence = "e5000000-0000-4000-8000-000000000001"
    fact = "eb000000-0000-4000-8000-000000000001"
    sender = "ea000000-0000-4000-8000-000000000001"
    contact = "ef000000-0000-4000-8000-000000000001"
    draft = "ec000000-0000-4000-8000-000000000002"
    revision = "ee000000-0000-4000-8000-000000000002"
    conn.execute("INSERT INTO contact_points(id,workspace_id,company_id,type,normalized_value,"
                 "validity,checked_at,quarantined) VALUES (%s,%s,%s,'business_email',"
                 "'recipient@fixture.example.test','provider_marked_valid',now(),false)",
                 (contact, WORKSPACE_ID, company))
    for index,purpose in enumerate(("outreach","export_contacts"),start=2):
        policy=f"ed000000-0000-4000-8000-{index:012x}"
        conn.execute("INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,"
                     "controller_scope_id,purpose,status,policy_version,basis_reference,provenance,"
                     "countries,expires_at,retention_days,decision_author_id) "
                     "VALUES (%s,%s,'project',%s,%s,%s,'permitted','fixture-v1',"
                     "'fictional-browser-policy','fixture-only','{US}',now()+interval '1 day',1,%s)",
                     (policy, WORKSPACE_ID, project, WORKSPACE_ID, purpose,
                      "e0000000-0000-4000-8000-000000000004"))
    content = {"subject":"Introduction: Fictional industrial sensors",
               "body":"We offer fictional industrial sensors [offer:eb000000-0000-4000-8000-000000000001].",
               "claims":[{"text":"Fictional industrial sensors","kind":"offer_fact",
                          "offer_fact_ids":[fact],"evidence_ids":[]}],
               "recipient_contact_id":contact,"sender_identity_version":f"sender:{sender}:1",
               "evidence_refs":[{"id":evidence,"version":1}],
               "objective":"Introduce the approved offer","tone":"professional","language":"en",
               "kind":"initial","parent_draft_id":None,"value_proposition_fact_ids":[fact],
               "icp_version_id":icp,"evidence_set_hash":"c"*64,
               "policy_decision_ids":["ed000000-0000-4000-8000-000000000001"],
               "grounding_status":"grounded"}
    keys=("recipient_contact_id","sender_identity_version","evidence_refs","icp_version_id",
          "evidence_set_hash","policy_decision_ids","objective","tone","language",
          "value_proposition_fact_ids")
    content["context_hash"]=_digest({key:content.get(key) for key in keys})
    conn.execute("INSERT INTO outreach_drafts(id,workspace_id,project_id,buyer_id,"
                 "current_revision,state) VALUES (%s,%s,%s,%s,1,'draft')",
                 (draft,WORKSPACE_ID,project,buyer))
    conn.execute("INSERT INTO draft_revisions(id,workspace_id,draft_id,revision_number,"
                 "content,content_hash,evidence_ids,offer_fact_ids) "
                 "VALUES (%s,%s,%s,1,%s::jsonb,%s,%s::jsonb,%s::jsonb)",
                 (revision,WORKSPACE_ID,draft,json.dumps(content),_digest(content),
                  json.dumps([evidence]),json.dumps([fact])))

def _seed_contact_budget(conn) -> None:
    """A fictional USD 0.30 limit, only in the disposable confirmation browser run."""
    import uuid
    from datetime import datetime, timezone
    from buyeros_api.services.budget_service import _period

    project = "e1000000-0000-4000-8000-000000000001"
    start, end, label = _period(datetime.now(timezone.utc))
    for scope, scope_id, category in (("workspace", WORKSPACE_ID, "all"),
                                      ("project", project, "all"),
                                      ("category", project, "contact_lookup")):
        conn.execute(
            "INSERT INTO budget_accounts(id,workspace_id,scope,scope_id,category,currency,"
            "period,period_start,period_end,approved_limit,settled_spend) "
            "VALUES (%s,%s,%s,%s,%s,'USD',%s,%s,%s,0.300000,0) "
            "ON CONFLICT (workspace_id,scope,scope_id,category,currency,period_start) "
            "DO UPDATE SET approved_limit=0.300000",
            (uuid.uuid4(), WORKSPACE_ID, scope, scope_id, category, label, start, end),
        )


def _seed_runs(conn) -> None:
    """Run-route fixture rows only; no external provider or worker is simulated."""
    import json
    import uuid
    from datetime import datetime, timezone
    from buyeros_api.db.icp import canonical_hash
    from buyeros_api.services.budget_service import _period

    project = "e9100000-0000-4000-8000-000000000001"
    icp = "e9200000-0000-4000-8000-000000000001"
    requirement = "e9300000-0000-4000-8000-000000000001"
    content = {"markets": ["US"], "languages": ["en"], "buyer_types": ["distributor"],
               "requirements": [{"id": requirement, "category": "must", "hard_exclusion": False, "text": "industrial sensors"}]}
    if os.environ.get("BUYEROS_E2E_SEED_T30_DRAFT") == "1":
        content["offer_facts"] = [{"id": "e9500000-0000-4000-8000-000000000001",
                                   "field": "product", "value": "Industrial sensors",
                                   "provenance": "user_entered", "approved": False}]
    limits = {"query_rounds": 3, "max_queries_per_run": 12, "max_results": 300,
              "max_pages": 200, "max_page_bytes": 2097152,
              "max_duration_seconds": 1800, "max_model_tokens": 100000,
              "provider_concurrency": 4}
    conn.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,"
                 "language_preferences,version,offer_revision) VALUES "
                 "(%s,%s,'Run Fixture Project','Fictional Seller','Industrial sensors','{US}','{en}',1,1)",
                 (project, WORKSPACE_ID))
    conn.execute("INSERT INTO icp_versions(id,workspace_id,project_id,number,content,content_hash,"
                 "basis_offer_revision,approved_at,approved_by) VALUES "
                 "(%s,%s,%s,1,%s::jsonb,%s,1,now(),%s)",
                 (icp, WORKSPACE_ID, project, json.dumps(content), canonical_hash(content),
                  "e0000000-0000-4000-8000-000000000004"))
    conn.execute("UPDATE projects SET active_icp_version_id=%s WHERE id=%s", (icp, project))
    if os.environ.get("BUYEROS_E2E_SEED_T30_DRAFT") == "1":
        sender = "e9600000-0000-4000-8000-000000000001"
        conn.execute("INSERT INTO sender_identity_versions(id,workspace_id,project_id,version_key,"
                     "display_name,organization,business_email,country,reviewed_by,reviewed_at,review_reason) "
                     "VALUES (%s,%s,%s,%s,'Fixture Alex','Fictional Seller','alex@example.test','US',"
                     "%s,now(),'T30 disposable fixture')",
                     (sender, WORKSPACE_ID, project, f"sender:{sender}:1",
                      "e0000000-0000-4000-8000-000000000004"))
        conn.execute("UPDATE projects SET active_sender_identity_version_id=%s,sender_identity_epoch=1 "
                     "WHERE id=%s", (sender, project))
        conn.execute("INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,"
                     "controller_scope_id,purpose,status,policy_version,basis_reference,provenance,"
                     "countries,expires_at,retention_days,decision_author_id) VALUES "
                     "(%s,%s,'project',%s,%s,'draft_preparation','permitted','fixture-v1',"
                     "'fictional-browser-policy','fixture-only','{US}',now()+interval '1 day',1,%s)",
                     (uuid.uuid4(), WORKSPACE_ID, project, WORKSPACE_ID,
                      "e0000000-0000-4000-8000-000000000004"))
    conn.execute("INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,controller_scope_id,"
                 "purpose,status,policy_version,basis_reference,provenance,countries,expires_at,retention_days,decision_author_id) "
                 "VALUES (%s,%s,'project',%s,%s,'account_research','permitted','fixture-v1','fixture','fixture',"
                 "'{US}',now()+interval '1 day',1,%s)",
                 (uuid.uuid4(), WORKSPACE_ID, project, WORKSPACE_ID,
                  "e0000000-0000-4000-8000-000000000004"))
    start,end,period=_period(datetime.now(timezone.utc))
    for scope,scope_id,category in (("workspace",WORKSPACE_ID,"all"),("project",project,"all"),
                                    ("category",project,"discovery")):
        conn.execute("INSERT INTO budget_accounts(id,workspace_id,scope,scope_id,category,currency,"
                     "period,period_start,period_end,approved_limit,settled_spend) "
                     "VALUES (%s,%s,%s,%s,%s,'USD',%s,%s,%s,10,0)",
                     (uuid.uuid4(),WORKSPACE_ID,scope,scope_id,category,period,start,end))
    for index in range(1,13):
        run_id=f"e9400000-0000-4000-8000-{index:012x}"
        status="running" if index==1 else "completed"
        stage="discover" if index==1 else "review"
        conn.execute("INSERT INTO search_runs(id,workspace_id,project_id,icp_version_id,status,stage,limits,"
                     "target_companies,raw_result_count,max_cost,execution_snapshot,usage_counters) "
                     "VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,4,0,2,'{}'::jsonb,'{}'::jsonb)",
                     (run_id,WORKSPACE_ID,project,icp,status,stage,json.dumps(limits)))
        for sequence,event_type in ((1,"run.queued"),(2,"run.started" if index==1 else "run.completed")):
            conn.execute("INSERT INTO run_events(id,workspace_id,run_id,sequence,event_type,payload) "
                         "VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
                         (uuid.uuid4(),WORKSPACE_ID,run_id,sequence,event_type,
                          json.dumps({"version": 1, "stage": stage, "company_count": 0,"raw_count": 0})))

def _seed_export_context(conn) -> None:
    """Explicitly fictional export policy; never an owner approval record."""
    import uuid

    project = "e1000000-0000-4000-8000-000000000001"
    conn.execute("INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,"
                 "controller_scope_id,purpose,status,policy_version,basis_reference,provenance,"
                 "countries,expires_at,retention_days,decision_author_id) VALUES "
                 "(%s,%s,'project',%s,%s,'export_accounts','permitted','fixture-v1',"
                 "'fictional-fixture','fixture',ARRAY['US'],now()+interval '1 day',1,%s)",
                 (uuid.uuid4(), WORKSPACE_ID, project, WORKSPACE_ID,
                  "e0000000-0000-4000-8000-000000000004"))
    conn.execute("INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,"
                 "controller_scope_id,purpose,status,policy_version,basis_reference,provenance,"
                 "countries,expires_at,retention_days,decision_author_id) VALUES "
                 "(%s,%s,'company',%s,%s,'export_accounts','blocked','fixture-v1',"
                 "'fictional-fixture','fixture',ARRAY['US'],now()+interval '1 day',1,%s)",
                 (uuid.uuid4(), WORKSPACE_ID, "e3000000-0000-4000-8000-000000000002",
                  WORKSPACE_ID, "e0000000-0000-4000-8000-000000000004"))


def fake_principal(request: Request) -> Principal:
    """Fixture-token mapping only; the production app has no identity override."""
    token = request.headers.get("Authorization", "")
    subjects = {"Bearer fixture-access": SUBJECT,
                "Bearer fixture-reviewer": "reviewer",
                "Bearer fixture-viewer": "viewer",
                "Bearer fixture-admin": "admin"}
    if token not in subjects:
        raise ApiError(401, "AUTH_REQUIRED", "fixture bearer required")
    return Principal(issuer=ISSUER, subject=subjects[token])


def main() -> None:
    if os.environ.get("BUYEROS_STRICT_INTEGRATION") != "1":
        raise RuntimeError("E2E fixture requires BUYEROS_STRICT_INTEGRATION=1")

    container = None
    owner_dsn = os.environ.get("BUYEROS_TEST_DATABASE_URL")
    if owner_dsn:
        _require_disposable_test_dsn(owner_dsn)
    else:
        container, owner_dsn = _start_container()
        marker = Path(__file__).resolve().parents[3] / "test-results" / "e2e-db-container.txt"
        marker.parent.mkdir(exist_ok=True)
        marker.write_text(container)

    try:
        os.environ["BUYEROS_DATABASE_URL"] = owner_dsn
        get_settings.cache_clear()
        service_root = Path(__file__).resolve().parents[1]
        config = Config(str(service_root / "alembic.ini"))
        config.set_main_option("script_location", str(service_root / "alembic"))
        command.upgrade(config, "head")
        seed(owner_dsn)

        os.environ["BUYEROS_DATABASE_URL"] = runtime_role_dsn(owner_dsn)
        get_settings.cache_clear()
        app = create_app()
        app.dependency_overrides[get_principal] = fake_principal
        if os.environ.get("BUYEROS_E2E_SEED_DRAFT_APPROVAL") == "1":
            @app.get("/fixture/approval-counts", include_in_schema=False)
            def approval_counts():
                with psycopg.connect(owner_dsn) as conn:
                    return {
                        "approvals": conn.execute("SELECT count(*) FROM approvals WHERE workspace_id=%s",
                            (WORKSPACE_ID,)).fetchone()[0],
                        "delivery_events": conn.execute("SELECT count(*) FROM outbox_events "
                            "WHERE workspace_id=%s AND event_type ~ '^delivery[.]'",
                            (WORKSPACE_ID,)).fetchone()[0],
                    }

        if os.environ.get("BUYEROS_E2E_SEED_EXPORTS") == "1":
            @app.get("/fixture/export-counts", include_in_schema=False)
            def export_counts():
                with psycopg.connect(owner_dsn) as conn:
                    return {
                        "exports": conn.execute("SELECT count(*) FROM export_jobs WHERE workspace_id=%s",
                            (WORKSPACE_ID,)).fetchone()[0],
                        "outcomes": conn.execute("SELECT count(*) FROM outcome_events WHERE workspace_id=%s",
                            (WORKSPACE_ID,)).fetchone()[0],
                        "delivery_events": conn.execute("SELECT count(*) FROM outbox_events "
                            "WHERE workspace_id=%s AND event_type ~ '^delivery[.]'",
                            (WORKSPACE_ID,)).fetchone()[0],
                    }

        if os.environ.get("BUYEROS_E2E_SEED_QUOTES") == "1":
            from datetime import datetime, timezone
            from decimal import Decimal
            from buyeros_api.api.routes.quotes import selected_contact_quote_capability
            from buyeros_api.providers.base import Money, ProviderCapability

            quote_capability = ProviderCapability(
                provider="fixture", adapter_version="contact-fixture-v1", service="contact",
                markets=frozenset({"US"}), languages=frozenset({"en"}),
                roles=frozenset({"Procurement manager"}), auth_model="fixture",
                pricing_version="fixture-price-v1", max_liability=Money(Decimal("0.300000")),
                idempotency="verified", status="verified", callback="unsupported", cancel="unsupported",
                retention="fixture-only", verified_at=datetime.now(timezone.utc),
                source_urls=("https://fixture.invalid/capability",),
            )
            app.dependency_overrides[selected_contact_quote_capability] = lambda: (quote_capability, "test")

            @app.get("/fixture/quote-counts", include_in_schema=False)
            def quote_counts():
                with psycopg.connect(owner_dsn) as conn:
                    counts = {table: conn.execute(
                        f"SELECT count(*) FROM {table} WHERE workspace_id=%s", (WORKSPACE_ID,)
                    ).fetchone()[0] for table in
                        ("enrichment_quotes", "budget_reservations", "provider_operations", "outbox_events")}
                if os.environ.get("BUYEROS_E2E_SEED_CONFIRM") == "1":
                    with psycopg.connect(owner_dsn) as conn:
                        counts["enrichment_jobs"] = conn.execute(
                            "SELECT count(*) FROM enrichment_jobs WHERE workspace_id=%s",
                            (WORKSPACE_ID,),
                        ).fetchone()[0]
                return counts
        if os.environ.get("BUYEROS_E2E_SEED_RUNS") == "1":
            from buyeros_api.api.routes.runs import selected_run_capability
            app.dependency_overrides[selected_run_capability] = lambda: ({
                "service":"search", "provider":"fixture", "verified":True,
                "price_version":"fixture-price-v1", "verified_filters":["market","language"],
                "markets":["US"], "languages":["en"], "roles":["distributor"],
                "market_languages":{"US":["en"]}}, "test")
            from fastapi import Body
            import uuid

            @app.post("/fixture/advance-run", include_in_schema=False)
            def advance_fixture_run(step: str = Body(embed=True)):
                """Explicit disposable browser event injection; never mounted in production."""
                run_id="e9400000-0000-4000-8000-000000000001"
                if step not in {"partial", "completed"}:
                    raise ApiError(422, "INVALID_REQUEST", "unsupported fixture step")
                with psycopg.connect(owner_dsn) as db:
                    with db.transaction():
                        row=db.execute("SELECT status,version FROM search_runs WHERE id=%s FOR UPDATE",
                                       (run_id,)).fetchone()
                        if row is None:
                            raise ApiError(404,"NOT_FOUND","fixture run absent")
                        sequence=db.execute("SELECT coalesce(max(sequence),0)+1 FROM run_events WHERE run_id=%s",
                                            (run_id,)).fetchone()[0]
                        db.execute("UPDATE search_runs SET status=%s,stage=%s,version=version+1 WHERE id=%s",
                                   (step,"review" if step=="completed" else "reconciliation_required",run_id))
                        db.execute("INSERT INTO run_events(id,workspace_id,run_id,sequence,event_type,payload) "
                                   "VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
                                   (uuid.uuid4(),WORKSPACE_ID,run_id,sequence,f"run.{step}",
                                    json.dumps({"version":row[1]+1,"stage":step,
                                                "company_count":0,"raw_count":0,"reason":"fixture_event"})))
                return {"fixture_only":True,"sequence":sequence}
        if os.environ.get("BUYEROS_E2E_PRIVATE_STORE") == "1":
            # Only this strict disposable server gets a fake private bucket.
            # This proves UI/API behavior, not R2 availability or worker delivery.
            from buyeros_api.api.routes import documents
            import uuid

            objects: dict[str, bytes] = {}

            class FixtureStore:
                def __init__(self, workspace_id):
                    self.prefix = f"tenants/{workspace_id}/"

                async def put_private(self, body, *, digest, retention_seconds):
                    key = self.prefix + str(uuid.uuid4())
                    objects[key] = body
                    return key

                async def get_private(self, key):
                    if not key.startswith(self.prefix):
                        raise ValueError("foreign key")
                    return objects[key]

                async def delete_private(self, key):
                    if not key.startswith(self.prefix):
                        raise ValueError("foreign key")
                    objects.pop(key, None)

            documents.get_private_store = lambda workspace_id: FixtureStore(workspace_id)
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning"))
        if sys.platform == "win32":
            asyncio.run(server.serve(), loop_factory=asyncio.SelectorEventLoop)
        else:
            asyncio.run(server.serve())
    finally:
        if container:
            _docker("rm", "-f", container)
            marker.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
