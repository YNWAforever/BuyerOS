"""T11 durable buyer assignment and bulk jobs on disposable PostgreSQL."""
import asyncio
import uuid

import psycopg

from tests.test_buyer_review_db import (
    ADMIN, OPERATOR, VIEWER, WORKSPACE_A, WORKSPACE_B, PROJECT_A, _admin_membership, _h, _seed_buyer, api,
)


def test_assign_owner_small_batch_is_durable_partial_and_role_scoped(api, seeded):
    valid = _seed_buyer(seeded, name="Assign valid")
    stale = _seed_buyer(seeded, name="Assign stale")
    missing = str(uuid.uuid4())
    owner_id = _admin_membership(seeded)
    body = {
        "selection": {"kind": "explicit", "buyers": [
            {"id": valid, "version": 1}, {"id": stale, "version": 99},
            {"id": missing, "version": 1},
        ]},
        "owner_membership_id": owner_id,
        "reason": "Fixture team assignment",
    }
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-owner-assignments"
    denied = api.post(path, json=body, headers=_h(subject=VIEWER, key="t11-owner-viewer"))
    assert denied.status_code == 403, denied.text
    assigned = api.post(path, json=body, headers=_h(subject=OPERATOR, key="t11-owner-batch"))
    assert assigned.status_code == 200, assigned.text
    data = assigned.json()["data"]
    assert (data["requested"], data["updated"], data["unchanged"], data["blocked"], data["conflicts"]) == (3, 1, 0, 1, 1)
    assert {item["status"] for item in data["results"]} == {"updated", "conflict", "blocked"}
    with psycopg.connect(seeded) as conn:
        assert str(conn.execute("SELECT owner_user_id FROM project_buyers WHERE id=%s", (valid,)).fetchone()[0]) == str(uuid.uuid5(uuid.NAMESPACE_URL, ADMIN))
        assert conn.execute("SELECT version FROM project_buyers WHERE id=%s", (valid,)).fetchone()[0] == 2
        assert conn.execute("SELECT owner_user_id FROM project_buyers WHERE id=%s", (stale,)).fetchone()[0] is None
    replay = api.post(path, json=body, headers=_h(subject=OPERATOR, key="t11-owner-batch"))
    assert replay.status_code == 200 and replay.json()["data"] == data
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT version FROM project_buyers WHERE id=%s", (valid,)).fetchone()[0] == 2


def test_unknown_async_job_is_not_a_fake_success(api):
    path = f"/v1/workspaces/{WORKSPACE_A}/jobs/{uuid.uuid4()}"
    response = api.get(path, headers=_h(subject=OPERATOR))
    assert response.status_code == 404, response.text




