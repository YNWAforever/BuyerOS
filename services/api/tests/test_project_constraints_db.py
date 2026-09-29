"""T04: same-workspace cross-project links must fail in PostgreSQL itself."""

import json

import psycopg
import pytest

from tests.conftest import runtime_role_dsn

WS_A = "11111111-1111-4111-8111-111111111111"
WS_B = "22222222-2222-4222-8222-222222222222"
PROJECT_A = "a0000000-0000-4000-8000-000000000001"
PROJECT_B = "a0000000-0000-4000-8000-000000000002"
ICP_A = "a1000000-0000-4000-8000-000000000001"
ICP_B = "a1000000-0000-4000-8000-000000000002"
COMPANY = "a2000000-0000-4000-8000-000000000001"
BUYER_A = "a3000000-0000-4000-8000-000000000001"
BUYER_B = "a3000000-0000-4000-8000-000000000002"
LIST_A = "a4000000-0000-4000-8000-000000000001"
SNAP_A = "a5000000-0000-4000-8000-000000000001"
FIT_B = "a6000000-0000-4000-8000-000000000001"


def _fixture_rows(conn):
    conn.execute(
        "INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) "
        "VALUES (%s,%s,'P2','C','Offer','{US}','{en}',1)", (PROJECT_B, WS_A),
    )
    for icp, project in ((ICP_A, PROJECT_A), (ICP_B, PROJECT_B)):
        conn.execute(
            "INSERT INTO icp_versions(id,workspace_id,project_id,number,content,content_hash,basis_offer_revision) "
            "VALUES (%s,%s,%s,1,'{}'::jsonb,%s,1)", (icp, WS_A, project, "sha256:" + "0" * 64),
        )
    conn.execute(
        "INSERT INTO companies(id,workspace_id,legal_name,display_name) "
        "VALUES (%s,%s,'Same Co','Same Co')", (COMPANY, WS_A),
    )
    for buyer, project in ((BUYER_A, PROJECT_A), (BUYER_B, PROJECT_B)):
        conn.execute(
            "INSERT INTO project_buyers(id,workspace_id,project_id,company_id,version) "
            "VALUES (%s,%s,%s,%s,1)", (buyer, WS_A, project, COMPANY),
        )
    conn.execute(
        "INSERT INTO buyer_lists(id,workspace_id,project_id,name) VALUES (%s,%s,%s,'List')",
        (LIST_A, WS_A, PROJECT_A),
    )
    conn.execute(
        "INSERT INTO buyer_snapshots(id,workspace_id,project_id,filter_hash,actor_user_id) "
        "VALUES (%s,%s,%s,'sha256:sample',%s)",
        (SNAP_A, WS_A, PROJECT_A, "a7000000-0000-4000-8000-000000000001"),
    )
    conn.execute(
        "INSERT INTO fit_assessments(id,workspace_id,project_id,project_buyer_id,icp_version_id,evidence_set_hash,"
        "verdict,rationale,evidence_ids) VALUES (%s,%s,%s,%s,%s,'sha256:sample','match','reason','[]'::jsonb)",
        (FIT_B, WS_A, PROJECT_B, BUYER_B, ICP_B),
    )


def _must_reject(conn, sql, params):
    conn.execute("SAVEPOINT cross_project_probe")
    try:
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            conn.execute(sql, params)
    finally:
        conn.execute("ROLLBACK TO SAVEPOINT cross_project_probe")
        conn.execute("RELEASE SAVEPOINT cross_project_probe")


def test_same_tenant_cross_project_links_rejected(seeded):
    with psycopg.connect(seeded) as conn:
        try:
            _fixture_rows(conn)
            _must_reject(
                conn,
                "UPDATE projects SET active_icp_version_id = %s WHERE id = %s",
                (ICP_B, PROJECT_A),
            )
            _must_reject(
                conn,
                "UPDATE icp_versions SET parent_id = %s WHERE id = %s",
                (ICP_B, ICP_A),
            )
            _must_reject(
                conn,
                "INSERT INTO list_memberships(id,workspace_id,project_id,list_id,buyer_id) VALUES (%s,%s,%s,%s,%s)",
                ("b1000000-0000-4000-8000-000000000001", WS_A, PROJECT_A, LIST_A, BUYER_B),
            )
            _must_reject(
                conn,
                "INSERT INTO fit_assessments(id,workspace_id,project_id,project_buyer_id,icp_version_id,"
                "evidence_set_hash,verdict,rationale,evidence_ids) "
                "VALUES (%s,%s,%s,%s,%s,'sha256:bad','match','bad','[]'::jsonb)",
                ("b2000000-0000-4000-8000-000000000001", WS_A, PROJECT_A, BUYER_A, ICP_B),
            )
            _must_reject(
                conn,
                "INSERT INTO search_runs(id,workspace_id,project_id,icp_version_id,status,limits,"
                "target_companies,raw_result_count) VALUES (%s,%s,%s,%s,'queued','{}'::jsonb,0,0)",
                ("b3000000-0000-4000-8000-000000000001", WS_A, PROJECT_A, ICP_B),
            )
            _must_reject(
                conn,
                "INSERT INTO buyer_snapshot_items(id,workspace_id,project_id,snapshot_id,ordinal,buyer_id,buyer_version) "
                "VALUES (%s,%s,%s,%s,1,%s,1)",
                ("b4000000-0000-4000-8000-000000000001", WS_A, PROJECT_A, SNAP_A, BUYER_B),
            )
            evidence_b = "a8000000-0000-4000-8000-000000000001"
            conn.execute(
                "INSERT INTO evidence(id,workspace_id,project_id,company_id,stance,excerpt) "
                "VALUES (%s,%s,%s,%s,'supports','Other project')",
                (evidence_b, WS_A, PROJECT_B, COMPANY),
            )
            _must_reject(
                conn,
                "INSERT INTO fit_assessments(id,workspace_id,project_id,project_buyer_id,icp_version_id,"
                "evidence_set_hash,verdict,rationale,evidence_ids) "
                "VALUES (%s,%s,%s,%s,%s,'sha256:bad','match','bad',%s::jsonb)",
                ("b6000000-0000-4000-8000-000000000001", WS_A, PROJECT_A, BUYER_A, ICP_A,
                 json.dumps([evidence_b])),
            )
            _must_reject(
                conn,
                "INSERT INTO human_reviews(id,workspace_id,project_buyer_id,fit_assessment_id,state,actor_user_id) "
                "VALUES (%s,%s,%s,%s,'accepted',%s)",
                ("b5000000-0000-4000-8000-000000000001", WS_A, BUYER_A, FIT_B,
                 "a7000000-0000-4000-8000-000000000001"),
            )
        finally:
            conn.rollback()


