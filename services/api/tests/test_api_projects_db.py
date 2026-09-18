"""BO-007: the project/profile columns exist and the migration round-trips."""
import asyncio
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from buyeros_api.api import auth
from buyeros_api.api.app import create_app
from buyeros_api.api.jwks import JwksKeyCache
from buyeros_api.api.verifier import TokenVerifier
from tests import auth_fixtures as fx
from tests.conftest import ALEMBIC_INI, SERVICE_ROOT, runtime_role_dsn

PROJECT_COLUMNS = {"company_name", "offer", "website", "markets", "language_preferences", "version", "active_icp_version_id"}
BACKFILLED_COLUMNS = ("company_name", "offer", "markets", "language_preferences", "version")


def test_project_profile_columns_exist(migrated):
    with psycopg.connect(migrated) as conn:
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'projects'"
        ).fetchall()
    present = {r[0] for r in rows}
    assert PROJECT_COLUMNS <= present, PROJECT_COLUMNS - present


def test_icp_versions_has_superseded_at(migrated):
    with psycopg.connect(migrated) as conn:
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'icp_versions'"
        ).fetchall()
    assert "superseded_at" in {r[0] for r in rows}


def test_new_project_columns_are_not_nullable(migrated):
    with psycopg.connect(migrated) as conn:
        rows = conn.execute(
            "SELECT column_name, is_nullable FROM information_schema.columns "
            "WHERE table_name = 'projects' AND column_name = ANY(%s)",
            (sorted(PROJECT_COLUMNS),),
        ).fetchall()
    nullable = {r[0] for r in rows if r[1] == "YES"}
    assert nullable == {"website", "active_icp_version_id"}, nullable


def test_0009_drops_the_backfill_server_defaults(migrated):
    with psycopg.connect(migrated) as conn:
        rows = conn.execute(
            "SELECT column_name, column_default FROM information_schema.columns "
            "WHERE table_name = 'projects' AND column_name = ANY(%s)",
            (list(BACKFILLED_COLUMNS),),
        ).fetchall()
    defaults = dict(rows)
    assert set(defaults) == set(BACKFILLED_COLUMNS), defaults
    assert all(default is None for default in defaults.values()), defaults


def test_0009_downgrade_then_upgrade_backfills_existing_rows(migrated):
    """0009 is reversible, and rows written before it are backfilled on re-upgrade."""
    from alembic import command
    from alembic.config import Config

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))

    with psycopg.connect(migrated) as conn:
        existing_rows = conn.execute(
            "SELECT id, company_name, offer, website, markets, language_preferences, "
            "version, active_icp_version_id FROM projects"
        ).fetchall()

    workspace_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    try:
        command.downgrade(config, "0008_grant_users_select")
        with psycopg.connect(migrated, autocommit=True) as conn:
            conn.execute("INSERT INTO workspaces(id, name) VALUES (%s, 'legacy')", (workspace_id,))
            conn.execute(
                "INSERT INTO projects(id, workspace_id, name) VALUES (%s, %s, 'Legacy project')",
                (project_id, workspace_id),
            )

        command.upgrade(config, "head")

        with psycopg.connect(migrated) as conn:
            row = conn.execute(
                "SELECT company_name, offer, markets, language_preferences, version, "
                "website, active_icp_version_id FROM projects WHERE id = %s",
                (project_id,),
            ).fetchone()
        assert row is not None
        company_name, offer, markets, language_preferences, version, website, active_icp = row
        assert company_name == ""
        assert offer == ""
        assert markets == []
        assert language_preferences == []
        assert version == 1
        assert website is None
        assert active_icp is None
    finally:
        command.upgrade(config, "head")
        with psycopg.connect(migrated, autocommit=True) as conn:
            for row in existing_rows:
                conn.execute(
                    "UPDATE projects SET company_name = %s, offer = %s, website = %s, "
                    "markets = %s, language_preferences = %s, version = %s, "
                    "active_icp_version_id = %s WHERE id = %s",
                    (*row[1:], row[0]),
                )
            conn.execute("DELETE FROM projects WHERE id = %s", (project_id,))
            conn.execute("DELETE FROM workspaces WHERE id = %s", (workspace_id,))


