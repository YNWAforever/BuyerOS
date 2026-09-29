"""T03: exact offer basis, approval history, audit and mutation races in PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import psycopg
from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app
from tests.contract_validation import assert_contract_response
from tests.test_api_projects_db import (
    ADMIN, REVIEWER, WORKSPACE_A, _approve_icp, _create, _h, _save_icp, api,
)


def _approval_call(client, version, *, key, expected_project_version=1):
    return client.post(
        f"/v1/workspaces/{WORKSPACE_A}/icp-versions/{version['id']}/approve",
        json={"content_hash": version["content_hash"], "confirmation": True,
              "expected_project_version": expected_project_version},
        headers=_h(subject=REVIEWER, key=key,
                   **{"If-Match": f'"{version["number"]}"'}),
    )


def test_saved_v2_approval_preserves_v1_history_and_records_one_audit(api, seeded):
    project_id = _create(api, key="history-project")
    v1 = _save_icp(api, project_id, key="history-save-v1")
    approved_v1 = _approve_icp(api, v1, key="history-approve-v1")
    v2 = _save_icp(api, project_id, key="history-save-v2", requirements_text="New market requirement")
    first = _approval_call(api, v2, key="history-approve-v2", expected_project_version=2)
    assert first.status_code == 200, first.text
    assert_contract_response("ICPVersionResponse", first.json())
    retry = _approval_call(api, v2, key="history-approve-v2", expected_project_version=2)
    assert retry.status_code == 200, retry.text
    assert retry.json()["data"] == first.json()["data"]
    assert first.json()["data"]["approved_by"]
    versions = api.get(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}/icp-versions", headers=_h()
    ).json()["data"]["items"]
    by_id = {row["id"]: row for row in versions}
    assert by_id[v1["id"]]["status"] == "superseded"
    assert by_id[v1["id"]]["is_current"] is False
    assert by_id[v1["id"]]["basis_status"] == "current"
    assert by_id[v1["id"]]["approved_at"] == approved_v1["approved_at"]
    assert by_id[v2["id"]]["status"] == "approved"
    assert by_id[v2["id"]]["is_current"] is True
    assert by_id[v2["id"]]["basis_status"] == "current"
    with psycopg.connect(seeded) as owner:
        audit_count = owner.execute(
            "SELECT count(*) FROM audit_events WHERE workspace_id = %s "
            "AND action = 'icp.approved' AND subject_id = %s", (WORKSPACE_A, v2["id"])
        ).fetchone()[0]
    assert audit_count == 1


def test_offer_change_stales_pending_basis_but_rename_does_not(api):
    project_id = _create(api, key="basis-change-project")
    pending = _save_icp(api, project_id, key="basis-change-save")
    renamed = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"name": "Renamed project"},
        headers=_h(key="basis-rename", **{"If-Match": '"1"'}),
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["offer_revision"] == 1
    changed = api.patch(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"offer": "A new material offer"},
        headers=_h(key="basis-offer-change", **{"If-Match": '"2"'}),
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["data"]["offer_revision"] == 2
    rejected = _approval_call(api, pending, key="basis-stale-approval", expected_project_version=3)
    assert rejected.status_code == 412, rejected.text
    assert rejected.json()["code"] == "STALE_REVISION"
    listed = api.get(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}/icp-versions", headers=_h()
    ).json()["data"]["items"]
    assert listed[0]["basis_status"] == "stale"
    assert listed[0]["is_current"] is False


def test_approve_archived_project_denied(api):
    project_id = _create(api, key="archive-approval-project")
    pending = _save_icp(api, project_id, key="archive-approval-save")
    archived = api.request(
        "DELETE", f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
        json={"reason": "Pilot ended."},
        headers=_h(subject=ADMIN, key="archive-before-approve", **{"If-Match": '"1"'}),
    )
    assert archived.status_code == 200, archived.text
    rejected = _approval_call(api, pending, key="approve-after-archive", expected_project_version=2)
    assert rejected.status_code in {409, 412}, rejected.text
    assert rejected.json()["code"] in {"INVALID_REQUEST", "STALE_REVISION"}


def test_real_icp_pagination_and_bounds(api):
    project_id = _create(api, key="pagination-project")
    for index in range(3):
        _save_icp(api, project_id, key=f"pagination-save-{index}",
                  requirements_text=f"Requirement {index}")
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}/icp-versions"
    page = api.get(path, params={"offset": 1, "limit": 1}, headers=_h())
    assert page.status_code == 200, page.text
    assert_contract_response("ICPVersionPageResponse", page.json())
    data = page.json()["data"]
    assert (data["offset"], data["limit"], data["total"]) == (1, 1, 3)
    assert [item["number"] for item in data["items"]] == [2]
    invalid = api.get(path, params={"offset": 0, "limit": 101}, headers=_h())
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "INVALID_REQUEST"


def test_approve_update_archive_races_never_double_activate_or_deadlock(api):
    for iteration, mutation in enumerate(("update", "archive", "update", "archive")):
        project_id = _create(api, key=f"race-project-{iteration}")
        pending = _save_icp(api, project_id, key=f"race-save-{iteration}")
        barrier = Barrier(2)

        def approve():
            with TestClient(create_app(), raise_server_exceptions=False) as client:
                barrier.wait(timeout=5)
                return _approval_call(client, pending, key=f"race-approve-{iteration}")

        def change():
            with TestClient(create_app(), raise_server_exceptions=False) as client:
                barrier.wait(timeout=5)
                headers = _h(subject=ADMIN if mutation == "archive" else None,
                             key=f"race-mutate-{iteration}", **{"If-Match": '"1"'})
                if mutation == "archive":
                    return client.request(
                        "DELETE", f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
                        json={"reason": "Race test"}, headers=headers,
                    )
                return client.patch(
                    f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}",
                    json={"offer": f"Changed {iteration}"},
                    headers=_h(key=f"race-mutate-{iteration}", **{"If-Match": '"1"'}),
                )

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(approve)
            second = pool.submit(change)
            approval, mutation_result = first.result(timeout=15), second.result(timeout=15)
        assert sorted((approval.status_code, mutation_result.status_code)) == [200, 412], (
            mutation, approval.text, mutation_result.text
        )
        project_response = api.get(
            f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}", headers=_h()
        )
        assert_contract_response("ProjectResponse", project_response.json())
        project = project_response.json()["data"]
        assert project["version"] == 2
        if approval.status_code == 200:
            assert project["active_icp_version_id"] == pending["id"]
        else:
            assert project["active_icp_version_id"] is None


def test_project_list_pagination_is_sql_bounded(api):
    for index in range(3):
        _create(api, key=f"project-page-create-{index}")
    path = f"/v1/workspaces/{WORKSPACE_A}/projects"
    first = api.get(path, params={"offset": 0, "limit": 1}, headers=_h())
    second = api.get(path, params={"offset": 1, "limit": 1}, headers=_h())
    assert first.status_code == second.status_code == 200
    assert_contract_response("ProjectPageResponse", first.json())
    assert_contract_response("ProjectPageResponse", second.json())
    assert first.json()["data"]["total"] >= 4
    assert len(first.json()["data"]["items"]) == len(second.json()["data"]["items"]) == 1
    assert first.json()["data"]["items"][0]["id"] != second.json()["data"]["items"][0]["id"]
    assert (second.json()["data"]["offset"], second.json()["data"]["limit"]) == (1, 1)
    rejected = api.get(path, params={"limit": 101}, headers=_h())
    assert rejected.status_code == 422
