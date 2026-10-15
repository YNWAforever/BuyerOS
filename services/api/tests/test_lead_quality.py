import copy
import importlib
import importlib.util
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from buyeros_api.api.lead_schemas import LeadObservationRecord

NOW = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)
PERSON, CONTACT = uuid.UUID(int=101), uuid.UUID(int=102)


def observation(claim, *, age=timedelta(0), seq=1, stance="supports", official=True):
    return LeadObservationRecord(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"{claim}:{seq}"), workspace_id=uuid.UUID(int=1),
        project_id=uuid.UUID(int=2), buyer_id=uuid.UUID(int=3), company_id=uuid.UUID(int=4),
        person_id=PERSON, contact_id=CONTACT if claim == "channel_ownership" else None,
        claim=claim, stance=stance, checked_at=NOW-age, content_hash=f"sha256:{claim}:{seq}",
        supersedes_id=None, recorded_by_user_id=uuid.UUID(int=5), created_at=NOW-age,
        sources=[{"title": "Team", "url": "https://rice.example.test/team",
                  "excerpt": "Named person has current rice procurement responsibility.",
                  "source_kind": "official" if official else "professional"}],
        rationale="Human source check", limitations=None,
        person={"id": str(PERSON), "full_name": "Alex Fixture", "role": "Purchasing Manager"},
        channel=({"id": str(CONTACT), "type": "business_email", "value": "alex@rice.example.test",
                  "person_id": str(PERSON), "validity": "unverified_public", "checked_at": None}
                 if claim == "channel_ownership" else None),
        redacted=False, availability="available",
    )


def quality(observations, *, review_changes=None, now=NOW):
    assert importlib.util.find_spec("buyeros_api.services.lead_quality") is not None, "lead quality feature is missing"
    module = importlib.import_module("buyeros_api.services.lead_quality")
    schemas = importlib.import_module("buyeros_api.api.lead_schemas")
    review = {
        "id": str(uuid.UUID(int=20)), "workspace_id": str(uuid.UUID(int=1)),
        "project_id": str(uuid.UUID(int=2)), "buyer_id": str(uuid.UUID(int=3)),
        "company_id": str(uuid.UUID(int=4)), "person_id": str(PERSON), "contact_id": str(CONTACT),
        "employment": "accepted", "procurement_scope": "accepted", "channel_ownership": "accepted",
        "case_version": 4, "context_hash": "sha256:fixture", "context_current": True,
        "observation_ids": [str(row.id) for row in observations], "previous_review_id": None,
        "recorded_by_user_id": str(uuid.UUID(int=5)), "created_at": NOW.isoformat(),
        "rationale": "Checked all cited sources", "conflict_resolution": None, "redacted": False,
    }
    review.update(review_changes or {})
    return module.evaluate_lead_quality(
        observations=observations, review=schemas.LeadReviewRecord.model_validate(review), now=now,
    )


@pytest.mark.parametrize("claim,age,want_person,want_channel", [
    ("employment", timedelta(days=30)-timedelta(seconds=1), True, True),
    ("employment", timedelta(days=30), False, False),
    ("procurement_scope", timedelta(days=30), False, False),
    ("channel_ownership", timedelta(days=7)-timedelta(seconds=1), True, True),
    ("channel_ownership", timedelta(days=7), True, False),
    ("employment", -timedelta(seconds=1), False, False),
], ids=["role_before_30d", "role_at_30d", "procurement_at_30d", "channel_before_7d", "channel_at_7d", "future"])
def test_freshness_boundary_and_future_observation(claim, age, want_person, want_channel):
    rows = [observation(kind, age=age if kind == claim else timedelta(0))
            for kind in ("employment", "procurement_scope", "channel_ownership")]
    actual = quality(rows)
    assert actual.qualified_person is want_person
    assert actual.direct_channel is want_channel
    hong_kong = quality(rows, now=NOW.astimezone(timezone(timedelta(hours=8))))
    assert hong_kong.model_dump() == actual.model_dump()


def test_public_channel_can_be_source_verified_without_technical_upgrade():
    rows = [observation(kind) for kind in ("employment", "procurement_scope", "channel_ownership")]
    before = copy.deepcopy(rows[-1].channel)
    result = quality(rows)
    assert result.qualified_person is True
    assert result.direct_channel is True
    assert rows[-1].channel == before
    assert before["validity"] == "unverified_public"


@pytest.mark.parametrize("mode", ["missing_procurement", "no_official_role", "shared_inbox", "department_form", "redacted", "stale_context"])
def test_evidence_gaps_do_not_turn_into_a_qualified_direct_contact(mode):
    rows = [observation(kind) for kind in ("employment", "procurement_scope", "channel_ownership")]
    changes = {}
    if mode == "missing_procurement":
        rows = [row for row in rows if row.claim != "procurement_scope"]
    elif mode == "no_official_role":
        for row in rows[:2]:
            row.sources[0].source_kind = "professional"
    elif mode == "shared_inbox":
        rows[-1].channel["value"] = "purchasing@rice.example.test"
    elif mode == "department_form":
        rows[-1].channel["type"] = "procurement_form"
    elif mode == "redacted":
        rows[0].redacted, rows[0].availability = True, "expired"
    else:
        changes["context_current"] = False
    result = quality(rows, review_changes=changes)
    assert result.direct_channel is False
    if mode not in {"shared_inbox", "department_form"}:
        assert result.qualified_person is False


def test_conflicting_new_evidence_requires_new_review():
    original = [observation(kind) for kind in ("employment", "procurement_scope", "channel_ownership")]
    refute = observation("employment", seq=2, stance="refutes")
    old_ids = [str(row.id) for row in original]
    assert quality(original + [refute], review_changes={"observation_ids": old_ids}).needs_review is True
    assert quality(original + [refute]).qualified_person is False
    resolved = quality(original + [refute], review_changes={
        "conflict_resolution": "The official current team page is confirmed; the other source is archived.",
    })
    assert resolved.qualified_person is True


def test_unrelated_same_company_candidate_does_not_invalidate_selected_person():
    rows = [observation(kind) for kind in ("employment", "procurement_scope", "channel_ownership")]
    other = observation("employment", seq=3)
    other.person_id = uuid.UUID(int=999)
    result = quality(rows + [other], review_changes={"observation_ids": [str(row.id) for row in rows]})
    assert result.qualified_person is True


def test_corrected_channel_invalidates_old_selected_context():
    rows = [observation(kind) for kind in ("employment", "procurement_scope", "channel_ownership")]
    replacement = observation("channel_ownership", seq=2)
    replacement.contact_id = uuid.UUID(int=103)
    replacement.channel["id"] = str(replacement.contact_id)
    replacement.supersedes_id = rows[-1].id
    result = quality(rows + [replacement], review_changes={"observation_ids": [str(row.id) for row in rows]})
    assert result.direct_channel is False
    assert result.needs_review is True
