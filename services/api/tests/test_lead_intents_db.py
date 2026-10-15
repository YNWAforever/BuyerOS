import copy
import uuid
from datetime import datetime, timedelta, timezone

import psycopg

from tests.lead_fixtures import (
    ACTORS, WORKSPACE, PROJECT, headers, observation_payload, prepare, apply, save_observation,
    lead_api, lead_case,
)


def test_intent_prepare_unknown_apply_unknown_and_exact_replay(lead_api, lead_case):
    payload, key = observation_payload(), str(uuid.uuid4())
    first = prepare(lead_api, lead_case, "observation.append", payload, key=key)
    assert first.status_code == 201, first.text
    intent = first.json()["data"]
    recovered = lead_api.get(f"{lead_case['base']}/lead-intents", headers=headers()).json()["data"]["items"]
    assert [row["id"] for row in recovered] == [intent["id"]]
    # Simulates losing the prepare response: an exact re-submit returns the same intent.
    assert prepare(lead_api, lead_case, "observation.append", payload, key=key).json()["data"]["id"] == intent["id"]
    original = apply(lead_api, lead_case, intent)
    assert original.status_code == 200, original.text
    receipt = original.json()["data"]
    # Simulates losing an applied response; recoverable until explicitly acknowledged.
    listed = lead_api.get(f"{lead_case['base']}/lead-intents", headers=headers()).json()["data"]["items"]
    assert listed[0]["state"] == "applied"
    replay = apply(lead_api, lead_case, intent)
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"] == receipt
    with psycopg.connect(lead_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM lead_observations").fetchone() == (1,)
        assert db.execute("SELECT count(*) FROM people").fetchone() == (1,)
        assert db.execute("SELECT count(*) FROM outbox_events").fetchone() == (0,)
    ack = lead_api.post(
        f"{lead_case['base']}/lead-intents/{intent['id']}/acknowledgements", json={},
        headers=headers(key=f"ack-{intent['id']}"),
    )
    assert ack.status_code == 200, ack.text
    assert lead_api.get(f"{lead_case['base']}/lead-intents", headers=headers()).json()["data"]["items"] == []


def test_conflicting_prepare_or_submission_key_cannot_change_original_request(lead_api, lead_case):
    payload, key = observation_payload(), str(uuid.uuid4())
    original = prepare(lead_api, lead_case, "observation.append", payload, key=key)
    assert original.status_code == 201, original.text
    changed = dict(payload, rationale="Different content")
    assert prepare(lead_api, lead_case, "observation.append", changed, key=key).status_code == 409
    intent = original.json()["data"]
    invalid = lead_api.post(
        f"{lead_case['base']}/lead-intents/{intent['id']}/apply", json={},
        headers=headers(key="a-different-submission-key"),
    )
    assert invalid.status_code == 409, invalid.text
    assert apply(lead_api, lead_case, intent).status_code == 200


def test_unresolved_exact_fingerprint_does_not_create_second_intent(lead_api, lead_case):
    payload = observation_payload()
    first = prepare(lead_api, lead_case, "observation.append", payload)
    second = prepare(lead_api, lead_case, "observation.append", payload)
    assert first.status_code == second.status_code == 201, (first.text, second.text)
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    with psycopg.connect(lead_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM lead_action_intents").fetchone() == (1,)


def test_revoked_actor_cannot_read_apply_or_replay_intent(lead_api, lead_case):
    _, intent, _ = save_observation(lead_api, lead_case)
    with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
        db.execute("UPDATE memberships SET roles=ARRAY['viewer'],version=version+1 WHERE user_id=%s",
                   (ACTORS["operator"],))
    assert lead_api.get(f"{lead_case['base']}/lead-intents/{intent['id']}", headers=headers()).status_code == 403
    assert apply(lead_api, lead_case, intent).status_code == 403
    hidden = lead_api.get(f"{lead_case['base']}/lead-intents/{intent['id']}", headers=headers("workspace_admin"))
    assert hidden.status_code == 404


def test_retention_redacts_recoverable_payload_and_replay(lead_api, lead_case):
    row, intent, receipt = save_observation(lead_api, lead_case)
    with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
        db.execute("UPDATE people SET retention_expires_at=now()-interval '1 day' WHERE id=%s", (row["person_id"],))
        db.execute("SELECT set_config('app.workspace_id',%s,false)", (WORKSPACE,))
        db.execute("SELECT buyeros_redact_lead_subject(%s,'person',%s)", (WORKSPACE, row["person_id"]))
    result = apply(lead_api, lead_case, intent)
    assert result.status_code == 200, result.text
    assert result.json()["data"]["resource_id"] == receipt["resource_id"]
    assert result.json()["data"]["redacted"] is True
    evidence = lead_api.get(f"{lead_case['base']}/buyers/{lead_case['buyer_id']}/lead-evidence", headers=headers())
    assert "Alex Test" not in evidence.text
    assert "Alex Test" not in result.text
    assert evidence.json()["data"]["items"][0]["redacted"] is True
    with psycopg.connect(lead_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM lead_observations").fetchone() == (1,)
        assert db.execute(
            "SELECT count(*) FROM lead_private_payloads WHERE contents::text LIKE '%Alex Test%'"
        ).fetchone() == (0,)


def test_cancel_only_prepared_and_never_undoes_applied_write(lead_api, lead_case):
    prepared = prepare(lead_api, lead_case, "observation.append", observation_payload())
    assert prepared.status_code == 201, prepared.text
    intent = prepared.json()["data"]
    cancelled = lead_api.post(
        f"{lead_case['base']}/lead-intents/{intent['id']}/cancel", json={},
        headers=headers(key=f"cancel-{intent['id']}"),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["state"] == "cancelled"
    assert apply(lead_api, lead_case, intent).status_code == 409
    _, committed, _ = save_observation(lead_api, lead_case)
    no_undo = lead_api.post(
        f"{lead_case['base']}/lead-intents/{committed['id']}/cancel", json={},
        headers=headers(key=f"cancel-{committed['id']}"),
    )
    assert no_undo.status_code == 200
    assert no_undo.json()["data"]["state"] == "applied"
