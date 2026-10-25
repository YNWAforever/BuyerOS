"""Existing research and saved drafts stay scoped under real PostgreSQL/RLS."""

from contextlib import contextmanager
import uuid

import psycopg

from tests import auth_fixtures as fx
from tests.test_api_projects_db import OPERATOR, WORKSPACE_A, _h, api
from tests.test_api_projects_db import api as project_api
from tests.test_draft_persistence_db import _prepare, _seed_draft
from tests.test_lookup_quotes_db import quote_case
from tests.test_run_admission_integration_db import _post, admission_case


WORKSPACE_B = "22222222-2222-4222-8222-222222222222"


@contextmanager
def _destination_operator(dsn):
    """A real fixture member of B who has no membership in source workspace A."""
    user_id, membership_id = uuid.uuid4(), uuid.uuid4()
    subject = f"auth0|core-scope-b-{user_id}"
    try:
        with psycopg.connect(dsn, autocommit=True) as db:
            db.execute("INSERT INTO users(id,issuer,subject) VALUES (%s,%s,%s)",
                       (user_id, fx.ISSUER, subject))
            db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) "
                       "VALUES (%s,%s,%s,'{operator}',true)",
                       (membership_id, WORKSPACE_B, user_id))
        yield subject
    finally:
        with psycopg.connect(dsn, autocommit=True) as db:
            db.execute("DELETE FROM api_rate_windows WHERE workspace_id=%s AND actor_id=%s",
                       (WORKSPACE_B, user_id))
            db.execute("DELETE FROM memberships WHERE id=%s", (membership_id,))
            db.execute("DELETE FROM users WHERE id=%s", (user_id,))


@contextmanager
def _revoked_source_operator(dsn):
    user_id = uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR)
    with psycopg.connect(dsn, autocommit=True) as db:
        changed = db.execute("UPDATE memberships SET active=false "
                             "WHERE workspace_id=%s AND user_id=%s AND active=true RETURNING id",
                             (WORKSPACE_A, user_id)).fetchall()
        assert len(changed) == 1
    try:
        yield
    finally:
        with psycopg.connect(dsn, autocommit=True) as db:
            db.execute("UPDATE memberships SET active=true WHERE id=%s", (changed[0][0],))


def _assert_destination_access(client, subject):
    response = client.get(f"/v1/workspaces/{WORKSPACE_B}/projects", headers=_h(subject))
    assert response.status_code == 200, response.text
    assert {project["name"] for project in response.json()["data"]["items"]} == {"ProjectB"}


def _assert_hidden(response):
    assert response.status_code == 404, response.text
    assert response.json()["code"] == "NOT_FOUND"


def _run_state(dsn, run_id):
    with psycopg.connect(dsn) as db:
        run = db.execute("SELECT to_jsonb(r) FROM search_runs r "
                         "WHERE workspace_id=%s AND id=%s", (WORKSPACE_A, run_id)).fetchone()
        assert run is not None
        events = db.execute("SELECT to_jsonb(e) FROM run_events e "
                            "WHERE workspace_id=%s AND run_id=%s ORDER BY sequence",
                            (WORKSPACE_A, run_id)).fetchall()
        outbox = db.execute("SELECT to_jsonb(e) FROM outbox_events e "
                            "WHERE workspace_id=%s AND payload->>'run_id'=%s ORDER BY id",
                            (WORKSPACE_A, run_id)).fetchall()
        return run, events, outbox


def _draft_state(dsn, draft_id):
    with psycopg.connect(dsn) as db:
        draft = db.execute("SELECT to_jsonb(d) FROM outreach_drafts d "
                           "WHERE workspace_id=%s AND id=%s", (WORKSPACE_A, draft_id)).fetchone()
        assert draft is not None
        revisions = db.execute("SELECT to_jsonb(r) FROM draft_revisions r "
                               "WHERE workspace_id=%s AND draft_id=%s ORDER BY revision_number",
                               (WORKSPACE_A, draft_id)).fetchall()
        return draft, revisions


