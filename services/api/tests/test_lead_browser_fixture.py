import pytest
import psycopg


def test_lead_fixture_refuses_remote_or_non_test_database():
    from tools.seed_lead_workflow_fixture import seed_lead_workflow_fixture
    for dsn in ("postgresql://example.invalid/production", "postgresql://127.0.0.1/customer_database"):
        with pytest.raises(pytest.UsageError, match="disposable"):
            seed_lead_workflow_fixture(dsn)


def test_owned_browser_seed_and_reset_preserve_24_companies_and_57_links(isolated_migrated, monkeypatch):
    from tools.serve_e2e_fixture import seed
    from tools.seed_lead_workflow_fixture import seed_lead_workflow_fixture, reset_lead_workflow_fixture, PROJECT
    monkeypatch.setenv("BUYEROS_E2E_SEED_BUYERS", "1")
    seed(isolated_migrated)
    seed_lead_workflow_fixture(isolated_migrated)
    with psycopg.connect(isolated_migrated) as db:
        companies = db.execute("SELECT id,company_id FROM project_buyers WHERE project_id=%s ORDER BY id", (PROJECT,)).fetchall()
        assert len(companies) == 24
        assert db.execute("SELECT sum(jsonb_array_length(sources)) FROM buyer_source_checks WHERE project_id=%s",
                          (PROJECT,)).fetchone() == (57,)
        assert db.execute("SELECT count(*) FROM lead_case_states WHERE project_id=%s AND priority", (PROJECT,)).fetchone() == (8,)
        assert db.execute("SELECT count(*) FROM lead_reviews WHERE project_id=%s", (PROJECT,)).fetchone() == (6,)
        assert db.execute("SELECT count(*) FROM contact_points WHERE company_id IN "
                          "(SELECT company_id FROM project_buyers WHERE project_id=%s)", (PROJECT,)).fetchone() == (4,)
    reset_lead_workflow_fixture(isolated_migrated)
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute("SELECT id,company_id FROM project_buyers WHERE project_id=%s ORDER BY id", (PROJECT,)).fetchall() == companies
        assert db.execute("SELECT count(*) FROM lead_reviews WHERE project_id=%s", (PROJECT,)).fetchone() == (6,)
        assert db.execute("SELECT count(*) FROM provider_operations").fetchone() == (0,)
