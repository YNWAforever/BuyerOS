"""Real runtime-role requests prove staged imports, tenant isolation and atomicity."""
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest

from tests.contract_validation import assert_contract_response
from tests.conftest import runtime_role_dsn
from tests.test_buyer_review_db import (
    PROJECT_A, PROJECT_B, WORKSPACE_A, WORKSPACE_B, OPERATOR, REVIEWER, VIEWER,
    _h, _seed_buyer, api,
)

BASE = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-imports"
CSV = b"Company,Website,Checked on,Public contact route,Observed public signal\nExample Buyer,https://example.com,2026-09-18,sales@example.com,Unverified catalogue claim\nSecond Buyer,https://second.example,2026-09-18,,Source claim\n"


def preview(api, content=CSV, *, key="preview-import-001", base=BASE, subject=OPERATOR):
    return api.post(base + "/preview", files={"file": ("buyers.csv", content, "text/csv")}, headers=_h(subject=subject, key=key))


def confirm(api, data, *, key="confirm-import-001", digest=None, base=BASE, subject=OPERATOR):
    return api.post(base + f"/{data['id']}/confirm", json={"preview_digest": digest or data["preview_digest"], "confirmation": True}, headers=_h(subject=subject, key=key))


def buyer_count(dsn):
    with psycopg.connect(dsn) as db:
        return db.execute("SELECT count(*) FROM project_buyers WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0]


def test_preview_then_confirm_preserves_provenance_without_creating_contact_or_review(api, seeded):
    before = buyer_count(seeded)
    response = preview(api)
    assert response.status_code == 201, response.text
    assert_contract_response("BuyerImportResponse", response.json())
    data = response.json()["data"]
    assert (data["total_rows"], data["ready_rows"], data["duplicate_rows"], data["invalid_rows"], data["can_import"]) == (2, 2, 0, 0, True)
    assert buyer_count(seeded) == before
    completed = confirm(api, data)
    assert completed.status_code == 200, completed.text
    assert_contract_response("BuyerImportResponse", completed.json())
    result = completed.json()["data"]
    assert result["status"] == "completed"
    assert result["imported_rows"] == 2
    assert len(set(result["buyer_ids"])) == 2
    assert buyer_count(seeded) == before + 2
    buyer_id = result["buyer_ids"][0]
    buyer = api.get(f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}", headers=_h()).json()["data"]
    assert buyer["contacts"] == []
    assert buyer["contact_research_status"] == "not_researched"
    assert "fit" not in buyer and "review" not in buyer
    provenance = api.get(f"/v1/workspaces/{WORKSPACE_A}/buyers/{buyer_id}/import-source", headers=_h(subject=VIEWER))
    assert provenance.status_code == 200, provenance.text
    assert_contract_response("BuyerImportSourceResponse", provenance.json())
    source = provenance.json()["data"]
    assert source["source_date"] == "2026-09-18"
    assert source["source_row"] == "CSV!A2:E2"
    assert source["original_fields"]["Public contact route"] == "sales@example.com"
    assert source["candidate_status"] == "unreviewed"
    with psycopg.connect(seeded) as db:
        for table in ("fit_assessments", "human_reviews", "provider_operations", "outbox_events"):
            assert db.execute(f"SELECT count(*) FROM {table} WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == 0


def test_duplicate_domain_entity_and_file_rows_skip_without_mutating_existing_buyer(api, seeded):
    existing = _seed_buyer(seeded, name="Already Known", domain="example.com", fit="match", review="accepted")
    content = b"Company,Website\nExample Buyer,https://www.example.com/path\nFresh Company,https://fresh.example\nFresh Company,\nALREADY KNOWN,https://other.example\n"
    data = preview(api, content).json()["data"]
    assert (data["ready_rows"], data["duplicate_rows"], data["invalid_rows"]) == (1, 3, 0)
    assert data["rows"][0]["duplicate_buyer_id"] == existing
    result = confirm(api, data)
    assert result.status_code == 200, result.text
    assert result.json()["data"]["imported_rows"] == 1
    assert result.json()["data"]["skipped_duplicate_rows"] == 3
    with psycopg.connect(seeded) as db:
        assert db.execute("SELECT version FROM project_buyers WHERE id=%s", (existing,)).fetchone()[0] == 1
        assert db.execute("SELECT state FROM human_reviews WHERE project_buyer_id=%s", (existing,)).fetchone()[0] == "accepted"


def test_exact_retry_and_read_reconciliation_return_original_committed_result(api, seeded):
    first = preview(api)
    assert first.status_code == 201, first.text
    data = first.json()["data"]
    assert preview(api).json()["data"] == data
    result = confirm(api, data)
    assert result.status_code == 200, result.text
    for replay in (confirm(api, data), confirm(api, data, key="confirm-retry-key"), api.get(BASE + f"/{data['id']}", headers=_h())):
        assert replay.status_code == 200, replay.text
        assert replay.json()["data"] == result.json()["data"]
    assert buyer_count(seeded) == 2
    assert confirm(api, data, digest="sha256:" + "0" * 64).status_code == 409
    assert preview(api, CSV.replace(b"Example Buyer", b"Changed Buyer")).status_code == 409


def test_invalid_row_blocks_entire_import_and_manifest_tamper_is_rejected(api, seeded):
    data = preview(api, CSV + b",javascript:alert(1),2026-09-18,,Unsafe\n").json()["data"]
    assert data["invalid_rows"] == 1 and data["can_import"] is False
    assert confirm(api, data).status_code == 422
    assert buyer_count(seeded) == 0
    valid = preview(api, key="second-preview-001").json()["data"]
    with psycopg.connect(seeded) as db:
        db.execute("UPDATE buyer_imports SET manifest=jsonb_set(manifest,'{rows,0,name}','\"Tampered Buyer\"'::jsonb) WHERE id=%s", (valid["id"],))
    assert confirm(api, valid, key="second-confirm-001").status_code == 409
    assert buyer_count(seeded) == 0


def test_changed_duplicates_expired_preview_and_wrong_digest_fail_before_mutation(api, seeded):
    data = preview(api).json()["data"]
    assert confirm(api, data, digest="sha256:" + "0" * 64).status_code == 409
    _seed_buyer(seeded, name="Concurrent Buyer", domain="example.com")
    assert confirm(api, data).status_code == 409
    assert buyer_count(seeded) == 1
    fresh = preview(api, key="fresh-preview-001").json()["data"]
    with psycopg.connect(seeded) as db:
        db.execute("UPDATE buyer_imports SET expires_at=now()-interval '1 second' WHERE id=%s", (fresh["id"],))
    assert confirm(api, fresh, key="expired-confirm-001").status_code == 409
    assert buyer_count(seeded) == 1


def test_viewers_other_actors_projects_and_workspaces_cannot_confirm_a_manifest(api, seeded):
    assert preview(api, subject=VIEWER).status_code == 403
    assert preview(api, subject=REVIEWER).status_code == 403
    data = preview(api).json()["data"]
    assert confirm(api, data, subject=VIEWER).status_code == 403
    wrong_project = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_B}/buyer-imports"
    wrong_workspace = f"/v1/workspaces/{WORKSPACE_B}/projects/{PROJECT_B}/buyer-imports"
    assert confirm(api, data, base=wrong_project).status_code == 404
    assert confirm(api, data, base=wrong_workspace).status_code == 404
    assert api.get(wrong_workspace + f"/{data['id']}", headers=_h()).status_code == 404
    from tests.test_buyer_review_db import ADMIN
    assert confirm(api, data, subject=ADMIN).status_code == 404
    assert buyer_count(seeded) == 0


def test_database_failure_rolls_back_all_buyers_provenance_and_idempotency(api, seeded):
    data = preview(api).json()["data"]
    with psycopg.connect(seeded) as db:
        db.execute("CREATE FUNCTION test_reject_import_buyer() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.display_name='Second Buyer' THEN RAISE EXCEPTION 'owned import failure'; END IF; RETURN NEW; END $$")
        db.execute("CREATE TRIGGER test_reject_import_buyer BEFORE INSERT ON companies FOR EACH ROW EXECUTE FUNCTION test_reject_import_buyer()")
    try:
        failed = confirm(api, data)
        assert failed.status_code == 500, failed.text
        with psycopg.connect(seeded) as db:
            assert db.execute("SELECT count(*) FROM project_buyers WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == 0
            assert db.execute("SELECT count(*) FROM companies WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == 0
            assert db.execute("SELECT count(*) FROM buyer_import_rows WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == 0
            assert db.execute("SELECT status FROM buyer_imports WHERE id=%s", (data["id"],)).fetchone()[0] == "previewed"
            assert db.execute("SELECT count(*) FROM idempotency_records WHERE key='confirm-import-001'").fetchone()[0] == 0
    finally:
        with psycopg.connect(seeded) as db:
            db.execute("DROP TRIGGER test_reject_import_buyer ON companies")
            db.execute("DROP FUNCTION test_reject_import_buyer()")
    retried = confirm(api, data)
    assert retried.status_code == 200, retried.text
    assert buyer_count(seeded) == 2


def test_runtime_rls_blocks_unscoped_and_cross_workspace_import_access(api, seeded):
    data = preview(api).json()["data"]
    result = confirm(api, data).json()["data"]
    with psycopg.connect(runtime_role_dsn(seeded)) as db:
        assert db.execute("SELECT count(*) FROM buyer_imports").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM buyer_import_rows").fetchone()[0] == 0
        db.execute("SELECT set_config('app.workspace_id',%s,true)", (WORKSPACE_B,))
        assert db.execute("SELECT count(*) FROM buyer_imports").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM buyer_import_rows").fetchone()[0] == 0
    response = api.get(f"/v1/workspaces/{WORKSPACE_B}/buyers/{result['buyer_ids'][0]}/import-source", headers=_h())
    assert response.status_code == 404


def test_concurrent_confirmation_imports_once(api, seeded):
    data = preview(api).json()["data"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda key: confirm(api, data, key=key), ("parallel-confirm-1", "parallel-confirm-2")))
    assert [response.status_code for response in responses] == [200, 200], [response.text for response in responses]
    assert responses[0].json()["data"] == responses[1].json()["data"]
    assert buyer_count(seeded) == 2


def test_company_in_another_project_requires_manual_identity_mapping(api, seeded):
    project_id, company_id = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(seeded) as db:
        db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) VALUES (%s,%s,'Other project','Other','Offer','{US}','{en}',1)", (project_id, WORKSPACE_A))
        db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name,domain) VALUES (%s,%s,'Existing verified entity','Existing verified entity','example.com')", (company_id, WORKSPACE_A))
        db.execute("INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES (%s,%s,%s,%s)", (uuid.uuid4(), WORKSPACE_A, project_id, company_id))
    data = preview(api).json()["data"]
    assert data["invalid_rows"] == 1
    assert data["rows"][0]["status"] == "invalid"
    assert "manual" in " ".join(data["rows"][0]["errors"]).lower()
    assert confirm(api, data).status_code == 422
    with psycopg.connect(seeded) as db:
        assert db.execute("SELECT count(*) FROM project_buyers WHERE project_id=%s", (PROJECT_A,)).fetchone()[0] == 0


def test_concurrent_archive_is_observed_before_importing(api, seeded):
    import time
    data = preview(api).json()["data"]
    with ThreadPoolExecutor(max_workers=1) as pool, psycopg.connect(seeded) as archive:
        archive.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE", (PROJECT_A,))
        pending = pool.submit(confirm, api, data)
        deadline = time.monotonic() + 10
        waiting = False
        while time.monotonic() < deadline and not pending.done():
            with psycopg.connect(seeded, autocommit=True) as observer:
                waiting = observer.execute("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE usename='buyeros_api' AND wait_event_type='Lock' AND (query LIKE '%%projects%%' OR query LIKE '%%project_buyers%%'))").fetchone()[0]
            if waiting:
                break
            time.sleep(0.02)
        assert waiting, "import must reach the held project lock"
        archive.execute("UPDATE projects SET status='archived',version=version+1 WHERE id=%s", (PROJECT_A,))
        archive.commit()
        response = pending.result(timeout=10)
    assert response.status_code == 409, response.text
    assert buyer_count(seeded) == 0


def test_confirmation_requires_literal_boolean_true_and_unknown_fields_are_rejected(api, seeded):
    data = preview(api).json()["data"]
    for value in (False, 1, "true", None):
        response = api.post(BASE + f"/{data['id']}/confirm", json={"preview_digest": data["preview_digest"], "confirmation": value}, headers=_h(key="strict-confirm-001"))
        assert response.status_code == 422, (value, response.text)
    response = api.post(BASE + f"/{data['id']}/confirm", json={"preview_digest": data["preview_digest"], "confirmation": True, "contacts": []}, headers=_h(key="strict-confirm-001"))
    assert response.status_code == 422
    assert buyer_count(seeded) == 0


def test_unicode_and_whitespace_entity_identity_is_stable_between_imports(api, seeded):
    _seed_buyer(seeded, name="Ｆｏｏ　Ｂｕｙｅｒ")
    data = preview(api, b"Company\nFoo Buyer\n").json()["data"]
    assert data["duplicate_rows"] == 1
    assert data["ready_rows"] == 0


@pytest.mark.parametrize("second_domain,in_other_project", [("other.example", False), ("shared.example", False), ("other.example", True)])
def test_conflicting_domain_and_entity_hints_require_manual_mapping(api, seeded, second_domain, in_other_project):
    _seed_buyer(seeded, name="Buyer A", domain="shared.example")
    second = _seed_buyer(seeded, name="Buyer B", domain=second_domain)
    if in_other_project:
        project_id = uuid.uuid4()
        with psycopg.connect(seeded) as db:
            db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) VALUES (%s,%s,'Other project','Other','Offer','{US}','{en}',1)", (project_id, WORKSPACE_A))
            db.execute("UPDATE project_buyers SET project_id=%s WHERE id=%s", (project_id, second))
    data = preview(api, b"Company,Website\nBuyer B,https://shared.example\n").json()["data"]
    assert (data["invalid_rows"], data["duplicate_rows"]) == (1, 0)
    assert data["rows"][0]["duplicate_buyer_id"] is None
    assert "manual" in " ".join(data["rows"][0]["errors"]).lower()
    assert confirm(api, data).status_code == 422