WORKSPACE_A = "11111111-1111-4111-8111-111111111111"
OPERATOR = "auth0|operator-a"
REVIEWER = "auth0|reviewer-a"
ADMIN = "auth0|admin-a"
CREATE = {
    "name": "Sensors Europe",
    "company_name": "HarbourSense Instruments",
    "offer": "Industrial sensing for process monitoring.",
    "markets": ["DE", "NL"],
    "language_preferences": ["en", "de"],
}


@pytest.fixture
def api(seeded, monkeypatch):
    """An authenticated client on the runtime role with operator, reviewer and admin members."""
    monkeypatch.setenv("BUYEROS_DATABASE_URL", runtime_role_dsn(seeded))
    monkeypatch.setenv("BUYEROS_AUTH0_ISSUER", fx.ISSUER)
    monkeypatch.setenv("BUYEROS_AUTH0_AUDIENCE", fx.AUDIENCE)
    from buyeros_api.settings import get_settings

    get_settings.cache_clear()
    cache = JwksKeyCache(lambda: asyncio.sleep(0, result=fx.jwks_document()), cache_seconds=300)
    monkeypatch.setattr(auth, "_verifier_from_settings", lambda: TokenVerifier(cache, issuer=fx.ISSUER, audience=fx.AUDIENCE))

    owner = psycopg.connect(seeded, autocommit=True)
    for subject, roles in ((OPERATOR, ["operator"]), (REVIEWER, ["reviewer"]), (ADMIN, ["workspace_admin"])):
        user_id = uuid.uuid5(uuid.NAMESPACE_URL, subject)
        owner.execute("DELETE FROM memberships WHERE user_id = %s", (user_id,))
        owner.execute("DELETE FROM users WHERE id = %s", (user_id,))
        owner.execute("INSERT INTO users(id, issuer, subject) VALUES (%s, %s, %s)", (user_id, fx.ISSUER, subject))
        owner.execute(
            "INSERT INTO memberships(id, workspace_id, user_id, roles, active) VALUES (%s, %s, %s, %s, true)",
            (uuid.uuid4(), WORKSPACE_A, user_id, roles),
        )
    owner.close()
    try:
        yield TestClient(create_app(), raise_server_exceptions=False)
    finally:
        get_settings.cache_clear()
        owner = psycopg.connect(seeded, autocommit=True)
        for subject in (OPERATOR, REVIEWER, ADMIN):
            user_id = uuid.uuid5(uuid.NAMESPACE_URL, subject)
            owner.execute("DELETE FROM memberships WHERE user_id = %s", (user_id,))
            owner.execute("DELETE FROM users WHERE id = %s", (user_id,))
        owner.execute("DELETE FROM idempotency_records WHERE workspace_id = %s", (WORKSPACE_A,))
        owner.execute("DELETE FROM icp_versions WHERE workspace_id = %s", (WORKSPACE_A,))
        owner.execute("DELETE FROM projects WHERE workspace_id = %s", (WORKSPACE_A,))
        owner.close()


def _h(subject=OPERATOR, key="create-01", **extra):
    headers = {"Authorization": f"Bearer {fx.make_token(sub=subject)}", "Idempotency-Key": key}
    headers.update(extra)
    return headers


def test_create_project_persists_the_full_payload(api):
    response = api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json=CREATE, headers=_h())
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["company_name"] == CREATE["company_name"]
    assert data["markets"] == ["DE", "NL"]
    assert data["version"] == 1
    assert response.headers["ETag"] == '"1"'