def _save_draft(case, key):
    client, dsn, buyers = case
    evidence_id = _prepare(client, dsn, buyers[0][0])
    draft_id = _seed_draft(dsn, buyers[0][0], evidence_id)
    path = f"/v1/workspaces/{WORKSPACE_A}/drafts/{draft_id}"
    body = {"body": "Saved synthetic core-flow draft; do not send."}
    headers = _h(key=key, **{"If-Match": '"1"'})
    saved = client.patch(path, json=body, headers=headers)
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["revision_number"] == 2
    assert saved.json()["data"]["delivery_enabled"] is False
    return path, draft_id, body, headers, saved.json()["data"]


def test_existing_run_cannot_be_read_cancelled_or_retried_through_another_workspace(admission_case):
    client, dsn = admission_case
    created = _post(client, key="core-scope-run-source")
    assert created.status_code == 202, created.text
    run_id = created.json()["data"]["id"]
    original = _run_state(dsn, run_id)
    assert original[1] and original[2]
    with _destination_operator(dsn) as subject:
        _assert_destination_access(client, subject)
        path = f"/v1/workspaces/{WORKSPACE_B}/runs/{run_id}"
        _assert_hidden(client.get(path, headers=_h(subject)))
        _assert_hidden(client.get(path + "/events", headers=_h(subject)))
        _assert_hidden(client.post(path + "/cancel", json={"reason": "Foreign mutation"},
            headers=_h(subject, key="core-scope-foreign-cancel", **{"If-Match": '"1"'})))
        _assert_hidden(client.post(path + "/retry",
            json={"reason": "Foreign retry", "resume_from_last_committed_checkpoint": True},
            headers=_h(subject, key="core-scope-foreign-retry", **{"If-Match": '"1"'})))
        _assert_hidden(client.get(f"/v1/workspaces/{WORKSPACE_A}/runs/{run_id}",
                                  headers=_h(subject)))
    assert _run_state(dsn, run_id) == original
    source = client.get(f"/v1/workspaces/{WORKSPACE_A}/runs/{run_id}", headers=_h())
    assert source.status_code == 200, source.text
    assert source.json()["data"]["id"] == run_id


def test_existing_saved_draft_cannot_be_read_or_edited_through_another_workspace(quote_case):
    client, dsn, _ = quote_case
    source_path, draft_id, _, _, saved = _save_draft(quote_case, "core-scope-draft-source")
    original = _draft_state(dsn, draft_id)
    with _destination_operator(dsn) as subject:
        _assert_destination_access(client, subject)
        path = f"/v1/workspaces/{WORKSPACE_B}/drafts/{draft_id}"
        _assert_hidden(client.get(path, headers=_h(subject)))
        for _ in range(2):
            _assert_hidden(client.patch(path, json={"body": "Foreign overwrite"},
                headers=_h(subject, key="core-scope-foreign-edit", **{"If-Match": '"2"'})))
        _assert_hidden(client.get(source_path, headers=_h(subject)))
    assert _draft_state(dsn, draft_id) == original
    readback = client.get(source_path, headers=_h())
    assert readback.status_code == 200, readback.text
    assert readback.json()["data"]["body"] == saved["body"]
    assert readback.json()["data"]["revision_number"] == 2


def test_revoked_membership_cannot_replay_saved_run_admission(admission_case):
    client, dsn = admission_case
    key = "core-scope-revoked-admission"
    created = _post(client, key=key)
    assert created.status_code == 202, created.text
    run_id = created.json()["data"]["id"]
    replay = _post(client, key=key)
    assert replay.status_code == 202, replay.text
    assert replay.json()["data"] == created.json()["data"]
    original = _run_state(dsn, run_id)
    with _revoked_source_operator(dsn):
        _assert_hidden(_post(client, key=key))
        _assert_hidden(client.get(f"/v1/workspaces/{WORKSPACE_A}/runs/{run_id}", headers=_h()))
    assert _run_state(dsn, run_id) == original


def test_revoked_membership_cannot_replay_saved_draft_edit(quote_case):
    client, dsn, _ = quote_case
    path, draft_id, body, headers, saved = _save_draft(quote_case, "core-scope-revoked-edit")
    replay = client.patch(path, json=body, headers=headers)
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"] == saved
    original = _draft_state(dsn, draft_id)
    with _revoked_source_operator(dsn):
        _assert_hidden(client.patch(path, json=body, headers=headers))
        _assert_hidden(client.get(path, headers=_h()))
    assert _draft_state(dsn, draft_id) == original
