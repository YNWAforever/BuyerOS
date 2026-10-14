"""Real project/ICP transactions with the hosted precondition carrier."""
import uuid

import psycopg

from tests.icp_fixtures import valid_icp_payload
from tests.test_api_projects_db import api, _create, _h, WORKSPACE_A


def test_hosted_profile_edit_and_replay_keep_one_project_revision_and_one_profile(api):
    project_id = _create(api, key="transport-create")
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}"
    body = {"offer": "Updated fixture product and value proposition."}
    headers = _h(key="transport-edit", **{"X-BuyerOS-If-Match": '"1"'})
    edited = api.patch(path, json=body, headers=headers)
    assert edited.status_code == 200, edited.text
    project = edited.json()["data"]
    assert project["version"] == project["offer_revision"] == 2
    assert edited.headers["ETag"] == '"2"'

    payload = valid_icp_payload()
    payload["basis_offer_revision"] = 2
    saved = api.post(path + "/icp-versions", json=payload, headers=_h(key="transport-edit"))
    assert saved.status_code == 201, saved.text
    # The transport carrier changes no canonical request identity: a native
    # If-Match replay of the original completed request returns the same receipt.
    for replay_headers in (headers, _h(key="transport-edit", **{"If-Match": '"1"'})):
        replay = api.patch(path, json=body, headers=replay_headers)
        assert replay.status_code == 200, replay.text
        assert replay.json()["data"] == project
    replay_profile = api.post(path + "/icp-versions", json=payload, headers=_h(key="transport-edit"))
    assert replay_profile.status_code == 201
    assert replay_profile.json()["data"] == saved.json()["data"]
    current = api.get(path, headers=_h()).json()["data"]
    assert current["version"] == current["offer_revision"] == 2
    profiles = api.get(path + "/icp-versions", headers=_h()).json()["data"]
    assert profiles["total"] == 1
    assert profiles["items"][0]["basis_offer_revision"] == 2


def test_hosted_precondition_keeps_stale_role_and_workspace_guards(api, seeded):
    project_id = _create(api, key="transport-guards-create")
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{project_id}"
    body = {"name": "Rejected edit"}
    stale = api.patch(path, json=body, headers=_h(key="transport-stale", **{"X-BuyerOS-If-Match": '"2"'}))
    assert stale.status_code == 412, stale.text
    assert stale.json()["code"] == "STALE_REVISION"
    # Reviewers may update projects; use an actual persisted viewer membership.
    with psycopg.connect(seeded, autocommit=True) as owner:
        owner.execute("UPDATE memberships SET roles = ARRAY['viewer'] WHERE user_id = %s",
                      (uuid.uuid5(uuid.NAMESPACE_URL, "auth0|reviewer-a"),))
    denied = api.patch(path, json=body, headers=_h(subject="auth0|reviewer-a", key="transport-role", **{"X-BuyerOS-If-Match": '"1"'}))
    assert denied.status_code == 403, denied.text
    other = path.replace(WORKSPACE_A, "22222222-2222-4222-8222-222222222222")
    hidden = api.patch(other, json=body, headers=_h(key="transport-workspace", **{"X-BuyerOS-If-Match": '"1"'}))
    assert hidden.status_code in (403, 404), hidden.text
    current = api.get(path, headers=_h()).json()["data"]
    assert current["version"] == current["offer_revision"] == 1
    assert current["name"] == "Sensors Europe"
