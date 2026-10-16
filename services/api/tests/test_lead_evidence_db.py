import copy
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from tests.lead_fixtures import (
    ACTORS, WORKSPACE, PROJECT, headers, observation_payload, prepare, save_observation,
    lead_api, lead_case,
)


@pytest.mark.parametrize("field,value", [
    ("sources", []),
    ("sources", [observation_payload()["sources"][0]] * 11),
    ("rationale", "x" * 4001),
    ("checked_at", (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()),
    ("validity", "provider_marked_valid"),
], ids=["empty_sources", "eleven_sources", "long_rationale", "future_checked_at", "injected_validity"])
def test_observation_payload_scope_and_limits(lead_api, lead_case, field, value):
    response = prepare(lead_api, lead_case, "observation.append", observation_payload(**{field: value}))
    assert response.status_code == 422, response.text
    with psycopg.connect(lead_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM lead_observations").fetchone() == (0,)
        assert db.execute("SELECT count(*) FROM lead_action_intents").fetchone() == (0,)


@pytest.mark.parametrize("bad_source", [
    {"url": "javascript:alert(1)"},
    {"url": "https://user:pass@rice.example.test/"},
    {"excerpt": "x" * 4001},
    {"title": " "},
])
def test_observation_rejects_unsafe_or_unbounded_source(lead_api, lead_case, bad_source):
    payload = observation_payload()
    payload["sources"][0].update(bad_source)
    response = prepare(lead_api, lead_case, "observation.append", payload)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("source_count", [1, 10])
def test_observation_persists_native_sources_and_preserves_technical_status(lead_api, lead_case, source_count):
    payload = observation_payload(rationale="x" * 4000)
    payload["sources"] = [copy.deepcopy(payload["sources"][0]) for _ in range(source_count)]
    row, _, _ = save_observation(lead_api, lead_case, payload)
    assert len(row["sources"]) == source_count
    assert row["rationale"] == "x" * 4000
    assert row["checked_at"] == payload["checked_at"].replace("+00:00", "Z")
    with psycopg.connect(lead_case["dsn"]) as db:
        assert db.execute("SELECT full_name FROM people WHERE id=%s", (row["person_id"],)).fetchone() == ("Alex Test",)
        assert db.execute("SELECT count(*) FROM evidence").fetchone() == (0,)
        assert db.execute("SELECT count(*) FROM provider_operations").fetchone() == (0,)


def test_foreign_buyer_and_person_are_not_disclosed(lead_api, lead_case):
    legitimate = prepare(lead_api, lead_case, "observation.append", observation_payload())
    assert legitimate.status_code == 201, legitimate.text
    foreign = dict(lead_case, buyer_id=lead_case["other_buyer_id"])
    assert prepare(lead_api, foreign, "observation.append", observation_payload()).status_code == 404
    outsider = uuid.uuid4()
    with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
        db.execute("INSERT INTO people(id,workspace_id,company_id) VALUES (%s,%s,%s)",
                   (outsider, "22222222-2222-4222-8222-222222222222", lead_case["other_company_id"]))
    payload = observation_payload(person={"person_id": str(outsider)})
    assert prepare(lead_api, lead_case, "observation.append", payload).status_code == 404


def test_homonyms_and_shared_channels_keep_identity_and_status(lead_api, lead_case):
    first, _, _ = save_observation(lead_api, lead_case)
    second, _, _ = save_observation(lead_api, lead_case, observation_payload(rationale="A different same-name candidate."))
    assert first["person_id"] != second["person_id"]
    shared = observation_payload(
        claim="channel_ownership", person={"person_id": first["person_id"]},
        channel={"type": "business_email", "value": "purchasing@rice.example.test", "person_id": first["person_id"]},
    )
    channel, _, _ = save_observation(lead_api, lead_case, shared)
    with psycopg.connect(lead_case["dsn"]) as db:
        assert db.execute("SELECT validity,checked_at FROM contact_points WHERE id=%s", (channel["contact_id"],)).fetchone() == ("unverified_public", None)
    conflict = copy.deepcopy(shared)
    conflict["person"] = {"person_id": second["person_id"]}
    conflict["channel"]["person_id"] = second["person_id"]
    assert prepare(lead_api, lead_case, "observation.append", conflict).status_code == 409
    with psycopg.connect(lead_case["dsn"]) as db:
        assert str(db.execute("SELECT person_id FROM contact_points WHERE id=%s", (channel["contact_id"],)).fetchone()[0]) == first["person_id"]


def test_missing_or_suppressed_policy_blocks_manual_personal_data(lead_api, lead_case):
    with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
        db.execute("DELETE FROM policy_decisions WHERE purpose='contact_research'")
    result = prepare(lead_api, lead_case, "observation.append", observation_payload())
    assert result.status_code == 403, result.text
    with psycopg.connect(lead_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM people").fetchone() == (0,)
        assert db.execute("SELECT count(*) FROM lead_action_intents").fetchone() == (0,)


def test_viewer_cannot_prepare_and_missing_key_is_rejected(lead_api, lead_case):
    assert prepare(lead_api, lead_case, "observation.append", observation_payload(), role="viewer").status_code == 403
    response = lead_api.post(
        f"{lead_case['base']}/lead-intents",
        json={"action": "observation.append", "buyer_id": lead_case["buyer_id"], "payload": observation_payload()},
        headers=headers(),
    )
    assert response.status_code == 400, response.text


@pytest.mark.parametrize("subject,channel_type,first_value,second_value", [
    ("person", "business_email", "alex@rice.example.test", "alex.second@rice.example.test"),
    ("department", "procurement_form", "https://rice.example.test/purchasing", "https://rice.example.test/suppliers"),
    ("referral", "referral", "https://rice.example.test/referral/a", "https://rice.example.test/referral/b"),
])
@pytest.mark.parametrize("correction", ["same_value", "same_id", "other_existing", "other_new"])
def test_channel_correction_preserves_exact_channel_subject(
    lead_api, lead_case, subject, channel_type, first_value, second_value, correction,
):
    """A correction for B must never suppress A, even without a named person."""
    person = None
    if subject == "person":
        employment, _, _ = save_observation(lead_api, lead_case)
        person = {"person_id": employment["person_id"]}
    channel = {"type": channel_type, "value": first_value}
    if person:
        channel["person_id"] = person["person_id"]
    payload = observation_payload(claim="channel_ownership", person=person, channel=channel)
    original, _, _ = save_observation(lead_api, lead_case, payload)
    replacement = copy.deepcopy(payload)
    replacement["supersedes_id"] = original["id"]
    replacement["stance"] = "refutes"
    if correction == "same_id":
        replacement["channel"] = {"contact_id": original["contact_id"]}
        if person:
            replacement["channel"]["person_id"] = person["person_id"]
    elif correction.startswith("other"):
        replacement["channel"]["value"] = second_value
        if correction == "other_existing":
            second_payload = copy.deepcopy(payload)
            second_payload["channel"]["value"] = second_value
            save_observation(lead_api, lead_case, second_payload)
    with psycopg.connect(lead_case["dsn"]) as db:
        before = db.execute("SELECT count(*) FROM lead_observations").fetchone()[0]
        intents_before = db.execute("SELECT count(*) FROM lead_action_intents").fetchone()[0]
    if correction.startswith("same"):
        corrected, _, _ = save_observation(lead_api, lead_case, replacement)
        assert corrected["contact_id"] == original["contact_id"]
        assert corrected["supersedes_id"] == original["id"]
        assert corrected["stance"] == "refutes"
    else:
        rejected = prepare(lead_api, lead_case, "observation.append", replacement)
        assert rejected.status_code == 422, rejected.text
        assert rejected.json()["message"] == "correction must describe the same subject and claim"
        with psycopg.connect(lead_case["dsn"]) as db:
            assert db.execute("SELECT count(*) FROM lead_observations").fetchone() == (before,)
            assert db.execute("SELECT count(*) FROM lead_action_intents").fetchone() == (intents_before,)
            assert db.execute("SELECT count(*) FROM lead_observations WHERE supersedes_id=%s",
                              (original["id"],)).fetchone() == (0,)
            assert str(db.execute("SELECT contact_id FROM lead_observations WHERE id=%s",
                                  (original["id"],)).fetchone()[0]) == original["contact_id"]
