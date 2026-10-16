import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient

from buyeros_api.api import auth
from buyeros_api.api.app import create_app
from buyeros_api.api.jwks import JwksKeyCache
from buyeros_api.api.verifier import TokenVerifier
from tests import auth_fixtures as fx
from tests.conftest import runtime_role_dsn

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
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0055_lead_workflow"
        assert conn.execute(
            "SELECT public.buyeros_search_receipts_writable(), "
            "public.buyeros_model_receipts_writable(), "
            "public.buyeros_contact_receipts_writable()"
        ).fetchone() == (True, True, True)

_SOURCE_WORKSPACE_A = "11111111-1111-4111-8111-111111111111"
_SOURCE_WORKSPACE_B = "22222222-2222-4222-8222-222222222222"
_SOURCE_PROJECT_A = "a0000000-0000-4000-8000-000000000001"
_SOURCE_OPERATOR = "auth0|source-check-operator"
_SOURCE_ADMIN = "auth0|source-check-admin"
_SOURCE_VIEWER = "auth0|source-check-viewer"


@pytest.fixture
def source_check_api(seeded, monkeypatch):
    monkeypatch.setenv("BUYEROS_DATABASE_URL", runtime_role_dsn(seeded))
    monkeypatch.setenv("BUYEROS_AUTH0_ISSUER", fx.ISSUER)
    monkeypatch.setenv("BUYEROS_AUTH0_AUDIENCE", fx.AUDIENCE)
    from buyeros_api.settings import get_settings

    get_settings.cache_clear()
    cache = JwksKeyCache(lambda: asyncio.sleep(0, result=fx.jwks_document()), cache_seconds=300)
    monkeypatch.setattr(
        auth, "_verifier_from_settings",
        lambda: TokenVerifier(cache, issuer=fx.ISSUER, audience=fx.AUDIENCE),
    )

    with psycopg.connect(seeded, autocommit=True) as owner:
        for subject, roles in (
            (_SOURCE_OPERATOR, ["operator"]),
            (_SOURCE_ADMIN, ["workspace_admin"]),
            (_SOURCE_VIEWER, ["viewer"]),
        ):
            user_id = uuid.uuid5(uuid.NAMESPACE_URL, subject)
            owner.execute("DELETE FROM memberships WHERE user_id=%s", (user_id,))
            owner.execute("DELETE FROM users WHERE id=%s", (user_id,))
            owner.execute(
                "INSERT INTO users(id, issuer, subject) VALUES (%s, %s, %s)",
                (user_id, fx.ISSUER, subject),
            )
            owner.execute(
                "INSERT INTO memberships(id, workspace_id, user_id, roles, active) "
                "VALUES (%s, %s, %s, %s, true)",
                (uuid.uuid4(), _SOURCE_WORKSPACE_A, user_id, roles),
            )

    try:
        yield TestClient(create_app(), raise_server_exceptions=False)
    finally:
        get_settings.cache_clear()
        with psycopg.connect(seeded, autocommit=True) as owner:
            cleanup = (
                "DELETE FROM buyer_source_checks WHERE workspace_id=%s",
                "DELETE FROM idempotency_records WHERE workspace_id=%s",
                "DELETE FROM human_reviews WHERE workspace_id=%s",
                "DELETE FROM evidence WHERE workspace_id=%s",
                "DELETE FROM source_documents WHERE workspace_id=%s",
                "DELETE FROM fit_assessments WHERE workspace_id=%s",
                "UPDATE projects SET active_icp_version_id=NULL WHERE workspace_id=%s",
                "DELETE FROM icp_versions WHERE workspace_id=%s",
                "DELETE FROM project_buyers WHERE workspace_id=%s",
                "DELETE FROM companies WHERE workspace_id=%s",
                "DELETE FROM audit_events WHERE workspace_id=%s",
            )
            for statement in cleanup:
                owner.execute(statement, (_SOURCE_WORKSPACE_A,))
            for subject in (_SOURCE_OPERATOR, _SOURCE_ADMIN, _SOURCE_VIEWER):
                user_id = uuid.uuid5(uuid.NAMESPACE_URL, subject)
                owner.execute("DELETE FROM memberships WHERE user_id=%s", (user_id,))
                owner.execute("DELETE FROM users WHERE id=%s", (user_id,))


