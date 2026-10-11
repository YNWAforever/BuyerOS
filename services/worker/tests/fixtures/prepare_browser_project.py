"""Fictional prerequisites for a UI-created project in an owned disposable container.

Seeds budget/purpose fixtures and, optionally, an existing valid fictional contact.
Does not create projects, ICPs, runs, buyers, reviews, drafts, approvals or outcomes.
The existing-contact input is not a live lookup or provider verification.
Each new case starts its two fictional actors with fresh rate counters; the
production limiter stays active throughout the actual journey.
"""
from datetime import datetime, timezone
import json
import sys
import uuid

import psycopg

from tests.fixtures.run_browser_research import owner_dsn, WORKSPACE
from buyeros_api.services.budget_service import _period


def main():
    if sys.argv[1:] == ["isolate-workbench"]:
        with psycopg.connect(owner_dsn()) as db:
            fixture = db.execute("SELECT 1 FROM projects WHERE id="
                "'e1000000-0000-4000-8000-000000000001' AND workspace_id=%s", (WORKSPACE,)).fetchone()
            reviewer = db.execute("SELECT issuer,subject FROM users WHERE id="
                "'e0000000-0000-4000-8000-000000000004'").fetchone()
            if fixture != (1,) or reviewer != ("urn:buyeros:e2e", "reviewer"):
                raise RuntimeError("refusing rate isolation outside the known fictional workbench")
            # Called once before an independent test, before its first login.
            # The limiter remains enabled for every request inside that case.
            db.execute("DELETE FROM api_rate_windows WHERE workspace_id=%s AND actor_id IN "
                "('e0000000-0000-4000-8000-000000000002','e0000000-0000-4000-8000-000000000004',"
                "'e0000000-0000-4000-8000-000000000006','e0000000-0000-4000-8000-000000000008')",
                (WORKSPACE,))
            # Independent cases reuse fictional accounts. Persisted preferences
            # are reset only before login, never inside the case that verifies them.
            db.execute("UPDATE workspace_preferences SET locale='en' WHERE workspace_id=%s "
                "AND user_id IN ('e0000000-0000-4000-8000-000000000002',"
                "'e0000000-0000-4000-8000-000000000004',"
                "'e0000000-0000-4000-8000-000000000006',"
                "'e0000000-0000-4000-8000-000000000008')", (WORKSPACE,))
            print(json.dumps({"fixture_initial_rate_windows_reset": True,
                              "fixture_initial_locale_reset": True}))
        return
    if len(sys.argv) not in {3, 4} or sys.argv[1] not in {"prepare", "contact"}:
        raise SystemExit("usage: prepare_browser_project.py prepare PROJECT_ID | contact PROJECT_ID RUN_ID | isolate-workbench")
    mode, project = sys.argv[1], uuid.UUID(sys.argv[2])
    with psycopg.connect(owner_dsn()) as db:
        row = db.execute("SELECT company_name FROM projects WHERE id=%s AND workspace_id=%s",
                         (project, WORKSPACE)).fetchone()
        if row != ("T30 Fictional Seller",):
            raise RuntimeError("refusing a project outside the UI-created fictional fixture")
        if mode == "prepare":
            already_prepared = db.execute("SELECT EXISTS(SELECT 1 FROM policy_decisions "
                "WHERE workspace_id=%s AND subject_type='project' AND subject_id=%s) "
                "OR EXISTS(SELECT 1 FROM search_runs WHERE workspace_id=%s AND project_id=%s)",
                (WORKSPACE, project, WORKSPACE, project)).fetchone()[0]
            if already_prepared:
                raise RuntimeError("prerequisites and rate counters are initialized only once before research")
            # Four independent cases reuse the loopback fixture's two actors.
            # Isolate their initial counters, never increase/disable a limit or
            # clear a window after this project's journey has started research.
            db.execute("DELETE FROM api_rate_windows WHERE workspace_id=%s AND actor_id IN "
                "('e0000000-0000-4000-8000-000000000002','e0000000-0000-4000-8000-000000000004')",
                (WORKSPACE,))
            actor = uuid.UUID("e0000000-0000-4000-8000-000000000004")
            for purpose in ("account_research", "contact_research", "draft_preparation", "outreach", "export_contacts"):
                db.execute("INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,"
                    "controller_scope_id,purpose,status,policy_version,basis_reference,provenance,countries,"
                    "expires_at,retention_days,decision_author_id) VALUES (%s,%s,'project',%s,%s,%s,"
                    "'permitted','fixture-v1','fictional-browser-prerequisite','fixture-only',"
                    "ARRAY['US'],now()+interval '1 day',1,%s)",
                    (uuid.uuid4(), WORKSPACE, project, WORKSPACE, purpose, actor))
            start, end, period = _period(datetime.now(timezone.utc))
            for scope, scope_id, category in (("workspace", WORKSPACE, "all"), ("project", project, "all"),
                                              ("category", project, "discovery")):
                exists = db.execute("SELECT id FROM budget_accounts WHERE workspace_id=%s AND scope=%s "
                    "AND scope_id=%s AND category=%s AND period=%s", (WORKSPACE, scope, scope_id, category, period)).fetchone()
                if not exists:
                    db.execute("INSERT INTO budget_accounts(id,workspace_id,scope,scope_id,category,currency,"
                        "period,period_start,period_end,approved_limit,settled_spend) "
                        "VALUES (%s,%s,%s,%s,%s,'USD',%s,%s,%s,10,0)",
                        (uuid.uuid4(), WORKSPACE, scope, scope_id, category, period, start, end))
                else:
                    db.execute("UPDATE budget_accounts SET approved_limit=10 WHERE id=%s AND workspace_id=%s",
                               (exists[0], WORKSPACE))
            print(json.dumps({"project_id": str(project), "fixture_prerequisites": True,
                              "fixture_initial_rate_windows_reset": True}))
        else:
            if len(sys.argv) != 4:
                raise RuntimeError("contact input requires the completed UI research run")
            run = uuid.UUID(sys.argv[3])
            completed = db.execute("SELECT status FROM search_runs WHERE id=%s AND project_id=%s AND workspace_id=%s",
                                   (run, project, WORKSPACE)).fetchone()
            buyers = db.execute("SELECT id,company_id FROM project_buyers WHERE project_id=%s AND workspace_id=%s",
                                (project, WORKSPACE)).fetchall()
            if completed != ("completed",) or len(buyers) != 1:
                raise RuntimeError("refusing contact seed without one real worker-materialized fixture buyer")
            # Canonicalization intentionally shares the same fictional company
            # between the four UI-created locale/layout projects. Reuse its known valid
            # input instead of violating the real contact-value uniqueness rule.
            existing = db.execute("SELECT id,validity,checked_at,retention_expires_at,quarantined "
                "FROM contact_points WHERE workspace_id=%s AND company_id=%s AND type='business_email' "
                "AND normalized_value='recipient@fixture.example.test'", (WORKSPACE, buyers[0][1])).fetchone()
            if existing:
                if (existing[1] != "provider_marked_valid" or existing[2] is None or existing[3] is None
                        or existing[3] <= datetime.now(timezone.utc) or existing[4]):
                    raise RuntimeError("refusing a changed or expired fictional contact input")
                contact = existing[0]
            else:
                contact = uuid.uuid4()
                db.execute("INSERT INTO contact_points(id,workspace_id,company_id,type,normalized_value,validity,"
                    "checked_at,retention_expires_at,quarantined) VALUES (%s,%s,%s,'business_email',"
                    "'recipient@fixture.example.test','provider_marked_valid',now(),now()+interval '1 day',false)",
                    (contact, WORKSPACE, buyers[0][1]))
            print(json.dumps({"project_id":str(project), "buyer_id":str(buyers[0][0]),
                              "contact_id":str(contact), "fixture_existing_contact":True}))


if __name__ == "__main__":
    main()