def test_the_same_create_key_and_body_replays_instead_of_duplicating(api):
    first = api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json=CREATE, headers=_h(key="create-replay"))
    assert first.status_code == 201, first.text
    second = api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json=CREATE, headers=_h(key="create-replay"))
    assert second.status_code == 201, second.text
    assert second.json()["data"]["id"] == first.json()["data"]["id"]
    listed = api.get(f"/v1/workspaces/{WORKSPACE_A}/projects", headers=_h(key="list-0001")).json()["data"]["items"]
    # `seeded` also leaves ProjectA in this workspace; assert the replay created no *second* copy.
    created_id = first.json()["data"]["id"]
    assert sum(item["id"] == created_id for item in listed) == 1


def test_the_same_create_key_with_a_different_body_conflicts(api):
    assert api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json=CREATE, headers=_h(key="create-conflict")).status_code == 201
    changed = {**CREATE, "name": "Sensors Europe revised"}
    response = api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json=changed, headers=_h(key="create-conflict"))
    assert response.status_code == 409
    assert response.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_a_malformed_idempotency_key_is_rejected(api):
    response = api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json=CREATE, headers=_h(key="short"))
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_REQUEST"


def test_a_full_length_idempotency_key_is_accepted_and_replays(api):
    key = "k" * 200
    assert len(key) == 200 and len(key) > 128  # contract's 8..200 bound, past the old VARCHAR(128)
    first = api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json=CREATE, headers=_h(key=key))
    assert first.status_code == 201, first.text
    second = api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json=CREATE, headers=_h(key=key))
    assert second.status_code == 201, second.text
    assert second.json()["data"]["id"] == first.json()["data"]["id"]


def test_unknown_keys_are_rejected(api):
    body = {**CREATE, "sender_identity": {"display_name": "x"}}
    response = api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json=body, headers=_h())
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"


def test_an_invalid_market_code_is_rejected(api):
    response = api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json={**CREATE, "markets": ["germany"]}, headers=_h())
    assert response.status_code == 422


def test_a_viewer_cannot_create(api):
    response = api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json=CREATE, headers=_h(subject=REVIEWER))
    # reviewer is deliberately not in createProject's x-permitted-roles (operator, workspace_admin)
    assert response.status_code == 403, response.text


def _create(api, key="create-1"):
    response = api.post(f"/v1/workspaces/{WORKSPACE_A}/projects", json=CREATE, headers=_h(key=key))
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def test_update_bumps_the_version_and_sets_the_etag(api):
    project_id = _create(api)
    response = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"offer": "Revised offer for process monitoring."},
        headers=_h(key="update-01", **{"If-Match": '"1"'}),
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["offer"].startswith("Revised")
    assert data["version"] == 2
    assert response.headers["ETag"] == '"2"'
    assert data["name"] == CREATE["name"]  # untouched fields survive a partial update


def test_a_repeated_update_key_and_body_replays_the_version(api):
    project_id = _create(api)
    body = {"offer": "Revised offer for process monitoring."}
    first = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json=body, headers=_h(key="update-replay", **{"If-Match": '"1"'}),
    )
    assert first.status_code == 200, first.text
    replay = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json=body, headers=_h(key="update-replay", **{"If-Match": '"1"'}),
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["version"] == 2  # a replay, not a second bump
    assert replay.json()["data"]["id"] == first.json()["data"]["id"]


def test_a_stale_if_match_is_rejected(api):
    project_id = _create(api)
    api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"offer": "first"},
        headers=_h(key="update-10", **{"If-Match": '"1"'}),
    )
    response = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"offer": "second"},
        headers=_h(key="update-11", **{"If-Match": '"1"'}),
    )
    assert response.status_code == 412
    assert response.json()["code"] == "STALE_REVISION"


def test_missing_if_match_is_rejected(api):
    project_id = _create(api)
    response = api.patch(f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}", json={"offer": "x"}, headers=_h(key="update-12"))
    assert response.status_code == 400


