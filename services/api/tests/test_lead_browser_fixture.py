import pytest
import psycopg


def test_owned_reset_waits_for_inflight_policy_transaction_before_deleting(isolated_migrated,monkeypatch):
    import hashlib,time
    from concurrent.futures import ThreadPoolExecutor
    from tools.serve_e2e_fixture import seed
    from tools.seed_lead_workflow_fixture import seed_lead_workflow_fixture,reset_lead_workflow_fixture,WORKSPACE,PROJECT
    monkeypatch.setenv("BUYEROS_E2E_SEED_BUYERS","1")
    seed(isolated_migrated);seed_lead_workflow_fixture(isolated_migrated)
    lock=int.from_bytes(hashlib.sha256(f"policy-gate:{WORKSPACE}".encode()).digest()[:8],"big",signed=True)
    with psycopg.connect(isolated_migrated) as owner,ThreadPoolExecutor(max_workers=1) as pool:
        before=owner.execute("SELECT id FROM lead_observations WHERE project_id=%s ORDER BY id",(PROJECT,)).fetchall()
        assert before
        owner.execute("SELECT pg_advisory_xact_lock(%s)",(lock,))
        future=pool.submit(reset_lead_workflow_fixture,isolated_migrated)
        try:
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                owner.execute("SELECT pg_stat_clear_snapshot()")
                current=owner.execute("SELECT id FROM lead_observations WHERE project_id=%s ORDER BY id",(PROJECT,)).fetchall()
                waiting=owner.execute("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() "
                    "AND pid<>pg_backend_pid() AND wait_event='advisory')").fetchone()[0]
                if waiting or current!=before:break
                time.sleep(.02)
            assert current==before,"reset deleted source rows before the in-flight write finished"
            assert waiting,"reset must share the actual workspace transaction lock"
        finally:
            owner.commit()
            future.result(timeout=20)
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute("SELECT count(*) FROM lead_reviews WHERE project_id=%s",(PROJECT,)).fetchone()==(6,)


def test_lead_fixture_refuses_remote_or_non_test_database():
    from tools.seed_lead_workflow_fixture import seed_lead_workflow_fixture
    for dsn in ("postgresql://example.invalid/production", "postgresql://127.0.0.1/customer_database"):
        with pytest.raises(pytest.UsageError, match="disposable"):
            seed_lead_workflow_fixture(dsn)


def test_second_purchaser_fixture_preserves_original_identity_and_evidence(isolated_migrated,monkeypatch):
    from tools.serve_e2e_fixture import seed
    from tools.seed_lead_workflow_fixture import seed_lead_workflow_fixture,apply_lead_fixture_scenario,PROJECT,BUYERS
    monkeypatch.setenv("BUYEROS_E2E_SEED_BUYERS","1")
    seed(isolated_migrated);seed_lead_workflow_fixture(isolated_migrated)
    with psycopg.connect(isolated_migrated) as db:
        original=db.execute("SELECT id,person_id,contact_id FROM lead_observations WHERE buyer_id=%s ORDER BY id",(BUYERS[0],)).fetchall()
    result=apply_lead_fixture_scenario(isolated_migrated,"second_purchaser")
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute("SELECT id,person_id,contact_id FROM lead_observations WHERE id=ANY(%s) ORDER BY id",
            ([row[0] for row in original],)).fetchall()==original
        person,contact=db.execute("SELECT person_id,contact_id FROM lead_reviews WHERE id=%s AND project_id=%s",
            (result["review_id"],PROJECT)).fetchone()
        assert str(person)==result["person_id"] and contact is not None
        assert person not in {row[1] for row in original}
        assert db.execute("SELECT count(*) FROM lead_reviews WHERE project_id=%s",(PROJECT,)).fetchone()==(7,)
        assert db.execute("SELECT count(*) FROM provider_operations").fetchone()==(0,)


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


def test_owned_reset_reestablishes_authority_for_current_membership_without_rewriting_history(isolated_migrated, monkeypatch):
    from tools.serve_e2e_fixture import seed
    from tools.seed_lead_workflow_fixture import seed_lead_workflow_fixture, reset_lead_workflow_fixture, ADMIN, WORKSPACE, PROJECT
    monkeypatch.setenv("BUYEROS_E2E_SEED_BUYERS", "1")
    seed(isolated_migrated)
    seed_lead_workflow_fixture(isolated_migrated)
    with psycopg.connect(isolated_migrated) as db:
        history = db.execute("SELECT id,terms_hash FROM policy_activation_resolutions ORDER BY id").fetchall()
        db.execute("UPDATE memberships SET active=false,roles=ARRAY['viewer'],version=version+1 "
                   "WHERE workspace_id=%s AND user_id=%s", (WORKSPACE, ADMIN))
    reset_lead_workflow_fixture(isolated_migrated)
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute("SELECT membership_version,version FROM policy_controller_authorities "
                          "WHERE workspace_id=%s AND project_id=%s ORDER BY version DESC LIMIT 1",
                          (WORKSPACE, PROJECT)).fetchone() == (2, 2)
        assert db.execute("SELECT count(*) FROM lead_reviews WHERE project_id=%s", (PROJECT,)).fetchone() == (6,)
        assert db.execute("SELECT id,terms_hash FROM policy_activation_resolutions WHERE id=ANY(%s) ORDER BY id",
                          ([row[0] for row in history],)).fetchall() == history
        assert db.execute("SELECT count(*) FROM provider_operations").fetchone() == (0,)