def test_conflicting_hints_within_one_file_are_not_silently_merged(api, seeded):
    content = b"Company,Website\nBuyer A,https://first.example\nBuyer B,https://second.example\nBuyer A,https://second.example\n"
    data = preview(api, content).json()["data"]
    assert (data["ready_rows"], data["invalid_rows"]) == (2, 1)
    assert confirm(api, data).status_code == 422
    assert buyer_count(seeded) == 0


def test_nonimported_buyer_source_is_null_and_runtime_cannot_edit_source_manifest(api, seeded):
    existing = _seed_buyer(seeded, name="Existing unrelated buyer")
    response = api.get(f"/v1/workspaces/{WORKSPACE_A}/buyers/{existing}/import-source", headers=_h(subject=VIEWER))
    assert response.status_code == 200
    assert response.json()["data"] is None
    assert_contract_response("BuyerImportSourceResponse", response.json())
    data = preview(api).json()["data"]
    for field, value in (("manifest", "'{}'::jsonb"), ("preview_digest", "'sha256:' || repeat('0',64)"), ("expires_at", "now()+interval '10 hours'")):
        with psycopg.connect(runtime_role_dsn(seeded)) as db:
            db.execute("SELECT set_config('app.workspace_id',%s,true)", (WORKSPACE_A,))
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                db.execute(f"UPDATE buyer_imports SET {field}={value} WHERE id=%s", (data["id"],))