def test_a_malformed_if_match_is_rejected(api):
    project_id = _create(api)
    response = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"offer": "x"},
        headers=_h(key="update-13", **{"If-Match": '"01"'}),
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_REQUEST"


def test_an_explicit_null_is_rejected_on_update(api):
    project_id = _create(api)
    response = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"name": None},
        headers=_h(key="update-null-1", **{"If-Match": '"1"'}),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"


def test_an_explicit_null_is_rejected_on_create(api):
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects",
        json={**CREATE, "website": None},
        headers=_h(key="create-null-1"),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"


def test_archive_requires_workspace_admin(api):
    project_id = _create(api)
    response = api.request(
        "DELETE",
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"reason": "Pilot ended."},
        headers=_h(key="archive-01", **{"If-Match": '"1"'}),
    )
    assert response.status_code == 403  # operator is not permitted to archive


def test_archive_requires_the_contract_reason(api):
    project_id = _create(api)
    response = api.request(
        "DELETE",
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        headers=_h(key="archive-02", **{"If-Match": '"1"'}),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"


def test_workspace_admin_archives_a_project(api):
    project_id = _create(api)
    response = api.request(
        "DELETE",
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"reason": "Pilot ended."},
        headers=_h(subject=ADMIN, key="archive-ok", **{"If-Match": '"1"'}),
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "archived"
    assert data["version"] == 2
    assert response.headers["ETag"] == '"2"'


def test_a_repeated_archive_key_and_body_replays(api):
    project_id = _create(api)
    body = {"reason": "Pilot ended."}
    headers = _h(subject=ADMIN, key="archive-replay", **{"If-Match": '"1"'})
    first = api.request("DELETE", f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}", json=body, headers=headers)
    assert first.status_code == 200, first.text
    replay = api.request("DELETE", f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}", json=body, headers=headers)
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["version"] == 2
    assert replay.json()["data"]["id"] == first.json()["data"]["id"]


def test_a_stale_archive_if_match_is_rejected(api):
    project_id = _create(api)
    first = api.request(
        "DELETE",
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"reason": "Pilot ended."},
        headers=_h(subject=ADMIN, key="archive-stale-1", **{"If-Match": '"1"'}),
    )
    assert first.status_code == 200, first.text
    response = api.request(
        "DELETE",
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"reason": "Pilot ended."},
        headers=_h(subject=ADMIN, key="archive-stale-2", **{"If-Match": '"1"'}),
    )
    assert response.status_code == 412
    assert response.json()["code"] == "STALE_REVISION"


def test_the_same_key_with_a_different_body_conflicts(api):
    project_id = _create(api)
    first = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"offer": "one"},
        headers=_h(key="dup-0001", **{"If-Match": '"1"'}),
    )
    assert first.status_code == 200
    second = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"offer": "two"},
        headers=_h(key="dup-0001", **{"If-Match": '"2"'}),
    )
    assert second.status_code == 409
    assert second.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_approval_sets_the_active_profile_and_requires_a_reviewer(api):
    project_id = _create(api)
    saved = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}/icp-versions",
        json={"requirements": [{"id": "r1", "text": "Distributes sensors", "category": "must", "hard_exclusion": False}],
              "markets": ["DE"], "buyer_types": ["Distributor"], "languages": ["en"], "offer_facts": []},
        headers=_h(key="i1"),
    )
    assert saved.status_code == 201, saved.text
    version = saved.json()["data"]
    body = {"content_hash": version["content_hash"], "confirmation": True}

    # operator cannot approve (approveICPVersion permits reviewer/workspace_admin)
    denied = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/icp-versions/{version['id']}/approve",
        json=body, headers=_h(key="ap1", **{"If-Match": f'"{version["number"]}"'}),
    )
    assert denied.status_code == 403

    approved = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/icp-versions/{version['id']}/approve",
        json=body, headers=_h(subject=REVIEWER, key="ap2", **{"If-Match": f'"{version["number"]}"'}),
    )
    assert approved.status_code == 200, approved.text

    project = api.get(f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}", headers=_h()).json()["data"]
    assert project["active_icp_version_id"] == version["id"]


