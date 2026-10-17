import importlib
import importlib.util
from dataclasses import replace
import psycopg
import pytest
from buyeros_api.api.errors import ApiError

from tests.policy_activation_fixtures import policy_case, owner_run, manifest_body, provision_fixture_authority


def service():
    name = "buyeros_api.services.policy_activation_bootstrap"
    assert importlib.util.find_spec(name) is not None, "reviewed authority bootstrap is not implemented"
    return importlib.import_module(name)


def objects(case):
    m = service()
    manifest = m.AuthorityManifest.model_validate(manifest_body(case))
    auth = m.BootstrapAuthorization(manifest_sha256=m.manifest_digest(manifest),
        target_sha256=manifest.target_sha256, source_sha=manifest.source_sha,
        approval_reference="fixture://approved-local-run", approval_evidence_sha256="b" * 64)
    return m, manifest, auth


def test_dry_run_has_no_mutation(policy_case):
    m, manifest, _ = objects(policy_case)
    async def run(session):
        plan = await m.inspect_authority_manifest(session, manifest, policy_case["now"])
        assert plan["would_create_version"] == 1
    owner_run(policy_case, run)
    with psycopg.connect(policy_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM policy_controller_authorities").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM policy_decisions").fetchone()[0] == 0


def test_api_role_cannot_self_designate_authority(policy_case):
    m, manifest, auth = objects(policy_case)
    async def run(session):
        with pytest.raises(ApiError) as caught:
            await m.verify_bootstrap_execution(session, manifest, auth)
        assert caught.value.status_code == 403 and caught.value.code == "PERMISSION_DENIED"
    owner_run(policy_case, run, runtime=True)


def test_wrong_target_or_unapproved_manifest_never_applies(policy_case):
    m, manifest, auth = objects(policy_case)
    async def run(session):
        with pytest.raises(ValueError, match="target|binding|authorization"):
            await m.verify_bootstrap_execution(session, manifest, auth.model_copy(update={"target_sha256": "f" * 64}))
        execution = await m.verify_bootstrap_execution(session, manifest, auth)
        with pytest.raises(ValueError, match="binding|manifest"):
            await m.apply_authority_manifest(session, manifest, replace(execution, manifest_sha256="e" * 64), policy_case["now"])
    owner_run(policy_case, run)


def test_same_manifest_reconciles_without_duplicate_authority_or_audit(policy_case):
    m = service()
    first = provision_fixture_authority(policy_case)
    replay = provision_fixture_authority(policy_case)
    assert first == replay
    with psycopg.connect(policy_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM policy_controller_authorities").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM audit_events WHERE action='policy.authority.provisioned'").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM policy_decisions").fetchone()[0] == 0
        receipt = db.execute("SELECT execution_receipt FROM policy_controller_authorities").fetchone()[0]
        assert receipt["service"] == "policy-authority-bootstrap"
        assert receipt["db_role"] == "buyeros"
        assert len(receipt["authorization_sha256"]) == 64


def test_revoke_keeps_history_even_when_designated_account_is_disabled(policy_case):
    m, manifest, auth = objects(policy_case)
    first = provision_fixture_authority(policy_case)
    with psycopg.connect(policy_case["dsn"]) as db:
        db.execute("UPDATE memberships SET active=false,version=version+1 WHERE user_id=%s", (policy_case["actors"]["owner"],))
    async def run(session):
        import hashlib
        from uuid import UUID
        revoke_manifest = manifest.model_copy(update={
            "operation": "revoke", "expected_authority_id": UUID(first["authority_id"]),
            "expected_authority_version": 1,
            "revocation_reason_sha256": hashlib.sha256(b"fixture authority withdrawal").hexdigest(),
        })
        revoke_auth = auth.model_copy(update={"manifest_sha256": m.manifest_digest(revoke_manifest)})
        execution = await m.verify_bootstrap_execution(session, revoke_manifest, revoke_auth)
        return await m.revoke_authority(session, first["authority_id"], 1,
                                       "fixture authority withdrawal", execution, policy_case["now"])
    revoked = owner_run(policy_case, run)
    assert revoked["version"] == 2 and revoked["status"] == "revoked"
    with psycopg.connect(policy_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM policy_controller_authorities").fetchone()[0] == 2


def test_provision_authorization_cannot_be_reused_to_revoke(policy_case):
    m, manifest, auth = objects(policy_case)
    first = provision_fixture_authority(policy_case)
    async def run(session):
        execution = await m.verify_bootstrap_execution(session, manifest, auth)
        with pytest.raises(ValueError, match="binding|operation"):
            await m.revoke_authority(session, first["authority_id"], 1, "wrong authorization",
                                     execution, policy_case["now"])
    owner_run(policy_case, run)


def test_revocation_authorization_binds_the_reason(policy_case):
    import hashlib
    from uuid import UUID
    m, manifest, auth = objects(policy_case)
    first = provision_fixture_authority(policy_case)
    revoke_manifest = manifest.model_copy(update={
        "operation": "revoke", "expected_authority_id": UUID(first["authority_id"]),
        "expected_authority_version": 1,
        "revocation_reason_sha256": hashlib.sha256(b"approved withdrawal reason").hexdigest(),
    })
    revoke_auth = auth.model_copy(update={"manifest_sha256": m.manifest_digest(revoke_manifest)})
    async def run(session):
        execution = await m.verify_bootstrap_execution(session, revoke_manifest, revoke_auth)
        with pytest.raises(ValueError, match="reason|binding"):
            await m.revoke_authority(session, first["authority_id"], 1, "a different reason", execution, policy_case["now"])
    owner_run(policy_case, run)
