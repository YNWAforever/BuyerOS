"""Final review regressions use real scoped records and normal lifecycle entry points."""
import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.lead_fixtures import (
    WORKSPACE, PROJECT, OTHER_PROJECT, ACTORS, lead_api, lead_case,
    headers, prepare, apply, observation_payload, save_observation,
)
from tests.test_lead_preparation_db import ready_preparation, create_preparation, review_preparation
from tests.test_lead_progress_db import case_view


def worker_sweep(case, monkeypatch, entry="recovery", limit=10):
    from buyeros_api.db.session import tenant_session
    monkeypatch.setattr("buyeros_api.execution.config.get_settings",
                        lambda: SimpleNamespace(retention_policy_version="final-fixture-retention"))
    async def run():
        engine = create_async_engine(case["dsn"].replace("postgresql://", "postgresql+psycopg://"),
                                     pool_size=1, max_overflow=0)
        try:
            async with engine.begin() as connection:
                await connection.execute(text("SET ROLE buyeros_worker"))
                assert not await connection.scalar(text(
                    "SELECT has_table_privilege(current_user,'lead_private_payloads','SELECT')"))
            if entry == "recovery":
                from buyeros_api.services.worker_recovery import _expire_retention
                async with tenant_session(engine, uuid.UUID(WORKSPACE)) as session:
                    return await _expire_retention(session, now=datetime.now(timezone.utc), limit=limit)
            from buyeros_api.execution.handlers.retention import expire_due_contacts
            return len(await expire_due_contacts(engine, datetime.now(timezone.utc),
                policy_version="final-fixture-retention", limit=limit))
        finally:
            await engine.dispose()
    return asyncio.run(run())


@pytest.mark.parametrize("entry", ["recovery", "execution"])
@pytest.mark.parametrize("subject", ["person", "prepared_payload"])
def test_normal_retention_discovers_person_only_and_unapplied_payloads(lead_api, lead_case, monkeypatch, entry, subject):
    marker = "Private Orphan Fixture"
    if subject == "person":
        record, _, _ = save_observation(lead_api, lead_case, observation_payload(person={"full_name": marker}))
        with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
            db.execute("UPDATE people SET retention_expires_at=now()-interval '1 day' WHERE id=%s",
                       (record["person_id"],))
    else:
        staged = prepare(lead_api, lead_case, "observation.append", observation_payload(person={"full_name": marker}))
        assert staged.status_code == 201, staged.text
        with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
            db.execute("UPDATE lead_private_payloads SET retention_expires_at=now()-interval '1 day' "
                       "WHERE id=(SELECT payload_id FROM lead_action_intents WHERE id=%s)",
                       (staged.json()["data"]["id"],))
    assert worker_sweep(lead_case, monkeypatch, entry, limit=1) == 1
    with psycopg.connect(lead_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM lead_private_payloads WHERE contents::text LIKE %s",
                          (f"%{marker}%",)).fetchone() == (0,)


        if subject == "person":
            assert db.execute("SELECT full_name,role FROM people WHERE id=%s",
                              (record["person_id"],)).fetchone() == (None, None)
    assert worker_sweep(lead_case, monkeypatch, entry, limit=1) == 0