def _seed_source_check_buyer(seeded, *, name="Source Check Buyer", with_fit=False):
    company_id = str(uuid.uuid4())
    buyer_id = str(uuid.uuid4())
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO companies(id, workspace_id, legal_name, display_name) VALUES (%s, %s, %s, %s)",
            (company_id, _SOURCE_WORKSPACE_A, name, name),
        )
        conn.execute(
            "INSERT INTO project_buyers(id, workspace_id, project_id, company_id) VALUES (%s, %s, %s, %s)",
            (buyer_id, _SOURCE_WORKSPACE_A, _SOURCE_PROJECT_A, company_id),
        )
        if with_fit:
            icp_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO icp_versions(id, workspace_id, project_id, number, content, content_hash, "
                "basis_offer_revision) VALUES (%s, %s, %s, 1, '{}'::jsonb, %s, 1)",
                (icp_id, _SOURCE_WORKSPACE_A, _SOURCE_PROJECT_A, "sha256:" + "0" * 64),
            )
            conn.execute(
                "UPDATE projects SET active_icp_version_id=%s WHERE workspace_id=%s AND id=%s",
                (icp_id, _SOURCE_WORKSPACE_A, _SOURCE_PROJECT_A),
            )
            conn.execute(
                "INSERT INTO fit_assessments(id, workspace_id, project_id, project_buyer_id, icp_version_id, "
                "evidence_set_hash, verdict, rationale, evidence_ids) "
                "VALUES (%s, %s, %s, %s, %s, %s, 'match', 'baseline fit', '[]'::jsonb)",
                (
                    str(uuid.uuid4()), _SOURCE_WORKSPACE_A, _SOURCE_PROJECT_A, buyer_id, icp_id,
                    "a" * 64,
                ),
            )
    return buyer_id, company_id


def _source_check_payload(**changes):
    payload = {
        "checked_on": "2026-10-15",
        "grade": "A",
        "rationale": "Official buyer profile matches the target rice category and UK market.",
        "limitations": "Public sources do not confirm current purchasing volume.",
        "sources": [
            {"title": "Official company profile", "url": "https://example.com/about"},
        ],
    }
    payload.update(changes)
    return payload


def _source_check_headers(*, subject=_SOURCE_OPERATOR, key="source-check-key-001"):
    return {"Authorization": f"Bearer {fx.make_token(sub=subject)}", "Idempotency-Key": key}


def _source_check_path(buyer_id, *, workspace_id=_SOURCE_WORKSPACE_A):
    return f"/v1/workspaces/{workspace_id}/buyers/{buyer_id}/source-checks"


def _source_check_count(seeded, buyer_id):
    with psycopg.connect(seeded) as conn:
        return conn.execute(
            "SELECT count(*) FROM buyer_source_checks WHERE workspace_id=%s AND buyer_id=%s",
            (_SOURCE_WORKSPACE_A, buyer_id),
        ).fetchone()[0]


