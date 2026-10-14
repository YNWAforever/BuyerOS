import psycopg


def test_buyer_source_check_migration_enforces_tenant_and_append_only_contract(isolated_migrated):
    with psycopg.connect(isolated_migrated) as conn:
        assert conn.execute("SELECT to_regclass('buyer_source_checks')").fetchone()[0] == "buyer_source_checks"

        relation = conn.execute(
            "SELECT relrowsecurity, relforcerowsecurity "
            "FROM pg_class WHERE oid='buyer_source_checks'::regclass"
        ).fetchone()
        assert relation == (True, True)

        foreign_keys = [
            row[0]
            for row in conn.execute(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid='buyer_source_checks'::regclass AND contype='f'"
            ).fetchall()
        ]
        assert any(
            "workspace_id, project_id, buyer_id" in definition and "project_buyers" in definition
            for definition in foreign_keys
        )
        assert any(
            "workspace_id, project_id" in definition and "projects" in definition
            for definition in foreign_keys
        )

        checks = [
            row[0]
            for row in conn.execute(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid='buyer_source_checks'::regclass AND contype='c'"
            ).fetchall()
        ]
        grade_check = next(definition for definition in checks if "'A'" in definition and "'B'" in definition and "'C'" in definition)
        assert all(grade in grade_check for grade in ("'A'", "'B'", "'C'"))
        assert any("jsonb_typeof" in definition and "sources" in definition for definition in checks)

        assert conn.execute(
            "SELECT has_table_privilege('buyeros_api', 'buyer_source_checks', 'SELECT'), "
            "has_table_privilege('buyeros_api', 'buyer_source_checks', 'INSERT'), "
            "has_table_privilege('buyeros_api', 'buyer_source_checks', 'UPDATE'), "
            "has_table_privilege('buyeros_api', 'buyer_source_checks', 'DELETE')"
        ).fetchone() == (True, True, False, False)


def test_buyer_source_check_model_has_independent_persisted_fields():
    from buyeros_api.db import buyers

    model = getattr(buyers, "BuyerSourceCheck", None)
    assert model is not None
    assert model.__tablename__ == "buyer_source_checks"
    assert {
        "workspace_id", "project_id", "buyer_id", "checked_on", "grade",
        "rationale", "limitations", "sources", "recorded_by_user_id", "created_at",
    } <= set(model.__table__.columns.keys())


def test_buyer_source_check_migration_advances_schema_receipt_fences(isolated_migrated):
    with psycopg.connect(isolated_migrated) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0054_buyer_source_checks"
        assert conn.execute(
            "SELECT public.buyeros_search_receipts_writable(), "
            "public.buyeros_model_receipts_writable(), "
            "public.buyeros_contact_receipts_writable()"
        ).fetchone() == (True, True, True)