def test_prepared_preparation_read_and_replay_recheck_draft_purpose(lead_api, lead_case):
    payload = ready_preparation(lead_api, lead_case)
    payload["body"] = "Private preparation note for Alex Test."
    key = str(uuid.uuid4())
    request = {"action": "preparation.create", "buyer_id": lead_case["buyer_id"], "payload": payload}
    staged = lead_api.post(f"{lead_case['base']}/lead-intents", json=request, headers=headers(key=key))
    assert staged.status_code == 201, staged.text
    intent = staged.json()["data"]
    with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
        db.execute("INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,controller_scope_id,"
            "purpose,status,policy_version,basis_reference,provenance,countries,expires_at,retention_days,decision_author_id)"
            "VALUES (%s,%s,'project',%s,%s,'draft_preparation','blocked','final-fixture',"
            "'purpose revoked','test',ARRAY['GB'],now()+interval '90 days',90,%s)",
            (uuid.uuid4(), WORKSPACE, PROJECT, WORKSPACE, ACTORS["workspace_admin"]))
    responses = [
        lead_api.get(f"{lead_case['base']}/lead-intents/{intent['id']}", headers=headers()),
        lead_api.get(f"{lead_case['base']}/lead-intents", headers=headers()),
        lead_api.post(f"{lead_case['base']}/lead-intents", json=request, headers=headers(key=key)),
    ]
    for response in responses:
        assert response.status_code in {200, 201}, response.text
        assert "Private preparation note" not in response.text
        data = response.json()["data"]
        rows = data["items"] if "items" in data else [data]
        original = next(row for row in rows if row["id"] == intent["id"])
        assert original["redacted"] is True and original["payload"] is None
    choices = lead_api.get(f"{lead_case['base']}/buyers/{lead_case['buyer_id']}/lead-reviews",
        params={"purpose": "draft_preparation"}, headers=headers())
    assert choices.status_code == 200
    assert all(row["redacted"] and row["rationale"] is None for row in choices.json()["data"]["items"])
    assert apply(lead_api, lead_case, intent).status_code == 403


