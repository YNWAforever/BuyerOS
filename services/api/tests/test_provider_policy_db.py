"""Actual controlled provider approval under API/worker RLS; no external calls."""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.policy_activation_fixtures import policy_case, policy_api, policy_headers, approve_provider_fixture, owner_run
from tests.test_provider_policy_contract import provider_context
from tests.policy_activation_target import assert_owned_test_dsn


def approve(case):
    approve_provider_fixture(case["dsn"], case["workspace"], case["project"], case["actors"]["owner"],
        purpose="contact_research", domains=("rice.example.test",),
        scope={"provider_name": "synthetic", "account_reference": "owned-test-account", "contract_sha256": "b" * 64})


def worker_gate(case, context):
    from tests.cutover_fixtures import role_dsn
    from buyeros_api.db.session import tenant_session
    from buyeros_api.services.policy_service import evaluate_current_policy
    assert_owned_test_dsn(case["dsn"])
    with psycopg.connect(case["dsn"]) as db:
        db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
    async def run():
        engine = create_async_engine(role_dsn(case["dsn"], "buyeros_worker").replace(
            "postgresql://", "postgresql+psycopg://", 1), poolclass=NullPool)
        try:
            async with tenant_session(engine, case["workspace"]) as session:
                return await evaluate_current_policy(session, {"workspace_id": case["workspace"],
                    "project_id": case["project"]}, "contact_research", datetime.now(timezone.utc),
                    use_context=context)
        finally:
            await engine.dispose()
    return asyncio.run(run())


def test_provider_approval_is_current_in_api_and_worker_with_exact_column_privileges(policy_case):
    case = policy_case
    approve(case)
    from buyeros_api.services.policy_service import evaluate_current_policy
    async def run(session):
        return await evaluate_current_policy(session, {"workspace_id": case["workspace"],
            "project_id": case["project"]}, "contact_research", datetime.now(timezone.utc),
            use_context=provider_context())
    assert owner_run(case, run, runtime=True)["allowed"]
    assert worker_gate(case, provider_context())["allowed"]
    assert not worker_gate(case, provider_context(account_reference="other"))["allowed"]
    assert not worker_gate(case, provider_context(project_id=uuid4()))["allowed"]
    with psycopg.connect(case["dsn"]) as db:
        for name in ("policy_controller_authorities", "policy_activation_requests", "policy_activation_resolutions"):
            assert not db.execute("SELECT has_table_privilege('buyeros_worker',%s,'SELECT')", (name,)).fetchone()[0]
            for op in ("INSERT", "UPDATE", "DELETE"):
                assert not db.execute("SELECT has_table_privilege('buyeros_worker',%s,%s)", (name, op)).fetchone()[0]
        assert not db.execute("SELECT has_column_privilege('buyeros_worker','policy_controller_authorities','designation_reference','SELECT')").fetchone()[0]
        assert not db.execute("SELECT has_column_privilege('buyeros_worker','policy_activation_requests','requester_id','SELECT')").fetchone()[0]
        assert not db.execute("SELECT has_column_privilege('buyeros_worker','policy_activation_resolutions','reason_hash','SELECT')").fetchone()[0]
        assert db.execute("SELECT count(*) FROM audit_events WHERE workspace_id=%s AND action='policy.activation.approved'", (case["workspace"],)).fetchone()[0] == 1
        # RLS still hides all proof across workspaces even with permitted columns.
        with db.transaction():
            db.execute("SET LOCAL ROLE buyeros_worker")
            db.execute("SELECT set_config('app.workspace_id',%s,true)", ("22222222-2222-4222-8222-222222222222",))
            assert db.execute("SELECT count(id) FROM policy_activation_requests").fetchone()[0] == 0