def test_source_check_create_and_list_are_scoped(source_check_api, seeded):
    buyer_id, _ = _seed_source_check_buyer(seeded)
    path = _source_check_path(buyer_id)
    first = source_check_api.post(
        path, json=_source_check_payload(), headers=_source_check_headers(key="source-create-001")
    )
    second = source_check_api.post(
        path,
        json=_source_check_payload(grade="B", rationale="The official profile confirms wholesale distribution."),
        headers=_source_check_headers(key="source-create-002"),
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    first_data = first.json()["data"]
    assert first_data["buyer_id"] == buyer_id
    assert first_data["workspace_id"] == _SOURCE_WORKSPACE_A
    assert first_data["recorded_by_user_id"] == str(uuid.uuid5(uuid.NAMESPACE_URL, _SOURCE_OPERATOR))

    page = source_check_api.get(path, params={"offset": 0, "limit": 20}, headers=_source_check_headers())
    assert page.status_code == 200, page.text
    data = page.json()["data"]
    assert data["offset"] == 0 and data["limit"] == 20 and data["total"] == 2
    assert {item["id"] for item in data["items"]} == {first_data["id"], second.json()["data"]["id"]}
    assert data["items"] == sorted(data["items"], key=lambda item: (item["created_at"], item["id"]))

    foreign_get = source_check_api.get(
        _source_check_path(buyer_id, workspace_id=_SOURCE_WORKSPACE_B),
        headers=_source_check_headers(),
    )
    foreign_post = source_check_api.post(
        _source_check_path(buyer_id, workspace_id=_SOURCE_WORKSPACE_B),
        json=_source_check_payload(), headers=_source_check_headers(key="source-foreign-001"),
    )
    assert foreign_get.status_code == 404
    assert foreign_post.status_code == 404
    assert _source_check_count(seeded, buyer_id) == 2


def test_source_check_post_requires_edit_and_idempotency(source_check_api, seeded):
    buyer_id, _ = _seed_source_check_buyer(seeded)
    path = _source_check_path(buyer_id)
    denied = source_check_api.post(
        path,
        json=_source_check_payload(),
        headers=_source_check_headers(subject=_SOURCE_VIEWER, key="source-viewer-001"),
    )
    missing_key = source_check_api.post(
        path,
        json=_source_check_payload(),
        headers={"Authorization": f"Bearer {fx.make_token(sub=_SOURCE_OPERATOR)}"},
    )
    assert denied.status_code == 403 and denied.json()["code"] == "PERMISSION_DENIED"
    assert missing_key.status_code == 400 and missing_key.json()["code"] == "INVALID_REQUEST"
    assert _source_check_count(seeded, buyer_id) == 0


def test_source_check_rejects_invalid_input_before_write(source_check_api, seeded):
    buyer_id, _ = _seed_source_check_buyer(seeded)
    long_url = "https://example.com/" + "x" * 2050
    invalid_payloads = [
        _source_check_payload(grade="D"),
        _source_check_payload(unexpected="not allowed"),
        _source_check_payload(sources=[{"title": "FTP", "url": "ftp://example.com/file"}]),
        _source_check_payload(sources=[{"title": "Hostless", "url": "https:///path"}]),
        _source_check_payload(sources=[{"title": "Credentials", "url": "https://user:secret@example.com/"}]),
        _source_check_payload(sources=[]),
        _source_check_payload(sources=[{"title": f"Source {i}", "url": f"https://example.com/{i}"} for i in range(11)]),
        _source_check_payload(rationale=" " * 4001),
        _source_check_payload(rationale="  "),
        _source_check_payload(limitations="x" * 4001),
        _source_check_payload(sources=[{"title": "T" * 301, "url": "https://example.com/"}]),
        _source_check_payload(sources=[{"title": "Long URL", "url": long_url}]),
    ]
    for index, payload in enumerate(invalid_payloads):
        response = source_check_api.post(
            _source_check_path(buyer_id),
            json=payload,
            headers=_source_check_headers(key=f"source-invalid-{index:03d}"),
        )
        assert response.status_code == 422, response.text
    assert _source_check_count(seeded, buyer_id) == 0


def test_source_check_replay_is_exact_and_conflicts_on_change(source_check_api, seeded):
    buyer_id, _ = _seed_source_check_buyer(seeded)
    path = _source_check_path(buyer_id)
    payload = _source_check_payload()
    headers = _source_check_headers(key="source-replay-001")
    first = source_check_api.post(path, json=payload, headers=headers)
    replay = source_check_api.post(path, json=payload, headers=headers)
    conflict = source_check_api.post(
        path, json=_source_check_payload(rationale="A materially different rationale."), headers=headers
    )
    assert first.status_code == replay.status_code == 201
    assert first.json()["data"] == replay.json()["data"]
    assert conflict.status_code == 409 and conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"
    assert _source_check_count(seeded, buyer_id) == 1


def test_source_checks_never_enter_research_evidence_or_fit(source_check_api, seeded):
    buyer_id, company_id = _seed_source_check_buyer(seeded, with_fit=True)
    with psycopg.connect(seeded, autocommit=True) as conn:
        source_document_id = str(uuid.uuid4())
        evidence_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO source_documents(id, workspace_id, canonical_url, digest, retrieved_at, language) "
            "VALUES (%s, %s, 'https://example.com/official', %s, now(), 'en')",
            (source_document_id, _SOURCE_WORKSPACE_A, "b" * 64),
        )
        conn.execute(
            "INSERT INTO evidence(id, workspace_id, project_id, company_id, source_document_id, stance, excerpt) "
            "VALUES (%s, %s, %s, %s, %s, 'supports', 'Existing research evidence')",
            (evidence_id, _SOURCE_WORKSPACE_A, _SOURCE_PROJECT_A, company_id, source_document_id),
        )
        before_fit = conn.execute(
            "SELECT id, verdict, rationale, evidence_set_hash, evidence_ids FROM fit_assessments "
            "WHERE workspace_id=%s AND project_id=%s AND project_buyer_id=%s",
            (_SOURCE_WORKSPACE_A, _SOURCE_PROJECT_A, buyer_id),
        ).fetchall()

    evidence_path = f"/v1/workspaces/{_SOURCE_WORKSPACE_A}/buyers/{buyer_id}/evidence"
    before_evidence = source_check_api.get(evidence_path, headers=_source_check_headers())
    assert before_evidence.status_code == 200, before_evidence.text
    created = source_check_api.post(
        _source_check_path(buyer_id),
        json=_source_check_payload(),
        headers=_source_check_headers(key="source-separate-001"),
    )
    after_evidence = source_check_api.get(evidence_path, headers=_source_check_headers())
    assert created.status_code == 201, created.text
    assert after_evidence.status_code == 200, after_evidence.text
    assert after_evidence.json()["data"] == before_evidence.json()["data"]
    with psycopg.connect(seeded) as conn:
        after_fit = conn.execute(
            "SELECT id, verdict, rationale, evidence_set_hash, evidence_ids FROM fit_assessments "
            "WHERE workspace_id=%s AND project_id=%s AND project_buyer_id=%s",
            (_SOURCE_WORKSPACE_A, _SOURCE_PROJECT_A, buyer_id),
        ).fetchall()
        counts = conn.execute(
            "SELECT (SELECT count(*) FROM evidence WHERE workspace_id=%s AND project_id=%s AND company_id=%s), "
            "(SELECT count(*) FROM buyer_source_checks WHERE workspace_id=%s AND project_id=%s AND buyer_id=%s)",
            (_SOURCE_WORKSPACE_A, _SOURCE_PROJECT_A, company_id, _SOURCE_WORKSPACE_A, _SOURCE_PROJECT_A, buyer_id),
        ).fetchone()
    assert after_fit == before_fit
    assert counts == (1, 1)