def test_runtime_role_pool_reuse_isolated(seeded):
    with psycopg.connect(seeded) as owner:
        role = owner.execute(
            "SELECT rolbypassrls FROM pg_roles WHERE rolname='buyeros_api'"
        ).fetchone()
    assert role == (False,)
    with psycopg.connect(runtime_role_dsn(seeded)) as conn:
        conn.execute("SELECT set_config('app.workspace_id', %s, true)", (WS_A,))
        names = {row[0] for row in conn.execute("SELECT name FROM projects")}
        assert names == {"ProjectA"}
        conn.commit()
        with pytest.raises((psycopg.errors.UndefinedObject, psycopg.errors.InvalidTextRepresentation)):
            conn.execute("SELECT name FROM projects").fetchall()
        conn.rollback()
        conn.execute("SELECT set_config('app.workspace_id', %s, true)", (WS_B,))
        names = {row[0] for row in conn.execute("SELECT name FROM projects")}
        assert names == {"ProjectB"}


def test_0013_preflight_reports_legacy_conflict_without_deleting_it(seeded, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from buyeros_api.settings import get_settings
    from tests.conftest import ALEMBIC_INI, SERVICE_ROOT

    monkeypatch.setenv("BUYEROS_DATABASE_MIGRATION_URL", seeded)
    get_settings.cache_clear()
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    try:
        command.downgrade(config, "0012_offer_basis_revision")
        with psycopg.connect(seeded, autocommit=True) as owner:
            owner.execute(
                "INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,"
                "language_preferences,version) VALUES (%s,%s,'Legacy P2','Co','Offer','{US}','{en}',1)",
                (PROJECT_B, WS_A),
            )
            owner.execute(
                "INSERT INTO icp_versions(id,workspace_id,project_id,number,content,content_hash) "
                "VALUES (%s,%s,%s,1,'{}'::jsonb,%s)",
                (ICP_B, WS_A, PROJECT_B, "sha256:" + "0" * 64),
            )
            owner.execute(
                "UPDATE projects SET active_icp_version_id=%s WHERE id=%s", (ICP_B, PROJECT_A)
            )
        with pytest.raises(RuntimeError, match="active_icp=1") as failure:
            command.upgrade(config, "0013_project_link_constraints")
        assert PROJECT_A in str(failure.value)
        with psycopg.connect(seeded, autocommit=True) as owner:
            pointer = owner.execute(
                "SELECT active_icp_version_id FROM projects WHERE id=%s", (PROJECT_A,)
            ).fetchone()[0]
            assert str(pointer) == ICP_B  # failed migration kept the row for explicit remediation
            owner.execute("UPDATE projects SET active_icp_version_id=NULL WHERE id=%s", (PROJECT_A,))
        command.upgrade(config, "0013_project_link_constraints")
        with psycopg.connect(seeded) as owner:
            head = owner.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        assert head == "0013_project_link_constraints"
        command.upgrade(config, "0014_buyer_management")
        with psycopg.connect(seeded) as owner:
            assert owner.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0014_buyer_management"
        command.upgrade(config, "head")
        with psycopg.connect(seeded) as owner:
            assert owner.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0033_api_rate_windows"
    finally:
        with psycopg.connect(seeded, autocommit=True) as owner:
            owner.execute("UPDATE projects SET active_icp_version_id=NULL WHERE id=%s", (PROJECT_A,))
        command.upgrade(config, "head")
        with psycopg.connect(seeded, autocommit=True) as owner:
            owner.execute("DELETE FROM icp_versions WHERE id=%s", (ICP_B,))
            owner.execute("DELETE FROM projects WHERE id=%s", (PROJECT_B,))
        get_settings.cache_clear()