def test_0016_bulk_job_tables_are_tenant_forced_and_disposable_rollback(migrated, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from tests.test_buyer_review_db import ALEMBIC_INI, SERVICE_ROOT

    monkeypatch.setenv("BUYEROS_DATABASE_URL", migrated)
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    with psycopg.connect(migrated) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0035_worker_recovery_probe"
        for table in ("async_jobs", "async_job_items"):
            assert conn.execute("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname=%s",
                                (table,)).fetchone() == (True, True)
    command.downgrade(config, "0015_policy_lifecycle")
    with psycopg.connect(migrated) as conn:
        assert conn.execute("SELECT to_regclass('async_jobs')").fetchone()[0] is None
    command.upgrade(config, "head")


def test_bulk_partial_result_and_resume(api, seeded):
    from buyeros_api.api.deps import tenant_scoped
    from buyeros_api.services.bulk_service import apply_bulk_chunk

    owner_id = _admin_membership(seeded)
    buyers = [_seed_buyer(seeded, name=f"Bulk {i:03d}",
                          owner_user_id=str(uuid.uuid5(uuid.NAMESPACE_URL, ADMIN)) if i == 0 else None)
              for i in range(100)]
    missing = str(uuid.uuid4())
    selection = {"kind": "explicit", "buyers": [
        {"id": buyer_id, "version": 99 if i == 1 else 1}
        for i, buyer_id in enumerate(buyers)
    ] + [{"id": missing, "version": 1}]}
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-owner-assignments"
    body = {"selection": selection, "owner_membership_id": owner_id, "reason": "Durable batch"}
    response = api.post(path, json=body, headers=_h(key="t11-bulk-owner"))
    assert response.status_code == 202, response.text
    from tests.contract_validation import assert_contract_response
    assert_contract_response("AsyncJobResponse", response.json())
    job = response.json()["data"]
    assert job["requested"] == 101 and job["processed"] == 0
    assert job["status"] == "queued"
    job_id = uuid.UUID(job["id"])
    replay = api.post(path, json=body, headers=_h(key="t11-bulk-owner"))
    assert replay.status_code == 202 and replay.json()["data"] == job

    async def first_and_crash():
        async with tenant_scoped(uuid.UUID(WORKSPACE_A)) as session:
            await apply_bulk_chunk(session, job_id)
        try:
            async with tenant_scoped(uuid.UUID(WORKSPACE_A)) as session:
                await apply_bulk_chunk(session, job_id)
                raise RuntimeError("simulated worker crash before transaction commit")
        except RuntimeError:
            pass
        async with tenant_scoped(uuid.UUID(WORKSPACE_A)) as session:
            await apply_bulk_chunk(session, job_id)
        async with tenant_scoped(uuid.UUID(WORKSPACE_A)) as session:
            await apply_bulk_chunk(session, job_id)

    asyncio.run(first_and_crash())
    result_path = f"/v1/workspaces/{WORKSPACE_A}/jobs/{job_id}"
    result = api.get(result_path + "?offset=0&limit=50", headers=_h())
    assert result.status_code == 200, result.text
    assert_contract_response("AsyncJobResponse", result.json())
    data = result.json()["data"]
    assert data["status"] == "completed"
    assert (data["requested"], data["processed"], data["updated"], data["unchanged"],
            data["blocked"], data["conflicts"]) == (101, 101, 98, 1, 1, 1)
    assert data["result_page"]["total"] == 101
    second_page = api.get(result_path + "?offset=50&limit=50", headers=_h()).json()["data"]["result_page"]
    third_page = api.get(result_path + "?offset=100&limit=50", headers=_h()).json()["data"]["result_page"]
    results = data["result_page"]["items"] + second_page["items"] + third_page["items"]
    assert len(results) == len({item["id"] for item in results}) == 101
    assert {item["status"] for item in results} == {"updated", "unchanged", "blocked", "conflict"}
    with psycopg.connect(seeded, autocommit=True) as db:
        db.execute("UPDATE async_job_items SET reason_code=%s WHERE job_id=%s AND status='blocked'",
                   (" \t=HYPERLINK", job_id))
    report = api.post(result_path + "/exports", json={},
                      headers=_h(key="t26-bulk-failure-export"))
    assert report.status_code == 202, report.text
    report_id = report.json()["data"]["id"]
    report_body = api.get(f"/v1/workspaces/{WORKSPACE_A}/exports/{report_id}/content",
                          headers=_h())
    assert report_body.status_code == 200, report_body.text
    assert report_body.text.startswith('"buyer_id","status","reason_code"')
    assert str(missing) in report_body.text
    assert report_body.text.count('"conflict"') == 1
    assert report_body.text.count('"blocked"') == 1
    assert "' \t=HYPERLINK" in report_body.text
    replay_report = api.post(result_path + "/exports", json={},
                             headers=_h(key="t26-bulk-failure-export"))
    assert replay_report.status_code == 202 and replay_report.json()["data"]["id"] == report_id
    with psycopg.connect(seeded, autocommit=True) as db:
        db.execute("UPDATE async_job_items SET reason_code='changed_after_export' "
                   "WHERE job_id=%s AND status='blocked'", (job_id,))
    revoked_report = api.get(f"/v1/workspaces/{WORKSPACE_A}/exports/{report_id}/content",
                             headers=_h())
    assert revoked_report.status_code == 403
    forbidden = api.get(f"/v1/workspaces/{WORKSPACE_A}/exports/{report_id}/content",
                        headers=_h(subject=VIEWER))
    assert forbidden.status_code == 403
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT count(*) FROM audit_events WHERE action='buyer.owner_assigned' AND workspace_id=%s",
                            (WORKSPACE_A,)).fetchone()[0] == 98
        assert conn.execute("SELECT count(*) FROM outbox_events WHERE event_type='bulk.mutate' AND workspace_id=%s",
                            (WORKSPACE_A,)).fetchone()[0] == 3
    retry_path = result_path + "/retry-failed"
    retried = api.post(retry_path, json={}, headers=_h(key="t11-retry-failures"))
    assert retried.status_code == 200, retried.text
    retry_data = retried.json()["data"]
    assert (retry_data["requested"], retry_data["updated"], retry_data["blocked"],
            retry_data["conflicts"]) == (2, 1, 1, 0)
    assert {row["id"] for row in retry_data["results"]} == {buyers[1], missing}
    replay_retry = api.post(retry_path, json={}, headers=_h(key="t11-retry-failures"))
    assert replay_retry.status_code == 200 and replay_retry.json()["data"] == retry_data
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT version FROM project_buyers WHERE id=%s", (buyers[1],)).fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM audit_events WHERE action='buyer.owner_assigned' AND workspace_id=%s",
                            (WORKSPACE_A,)).fetchone()[0] == 99


