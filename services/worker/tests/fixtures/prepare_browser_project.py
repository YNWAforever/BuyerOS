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


    # After committing prerequisite rows, use the actual controlled workflow.
    # These are fictional owner designations, never direct permitted writes.
    from tests.controlled_policy_fixtures import api_fixture_helpers, fixture_research_binding
    helpers = api_fixture_helpers()
    dsn = owner_dsn()
    controller = helpers.ensure_fixture_controller(dsn, WORKSPACE, project)
    domains = ("fixture.example.test",)
    if mode == "prepare":
        from buyeros_api.services import policy_activation_bootstrap as bootstrap
        from buyeros_api.api.policy_activation_schemas import MANUAL_ACTIONS
        now = datetime.now(timezone.utc)
        with psycopg.connect(dsn) as db:
            membership_version = db.execute("SELECT version FROM memberships WHERE workspace_id=%s AND user_id=%s",
                                            (WORKSPACE, controller)).fetchone()[0]
        case = {"dsn": dsn, "workspace": WORKSPACE, "project": project,
                "actors": {"owner": controller}, "membership_version": membership_version, "now": now}
        manifest = bootstrap.AuthorityManifest.model_validate({**helpers.manifest_body(case),
            "purposes": ["account_research", "contact_research", "draft_preparation", "outreach"],
            "allowed_actions": sorted(MANUAL_ACTIONS | {"research.search", "research.read", "research.persist",
                                      "research.fetch", "contact.read", "draft.generate", "delivery.review"})})
        authorization = bootstrap.BootstrapAuthorization(manifest_sha256=bootstrap.manifest_digest(manifest),
            target_sha256=manifest.target_sha256, source_sha=manifest.source_sha,
            approval_reference="fixture://owned-browser-designation", approval_evidence_sha256="b"*64)
        async def designate(session):
            execution = await bootstrap.verify_bootstrap_execution(session, manifest, authorization)
            return await bootstrap.apply_authority_manifest(session, manifest, execution, now)
        helpers.owner_run(case, designate)
        helpers.approve_research_fixture(dsn, WORKSPACE, project, domains=domains,
            search=fixture_research_binding("search"), transaction_role=True, countries=("US",))
    else:
        from buyeros_api.db.icp import canonical_hash
        with psycopg.connect(dsn) as db:
            sender = db.execute("SELECT active_sender_identity_version_id FROM projects WHERE workspace_id=%s AND id=%s",
                                (WORKSPACE, project)).fetchone()[0]
        scope = {"provider_name": "fixture", "account_reference": "owned-browser-account",
                 "contract_sha256": canonical_hash({"schema": "owned-browser-template.v1"}).removeprefix("sha256:"),
                 "recipient_refs": [str(contact)]}
        helpers.approve_provider_fixture(dsn, WORKSPACE, project, controller, purpose="contact_research",
            domains=domains, actions=["contact.read"], scope=scope, transaction_role=True)
        scope = {**scope, "sender_identity_id": str(sender)}
        helpers.approve_provider_fixture(dsn, WORKSPACE, project, controller, purpose="draft_preparation",
            domains=domains, scope=scope, transaction_role=True)
        helpers.approve_provider_fixture(dsn, WORKSPACE, project, controller, purpose="outreach",
            domains=domains, actions=["delivery.review"], scope=scope, transaction_role=True)


if __name__ == "__main__":
    main()
