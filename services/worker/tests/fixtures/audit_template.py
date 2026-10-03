"""Bounded Q07 fixture in the owner-verified disposable workbench database.

Fictional retained contact/purposes are inputs, never provider or owner approvals.
Materialize one actual zero-cost API-created draft intent with the shared worker
handler, runtime/RLS role and generation fence. Dispatch state is fixture-staged;
this does not verify continuous Celery/Valkey, Cloudflare or production delivery.
"""
import json
import os
import sys
import uuid
import psycopg
from tests.fixtures.run_browser_research import owner_dsn, prepare_browser_runtime, WORKSPACE

PROJECT = uuid.UUID("e1000000-0000-4000-8000-000000000001")
COMPANY = uuid.UUID("e3000000-0000-4000-8000-000000000001")
ACTOR = uuid.UUID("e0000000-0000-4000-8000-000000000002")
REVIEWER = uuid.UUID("e0000000-0000-4000-8000-000000000004")
CONTACT = uuid.UUID("ef070000-0000-4000-8000-000000000001")

def main():
    args = sys.argv[1:]
    if args != ["prepare"] and not (len(args) == 2 and args[0] == "materialize"):
        raise ValueError("prepare or materialize JOB_ID required")
    dsn = owner_dsn()
    with psycopg.connect(dsn) as db:
        if db.execute("SELECT company_name FROM projects WHERE id=%s AND workspace_id=%s", (PROJECT, WORKSPACE)).fetchone() != ("Fictional Seller",):
            raise RuntimeError("unknown fictional project")
        if db.execute("SELECT issuer,subject FROM users WHERE id=%s", (REVIEWER,)).fetchone() != ("urn:buyeros:e2e", "reviewer"):
            raise RuntimeError("unknown fictional identity")
        if args == ["prepare"]:
            existing = db.execute("SELECT normalized_value,validity,retention_expires_at>now() FROM contact_points WHERE id=%s AND workspace_id=%s AND company_id=%s", (CONTACT, WORKSPACE, COMPANY)).fetchone()
            if existing and existing != ("recipient@fixture.example.test", "provider_marked_valid", True):
                raise RuntimeError("fictional contact changed")
            if not existing:
                db.execute("INSERT INTO contact_points(id,workspace_id,company_id,type,normalized_value,validity,checked_at,quarantined,retention_expires_at) VALUES (%s,%s,%s,'business_email','recipient@fixture.example.test','provider_marked_valid',now(),false,now()+interval '1 day')", (CONTACT, WORKSPACE, COMPANY))
            for purpose in ("contact_research", "outreach", "export_contacts"):
                if not db.execute("SELECT 1 FROM policy_decisions WHERE workspace_id=%s AND subject_type='project' AND subject_id=%s AND purpose=%s", (WORKSPACE, PROJECT, purpose)).fetchone():
                    db.execute("INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,controller_scope_id,purpose,status,policy_version,basis_reference,provenance,countries,expires_at,retention_days,decision_author_id) VALUES (%s,%s,'project',%s,%s,%s,'permitted','fixture-v1','Q07 fictional prerequisite','fixture-only',ARRAY['US'],now()+interval '1 day',1,%s)", (uuid.uuid4(), WORKSPACE, PROJECT, WORKSPACE, purpose, REVIEWER))
            print(json.dumps({"fixture_only": True, "contact": str(CONTACT)}))
            return
        job_id = uuid.UUID(args[1])
        command = db.execute("SELECT command FROM async_jobs WHERE id=%s AND workspace_id=%s AND project_id=%s AND actor_user_id=%s AND operation='generateDraft' AND status='queued'", (job_id, WORKSPACE, PROJECT, ACTOR)).fetchone()
        if not command or command[0].get("route") != "grounded-template.v1" or command[0].get("max_cost") != "0.000000":
            raise RuntimeError("only this actor's new zero-cost template job is allowed")
    runtime = prepare_browser_runtime(dsn)
    with psycopg.connect(dsn) as db:
        epoch = db.execute("SELECT epoch FROM worker_runtime_control WHERE backend='celery' AND enabled").fetchone()[0]
        intent = db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1,runtime_backend='celery',runtime_epoch=%s WHERE workspace_id=%s AND event_type='draft.generate' AND payload->>'job_id'=%s AND state='ready' AND fencing_generation=0 RETURNING intent_key", (epoch, WORKSPACE, str(job_id))).fetchall()
        if len(intent) != 1:
            raise RuntimeError("one ready draft intent required")
        before = [db.execute(f"SELECT count(*) FROM {table} WHERE workspace_id=%s", (WORKSPACE,)).fetchone()[0] for table in ("provider_operations", "budget_reservations")]
    os.environ.update(BUYEROS_DATABASE_URL=runtime, BUYEROS_CELERY_EXECUTION_ENABLED="true", BUYEROS_PAID_DISPATCH_ENABLED="false")
    from buyeros_worker.config import get_settings
    from buyeros_worker.tasks import execute_intent_sync
    get_settings.cache_clear()
    result = execute_intent_sync(intent[0][0], str(WORKSPACE), 1, environment="test")
    duplicate = execute_intent_sync(intent[0][0], str(WORKSPACE), 1, environment="test")
    with psycopg.connect(dsn) as db:
        status, command = db.execute("SELECT status,command FROM async_jobs WHERE id=%s AND workspace_id=%s", (job_id, WORKSPACE)).fetchone()
        after = [db.execute(f"SELECT count(*) FROM {table} WHERE workspace_id=%s", (WORKSPACE,)).fetchone()[0] for table in ("provider_operations", "budget_reservations")]
        revisions = db.execute("SELECT count(*) FROM draft_revisions WHERE draft_id=%s AND workspace_id=%s", (uuid.UUID(command["result_draft_id"]), WORKSPACE)).fetchone()[0]
        if result != "done" or duplicate != "duplicate" or status != "completed" or before != after or revisions != 1:
            raise RuntimeError("actual fenced template materialization failed")
    print(json.dumps({"fixture_only": True, "dispatch_fixture_staged": True, "job": str(job_id), "draft": command["result_draft_id"], "result": result, "duplicate": duplicate, "revisions": revisions, "paid_before": before, "paid_after": after}))

if __name__ == "__main__":
    main()
