"""T24: reviewed sender identity is versioned project configuration."""

import uuid

import psycopg

from tests.test_api_projects_db import ADMIN, OPERATOR, REVIEWER, WORKSPACE_A, _h, api

PROJECT_A = "a0000000-0000-4000-8000-000000000001"


def _sender(name: str = "Alex Chan") -> dict:
    return {
        "display_name": name,
        "role_title": "Partnerships Lead",
        "organization": "ProjectA Co",
        "business_email": "alex@example.test",
        "country": "US",
        "sender_confirmation": True,
        "reason": "Approved sender metadata for draft preparation",
    }


def test_reviewer_creates_immutable_sender_version_and_get_roundtrip(api, seeded):
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}"
    response = api.patch(path, json={"sender_identity": _sender()},
                         headers=_h(REVIEWER, key="sender-create-001", **{"If-Match": '"1"'}))
    assert response.status_code == 200, response.text
    sender = response.json()["data"]["sender_identity"]
    assert sender["display_name"] == "Alex Chan"
    assert sender["status"] == "approved"
    assert sender["version_key"].startswith("sender:")
    assert sender["reviewed_by"] == str(uuid.uuid5(uuid.NAMESPACE_URL, REVIEWER))
    assert api.get(path, headers=_h(REVIEWER)).json()["data"]["sender_identity"] == sender
    with psycopg.connect(seeded) as db:
        assert db.execute("SELECT count(*) FROM sender_identity_versions WHERE project_id=%s",
                          (PROJECT_A,)).fetchone()[0] == 1


def test_operator_cannot_approve_sender_metadata(api):
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}"
    response = api.patch(path, json={"sender_identity": _sender()},
                         headers=_h(OPERATOR, key="sender-denied-001", **{"If-Match": '"1"'}))
    assert response.status_code == 403, response.text


def test_replacement_retires_old_version_and_replay_does_not_append(api, seeded):
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}"
    first = api.patch(path, json={"sender_identity": _sender()},
                      headers=_h(ADMIN, key="sender-replace-001", **{"If-Match": '"1"'}))
    assert first.status_code == 200, first.text
    old = first.json()["data"]["sender_identity"]
    replacement = api.patch(path, json={"sender_identity": _sender("Rina Patel")},
                            headers=_h(REVIEWER, key="sender-replace-002", **{"If-Match": '"2"'}))
    assert replacement.status_code == 200, replacement.text
    current = replacement.json()["data"]["sender_identity"]
    assert current["version_key"] != old["version_key"]
    assert current["version_key"].endswith(":2")
    assert current["display_name"] == "Rina Patel"
    replay = api.patch(path, json={"sender_identity": _sender("Rina Patel")},
                       headers=_h(REVIEWER, key="sender-replace-002", **{"If-Match": '"2"'}))
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["sender_identity"] == current
    with psycopg.connect(seeded) as db:
        rows = db.execute("SELECT version_key,retired FROM sender_identity_versions "
                          "WHERE project_id=%s ORDER BY created_at,id", (PROJECT_A,)).fetchall()
        assert len(rows) == 2
        assert dict(rows)[old["version_key"]] is True
        assert dict(rows)[current["version_key"]] is False
        assert db.execute("SELECT count(*) FROM audit_events WHERE subject_id=%s "
                          "AND action='sender_identity.reviewed'", (PROJECT_A,)).fetchone()[0] == 2


def test_sender_confirmation_reason_and_stale_precondition_are_required(api):
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}"
    for change in ({"sender_confirmation": False}, {"reason": ""}, {"business_email": "invalid"}):
        payload = _sender() | change
        response = api.patch(path, json={"sender_identity": payload},
                             headers=_h(REVIEWER, key="sender-invalid-001", **{"If-Match": '"1"'}))
        assert response.status_code == 422, response.text
    first = api.patch(path, json={"sender_identity": _sender()},
                      headers=_h(REVIEWER, key="sender-stale-001", **{"If-Match": '"1"'}))
    assert first.status_code == 200, first.text
    stale = api.patch(path, json={"sender_identity": _sender("Stale Name")},
                      headers=_h(REVIEWER, key="sender-stale-002", **{"If-Match": '"1"'}))
    assert stale.status_code == 412, stale.text


def test_sender_content_is_immutable_and_active_pointer_stays_in_project(api, seeded):
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}"
    first = api.patch(path, json={"sender_identity": _sender()},
                      headers=_h(REVIEWER, key="sender-fk-001", **{"If-Match": '"1"'}))
    assert first.status_code == 200, first.text
    sender_id = first.json()["data"]["sender_identity"]["id"]
    with psycopg.connect(seeded) as db:
        try:
            with db.transaction():
                db.execute("UPDATE sender_identity_versions SET display_name='forged' WHERE id=%s", (sender_id,))
        except psycopg.Error:
            pass
        else:
            raise AssertionError("immutable sender content was modified")
        other_project = uuid.uuid4()
        foreign_sender = uuid.uuid4()
        db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) "
                   "VALUES (%s,%s,'Other','Other Co','Other offer',ARRAY['US'],ARRAY['en'],1)",
                   (other_project, WORKSPACE_A))
        db.execute("INSERT INTO sender_identity_versions(id,workspace_id,project_id,version_key,display_name,"
                   "organization,business_email) VALUES (%s,%s,%s,%s,'Other','Other Co','other@example.test')",
                   (foreign_sender, WORKSPACE_A, other_project, f"sender:{foreign_sender}:1"))
        try:
            with db.transaction():
                db.execute("UPDATE projects SET active_sender_identity_version_id=%s WHERE id=%s",
                           (foreign_sender, PROJECT_A))
        except psycopg.errors.ForeignKeyViolation:
            pass
        else:
            raise AssertionError("foreign-project sender pointer was accepted")
        db.execute("DELETE FROM sender_identity_versions WHERE id=%s", (foreign_sender,))
        db.execute("DELETE FROM projects WHERE id=%s", (other_project,))