def _save_icp(api, project_id, *, key, requirements_text="Distributes sensors"):
    saved = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}/icp-versions",
        json={"requirements": [{"id": "r1", "text": requirements_text, "category": "must", "hard_exclusion": False}],
              "markets": ["DE"], "buyer_types": ["Distributor"], "languages": ["en"], "offer_facts": []},
        headers=_h(key=key),
    )
    assert saved.status_code == 201, saved.text
    return saved.json()["data"]


def _approve_icp(api, version, *, key, subject=REVIEWER):
    response = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/icp-versions/{version['id']}/approve",
        json={"content_hash": version["content_hash"], "confirmation": True},
        headers=_h(subject=subject, key=key, **{"If-Match": f'"{version["number"]}"'}),
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_concurrent_same_key_inserts_do_not_surface_a_500(api):
    """Two sessions race the same scoped idempotency key: the loser replays or gets a 409,
    never an unhandled unique-constraint error."""
    from buyeros_api.api.deps import get_engine
    from buyeros_api.api.errors import ApiError
    from buyeros_api.api.idempotency import begin_idempotency
    from buyeros_api.db.session import tenant_session

    workspace_id = uuid.UUID(WORKSPACE_A)
    actor_id = uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR)
    key = "race-" + uuid.uuid4().hex
    body = {"name": "race"}

    async def scenario():
        engine = get_engine()
        a_ready = asyncio.Event()
        b_started = asyncio.Event()
        out: dict = {}

        async def session_a():
            async with tenant_session(engine, workspace_id) as session:
                await begin_idempotency(
                    session, workspace_id=workspace_id, actor_id=actor_id,
                    operation_id="createProject", key=key, body=body,
                )
                a_ready.set()
                await b_started.wait()
                # Let the peer reach its conflicting INSERT while this row is uncommitted.
                await asyncio.sleep(0.5)
            # Exiting commits, releasing the unique-index lock the peer blocks on.

        async def session_b():
            await a_ready.wait()
            async with tenant_session(engine, workspace_id) as session:
                b_started.set()
                try:
                    out["outcome"] = await begin_idempotency(
                        session, workspace_id=workspace_id, actor_id=actor_id,
                        operation_id="createProject", key=key, body=body,
                    )
                except ApiError as exc:
                    out["error"] = exc

        await asyncio.gather(session_a(), session_b())
        return out

    result = asyncio.run(scenario())
    outcome = result.get("outcome")
    if outcome is not None:
        assert outcome.replay is True
    else:
        error = result["error"]
        assert error.status_code == 409
        assert error.code == "IDEMPOTENCY_CONFLICT"


def test_approving_a_new_version_supersedes_the_previous_active_one(api):
    project_id = _create(api, key="supersede-create")
    v1 = _save_icp(api, project_id, key="supersede-v1")
    approved_v1 = _approve_icp(api, v1, key="supersede-ap1")
    v2 = _save_icp(api, project_id, key="supersede-v2", requirements_text="Revised requirement")
    _approve_icp(api, v2, key="supersede-ap2")

    project = api.get(f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}", headers=_h()).json()["data"]
    assert project["active_icp_version_id"] == v2["id"]

    versions = api.get(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}/icp-versions", headers=_h()
    ).json()["data"]["items"]
    by_id = {v["id"]: v for v in versions}
    assert by_id[v1["id"]]["status"] == "superseded"
    assert by_id[v1["id"]]["approved_at"] == approved_v1["approved_at"]
    assert by_id[v2["id"]]["status"] == "approved"
    assert sum(v["status"] == "approved" for v in versions) == 1


