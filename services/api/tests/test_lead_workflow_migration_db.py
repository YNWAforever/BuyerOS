"""The lead journal must not weaken tenant or append-only boundaries."""
import uuid

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg import sql

from tests.conftest import ALEMBIC_INI, SERVICE_ROOT, runtime_role_dsn

TABLES = (
    "lead_case_states", "lead_observations", "lead_private_payloads",
    "lead_reviews", "lead_review_evidence", "lead_preparations",
    "lead_preparation_revisions", "lead_preparation_evidence",
    "lead_preparation_content_reviews", "lead_action_intents",
    "pilot_budget_policies", "pilot_cost_events",
    "pilot_credit_observations", "pilot_reconciliations",
)
JOURNALS = (
    "lead_observations", "lead_reviews", "lead_review_evidence",
    "lead_preparation_revisions", "lead_preparation_evidence",
    "lead_preparation_content_reviews", "pilot_cost_events",
    "pilot_credit_observations", "pilot_reconciliations",
)


def test_lead_workflow_schema_is_tenant_scoped_and_append_only(isolated_migrated):
    with psycopg.connect(isolated_migrated) as db:
        for table in TABLES:
            assert db.execute("SELECT to_regclass(%s)", (table,)).fetchone()[0] == table
            assert db.execute(
                "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass",
                (table,),
            ).fetchone() == (True, True)
            assert db.execute(
                "SELECT has_table_privilege('buyeros_worker',%s,'INSERT')", (table,)
            ).fetchone() == (False,)
        for table in JOURNALS:
            assert db.execute(
                "SELECT has_table_privilege('buyeros_api',%s,'SELECT'),"
                "has_table_privilege('buyeros_api',%s,'INSERT'),"
                "has_table_privilege('buyeros_api',%s,'UPDATE'),"
                "has_table_privilege('buyeros_api',%s,'DELETE')", (table,) * 4,
            ).fetchone() == (True, True, False, False)
        constraints = [
            value[0] for value in db.execute(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid='lead_observations'::regclass AND contype='f'"
            )
        ]
        assert any("workspace_id, project_id, buyer_id, company_id" in row for row in constraints)
        assert any("workspace_id, company_id, person_id" in row for row in constraints)
        assert any("workspace_id, company_id, contact_id" in row for row in constraints)


def test_0054_upgrade_preserves_original_source_checks_and_fences(isolated_seeded, monkeypatch):
    """A real predecessor-to-head upgrade retains an existing human source check."""
    from buyeros_api.settings import get_settings

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    # A fresh isolated database contains no new lead rows and can safely return
    # to the predecessor for this upgrade test. Never use a hosted DSN.
    command.downgrade(config, "0054_buyer_source_checks")
    company, buyer, check, actor = (uuid.uuid4() for _ in range(4))
    workspace = uuid.UUID("11111111-1111-4111-8111-111111111111")
    project = uuid.UUID("a0000000-0000-4000-8000-000000000001")
    with psycopg.connect(isolated_seeded, autocommit=True) as db:
        db.execute("INSERT INTO users(id,issuer,subject) VALUES (%s,'urn:lead:test',%s)", (actor, str(actor)))
        db.execute(
            "INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES (%s,%s,'Original','Original')",
            (company, workspace),
        )
        db.execute(
            "INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES (%s,%s,%s,%s)",
            (buyer, workspace, project, company),
        )
        db.execute(
            "INSERT INTO buyer_source_checks"
            "(id,workspace_id,project_id,buyer_id,checked_on,grade,rationale,limitations,sources,recorded_by_user_id)"
            "VALUES (%s,%s,%s,%s,'2026-10-15','B','Original reason','Origin unconfirmed',"
            "'[{\"title\":\"Official\",\"url\":\"https://example.test/rice\"}]',%s)",
            (check, workspace, project, buyer, actor),
        )
        before = db.execute("SELECT * FROM buyer_source_checks WHERE id=%s", (check,)).fetchone()
    command.upgrade(config, "head")
    with psycopg.connect(isolated_seeded) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0055_lead_workflow",)
        assert db.execute("SELECT * FROM buyer_source_checks WHERE id=%s", (check,)).fetchone() == before
        assert db.execute(
            "SELECT buyeros_search_receipts_writable(),buyeros_model_receipts_writable(),"
            "buyeros_contact_receipts_writable()"
        ).fetchone() == (True, True, True)


def test_lead_journal_rejects_foreign_company_and_runtime_mutation(isolated_seeded):
    workspace = uuid.UUID("11111111-1111-4111-8111-111111111111")
    project = uuid.UUID("a0000000-0000-4000-8000-000000000001")
    company, other, buyer, person, observation, actor = (uuid.uuid4() for _ in range(6))
    with psycopg.connect(isolated_seeded, autocommit=True) as db:
        db.execute("INSERT INTO users(id,issuer,subject) VALUES (%s,'urn:lead:test',%s)", (actor, str(actor)))
        for identity in (company, other):
            db.execute(
                "INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES (%s,%s,'Test','Test')",
                (identity, workspace),
            )
        db.execute(
            "INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES (%s,%s,%s,%s)",
            (buyer, workspace, project, company),
        )
        db.execute("INSERT INTO people(id,workspace_id,company_id) VALUES (%s,%s,%s)", (person, workspace, other))
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            db.execute(
                "INSERT INTO lead_observations"
                "(id,workspace_id,project_id,buyer_id,company_id,person_id,claim,stance,checked_at,content_hash,recorded_by_user_id)"
                "VALUES (%s,%s,%s,%s,%s,%s,'employment','supports',now(),'sha256:test',%s)",
                (observation, workspace, project, buyer, company, person, actor),
            )
    with psycopg.connect(runtime_role_dsn(isolated_seeded)) as db:
        db.execute("SELECT set_config('app.workspace_id',%s,true)", (str(workspace),))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute(sql.SQL("UPDATE {} SET content_hash='changed'").format(sql.Identifier("lead_observations")))