def test_provider_recheck_denies_after_owner_membership_revocation(policy_case):
    case = policy_case
    approve(case)
    assert worker_gate(case, provider_context())["allowed"]
    with psycopg.connect(case["dsn"]) as db:
        before = db.execute("SELECT count(*) FROM provider_operations").fetchone()[0]
        db.execute("UPDATE memberships SET active=false,version=version+1 WHERE user_id=%s",
                   (case["actors"]["owner"],))
    assert not worker_gate(case, provider_context())["allowed"]
    with psycopg.connect(case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM provider_operations").fetchone()[0] == before


def test_provider_canonical_record_is_retrievable_through_normal_auth_with_flags_off(policy_case, policy_api):
    from tests.contract_validation import assert_contract_response
    case = policy_case
    approve(case)
    response = policy_api.get(f"/v1/workspaces/{case['workspace']}/policy-activation-requests",
        params={"project_id": str(case["project"])}, headers=policy_headers(case, "owner"))
    assert response.status_code == 200, response.text
    assert_contract_response("ActivationPageResponse", response.json())
    records = response.json()["data"]["items"]
    assert len(records) == 1 and records[0]["receipt"]["outcome"] == "approved"
    assert records[0]["terms"]["provider_scope"]["account_reference"] == "owned-test-account"
    from buyeros_api.settings import get_settings
    assert not get_settings().paid_admission_enabled and not get_settings().delivery_admission_enabled


def test_provider_approval_requires_current_designated_owner_and_atomic_audit(policy_case, monkeypatch):
    from buyeros_api.api.policy_activation_schemas import ActivationSubmit, ActivationDecision
    from buyeros_api.services import policy_activation_service as service
    from buyeros_api.api.errors import ApiError
    from tests.policy_activation_fixtures import manifest_body, current_terms
    from buyeros_api.services import policy_activation_bootstrap as bootstrap
    case = policy_case
    manifest = bootstrap.AuthorityManifest.model_validate({**manifest_body(case),
        "allowed_actions": ["contact.enrich"]})
    auth = bootstrap.BootstrapAuthorization(manifest_sha256=bootstrap.manifest_digest(manifest),
        target_sha256=manifest.target_sha256, source_sha=manifest.source_sha,
        approval_reference="fixture://provider-owned-designation", approval_evidence_sha256="a" * 64)
    async def provision(session):
        verified = await bootstrap.verify_bootstrap_execution(session, manifest, auth)
        return await bootstrap.apply_authority_manifest(session, manifest, verified, case["now"])
    authority = owner_run(case, provision)
    actor = service.PolicyActor(case["workspace"], case["actors"]["owner"], frozenset({"workspace_admin"}), 1)
    terms = {**current_terms(case), "template_version": "provider-native.v1", "allowed_actions": ["contact.enrich"],
             "provider_scope": {"provider_name": "synthetic", "account_reference": "owned-test-account", "contract_sha256": "b" * 64}}
    async def submit(session):
        return await service.submit_activation(session, actor=actor, data=ActivationSubmit(
            client_request_id=uuid4(), authority_id=authority["authority_id"], authority_version=1,
            expected_policy_id=None, expected_policy_version=None, terms=terms,
            request_deadline=case["now"]+timedelta(days=1)), key="provider-submit-atomic", now=case["now"])
    request = owner_run(case, submit, runtime=True)
    decision = ActivationDecision(action="approve", terms_hash=request.terms_hash,
        expected_policy_id=None, expected_policy_version=None, reason="Synthetic provider permission only.")
    async def decide(session, selected_actor=actor):
        return await service.decide_activation(session, actor=selected_actor, request_id=request.id,
            data=decision, key="provider-approve-atomic", now=case["now"])
    unqualified = service.PolicyActor(case["workspace"], case["actors"]["unqualified"], frozenset({"workspace_admin"}), 1)
    with pytest.raises(ApiError) as error:
        owner_run(case, lambda s: decide(s, unqualified), runtime=True)
    assert error.value.status_code == 403
    original = service.append_audit
    def audit_failure(*args, **kwargs):
        raise RuntimeError("synthetic audit storage unavailable")
    monkeypatch.setattr(service, "append_audit", audit_failure)
    with pytest.raises(RuntimeError, match="audit storage"):
        owner_run(case, decide, runtime=True)
    with psycopg.connect(case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM policy_activation_resolutions WHERE request_id=%s", (request.id,)).fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM policy_decisions WHERE status='permitted'").fetchone()[0] == 0
    monkeypatch.setattr(service, "append_audit", original)
    result = owner_run(case, decide, runtime=True)
    replay = owner_run(case, decide, runtime=True)
    assert result.receipt == replay.receipt and result.receipt.outcome == "approved"
    assert worker_gate(case, provider_context())["allowed"]