def test_a_material_change_retains_prior_approval_and_a_later_save_stays_retrievable(api):
    project_id = _create(api, key="material-create")
    v1 = _save_icp(api, project_id, key="material-v1")
    approved_v1 = _approve_icp(api, v1, key="material-ap1")
    api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"offer": "A materially different offer."},
        headers=_h(key="material-update", **{"If-Match": '"1"'}),
    )
    project = api.get(f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}", headers=_h()).json()["data"]
    assert project["active_icp_version_id"] is None

    v2 = _save_icp(api, project_id, key="material-v2", requirements_text="A new requirement")
    versions = api.get(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}/icp-versions", headers=_h()
    ).json()["data"]["items"]
    by_id = {v["id"]: v for v in versions}
    assert by_id[v1["id"]]["status"] == "superseded"
    assert by_id[v1["id"]]["approved_at"] == approved_v1["approved_at"]
    assert by_id[v2["id"]]["status"] == "saved"


def test_approving_a_foreign_workspace_version_is_a_non_enumerating_404(api, seeded):
    foreign_version = str(uuid.uuid4())
    project_b = "b0000000-0000-4000-8000-000000000002"
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO icp_versions(id, workspace_id, project_id, number, content, content_hash) "
            "VALUES (%s, %s, %s, 1, '{}'::jsonb, 'sha256:foreign')",
            (foreign_version, "22222222-2222-4222-8222-222222222222", project_b),
        )
    try:
        response = api.post(
            f"/v1/workspaces/{WORKSPACE_A}/icp-versions/{foreign_version}/approve",
            json={"content_hash": "sha256:foreign", "confirmation": True},
            headers=_h(subject=REVIEWER, key="foreign-approve", **{"If-Match": '"1"'}),
        )
        assert response.status_code == 404, response.text
        assert response.json()["code"] == "NOT_FOUND"
        assert "data" not in response.json()
        assert foreign_version not in response.text
    finally:
        with psycopg.connect(seeded, autocommit=True) as conn:
            conn.execute("DELETE FROM icp_versions WHERE id = %s", (foreign_version,))


def test_a_foreign_project_cannot_be_updated_or_archived(api):
    foreign = "b0000000-0000-4000-8000-000000000002"
    patched = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{foreign}",
        json={"offer": "x"},
        headers=_h(key="foreign-patch", **{"If-Match": '"1"'}),
    )
    assert patched.status_code == 404, patched.text
    assert patched.json()["code"] == "NOT_FOUND"

    archived = api.request(
        "DELETE",
        f"/v1/workspaces/{WORKSPACE_A}/projects/{foreign}",
        json={"reason": "Pilot ended."},
        headers=_h(subject=ADMIN, key="foreign-delete", **{"If-Match": '"1"'}),
    )
    assert archived.status_code == 404, archived.text
    assert archived.json()["code"] == "NOT_FOUND"


def test_a_material_change_supersedes_and_reopens_the_profile(api):
    project_id = _create(api)
    saved = api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}/icp-versions",
        json={"requirements": [{"id": "r1", "text": "x", "category": "must", "hard_exclusion": False}],
              "markets": ["DE"], "buyer_types": ["Distributor"], "languages": ["en"], "offer_facts": []},
        headers=_h(key="i1"),
    ).json()["data"]
    api.post(
        f"/v1/workspaces/{WORKSPACE_A}/icp-versions/{saved['id']}/approve",
        json={"content_hash": saved["content_hash"], "confirmation": True},
        headers=_h(subject=REVIEWER, key="ap1", **{"If-Match": f'"{saved["number"]}"'}),
    )
    api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"offer": "A materially different offer."},
        headers=_h(key="update-30", **{"If-Match": '"1"'}),
    )
    project = api.get(f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}", headers=_h()).json()["data"]
    assert project["active_icp_version_id"] is None
    versions = api.get(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}/icp-versions", headers=_h()
    ).json()["data"]["items"]
    assert [v["status"] for v in versions] == ["superseded"]