def test_job_read_is_actor_bound_even_for_same_workspace(api, seeded):
    # The first async regression creates a job; this guard is exercised separately with a seeded job.
    with psycopg.connect(seeded, autocommit=True) as conn:
        operator_id = uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR)
        job_id = str(uuid.uuid4())
        conn.execute("INSERT INTO async_jobs(id, workspace_id, project_id, actor_user_id, kind, operation, command, status, requested) "
                     "VALUES (%s,%s,%s,%s,'bulk_mutation','assignBuyerOwners','{}'::jsonb,'queued',1)",
                     (job_id, WORKSPACE_A, PROJECT_A, operator_id))
    path = f"/v1/workspaces/{WORKSPACE_A}/jobs/{job_id}"
    assert api.get(path, headers=_h(subject=OPERATOR)).status_code == 200
    assert api.get(path, headers=_h(subject=VIEWER)).status_code == 404
    assert api.get(path.replace(WORKSPACE_A, WORKSPACE_B), headers=_h(subject=OPERATOR)).status_code in {403, 404}


def test_t11_owner_assignment_is_a_strict_contract_extension():
    import yaml
    from pathlib import Path

    spec = yaml.safe_load((Path(__file__).resolve().parents[3] / "docs/buyeros/contracts/openapi.proposed.yaml").read_text(encoding="utf-8"))
    path = "/v1/workspaces/{workspace_id}/projects/{project_id}/buyer-owner-assignments"
    operation = spec["paths"][path]["post"]
    assert operation["operationId"] == "assignBuyerOwners"
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("OwnerAssignRequest")
    assert "202" in operation["responses"]
    assert spec["paths"]["/v1/workspaces/{workspace_id}/jobs/{job_id}/cancel"]["post"]["operationId"] == "cancelAsyncJob"
    retry = spec["paths"]["/v1/workspaces/{workspace_id}/jobs/{job_id}/retry-failed"]["post"]
    assert retry["operationId"] == "retryFailedAsyncJob"
    assert {"200", "202"} <= set(retry["responses"])
    # The disposable retry test above verifies this declared path reaches the actual FastAPI handler.
    for operation_id, path in (("reviewBuyers", "/v1/workspaces/{workspace_id}/projects/{project_id}/buyer-reviews"),
                               ("changeListMemberships", "/v1/workspaces/{workspace_id}/lists/{list_id}/memberships")):
        assert spec["paths"][path]["post"]["operationId"] == operation_id
        assert "202" in spec["paths"][path]["post"]["responses"]


def test_async_owner_target_must_be_active_before_enqueue(api, seeded):
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-owner-assignments"
    body = {"selection": {"kind": "explicit", "buyers": [
        {"id": str(uuid.uuid4()), "version": 1} for _ in range(101)
    ]}, "owner_membership_id": str(uuid.uuid4()), "reason": "Invalid target must not enqueue"}
    response = api.post(path, json=body, headers=_h(key="t11-invalid-async-owner"))
    assert response.status_code == 422, response.text
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT count(*) FROM async_jobs WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == 0


def test_retry_failed_only_new_versions(api, seeded):
    buyer_id = _seed_buyer(seeded, name="Retry failed version")
    owner_id = _admin_membership(seeded)
    job_id = str(uuid.uuid4())
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("INSERT INTO async_jobs(id, workspace_id, project_id, actor_user_id, kind, operation, "
                     "command, status, requested, processed, conflicts) "
                     "VALUES (%s,%s,%s,%s,'bulk_mutation','assignBuyerOwners',%s::jsonb,'completed',1,1,1)",
                     (job_id, WORKSPACE_A, PROJECT_A, uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR),
                      '{"owner_membership_id":"' + owner_id + '","reason":"Retry only failed"}'))
        conn.execute("INSERT INTO async_job_items(id, workspace_id, job_id, buyer_id, ordinal, expected_version, status, reason_code) "
                     "VALUES (%s,%s,%s,%s,0,99,'conflict','version_conflict')",
                     (str(uuid.uuid4()), WORKSPACE_A, job_id, buyer_id))
    path = f"/v1/workspaces/{WORKSPACE_A}/jobs/{job_id}/retry-failed"
    assert api.post(path, json={}, headers=_h(subject=VIEWER,key="t11-retry-viewer")).status_code == 404
    result = api.post(path, json={}, headers=_h(key="t11-retry-current"))
    assert result.status_code == 200, result.text
    data = result.json()["data"]
    assert data["requested"] == data["updated"] == 1
    assert data["results"][0]["id"] == buyer_id and data["results"][0]["version"] == 2
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT status FROM async_job_items WHERE job_id=%s", (job_id,)).fetchone()[0] == "conflict"


