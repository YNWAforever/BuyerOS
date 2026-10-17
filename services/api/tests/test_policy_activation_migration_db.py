"""Only run via the owned-target runner; no production URL fallback."""
import psycopg
import pytest
from uuid import uuid4
from psycopg.types.json import Jsonb

TABLES = ("policy_controller_authorities", "policy_activation_requests", "policy_activation_resolutions")


def test_0056_accepts_disabled_runtime_inspection_but_not_an_unknown_future_head(isolated_migrated):
    from buyeros_api.services.worker_recovery import set_execution_runtime
    with psycopg.connect(isolated_migrated) as db:
        before = db.execute("SELECT backend,enabled,epoch FROM worker_runtime_control").fetchone()
    result = set_execution_runtime(isolated_migrated, expected_epoch=before[2], backend=before[0],
                                   enabled=False, reason="Owned policy migration dry-run")
    assert result["applied"] is False and result["enabled"] is False
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute("SELECT backend,enabled,epoch FROM worker_runtime_control").fetchone() == before
        db.execute("UPDATE alembic_version SET version_num='0099_unreviewed_future'")
    try:
        with pytest.raises(ValueError, match="compatible"):
            set_execution_runtime(isolated_migrated, expected_epoch=before[2], backend=before[0],
                                  enabled=False, reason="Future head must stay rejected")
    finally:
        with psycopg.connect(isolated_migrated) as db:
            db.execute("UPDATE alembic_version SET version_num='0056_policy_activation'")


def schema_member(db, workspace):
    user = uuid4()
    db.execute("INSERT INTO users(id,issuer,subject) VALUES(%s,'https://oidc.buyeros.test/',%s)",
               (user, "schema-only-" + str(user)))
    db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active,version) "
               "VALUES(%s,%s,%s,ARRAY['workspace_admin'],true,1)", (uuid4(), workspace, user))
    return user


def schema_authority(db):
    workspace, project = db.execute("SELECT workspace_id,id FROM projects ORDER BY id LIMIT 1").fetchone()
    user, version = schema_member(db, workspace), 1
    authority = uuid4()
    db.execute(
        "INSERT INTO policy_controller_authorities "
        "(id,workspace_id,project_id,approver_user_id,membership_version,version,status,purposes,"
        "allowed_actions,valid_from,expires_at,designation_reference,designation_sha256,manifest_sha256,execution_receipt) "
        "VALUES (%s,%s,%s,%s,%s,1,'active',ARRAY['account_research'],ARRAY['lead.evidence.read'],"
        "now()-interval '1 day',now()+interval '1 day','fixture://schema-only-history',%s,%s,'{}'::jsonb)",
        (authority, workspace, project, user, version, "a" * 64, "b" * 64),
    )
    return workspace, project, user, authority


def test_0055_upgrade_adds_three_tables_with_forced_rls_and_exact_privileges(isolated_migrated, record_property):
    with psycopg.connect(isolated_migrated) as db:
        record_property("actual_server_version_num", db.execute("SHOW server_version_num").fetchone()[0])
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0056_policy_activation",)
        for name in TABLES:
            assert db.execute(
                "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=to_regclass(%s)",
                ("public." + name,),
            ).fetchone() == (True, True)
            assert not db.execute("SELECT has_table_privilege('buyeros_worker',%s,'INSERT')", (name,)).fetchone()[0]
        for role in ("buyeros_api", "buyeros_worker"):
            for name in ("policy_decisions", "audit_events"):
                for verb in ("UPDATE", "DELETE"):
                    assert not db.execute("SELECT has_table_privilege(%s,%s,%s)", (role, name, verb)).fetchone()[0]
        assert db.execute("SELECT has_table_privilege('buyeros_api','audit_events','INSERT')").fetchone()[0]
        assert not db.execute("SELECT has_table_privilege('buyeros_worker','policy_decisions','INSERT')").fetchone()[0]


def test_populated_downgrade_refuses_to_destroy_policy_history(isolated_seeded):
    from alembic import command
    from alembic.config import Config
    from tests.conftest import ALEMBIC_INI, SERVICE_ROOT
    # This is a schema-history refusal fixture, not an authority activation.
    # It must not depend on the T03 service we have not implemented yet.
    with psycopg.connect(isolated_seeded) as db:
        schema_authority(db)
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    with pytest.raises(RuntimeError, match="preserve.*policy|policy.*history"):
        command.downgrade(config, "0055_lead_workflow")


def test_cross_tenant_links_and_runtime_rewrites_are_denied(isolated_seeded):
    from tests.test_policy_activation_contract import terms_body
    with psycopg.connect(isolated_seeded) as db:
        workspace, project, _, authority = schema_authority(db)
        foreign_workspace, foreign_project = db.execute(
            "SELECT workspace_id,id FROM projects WHERE workspace_id<>%s LIMIT 1", (workspace,)
        ).fetchone()
        foreign_user = schema_member(db, foreign_workspace)
        terms = {**terms_body(), "workspace_id": str(foreign_workspace),
                 "controller_scope_id": str(foreign_workspace), "project_id": str(foreign_project)}
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            with db.transaction():
                db.execute(
                    "INSERT INTO policy_activation_requests(id,workspace_id,project_id,requester_id,"
                    "client_request_id,authority_id,authority_version,terms,terms_hash,request_deadline) "
                    "VALUES (%s,%s,%s,%s,%s,%s,1,%s,%s,now()+interval '1 hour')",
                    (uuid4(), foreign_workspace, foreign_project, foreign_user, uuid4(), authority, Jsonb(terms), "c" * 64),
                )
        for table in (*TABLES, "audit_events", "policy_decisions"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with db.transaction():
                    db.execute("SET LOCAL ROLE buyeros_api")
                    db.execute("SELECT set_config('app.workspace_id',%s,true)", (str(workspace),))
                    db.execute(f"UPDATE public.{table} SET updated_at=updated_at")
        with db.transaction():
            db.execute("SET LOCAL ROLE buyeros_api")
            db.execute("SELECT set_config('app.workspace_id',%s,true)", (str(workspace),))
            probe = uuid4()
            db.execute("INSERT INTO audit_events(id,workspace_id,action,subject_type) VALUES(%s,%s,'fixture.audit','fixture')",
                       (probe, workspace))
            assert db.execute("SELECT count(*) FROM audit_events WHERE id=%s", (probe,)).fetchone()[0] == 1
        db.execute("RESET ROLE")


def test_empty_downgrade_keeps_hardening_and_repeated_upgrade_is_noop(isolated_migrated):
    from alembic import command
    from alembic.config import Config
    from tests.conftest import ALEMBIC_INI, SERVICE_ROOT
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    command.downgrade(config, "0055_lead_workflow")
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute("SELECT to_regclass('public.policy_activation_requests')").fetchone()[0] is None
        assert not db.execute("SELECT has_table_privilege('buyeros_api','audit_events','DELETE')").fetchone()[0]
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0056_policy_activation"
        assert db.execute("SELECT count(*) FROM policy_activation_requests").fetchone()[0] == 0
