"""T02: immutable ICP numbering and replay under real PostgreSQL/RLS."""

from concurrent.futures import ThreadPoolExecutor

import psycopg
from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app
from tests.contract_validation import assert_contract_response
from tests.icp_fixtures import valid_icp_payload
from tests.test_api_projects_db import WORKSPACE_A, _create, _h, api


def _post(client, project_id, body, *, key):
    return client.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}/icp-versions",
        json=body,
        headers=_h(key=key),
    )


def test_retried_save_one_version(api, seeded):
    project_id = _create(api, "create-icp-replay")
    body = valid_icp_payload()
    first = _post(api, project_id, body, key="save-icp-replay")
    assert first.status_code == 201, first.text
    replay = _post(api, project_id, body, key="save-icp-replay")
    assert replay.status_code == 201, replay.text
    assert replay.json()["data"] == first.json()["data"]
    assert first.json()["data"]["number"] == 1
    assert_contract_response("ICPVersionResponse", first.json())
    with psycopg.connect(seeded) as owner:
        count = owner.execute(
            "SELECT count(*) FROM icp_versions WHERE workspace_id = %s AND project_id = %s",
            (WORKSPACE_A, project_id),
        ).fetchone()[0]
    assert count == 1


def test_parallel_distinct_saves_allocate_unique_numbers(api):
    project_id = _create(api, "create-icp-parallel")

    def save(i):
        body = valid_icp_payload()
        body["requirements"][0]["text"] = f"Requirement {i}"
        with TestClient(create_app(), raise_server_exceptions=False) as client:
            return _post(client, project_id, body, key=f"save-parallel-{i}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, range(2)))
    assert {r.status_code for r in results} == {201}, [r.status_code for r in results]
    assert {r.json()["data"]["number"] for r in results} == {1, 2}


def test_non_current_basis_cannot_save(api):
    project_id = _create(api, "create-icp-basis")
    body = valid_icp_payload()
    body["basis_offer_revision"] = 2
    response = _post(api, project_id, body, key="save-wrong-basis")
    assert response.status_code == 412, response.text
    assert response.json()["code"] == "STALE_REVISION"


def test_unknown_parent_is_rejected(api):
    project_id = _create(api, "create-icp-parent")
    body = valid_icp_payload()
    body["parent_icp_version_id"] = "f0000000-0000-4000-8000-000000000001"
    response = _post(api, project_id, body, key="save-unknown-parent")
    assert response.status_code == 404, response.text


def test_caller_fact_approval_flag_is_cleared(api):
    project_id = _create(api, "create-icp-fact-flag")
    body = valid_icp_payload()
    body["offer_facts"][0]["approved"] = True
    response = _post(api, project_id, body, key="save-fact-flag")
    assert response.status_code == 201, response.text
    assert response.json()["data"]["offer_facts"][0]["approved"] is False
    assert response.json()["data"]["status"] == "saved"


def test_exact_reviewer_approval_authorizes_saved_offer_fact_without_rewriting_content(api, seeded):
    from tests.test_api_projects_db import REVIEWER

    project_id = _create(api, "create-icp-approved-fact")
    body = valid_icp_payload()
    body["offer_facts"][0]["approved"] = True  # Caller flag is untrusted before review.
    saved = _post(api, project_id, body, key="save-approved-fact-transition")
    assert saved.status_code == 201, saved.text
    version = saved.json()["data"]
    assert version["offer_facts"][0]["approved"] is False
    approved = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/icp-versions/{version['id']}/approve",
        json={"content_hash": version["content_hash"], "confirmation": True,
              "expected_project_version": 1},
        headers=_h(subject=REVIEWER, key="approve-fact-transition", **{"If-Match": '"1"'}),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["offer_facts"][0]["approved"] is True
    with psycopg.connect(seeded) as owner:
        content, content_hash = owner.execute(
            "SELECT content,content_hash FROM icp_versions WHERE id=%s", (version["id"],)
        ).fetchone()
    assert content["offer_facts"][0]["approved"] is False
    assert content_hash == version["content_hash"]


def test_approval_requires_current_project_version_and_known_basis(api, seeded):
    from tests.test_api_projects_db import REVIEWER

    project_id = _create(api, "create-icp-approval-context")
    saved = _post(api, project_id, valid_icp_payload(), key="save-approval-context")
    assert saved.status_code == 201, saved.text
    version = saved.json()["data"]
    path = f"/v1/workspaces/{WORKSPACE_A}/icp-versions/{version['id']}/approve"
    headers = _h(subject=REVIEWER, key="approve-wrong-project-version", **{"If-Match": '"1"'})
    stale = api.post(
        path,
        json={"content_hash": version["content_hash"], "confirmation": True,
              "expected_project_version": 2},
        headers=headers,
    )
    assert stale.status_code == 412, stale.text
    assert stale.json()["code"] == "STALE_REVISION"
    with psycopg.connect(seeded, autocommit=True) as owner:
        owner.execute("UPDATE icp_versions SET basis_offer_revision = NULL WHERE id = %s", (version["id"],))
    legacy = api.post(
        path,
        json={"content_hash": version["content_hash"], "confirmation": True,
              "expected_project_version": 1},
        headers=_h(subject=REVIEWER, key="approve-unknown-basis", **{"If-Match": '"1"'}),
    )
    assert legacy.status_code == 412, legacy.text
    assert legacy.json()["code"] == "STALE_REVISION"
    with psycopg.connect(seeded) as owner:
        approved = owner.execute(
            "SELECT approved_at FROM icp_versions WHERE id = %s", (version["id"],)
        ).fetchone()[0]
    assert approved is None


def test_0012_downgrade_upgrade_preserves_legacy_as_unapprovable(api, seeded, monkeypatch):
    """Only the disposable test database is migrated; historical ICP basis stays NULL."""
    from alembic import command
    from alembic.config import Config
    from tests.conftest import ALEMBIC_INI, SERVICE_ROOT
    from buyeros_api.settings import get_settings

    monkeypatch.setenv("BUYEROS_DATABASE_MIGRATION_URL", seeded)
    get_settings.cache_clear()
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    legacy_id = "e2000000-0000-4000-8000-000000000001"
    try:
        command.downgrade(config, "0011_project_buyer_version")
        with psycopg.connect(seeded, autocommit=True) as owner:
            columns = {
                row[0] for row in owner.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'icp_versions'"
                ).fetchall()
            }
            assert "basis_offer_revision" not in columns
            owner.execute(
                "INSERT INTO icp_versions(id, workspace_id, project_id, number, content, content_hash) "
                "VALUES (%s, %s, %s, 1, '{}'::jsonb, %s)",
                (legacy_id, WORKSPACE_A, "a0000000-0000-4000-8000-000000000001", "sha256:" + "0" * 64),
            )
        command.upgrade(config, "head")
        with psycopg.connect(seeded) as owner:
            basis, offer_revision = owner.execute(
                "SELECT i.basis_offer_revision, p.offer_revision FROM icp_versions i "
                "JOIN projects p ON p.id = i.project_id WHERE i.id = %s", (legacy_id,)
            ).fetchone()
        assert basis is None
        assert offer_revision == 1
        from tests.test_api_projects_db import REVIEWER
        response = api.post(
            f"/v1/workspaces/{WORKSPACE_A}/icp-versions/{legacy_id}/approve",
            json={"content_hash": "sha256:" + "0" * 64, "confirmation": True,
                  "expected_project_version": 1},
            headers=_h(subject=REVIEWER, key="approve-migrated-legacy", **{"If-Match": '"1"'}),
        )
        assert response.status_code == 412, response.text
        assert response.json()["code"] == "STALE_REVISION"
    finally:
        command.upgrade(config, "head")
        get_settings.cache_clear()