def test_human_preparation_reasons_are_retained_privately_and_erased(lead_api, lead_case, monkeypatch):
    payload = ready_preparation(lead_api, lead_case)
    view, _ = create_preparation(lead_api, lead_case, payload)
    reason = "Reviewed Alice Smith at +441234567890"
    staged = prepare(lead_api, lead_case, "preparation.review", {
        "revision_id": view["revision_id"], "context_hash": view["context_hash"],
        "reason": reason, "confirmation": True,
    }, role="workspace_admin", target_id=view["id"], version=view["version"])
    assert staged.status_code == 201, staged.text
    assert apply(lead_api, lead_case, staged.json()["data"], role="workspace_admin").status_code == 200
    archive = prepare(lead_api, lead_case, "preparation.archive", {"reason": reason},
                      role="workspace_admin", target_id=view["id"], version=2)
    assert archive.status_code == 201, archive.text
    assert apply(lead_api, lead_case, archive.json()["data"], role="workspace_admin").status_code == 200
    with psycopg.connect(lead_case["dsn"]) as db:
        reasons = str(db.execute("SELECT reason FROM audit_events WHERE action LIKE 'lead.preparation.%'").fetchall()).lower()
        assert "alice" not in reasons and "441234567890" not in reasons
    current = lead_api.get(f"{lead_case['base']}/lead-preparations/{view['id']}", headers=headers()).json()["data"]
    assert current["review_reason"] == reason
    assert current["state_reason"] == reason
    with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
        db.execute("UPDATE people SET retention_expires_at=now()-interval '1 day' WHERE id=%s", (payload["person_id"],))
    worker_sweep(lead_case, monkeypatch)
    erased = lead_api.get(f"{lead_case['base']}/lead-preparations/{view['id']}", headers=headers())
    assert erased.status_code == 200 and "Alice" not in erased.text and "441234567890" not in erased.text
    with psycopg.connect(lead_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM lead_private_payloads WHERE contents::text LIKE '%441234567890%'").fetchone() == (0,)


@pytest.mark.parametrize("mode,want", [
    ("other_uncertain", 1), ("other_qualified", 1), ("same_rejected", 0), ("same_other_channel_rejected", 0),
])
def test_reviews_are_scoped_to_subject_and_preparation_binding(lead_api, lead_case, mode, want):
    payload = ready_preparation(lead_api, lead_case)
    view, _ = create_preparation(lead_api, lead_case, payload)
    assert review_preparation(lead_api, lead_case, view).status_code == 200
    person, contact, ids = payload["person_id"], payload["contact_id"], payload["observation_ids"]
    if mode.startswith("other"):
        employment, _, _ = save_observation(lead_api, lead_case,
            observation_payload(person={"full_name": "Blair Fixture", "role": "Purchaser"}))
        person, contact, ids = employment["person_id"], None, [employment["id"]]
        if mode == "other_qualified":
            procurement, _, _ = save_observation(lead_api, lead_case,
                observation_payload(claim="procurement_scope", person={"person_id": person}))
            channel, _, _ = save_observation(lead_api, lead_case,
                observation_payload(claim="channel_ownership", person={"person_id": person},
                    channel={"type": "business_email", "value": "blair@rice.example.test", "person_id": person}))
            contact, ids = channel["contact_id"], ids + [procurement["id"], channel["id"]]
    elif mode == "same_other_channel_rejected":
        channel, _, _ = save_observation(lead_api, lead_case,
            observation_payload(claim="channel_ownership", person={"person_id": person},
                channel={"type": "business_email", "value": "alex.second@rice.example.test", "person_id": person}))
        contact, ids = channel["contact_id"], payload["observation_ids"][:2] + [channel["id"]]
    review = {"person_id": person, "contact_id": contact,
        "employment": "rejected" if mode.startswith("same") else "accepted",
        "procurement_scope": "uncertain" if mode == "other_uncertain" else "accepted",
        "channel_ownership": "accepted" if contact else "uncertain",
        "observation_ids": ids, "rationale": "Independent current subject judgement"}
    staged = prepare(lead_api, lead_case, "lead.review", review, version=case_view(lead_api, lead_case)["version"])
    assert staged.status_code == 201, staged.text
    assert apply(lead_api, lead_case, staged.json()["data"]).status_code == 200
    progress = lead_api.get(f"{lead_case['base']}/lead-workflow", headers=headers()).json()["data"]
    assert progress["metrics"]["direct_channel_companies"] == want
    current = lead_api.get(f"{lead_case['base']}/lead-preparations/{view['id']}", headers=headers()).json()["data"]
    assert current["state"] == ("reviewed" if want else "needs_review")


def test_purchasing_review_history_is_bounded_complete_and_scope_checked(lead_api, lead_case):
    payload = ready_preparation(lead_api, lead_case)
    ids = [payload["lead_review_id"]]
    for index in range(5):
        staged = prepare(lead_api, lead_case, "lead.review", {
            "person_id": payload["person_id"], "contact_id": payload["contact_id"],
            "employment": "accepted", "procurement_scope": "accepted", "channel_ownership": "accepted",
            "observation_ids": payload["observation_ids"], "rationale": f"Historical judgement {index+1}",
        }, version=case_view(lead_api, lead_case)["version"])
        assert staged.status_code == 201
        result = apply(lead_api, lead_case, staged.json()["data"])
        assert result.status_code == 200, result.text
        ids.append(result.json()["data"]["resource_id"])
    path = f"{lead_case['base']}/buyers/{lead_case['buyer_id']}/lead-reviews"
    first = lead_api.get(path, params={"limit": 3}, headers=headers())
    assert first.status_code == 200, first.text
    second = lead_api.get(path, params={"offset": 3, "limit": 3}, headers=headers())
    assert second.status_code == 200, second.text
    rows = first.json()["data"]["items"] + second.json()["data"]["items"]
    assert first.json()["data"]["total"] == second.json()["data"]["total"] == 6
    assert {row["id"] for row in rows} == set(ids)
    assert all(row["observation_ids"] == sorted(payload["observation_ids"]) for row in rows)
    assert all(row["recorded_by_user_id"] == str(ACTORS["operator"]) and row["rationale"] for row in rows)
    assert lead_api.get(path.replace(PROJECT, OTHER_PROJECT), headers=headers()).status_code == 404


@pytest.mark.parametrize("head", ["0055_lead_workflow", "0056_policy_activation", "9999_unreviewed"])
def test_missing_current_or_future_schema_never_bypasses_native_admission(lead_case, head):
    from buyeros_api.api.errors import ApiError
    from buyeros_api.db.session import tenant_session
    from buyeros_api.services.pilot_budget_service import assert_pilot_admission
    from decimal import Decimal
    with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
        db.execute("ALTER TABLE pilot_budget_policies RENAME TO unavailable_pilot_policy")
        db.execute("UPDATE alembic_version SET version_num=%s", (head,))
    async def run():
        engine = create_async_engine(lead_case["dsn"].replace("postgresql://", "postgresql+psycopg://"))
        try:
            async with tenant_session(engine, uuid.UUID(WORKSPACE)) as session:
                with pytest.raises(ApiError) as error:
                    await assert_pilot_admission(session, workspace_id=uuid.UUID(WORKSPACE),
                        project_id=uuid.UUID(PROJECT), operation_id=uuid.uuid4(),
                        upper_bound=Decimal("0.4"), now=datetime.now(timezone.utc))
                assert error.value.code == "POLICY_BLOCKED"
        finally:
            await engine.dispose()
    asyncio.run(run())


def test_normal_sweep_erases_preparation_at_product_document_deadline(lead_api, lead_case, monkeypatch):
    """An expiring attachment must not leave a longer-lived derived private copy."""
    from buyeros_api.db.icp import canonical_hash
    payload = ready_preparation(lead_api, lead_case)
    document = str(uuid.uuid4())
    marker = "Private product attachment expiry quotation"
    with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
        db.execute("INSERT INTO offer_documents(id,workspace_id,project_id,kind,filename,media_type,status,"
            "version,sha256,retention_until,extraction_metadata) VALUES (%s,%s,%s,'upload','expiry.txt',"
            "'text/plain','ready',1,%s,now()+interval '5 seconds',"
            "'{\"format\":\"text\",\"classification\":\"text\",\"byte_length\":42}')",
            (document, WORKSPACE, PROJECT, "c"*64))
        icp = payload["product_fact_refs"][0]["icp_version_id"]
        content = db.execute("SELECT content FROM icp_versions WHERE id=%s", (icp,)).fetchone()[0]
        content["offer_facts"][0].update(provenance="document_excerpt", source_document_id=document, excerpt=marker)
        digest = canonical_hash(content)
        db.execute("UPDATE icp_versions SET content=%s::jsonb,content_hash=%s WHERE id=%s",
                   (json.dumps(content), digest, icp))
    payload["product_fact_refs"][0]["icp_content_hash"] = digest
    payload["body"] = marker
    from tests.policy_activation_fixtures import approve_native_fixture
    approve_native_fixture(lead_case["dsn"], WORKSPACE, PROJECT, ACTORS["workspace_admin"], documents=(document,))
    created, _ = create_preparation(lead_api, lead_case, payload)
    assert created["redacted"] is False and created["content"]["body"] == marker
    bound = time.monotonic() + 10
    with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
        while not db.execute("SELECT retention_until<=now() FROM offer_documents WHERE id=%s", (document,)).fetchone()[0]:
            assert time.monotonic() < bound, "fixture document deadline did not elapse"
            time.sleep(0.05)
    assert worker_sweep(lead_case, monkeypatch) > 0
    with psycopg.connect(lead_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM lead_private_payloads WHERE contents::text LIKE %s",
                          (f"%{marker}%",)).fetchone() == (0,)


def test_review_content_cannot_outlive_one_expired_cited_observation(lead_api, lead_case):
    """Findings #3: a surviving citation may not keep expired review content readable."""
    payload = ready_preparation(lead_api, lead_case)
    ids = payload["observation_ids"]
    assert len(ids) >= 2
    view, _ = create_preparation(lead_api, lead_case, payload)
    assert view["redacted"] is False
    marker = "Private rationale that must expire with its citation"
    with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
        review_id = db.execute(
            "SELECT id FROM lead_reviews WHERE buyer_id=%s ORDER BY case_version DESC LIMIT 1",
            (lead_case["buyer_id"],)).fetchone()[0]
        db.execute("UPDATE lead_private_payloads SET contents=jsonb_set(contents,'{rationale}',%s::jsonb) "
                   "WHERE id=(SELECT payload_id FROM lead_reviews WHERE id=%s)", (json.dumps(marker), review_id))
        db.execute("UPDATE lead_private_payloads SET retention_expires_at=now()-interval '1 day' "
                   "WHERE id=(SELECT payload_id FROM lead_observations WHERE id=%s)", (ids[0],))
    path = f"{lead_case['base']}/buyers/{lead_case['buyer_id']}/lead-reviews"
    current = lead_api.get(path, headers=headers())
    assert current.status_code == 200, current.text
    assert marker not in current.text, "expired citation kept its review content readable"
    assert all(row["redacted"] is True for row in current.json()["data"]["items"])
