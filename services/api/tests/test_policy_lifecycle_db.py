"""T10 purpose policy and scoped suppression on disposable PostgreSQL."""
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import asyncio
import uuid

import psycopg

from tests.contract_validation import assert_contract_response
from tests.test_buyer_review_db import ADMIN, OPERATOR, REVIEWER, VIEWER, WORKSPACE_A, PROJECT_A, _h, _seed_buyer, api


def _expiry(days=30):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def test_blocked_policy_decision_is_durable_contract_and_role_scoped(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Policy subject", fit="match", review="accepted")
    with psycopg.connect(seeded) as conn:
        company_id = str(conn.execute("SELECT company_id FROM project_buyers WHERE id=%s", (buyer_id,)).fetchone()[0])
    path = f"/v1/workspaces/{WORKSPACE_A}/policy-decisions"
    body = {"subject_type": "company", "subject_id": company_id, "controller_scope_id": WORKSPACE_A,
            "purpose": "contact_research", "status": "blocked", "policy_version": "fixture-review-v1",
            "basis_reference": "fixture-reviewed-policy", "provenance": "human_fixture",
            "countries": ["HK"], "expires_at": _expiry(), "retention_days": 30}
    denied = api.post(path, json=body, headers=_h(subject=OPERATOR, key="t10-policy-operator"))
    assert denied.status_code == 403, denied.text
    created = api.post(path, json=body, headers=_h(subject=ADMIN, key="t10-policy-block"))
    assert created.status_code == 201, created.text
    assert_contract_response("PolicyDecisionResponse", created.json())
    listed = api.get(path, params={"subject_id": company_id}, headers=_h(subject=ADMIN))
    assert listed.status_code == 200, listed.text
    assert_contract_response("PolicyDecisionPageResponse", listed.json())
    assert [row["id"] for row in listed.json()["data"]["items"]] == [created.json()["data"]["id"]]
    assert api.get(path, headers=_h(subject=VIEWER)).status_code == 403


def test_company_suppression_create_remove_retains_history_and_never_grants_permission(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Suppressed company", fit="match", review="accepted")
    with psycopg.connect(seeded) as conn:
        company_id = str(conn.execute("SELECT company_id FROM project_buyers WHERE id=%s", (buyer_id,)).fetchone()[0])
    path = f"/v1/workspaces/{WORKSPACE_A}/suppressions"
    body = {"subject_type": "company", "subject_id": company_id, "controller_scope_id": WORKSPACE_A,
            "purposes": ["contact_research", "export_contacts"], "reason": "Fixture data owner requested stop"}
    created = api.post(path, json=body, headers=_h(subject=ADMIN, key="t10-suppress-company"))
    assert created.status_code == 201, created.text
    assert_contract_response("SuppressionResponse", created.json())
    item = created.json()["data"]
    assert item["active"] is True and item["version"] == 1
    listed = api.get(path, headers=_h(subject=REVIEWER))
    assert listed.status_code == 200, listed.text
    assert_contract_response("SuppressionPageResponse", listed.json())
    assert listed.json()["data"]["total"] == 1
    removed = api.post(f"{path}/{item['id']}/remove", json={"reason": "Fixture review complete"},
                       headers=_h(subject=ADMIN, key="t10-remove-company", **{"If-Match": '"1"'}))
    assert removed.status_code == 200, removed.text
    assert_contract_response("SuppressionResponse", removed.json())
    assert removed.json()["data"]["active"] is False and removed.json()["data"]["version"] == 2
    assert api.post(f"{path}/{item['id']}/remove", json={"reason": "Again"},
                    headers=_h(subject=ADMIN, key="t10-stale-remove", **{"If-Match": '"1"'})).status_code == 412
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT count(*) FROM suppressions WHERE id=%s", (item["id"],)).fetchone()[0] == 1


def _gate(subject, purpose):
    from buyeros_api.api.deps import tenant_scoped
    from buyeros_api.services.policy_service import evaluate_current_policy

    async def run():
        async with tenant_scoped(uuid.UUID(WORKSPACE_A)) as session:
            return await evaluate_current_policy(session, subject, purpose, datetime.now(timezone.utc))
    return asyncio.run(run())


def _fixture_permit(seeded, company_id, *, purpose="contact_research", expires=None):
    decision_id = str(uuid.uuid4())
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,controller_scope_id,purpose,status,"
            "policy_version,basis_reference,provenance,countries,expires_at,retention_days,decision_author_id,version) "
            "VALUES (%s,%s,'company',%s,%s,%s,'permitted','fixture-only','fixture-approved-basis',"
            "'fixture-only',ARRAY['HK'],%s,30,%s,1)",
            (decision_id, WORKSPACE_A, company_id, WORKSPACE_A, purpose, expires or _expiry(), str(uuid.uuid5(uuid.NAMESPACE_URL, ADMIN))),
        )
    return decision_id


def test_current_gate_keeps_acceptance_validity_and_each_purpose_separate(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Accepted valid contact", fit="match", review="accepted", domain="policy.example")
    contact_id = str(uuid.uuid4())
    with psycopg.connect(seeded, autocommit=True) as conn:
        company_id = str(conn.execute("SELECT company_id FROM project_buyers WHERE id=%s", (buyer_id,)).fetchone()[0])
        conn.execute("INSERT INTO contact_points(id,workspace_id,company_id,type,normalized_value,validity) "
                     "VALUES (%s,%s,%s,'business_email','fixture@policy.example','provider_marked_valid')",
                     (contact_id, WORKSPACE_A, company_id))
    subject = {"workspace_id": WORKSPACE_A, "controller_scope_id": WORKSPACE_A,
               "project_id": PROJECT_A, "company_id": company_id, "contact_point_id": contact_id,
               "normalized_domain": "policy.example"}
    assert _gate(subject, "contact_research") == {"status": "unknown", "allowed": False, "reason_codes": ["policy_unknown"]}
    _fixture_permit(seeded, company_id)  # Test-only owner fixture; the HTTP permit path stays blocked.
    assert _gate(subject, "contact_research")["allowed"] is True
    assert _gate(subject, "outreach")["status"] == "unknown"
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("UPDATE policy_decisions SET expires_at=now()-interval '1 second' WHERE subject_id=%s", (company_id,))
    assert _gate(subject, "contact_research")["status"] == "unknown"
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("DELETE FROM contact_points WHERE id=%s", (contact_id,))


def test_active_domain_suppression_overrides_fixture_policy_and_remove_keeps_approval_invalidated(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Domain suppression", fit="match", review="accepted", domain="shared.example")
    with psycopg.connect(seeded, autocommit=True) as conn:
        company_id = str(conn.execute("SELECT company_id FROM project_buyers WHERE id=%s", (buyer_id,)).fetchone()[0])
    _fixture_permit(seeded, company_id)
    contact_id = str(uuid.uuid4())
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("INSERT INTO contact_points(id,workspace_id,company_id,type,normalized_value,validity) "
                     "VALUES (%s,%s,%s,'business_email','fixture@shared.example','provider_marked_valid')",
                     (contact_id, WORKSPACE_A, company_id))
    subject = {"workspace_id": WORKSPACE_A, "company_id": company_id, "project_id": PROJECT_A,
               "contact_point_id": contact_id, "normalized_domain": "shared.example"}
    assert _gate(subject, "contact_research")["allowed"] is True
    draft_id, approval_id = str(uuid.uuid4()), str(uuid.uuid4())
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("INSERT INTO outreach_drafts(id,workspace_id,project_id,buyer_id,current_revision,state) "
                     "VALUES (%s,%s,%s,%s,1,'approved')", (draft_id, WORKSPACE_A, PROJECT_A, buyer_id))
        conn.execute("INSERT INTO approvals(id,workspace_id,draft_id,revision_number,content_hash,context_fingerprint,approver_id) "
                     "VALUES (%s,%s,%s,1,%s,%s,%s)",
                     (approval_id, WORKSPACE_A, draft_id, "sha256:"+"a"*64, "sha256:"+"b"*64, str(uuid.uuid4())))
    path = f"/v1/workspaces/{WORKSPACE_A}/suppressions"
    created = api.post(path, json={"subject_type": "domain", "normalized_domain": "SHARED.EXAMPLE.",
        "controller_scope_id": WORKSPACE_A, "purposes": ["contact_research"], "reason": "Fixture controller stop"},
        headers=_h(subject=ADMIN, key="t10-domain-stop"))
    assert created.status_code == 201, created.text
    assert _gate(subject, "contact_research")["status"] == "suppressed"
    without_caller_domain = {key: value for key, value in subject.items() if key != "normalized_domain"}
    assert _gate(without_caller_domain, "contact_research")["status"] == "suppressed"
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT invalidated_reason FROM approvals WHERE id=%s", (approval_id,)).fetchone()[0] == "suppression_added"
        assert conn.execute("SELECT quarantined FROM contact_points WHERE id=%s", (contact_id,)).fetchone()[0] is True
    removed = api.post(f"{path}/{created.json()['data']['id']}/remove", json={"reason": "Fixture review complete"},
        headers=_h(subject=ADMIN, key="t10-domain-remove", **{"If-Match": '"1"'}))
    assert removed.status_code == 200
    assert _gate(subject, "contact_research")["allowed"] is True
    with psycopg.connect(seeded, autocommit=True) as conn:
        assert conn.execute("SELECT invalidated_reason FROM approvals WHERE id=%s", (approval_id,)).fetchone()[0] == "suppression_added"
        assert conn.execute("SELECT quarantined FROM contact_points WHERE id=%s", (contact_id,)).fetchone()[0] is True
        conn.execute("DELETE FROM contact_points WHERE id=%s", (contact_id,))
        conn.execute("DELETE FROM approvals WHERE id=%s", (approval_id,))
        conn.execute("DELETE FROM outreach_drafts WHERE id=%s", (draft_id,))


def test_unapproved_permitted_policy_is_denied_even_for_workspace_admin(api, seeded):
    buyer_id = _seed_buyer(seeded, name="No permit grant")
    with psycopg.connect(seeded) as conn:
        company_id = str(conn.execute("SELECT company_id FROM project_buyers WHERE id=%s", (buyer_id,)).fetchone()[0])
    body = {"subject_type": "company", "subject_id": company_id, "controller_scope_id": WORKSPACE_A,
            "purpose": "contact_research", "status": "permitted", "policy_version": "unapproved",
            "basis_reference": "unapproved-reference", "provenance": "client-checkbox",
            "countries": ["HK"], "expires_at": _expiry(), "retention_days": 30}
    denied = api.post(f"/v1/workspaces/{WORKSPACE_A}/policy-decisions", json=body,
                      headers=_h(subject=ADMIN, key="t10-no-self-permit"))
    assert denied.status_code == 403 and denied.json()["code"] == "POLICY_APPROVAL_REQUIRED"
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT count(*) FROM policy_decisions WHERE subject_id=%s", (company_id,)).fetchone()[0] == 0



def test_policy_gate_uses_latest_each_scope_and_most_restrictive_result(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Restrictive policy", fit="match", review="accepted")
    with psycopg.connect(seeded, autocommit=True) as conn:
        company_id = str(conn.execute("SELECT company_id FROM project_buyers WHERE id=%s", (buyer_id,)).fetchone()[0])
    _fixture_permit(seeded, company_id)
    subject = {"workspace_id": WORKSPACE_A, "controller_scope_id": WORKSPACE_A,
               "project_id": PROJECT_A, "company_id": company_id}
    assert _gate(subject, "contact_research")["status"] == "permitted"
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,controller_scope_id,purpose,status,"
            "policy_version,basis_reference,provenance,countries,expires_at,retention_days,decision_author_id,version) "
            "VALUES (%s,%s,'project',%s,%s,'contact_research','blocked','fixture-only','fixture-stop',"
            "'fixture-only',ARRAY['HK'],%s,30,%s,1)",
            (str(uuid.uuid4()), WORKSPACE_A, PROJECT_A, WORKSPACE_A, _expiry(),
             str(uuid.uuid5(uuid.NAMESPACE_URL, ADMIN))),
        )
    assert _gate(subject, "contact_research") == {
        "status": "blocked", "allowed": False, "reason_codes": ["policy_blocked"]}
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("DELETE FROM policy_decisions WHERE workspace_id=%s AND subject_type='project' AND subject_id=%s",
                     (WORKSPACE_A, PROJECT_A))
    assert _gate(subject, "contact_research")["status"] == "permitted"
    body = {"subject_type": "company", "subject_id": company_id, "controller_scope_id": WORKSPACE_A,
            "purpose": "contact_research", "status": "requires_review", "policy_version": "fixture-review-v2",
            "basis_reference": "fixture-review-needed", "provenance": "human_fixture",
            "countries": ["HK"], "expires_at": _expiry(), "retention_days": 30}
    recorded = api.post(f"/v1/workspaces/{WORKSPACE_A}/policy-decisions", json=body,
                        headers=_h(subject=ADMIN, key="t10-restrict-latest"))
    assert recorded.status_code == 201, recorded.text
    assert _gate(subject, "contact_research") == {
        "status": "requires_review", "allowed": False, "reason_codes": ["policy_review_required"]}


def test_current_policy_gate_waits_for_inflight_policy_mutation(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Gate race", fit="match", review="accepted")
    with psycopg.connect(seeded) as conn:
        company_id = str(conn.execute("SELECT company_id FROM project_buyers WHERE id=%s", (buyer_id,)).fetchone()[0])
    _fixture_permit(seeded, company_id)
    subject = {"workspace_id": WORKSPACE_A, "controller_scope_id": WORKSPACE_A,
               "project_id": PROJECT_A, "company_id": company_id}
    lock_id = int.from_bytes(sha256(f"policy-gate:{WORKSPACE_A}".encode()).digest()[:8], "big", signed=True)
    with psycopg.connect(seeded) as owner, ThreadPoolExecutor(max_workers=1) as pool:
        owner.execute("SELECT pg_advisory_xact_lock(%s)", (lock_id,))
        future = pool.submit(_gate, subject, "contact_research")
        # A gate may not decide on the previous permission while a same-workspace
        # policy writer holds the mutation lock.
        import time
        time.sleep(0.25)
        waiting = not future.done()
        owner.commit()
        result = future.result(timeout=10)
    assert waiting is True
    assert result["status"] == "permitted"

def test_0015_policy_upgrade_and_safe_downgrade_on_disposable_db(migrated, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from tests.test_buyer_review_db import ALEMBIC_INI, SERVICE_ROOT
    monkeypatch.setenv("BUYEROS_DATABASE_URL", migrated)
    config = Config(str(ALEMBIC_INI));config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    command.downgrade(config, "0015_policy_lifecycle")
    with psycopg.connect(migrated) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0015_policy_lifecycle"
        assert conn.execute("SELECT relforcerowsecurity FROM pg_class WHERE relname='policy_decisions'").fetchone()[0] is True
    command.downgrade(config, "0014_buyer_management")
    with psycopg.connect(migrated) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0014_buyer_management"
        assert conn.execute("SELECT count(*) FROM information_schema.columns WHERE table_name='policy_decisions' AND column_name='subject_id'").fetchone()[0] == 0
    command.upgrade(config, "head")
    with psycopg.connect(migrated) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0034_worker_execution"
