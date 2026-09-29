"""T01: project replay is bound to its target, precondition and first result."""

from concurrent.futures import ThreadPoolExecutor
import uuid

import psycopg
from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app
from tests.test_api_projects_db import CREATE, OPERATOR, WORKSPACE_A, _create, _h, api


def _patch(client, project_id, *, key, version='"1"', body=None):
    return client.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json=body or {"offer": "First accepted mutation"},
        headers=_h(key=key, **{"If-Match": version}),
    )


def test_same_key_same_request_replays_exact_result(api):
    project_id = _create(api, "create-exact-1")
    first = _patch(api, project_id, key="update-exact-1")
    assert first.status_code == 200, first.text
    later = _patch(api, project_id, key="update-exact-2", version='"2"', body={"name": "Later name"})
    assert later.status_code == 200, later.text

    replay = _patch(api, project_id, key="update-exact-1")
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"] == first.json()["data"]
    assert replay.headers["ETag"] == first.headers["ETag"] == '"2"'
    assert later.json()["data"]["version"] == 3


def test_same_key_other_target_conflicts(api):
    project_a = _create(api, "create-target-a")
    project_b = _create(api, "create-target-b")
    first = _patch(api, project_a, key="shared-target-key")
    assert first.status_code == 200, first.text
    other = _patch(api, project_b, key="shared-target-key")
    assert other.status_code == 409, other.text
    assert other.json()["code"] == "IDEMPOTENCY_CONFLICT"
    current = api.get(f"/v1/workspaces/{WORKSPACE_A}/projects/{project_b}", headers=_h())
    assert current.json()["data"]["version"] == 1


def test_changed_if_match_conflicts(api):
    project_id = _create(api, "create-precondition")
    assert _patch(api, project_id, key="update-precondition").status_code == 200
    changed = _patch(api, project_id, key="update-precondition", version='"2"')
    assert changed.status_code == 409, changed.text
    assert changed.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_twenty_concurrent_same_keys_one_write(api):
    project_id = _create(api, "create-concurrent")

    def attempt(_):
        with TestClient(create_app(), raise_server_exceptions=False) as client:
            return _patch(client, project_id, key="update-concurrent")

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(attempt, range(20)))

    assert {result.status_code for result in results} == {200}, [r.status_code for r in results]
    assert {result.json()["data"]["version"] for result in results} == {2}
    assert {result.json()["data"]["id"] for result in results} == {project_id}


def test_revoked_membership_cannot_replay(api, seeded):
    project_id = _create(api, "create-revoked")
    first = _patch(api, project_id, key="update-revoked")
    assert first.status_code == 200, first.text
    actor_id = uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR)
    with psycopg.connect(seeded, autocommit=True) as owner:
        owner.execute(
            "UPDATE memberships SET active = false WHERE workspace_id = %s AND user_id = %s",
            (WORKSPACE_A, actor_id),
        )
    try:
        replay = _patch(api, project_id, key="update-revoked")
        assert replay.status_code == 404
    finally:
        with psycopg.connect(seeded, autocommit=True) as owner:
            owner.execute(
                "UPDATE memberships SET active = true WHERE workspace_id = %s AND user_id = %s",
                (WORKSPACE_A, actor_id),
            )


def test_create_replay_keeps_first_result_after_project_changes(api):
    path = f"/v1/workspaces/{WORKSPACE_A}/projects"
    first = api.post(path, json=CREATE, headers=_h(key="create-frozen-result"))
    assert first.status_code == 201, first.text
    project_id = first.json()["data"]["id"]
    changed = _patch(api, project_id, key="update-after-create")
    assert changed.status_code == 200, changed.text

    replay = api.post(path, json=CREATE, headers=_h(key="create-frozen-result"))
    assert replay.status_code == 201, replay.text
    assert replay.json()["data"] == first.json()["data"]
    assert replay.headers["ETag"] == first.headers["ETag"] == '"1"'


def test_legacy_body_only_record_requires_new_key(api, seeded):
    from buyeros_api.services.confirm_service import request_fingerprint as old_fingerprint

    project_id = _create(api, "create-legacy")
    actor_id = uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR)
    body = {"offer": "First accepted mutation"}
    with psycopg.connect(seeded, autocommit=True) as owner:
        owner.execute(
            "INSERT INTO idempotency_records"
            "(id, workspace_id, actor_id, operation_id, key, request_hash, status, resource_id) "
            "VALUES (%s, %s, %s, 'updateProject', %s, %s, 'completed', %s)",
            (uuid.uuid4(), WORKSPACE_A, actor_id, "legacy-body-key", old_fingerprint(body), project_id),
        )
    replay = _patch(api, project_id, key="legacy-body-key", body=body)
    assert replay.status_code == 409, replay.text
    assert replay.json()["code"] == "IDEMPOTENCY_CONFLICT"
    current = api.get(f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}", headers=_h())
    assert current.json()["data"]["version"] == 1


def test_completed_record_keeps_http_status_version_and_result(api, seeded):
    project_id = _create(api, "create-ledger-shape")
    first = _patch(api, project_id, key="update-ledger-shape")
    assert first.status_code == 200, first.text
    actor_id = uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR)
    with psycopg.connect(seeded) as owner:
        stored = owner.execute(
            "SELECT status, resource_id, response FROM idempotency_records "
            "WHERE workspace_id = %s AND actor_id = %s AND operation_id = 'updateProject' AND key = %s",
            (WORKSPACE_A, actor_id, "update-ledger-shape"),
        ).fetchone()
    assert stored[0] == "completed"
    assert stored[1] == project_id
    assert stored[2] == {
        "http_status": 200,
        "version": 2,
        "data": first.json()["data"],
    }