def test_review_and_list_mutations_queue_101_rows_with_exact_replay(api, seeded):
    selection = {"kind": "explicit", "buyers": [
        {"id": str(uuid.uuid4()), "version": 1} for _ in range(101)
    ]}
    review_path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-reviews"
    review_body = {"selection": selection, "status": "accepted", "reason": "Fixture review queue"}
    review = api.post(review_path, json=review_body, headers=_h(subject=ADMIN,key="t11-review-async"))
    assert review.status_code == 202, review.text
    review_job = review.json()["data"]
    assert review_job["requested"] == 101 and review_job["processed"] == 0
    replay = api.post(review_path, json=review_body, headers=_h(subject=ADMIN,key="t11-review-async"))
    assert replay.status_code == 202 and replay.json()["data"] == review_job
    list_path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/lists"
    created = api.post(list_path, json={"name": "Bulk list"}, headers=_h(key="t11-list-create"))
    assert created.status_code == 201, created.text
    list_id = created.json()["data"]["id"]
    change_path = f"/v1/workspaces/{WORKSPACE_A}/lists/{list_id}/memberships"
    change = api.post(change_path, json={"selection": selection, "operation": "add"},
                      headers=_h(key="t11-list-async", **{"If-Match": '"1"'}))
    assert change.status_code == 202, change.text
    list_job = change.json()["data"]
    assert list_job["requested"] == 101 and list_job["id"] != review_job["id"]
    with psycopg.connect(seeded) as conn:
        rows = conn.execute("SELECT operation, requested FROM async_jobs WHERE workspace_id=%s ORDER BY operation",
                            (WORKSPACE_A,)).fetchall()
        assert rows == [("changeListMemberships", 101), ("reviewBuyers", 101)]
        assert conn.execute("SELECT count(*) FROM human_reviews WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM list_memberships WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == 0


def test_cancel_bulk_job_preserves_committed_rows_and_stops_pending(api, seeded):
    from buyeros_api.api.deps import tenant_scoped
    from buyeros_api.services.bulk_service import apply_bulk_chunk

    buyer_id = _seed_buyer(seeded, name="Already committed before cancel")
    owner_id = _admin_membership(seeded)
    missing = [f"ffffffff-ffff-4fff-8fff-{index:012x}" for index in range(1, 101)]
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/buyer-owner-assignments"
    selection = {"kind": "explicit", "buyers": [{"id": buyer_id, "version": 1}] +
                 [{"id": value, "version": 1} for value in missing]}
    accepted = api.post(path, json={"selection": selection, "owner_membership_id": owner_id,
                                    "reason": "Cancel after first commit"}, headers=_h(key="t11-cancel-job"))
    assert accepted.status_code == 202, accepted.text
    job_id = accepted.json()["data"]["id"]

    async def first_chunk():
        async with tenant_scoped(uuid.UUID(WORKSPACE_A)) as session:
            await apply_bulk_chunk(session, uuid.UUID(job_id))
    asyncio.run(first_chunk())
    cancel_path = f"/v1/workspaces/{WORKSPACE_A}/jobs/{job_id}/cancel"
    assert api.post(cancel_path, json={}, headers=_h(subject=VIEWER,key="t11-cancel-viewer")).status_code == 404
    cancelled = api.post(cancel_path, json={}, headers=_h(key="t11-cancel-owned"))
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == "cancel_requested"
    replay = api.post(cancel_path, json={}, headers=_h(key="t11-cancel-owned"))
    assert replay.status_code == 200 and replay.json()["data"] == cancelled.json()["data"]

    async def finish_cancellation():
        for _ in range(2):
            async with tenant_scoped(uuid.UUID(WORKSPACE_A)) as session:
                await apply_bulk_chunk(session, uuid.UUID(job_id))
    asyncio.run(finish_cancellation())
    status = api.get(f"/v1/workspaces/{WORKSPACE_A}/jobs/{job_id}?offset=0&limit=100",
                     headers=_h()).json()["data"]
    assert status["status"] == "cancelled" and status["processed"] == 101
    assert status["updated"] == 1 and status["cancelled"] == 51
    assert {row["status"] for row in status["result_page"]["items"]} == {"updated", "blocked", "cancelled"}
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT version FROM project_buyers WHERE id=%s", (buyer_id,)).fetchone()[0] == 2