def test_populated_import_migration_rollback_preserves_provenance(isolated_api, isolated_seeded):
    from alembic import command
    from alembic.config import Config
    from tests.conftest import ALEMBIC_INI, SERVICE_ROOT
    data = preview(isolated_api).json()["data"]
    result = confirm(isolated_api, data).json()["data"]
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    with pytest.raises(RuntimeError, match="retained import provenance"):
        command.downgrade(config, "0050_c61_delivery_authorizations")
    with psycopg.connect(isolated_seeded) as db:
        stored = db.execute("SELECT result FROM buyer_imports WHERE id=%s", (data["id"],)).fetchone()[0]
        assert stored == result
        assert db.execute("SELECT count(*) FROM buyer_import_rows WHERE import_id=%s", (data["id"],)).fetchone()[0] == 2
        assert db.execute("SELECT buyeros_search_receipts_writable(),buyeros_model_receipts_writable(),buyeros_contact_receipts_writable()").fetchone() == (True, True, True)


def test_nobypass_migration_owner_cannot_drop_import_provenance_hidden_by_rls(isolated_api, isolated_seeded, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from psycopg import sql
    from tests.conftest import ALEMBIC_INI, SERVICE_ROOT
    from buyeros_api.settings import get_settings
    data = preview(isolated_api).json()["data"]
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    command.downgrade(config, "0051_buyer_imports")
    role = "buyeros_import_migration_" + uuid.uuid4().hex
    with psycopg.connect(isolated_seeded, autocommit=True) as db:
        db.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD 'test-only'").format(sql.Identifier(role)))
        db.execute(sql.SQL("GRANT USAGE,CREATE ON SCHEMA public TO {}").format(sql.Identifier(role)))
        for table in ("buyer_imports", "buyer_import_rows", "alembic_version"):
            db.execute(sql.SQL("ALTER TABLE {} OWNER TO {}").format(sql.Identifier(table), sql.Identifier(role)))
        for service in ("search", "model", "contact"):
            db.execute(sql.SQL("ALTER FUNCTION {}() OWNER TO {}").format(sql.Identifier("buyeros_" + service + "_receipts_writable"), sql.Identifier(role)))
    owner_dsn = isolated_seeded.replace("buyeros:buyeros@", role + ":test-only@", 1)
    monkeypatch.setenv("BUYEROS_DATABASE_MIGRATION_URL", owner_dsn)
    get_settings.cache_clear()
    try:
        with psycopg.connect(owner_dsn) as owner:
            assert owner.execute("SELECT count(*) FROM buyer_imports").fetchone()[0] == 0
        with pytest.raises(RuntimeError, match="retained import provenance"):
            command.downgrade(config, "0050_c61_delivery_authorizations")
        with psycopg.connect(isolated_seeded) as db:
            assert db.execute("SELECT count(*) FROM buyer_imports WHERE id=%s", (data["id"],)).fetchone()[0] == 1
            assert db.execute("SELECT relforcerowsecurity FROM pg_class WHERE oid='buyer_imports'::regclass").fetchone()[0] is True
    finally:
        monkeypatch.setenv("BUYEROS_DATABASE_MIGRATION_URL", isolated_seeded)
        get_settings.cache_clear()
        with psycopg.connect(isolated_seeded, autocommit=True) as db:
            db.execute(sql.SQL("REASSIGN OWNED BY {} TO buyeros").format(sql.Identifier(role)))
            db.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(role)))
            db.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
        command.upgrade(config, "head")
