"""Q09 current canonical actor names without authority or history changes."""
import uuid
import psycopg
from tests.contract_validation import assert_contract_response
from tests.test_api_projects_db import api
from tests.test_lookup_quotes_db import OPERATOR, WORKSPACE_A, PROJECT, _h, quote_case


def test_manual_event_projects_canonical_name_and_replay_does_not_relink(quote_case):
    api, dsn, buyers = quote_case
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/outcomes"
    body = {"buyer_id": buyers[0][0], "stage": "reply", "source": "manual",
            "occurred_at": "2026-09-20T11:15:00Z", "notes": "Q09 staff-reported reply"}
    with psycopg.connect(dsn) as db:
        actor = uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR)
        db.execute("UPDATE users SET display_name='Q09 Fictional Operator' WHERE id=%s", (actor,))
    response = api.post(path, json=body, headers=_h(OPERATOR, key="q09-canonical-name"))
    assert response.status_code == 201, response.text
    event = response.json()["data"]
    assert event["actor_display_name"] == "Q09 Fictional Operator"
    assert event["actor_id"] == str(actor)
    assert_contract_response("OutcomeEventResponse", response.json())
    with psycopg.connect(dsn) as db:
        before = db.execute("SELECT count(*) FROM outcome_events WHERE project_id=%s", (PROJECT,)).fetchone()[0]
        db.execute("UPDATE users SET display_name='Q09 Renamed Operator' WHERE id=%s", (actor,))
    replay = api.post(path, json=body, headers=_h(OPERATOR, key="q09-canonical-name"))
    assert replay.status_code == 201
    assert replay.json()["data"]["id"] == event["id"]
    assert replay.json()["data"]["actor_id"] == event["actor_id"]
    assert replay.json()["data"]["actor_display_name"] == "Q09 Renamed Operator"
    listed = api.get(path, headers=_h(OPERATOR)).json()["data"]
    assert listed["items"][0]["actor_display_name"] == "Q09 Renamed Operator"
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT count(*) FROM outcome_events WHERE project_id=%s", (PROJECT,)).fetchone()[0] == before
        assert db.execute("SELECT actor_user_id FROM outcome_events WHERE id=%s", (event["id"],)).fetchone()[0] == actor


def test_missing_actor_name_is_null_and_other_tenant_events_not_exposed(quote_case):
    api, dsn, buyers = quote_case
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/outcomes"
    response = api.post(path, json={"buyer_id": buyers[0][0], "stage": "meeting", "source": "manual",
        "occurred_at": "2026-09-20T11:15:00Z", "notes": "Q09 unnamed canonical actor"}, headers=_h(OPERATOR, key="q09-null-name"))
    assert response.status_code == 201
    actor = response.json()["data"]["actor_id"]
    with psycopg.connect(dsn) as db:
        db.execute("UPDATE users SET display_name=NULL WHERE id=%s", (actor,))
    events = api.get(path, headers=_h(OPERATOR))
    assert events.status_code == 200
    assert events.json()["data"]["items"][0]["actor_display_name"] is None
    assert_contract_response("OutcomeEventPageResponse", events.json())
    foreign_workspace = "22222222-2222-4222-8222-222222222222"
    foreign_project = "b0000000-0000-4000-8000-000000000002"
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT workspace_id FROM projects WHERE id=%s", (foreign_project,)).fetchone()[0] == uuid.UUID(foreign_workspace)
    denied = api.get(f"/v1/workspaces/{foreign_workspace}/projects/{foreign_project}/outcomes", headers=_h(OPERATOR))
    assert denied.status_code == 404  # Existing non-enumerating membership contract.
    assert denied.json()["code"] == "NOT_FOUND"
    assert "data" not in denied.json()
    assert "Q09 unnamed canonical actor" not in denied.text
