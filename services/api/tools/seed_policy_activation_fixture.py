"""Synthetic normal-UI policy fixture. Never imported/mounted by the production app."""
from datetime import datetime, timezone
from uuid import UUID
import psycopg
from tests.policy_activation_target import assert_owned_test_dsn
from tests.policy_activation_fixtures import provision_fixture_authority

W = "e0000000-0000-4000-8000-000000000001"
P = "e1000000-0000-4000-8000-000000000001"
OWNER = "e0000000-0000-4000-8000-000000000008"
REQUESTER = "e0000000-0000-4000-8000-000000000012"


def seed_policy_fixture(dsn):
    assert_owned_test_dsn(dsn)
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT issuer,subject FROM users WHERE id=%s", (OWNER,)).fetchone() == ("urn:buyeros:e2e", "admin")
        db.execute("INSERT INTO users(id,issuer,subject) VALUES(%s,'urn:buyeros:e2e','policy-requester')", (REQUESTER,))
        db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) "
                   "VALUES('e0000000-0000-4000-8000-000000000013',%s,%s,ARRAY['workspace_admin'],true)", (W, REQUESTER))
        db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) "
                   "VALUES('e1000000-0000-4000-8000-000000000002',%s,'Other synthetic project',"
                   "'Fictional seller','Synthetic offer',ARRAY['GB'],ARRAY['en'],1)", (W,))
    reset_policy_fixture(dsn)


def reset_policy_fixture(dsn):
    assert_owned_test_dsn(dsn)
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT name FROM workspaces WHERE id=%s", (W,)).fetchone() == ("E2E fixture workspace",)
        for table in ("policy_activation_resolutions", "policy_activation_requests", "policy_controller_authorities",
                      "policy_decisions"):
            db.execute(f"DELETE FROM {table} WHERE workspace_id=%s", (W,))
        db.execute("DELETE FROM audit_events WHERE workspace_id=%s AND action LIKE 'policy.%%'", (W,))
        db.execute("DELETE FROM idempotency_records WHERE workspace_id=%s AND operation_id=ANY(%s)",
                   (W, ["submitPolicyActivationRequest", "decidePolicyActivationRequest", "withdrawPolicyActivationRequest"]))
        db.execute("DELETE FROM api_rate_windows WHERE workspace_id=%s", (W,))
    provision_fixture_authority({"dsn": dsn, "workspace": UUID(W), "project": UUID(P),
                                 "actors": {"owner": UUID(OWNER)}, "now": datetime.now(timezone.utc)})


def policy_counts(dsn):
    assert_owned_test_dsn(dsn)
    with psycopg.connect(dsn) as db:
        return {
            "fixture_only": True,
            "requests": db.execute("SELECT count(*) FROM policy_activation_requests WHERE workspace_id=%s", (W,)).fetchone()[0],
            "resolutions": db.execute("SELECT count(*) FROM policy_activation_resolutions WHERE workspace_id=%s", (W,)).fetchone()[0],
            "permitted": db.execute("SELECT count(*) FROM policy_decisions WHERE workspace_id=%s AND status='permitted'", (W,)).fetchone()[0],
            "submitted_audits": db.execute("SELECT count(*) FROM audit_events WHERE workspace_id=%s AND action='policy.activation.submitted'", (W,)).fetchone()[0],
            "approved_audits": db.execute("SELECT count(*) FROM audit_events WHERE workspace_id=%s AND action='policy.activation.approved'", (W,)).fetchone()[0],
            "providers": db.execute("SELECT count(*) FROM provider_operations").fetchone()[0],
            "delivery": db.execute("SELECT count(*) FROM outbox_events WHERE event_type LIKE 'delivery.%%'").fetchone()[0],
        }
