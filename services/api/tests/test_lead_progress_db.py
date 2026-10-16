import asyncio
import importlib.util
import uuid
from datetime import datetime, timezone

import psycopg

from tests.lead_fixtures import (
    ACTORS, WORKSPACE, PROJECT, headers, prepare, apply, observation_payload, save_observation,
    lead_api, lead_case,
)


def check_company(case, buyer=None):
    with psycopg.connect(case["dsn"], autocommit=True) as db:
        db.execute(
            "INSERT INTO buyer_source_checks"
            "(id,workspace_id,project_id,buyer_id,checked_on,grade,rationale,sources,recorded_by_user_id)"
            "VALUES (%s,%s,%s,%s,'2026-10-15','B','Official UK rice wholesale channel',"
            "'[{\"title\":\"Official catalog\",\"url\":\"https://rice.example.test/catalog\"}]',%s)",
            (uuid.uuid4(), WORKSPACE, PROJECT, buyer or case["buyer_id"], ACTORS["workspace_admin"]),
        )


def case_view(api, case):
    response = api.get(f"{case['base']}/buyers/{case['buyer_id']}/lead-workflow", headers=headers())
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_case_read_is_pure_and_stale_case_update_cannot_overwrite(lead_api, lead_case):
    check_company(lead_case)
    initial = case_view(lead_api, lead_case)
    assert initial["version"] == 1 and initial["state_exists"] is False
    with psycopg.connect(lead_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM lead_case_states").fetchone() == (0,)
    payload = {"priority": True, "priority_reason": "Official trade-size rice range", "next_action": "Find purchasing manager"}
    staged = prepare(lead_api, lead_case, "case.update", payload, version=1)
    assert staged.status_code == 201, staged.text
    assert apply(lead_api, lead_case, staged.json()["data"]).status_code == 200
    assert case_view(lead_api, lead_case)["version"] == 2
    stale = prepare(lead_api, lead_case, "case.update", dict(payload, priority=False), version=1)
    assert stale.status_code == 201, stale.text
    assert apply(lead_api, lead_case, stale.json()["data"]).status_code == 412
    assert case_view(lead_api, lead_case)["priority"] is True


def test_conflicting_or_changed_person_evidence_invalidates_selected_review(lead_api, lead_case):
    employment, _, _ = save_observation(lead_api, lead_case)
    procurement, _, _ = save_observation(lead_api, lead_case, observation_payload(
        claim="procurement_scope", person={"person_id": employment["person_id"]},
    ))
    view = case_view(lead_api, lead_case)
    review = {"person_id": employment["person_id"], "contact_id": None,
              "employment": "accepted", "procurement_scope": "accepted", "channel_ownership": "uncertain",
              "observation_ids": [employment["id"], procurement["id"]], "rationale": "Official role and rice category confirmed"}
    staged = prepare(lead_api, lead_case, "lead.review", review, version=view["version"])
    assert staged.status_code == 201, staged.text
    result = apply(lead_api, lead_case, staged.json()["data"])
    assert result.status_code == 200, result.text
    assert case_view(lead_api, lead_case)["quality"]["qualified_person"] is True
    with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
        db.execute("UPDATE people SET role='Finance Director' WHERE id=%s", (employment["person_id"],))
    assert case_view(lead_api, lead_case)["quality"]["needs_review"] is True
    save_observation(lead_api, lead_case, observation_payload(
        claim="employment", stance="refutes", person={"person_id": employment["person_id"]},
    ))
    assert case_view(lead_api, lead_case)["quality"]["qualified_person"] is False


def test_correction_cannot_replace_another_person_with_a_new_identity(lead_api, lead_case):
    original, _, _ = save_observation(lead_api, lead_case)
    response = prepare(lead_api, lead_case, "observation.append",
        observation_payload(person={"full_name": "Someone Else", "role": "Director"},
                            supersedes_id=original["id"]))
    assert response.status_code == 422, response.text


def test_progress_counts_distinct_priority_companies(lead_api, lead_case):
    assert importlib.util.find_spec("buyeros_api.services.lead_progress_service") is not None, "progress feature is missing"
    from sqlalchemy.ext.asyncio import create_async_engine
    from buyeros_api.db.session import tenant_session
    from buyeros_api.api.lead_schemas import LeadScope, LeadCaseUpdate, LeadObservationInput, LeadReviewInput
    from buyeros_api.services.lead_evidence_service import append_observation
    from buyeros_api.services.lead_review_service import append_lead_review, update_lead_case
    from tests.conftest import runtime_role_dsn

    buyers = [(lead_case["buyer_id"], lead_case["company_id"])]
    with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
        for index in range(23):
            company, buyer = uuid.uuid4(), uuid.uuid4()
            db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name,domain) "
                       "VALUES (%s,%s,%s,%s,'rice.example.test')",
                       (company, WORKSPACE, f"Rice Fixture {index}", f"Rice Fixture {index}"))
            db.execute("INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES (%s,%s,%s,%s)",
                       (buyer, WORKSPACE, PROJECT, company))
            buyers.append((str(buyer), str(company)))
    for buyer, _ in buyers:
        check_company(lead_case, buyer)

    async def seed():
        engine = create_async_engine(runtime_role_dsn(lead_case["dsn"]).replace("postgresql://", "postgresql+psycopg://"))
        try:
            for index, (buyer, company) in enumerate(buyers):
                scope = LeadScope(uuid.UUID(WORKSPACE), uuid.UUID(PROJECT), uuid.UUID(buyer),
                                  uuid.UUID(company), ACTORS["operator"], 1, frozenset({"operator"}))
                async with tenant_session(engine, scope.workspace_id) as session:
                    if index < 8:
                        await update_lead_case(session, scope=scope, expected_version=1,
                            data=LeadCaseUpdate(priority=True, priority_reason="Official bulk rice catalog", next_action="Verify purchasing"))
                    if index < 6 or index in {10, 11}:
                        employment = await append_observation(session, scope=scope,
                            data=LeadObservationInput.model_validate(observation_payload()), now=datetime.now(timezone.utc))
                        person = employment["person_id"]
                        procurement = await append_observation(session, scope=scope,
                            data=LeadObservationInput.model_validate(observation_payload(
                                claim="procurement_scope", person={"person_id": person})), now=datetime.now(timezone.utc))
                        ids, contact = [employment["id"], procurement["id"]], None
                        if index < 4 or index in {10, 11}:
                            channel = await append_observation(session, scope=scope,
                                data=LeadObservationInput.model_validate(observation_payload(
                                    claim="channel_ownership", person={"person_id": person},
                                    channel={"type": "business_email", "value": f"buyer{index}@rice.example.test", "person_id": person},
                                )), now=datetime.now(timezone.utc))
                            ids.append(channel["id"])
                            contact = channel["contact_id"]
                        # Case version: initial 1, priority edit if present, then each observation.
                        version = 1 + (index < 8) + len(ids)
                        await append_lead_review(session, scope=scope, expected_version=version,
                            data=LeadReviewInput(person_id=person, contact_id=contact, employment="accepted",
                                procurement_scope="accepted", channel_ownership="accepted" if contact else "uncertain",
                                observation_ids=ids, rationale="All official role and channel sources checked"),
                            now=datetime.now(timezone.utc))
        finally:
            await engine.dispose()
    asyncio.run(seed())
    response = lead_api.get(f"{lead_case['base']}/lead-workflow?limit=5", headers=headers())
    assert response.status_code == 200, response.text
    page = response.json()["data"]
    assert page["total"] == 24 and len(page["items"]) == 5
    assert page["metrics"] == {
        "company_cards": 24, "priority_companies": 8, "qualified_people_companies": 6,
        "direct_channel_companies": 4, "reviewed_preparation_companies": 0,
    }
    filtered = lead_api.get(f"{lead_case['base']}/lead-workflow?qualifies_for=direct_channel", headers=headers()).json()["data"]
    assert filtered["total"] == filtered["metrics"]["direct_channel_companies"] == 4
    with psycopg.connect(lead_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM provider_operations").fetchone() == (0,)
