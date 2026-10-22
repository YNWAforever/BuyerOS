"""Fictional browser prerequisites, restricted to the owned loopback fixture."""
import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timezone, timedelta

import psycopg
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import _require_disposable_test_dsn, runtime_role_dsn
from buyeros_api.db.icp import canonical_hash
from buyeros_api.db.session import tenant_session
from buyeros_api.api.lead_schemas import LeadScope, LeadCaseUpdate, LeadObservationInput, LeadReviewInput
from buyeros_api.services.lead_evidence_service import append_observation
from buyeros_api.services.lead_review_service import update_lead_case, append_lead_review

WORKSPACE = "e0000000-0000-4000-8000-000000000001"
PROJECT = "e3100000-0000-4000-8000-000000000001"
ADMIN = "e0000000-0000-4000-8000-000000000008"
ICP = "e3400000-0000-4000-8000-000000000001"
FACT = "e3500000-0000-4000-8000-000000000001"
DOCUMENT = "e3600000-0000-4000-8000-000000000001"
BUYERS = [f"e3200000-0000-4000-8000-{index+1:012d}" for index in range(24)]
COMPANIES = [f"e3300000-0000-4000-8000-{index+1:012d}" for index in range(24)]


def _guard(dsn):
    _require_disposable_test_dsn(dsn)
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT issuer,subject FROM users WHERE id=%s", (ADMIN,)).fetchone() == ("urn:buyeros:e2e", "admin")
        assert db.execute("SELECT name FROM workspaces WHERE id=%s", (WORKSPACE,)).fetchone() == ("E2E fixture workspace",)


def reset_lead_workflow_fixture(dsn):
    _guard(dsn)
    with psycopg.connect(dsn) as db:
        # A canceled browser can leave an apply request finishing on the server.
        # Serialize this exact fixture reset with that write, then delete its
        # rows atomically. Never interleave DELETEs with a revision commit.
        # Match apply_intent's row -> workspace-lock order, so an in-flight
        # request waiting for policy authorization cannot deadlock the reset.
        db.execute("SELECT id FROM lead_action_intents WHERE workspace_id=%s AND project_id=%s "
                   "ORDER BY id FOR UPDATE",(WORKSPACE,PROJECT)).fetchall()
        lock=int.from_bytes(hashlib.sha256(f"policy-gate:{WORKSPACE}".encode()).digest()[:8],"big",signed=True)
        db.execute("SELECT pg_advisory_xact_lock(%s)",(lock,))
        for table in (
            "lead_preparation_evidence", "lead_preparation_content_reviews", "lead_preparation_revisions",
            "lead_preparations", "lead_review_evidence", "lead_reviews", "lead_observations", "lead_action_intents",
            "lead_case_states", "pilot_cost_events", "pilot_credit_observations", "pilot_reconciliations",
            "pilot_budget_policies", "lead_private_payloads",
        ):
            db.execute(f"DELETE FROM {table} WHERE workspace_id=%s AND project_id=%s", (WORKSPACE, PROJECT))
        db.execute("DELETE FROM idempotency_records WHERE workspace_id=%s AND operation_id='prepareLeadIntent'", (WORKSPACE,))
        db.execute("DELETE FROM contact_points WHERE workspace_id=%s AND company_id=ANY(%s::uuid[])", (WORKSPACE, COMPANIES))
        db.execute("DELETE FROM people WHERE workspace_id=%s AND company_id=ANY(%s::uuid[])", (WORKSPACE, COMPANIES))
        db.execute("UPDATE projects SET offer_revision=1,version=1,active_icp_version_id=%s WHERE id=%s", (ICP, PROJECT))
        db.execute("UPDATE icp_versions SET superseded_at=NULL,approved_at=now(),approved_by=%s WHERE id=%s", (ADMIN, ICP))
        content = db.execute("SELECT content FROM icp_versions WHERE id=%s", (ICP,)).fetchone()[0]
        content["offer_facts"] = [{"id": FACT, "field": "product", "value": "Thai jasmine rice",
            "provenance": "document_excerpt", "approved": False, "source_document_id": DOCUMENT,
            "excerpt": "Thai jasmine rice. Fictional fixture source."}]
        db.execute("UPDATE icp_versions SET content=%s::jsonb,content_hash=%s WHERE id=%s",
                   (json.dumps(content), canonical_hash(content), ICP))
        db.execute("UPDATE offer_documents SET status='ready',extraction_metadata='{}'::jsonb,"
                   "deleted_at=NULL,retention_until=now()+interval '90 days' WHERE id=%s", (DOCUMENT,))
        db.execute("UPDATE memberships SET active=true,roles=CASE "
                   "WHEN user_id='e0000000-0000-4000-8000-000000000008'::uuid THEN ARRAY['workspace_admin'] "
                   "WHEN user_id='e0000000-0000-4000-8000-000000000004'::uuid THEN ARRAY['reviewer'] "
                   "WHEN user_id='e0000000-0000-4000-8000-000000000006'::uuid THEN ARRAY['viewer'] "
                   "ELSE ARRAY['operator'] END "
                   "WHERE workspace_id=%s", (WORKSPACE,))
        db.execute("UPDATE project_buyers SET owner_user_id=NULL,version=1 "
                   "WHERE workspace_id=%s AND project_id=%s AND id=ANY(%s::uuid[])",
                   (WORKSPACE,PROJECT,BUYERS))
        db.execute("DELETE FROM api_rate_windows WHERE workspace_id=%s", (WORKSPACE,))
        db.execute("UPDATE workspace_preferences SET locale='en' WHERE workspace_id=%s", (WORKSPACE,))
    from tests.policy_activation_fixtures import approve_native_fixture
    approve_native_fixture(dsn, WORKSPACE, PROJECT, ADMIN,
                           domains=tuple(f"buyer{index+1}.example.test" for index in range(24)),
                           documents=(DOCUMENT,))
    asyncio.run(_seed_records(dsn))


def seed_lead_workflow_fixture(dsn):
    _guard(dsn)
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) "
                   "VALUES (%s,%s,'Lead workflow fixture','Fixture Rice Seller','Thai jasmine rice',ARRAY['GB'],ARRAY['en'],1)",
                   (PROJECT, WORKSPACE))
        content = {"markets": ["GB"], "languages": ["en"], "buyer_types": ["distributor"],
                   "desired_roles": ["Procurement manager"], "requirements": [],
                   "offer_facts": [{"id": FACT, "field": "product", "value": "Thai jasmine rice",
                                    "provenance": "user_entered", "approved": False}]}
        db.execute("INSERT INTO icp_versions(id,workspace_id,project_id,number,basis_offer_revision,content,content_hash,"
                   "approved_at,approved_by) VALUES (%s,%s,%s,1,1,%s::jsonb,%s,now(),%s)",
                   (ICP, WORKSPACE, PROJECT, json.dumps(content), canonical_hash(content), ADMIN))
        db.execute("UPDATE projects SET active_icp_version_id=%s WHERE id=%s", (ICP, PROJECT))
        db.execute("INSERT INTO offer_documents(id,workspace_id,project_id,kind,filename,media_type,status,version,"
                   "sha256,retention_until) VALUES (%s,%s,%s,'upload','Fixture product.pptx',"
                   "'application/vnd.openxmlformats-officedocument.presentationml.presentation','ready',1,%s,"
                   "now()+interval '90 days')", (DOCUMENT, WORKSPACE, PROJECT, "f"*64))
        for index, (buyer, company) in enumerate(zip(BUYERS, COMPANIES)):
            name = f"Fixture Rice Buyer {index+1:02d}"
            db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name,domain) VALUES (%s,%s,%s,%s,%s)",
                       (company, WORKSPACE, name, name, f"buyer{index+1}.example.test"))
            db.execute("INSERT INTO project_buyers(id,workspace_id,project_id,company_id,note) VALUES (%s,%s,%s,%s,%s)",
                       (buyer, WORKSPACE, PROJECT, company, "Fictional fixture, not a real Golden Resources lead."))
            sources = [{"title": f"Official fixture source {number+1}",
                        "url": f"https://buyer{index+1}.example.test/source-{number+1}"}
                       for number in range(2 if index < 15 else 3)]
            db.execute("INSERT INTO buyer_source_checks(id,workspace_id,project_id,buyer_id,checked_on,grade,rationale,"
                       "limitations,sources,recorded_by_user_id) VALUES (%s,%s,%s,%s,'2026-10-15',%s,%s,%s,%s::jsonb,%s)",
                       (uuid.uuid4(), WORKSPACE, PROJECT, buyer, "A" if index < 6 else "C" if index == 23 else "B",
                        "Fictional UK rice trade channel; manual source-review fixture.",
                        "Fixture only; no actual buyer, purchasing intent or deliverability is established.",
                        json.dumps(sources), ADMIN))
    reset_lead_workflow_fixture(dsn)


def apply_lead_fixture_scenario(dsn, scenario):
    _guard(dsn)
    if scenario == "second_purchaser":
        return asyncio.run(_seed_second_purchaser(dsn))
    with psycopg.connect(dsn) as db:
        if scenario == "expire_channel":
            db.execute("UPDATE contact_points SET retention_expires_at=now()-interval '1 second' "
                       "WHERE workspace_id=%s AND company_id=ANY(%s::uuid[])",
                       (WORKSPACE, COMPANIES))
        elif scenario == "t21_named_members":
            # Only the verified disposable E2E workspace and its existing actors.
            names = {
                ADMIN: "Fixture Alex Chan",
                "e0000000-0000-4000-8000-000000000004": "Fixture Alex Chan",
                "e0000000-0000-4000-8000-000000000006": "Fixture Blair Lee",
            }
            for actor, name in names.items():
                db.execute("UPDATE users SET display_name=%s WHERE id=%s AND EXISTS "
                           "(SELECT 1 FROM memberships WHERE user_id=users.id AND workspace_id=%s)",
                           (name, actor, WORKSPACE))
            for buyer, actor in [(BUYERS[0], ADMIN), (BUYERS[1], "e0000000-0000-4000-8000-000000000004")]:
                db.execute("UPDATE project_buyers SET owner_user_id=%s,version=version+1 "
                           "WHERE id=%s AND workspace_id=%s AND project_id=%s",
                           (actor,buyer,WORKSPACE,PROJECT))
        elif scenario == "product_caveat":
            content = db.execute("SELECT content FROM icp_versions WHERE id=%s", (ICP,)).fetchone()[0]
            content["offer_facts"] = []
            db.execute("UPDATE icp_versions SET content=%s::jsonb,content_hash=%s WHERE id=%s",
                       (json.dumps(content), canonical_hash(content), ICP))
            db.execute("UPDATE offer_documents SET extraction_metadata=%s::jsonb WHERE id=%s",
                       (json.dumps({"format":"pptx","byte_length":64,"classification":"image_only",
                                    "slide_count":2,"text_slide_count":0}), DOCUMENT))
        else:
            raise ValueError("unsupported fixture scenario")


async def _seed_second_purchaser(dsn):
    """One atomic synthetic prerequisite; ordinary services keep every gate."""
    from sqlalchemy import select
    from buyeros_api.db.models import Membership
    from buyeros_api.db.lead_workflow import LeadCaseState
    engine=create_async_engine(runtime_role_dsn(dsn).replace("postgresql://","postgresql+psycopg://"))
    try:
        async with tenant_session(engine,uuid.UUID(WORKSPACE)) as session:
            member=await session.scalar(select(Membership).where(Membership.workspace_id==uuid.UUID(WORKSPACE),
                Membership.user_id==uuid.UUID(ADMIN),Membership.active.is_(True)))
            if member is None or "workspace_admin" not in member.roles:
                raise ValueError("current synthetic fixture administrator required")
            scope=LeadScope(uuid.UUID(WORKSPACE),uuid.UUID(PROJECT),uuid.UUID(BUYERS[0]),uuid.UUID(COMPANIES[0]),
                uuid.UUID(ADMIN),member.version,frozenset(member.roles))
            now=datetime.now(timezone.utc)
            base={"stance":"supports","checked_at":now.isoformat(),
                "rationale":"Independent official purchasing role and business channel.",
                "sources":[{"title":"Official second purchaser","url":"https://buyer1.example.test/blair",
                    "excerpt":"Blair Fixture buys rice and uses blair@buyer1.example.test.","source_kind":"official"}]}
            employment=await append_observation(session,scope=scope,data=LeadObservationInput.model_validate({
                **base,"claim":"employment","person":{"full_name":"Blair Fixture","role":"Rice Buyer"}}),now=now)
            person=employment["person_id"]
            procurement=await append_observation(session,scope=scope,data=LeadObservationInput.model_validate({
                **base,"claim":"procurement_scope","person":{"person_id":person}}),now=now)
            channel=await append_observation(session,scope=scope,data=LeadObservationInput.model_validate({
                **base,"claim":"channel_ownership","person":{"person_id":person},
                "channel":{"type":"business_email","value":"blair@buyer1.example.test","person_id":person}}),now=now)
            state=await session.scalar(select(LeadCaseState).where(LeadCaseState.workspace_id==scope.workspace_id,
                LeadCaseState.project_id==scope.project_id,LeadCaseState.buyer_id==scope.buyer_id))
            review=await append_lead_review(session,scope=scope,expected_version=state.version,
                data=LeadReviewInput(person_id=person,contact_id=channel["contact_id"],employment="accepted",
                    procurement_scope="accepted",channel_ownership="accepted",
                    observation_ids=[employment["id"],procurement["id"],channel["id"]],
                    rationale=base["rationale"]),now=now)
            return {"fixture_only":True,"person_id":person,"review_id":review["id"]}
    finally:
        await engine.dispose()


async def _seed_records(dsn):
    engine = create_async_engine(runtime_role_dsn(dsn).replace("postgresql://", "postgresql+psycopg://"))
    try:
        for index, (buyer, company) in enumerate(zip(BUYERS, COMPANIES)):
            scope = LeadScope(uuid.UUID(WORKSPACE), uuid.UUID(PROJECT), uuid.UUID(buyer), uuid.UUID(company),
                              uuid.UUID(ADMIN), 1, frozenset({"workspace_admin"}))
            async with tenant_session(engine, scope.workspace_id) as session:
                if index < 8:
                    await update_lead_case(session, scope=scope, expected_version=1,
                        data=LeadCaseUpdate(priority=True, priority_reason="Fictional official bulk-rice catalog",
                                            next_action="Review purchasing contact"))
                if index >= 6:
                    continue
                person_name = f"Fixture Purchaser {index+1:02d}"
                base = {"stance": "supports", "checked_at": datetime.now(timezone.utc).isoformat(),
                        "rationale": "Fictional official purchasing role check.", "limitations": "Test data only.",
                        "sources": [{"title": "Official fictional team page", "url": f"https://buyer{index+1}.example.test/team",
                                     "excerpt": f"{person_name} manages the rice purchasing category.",
                                     "source_kind": "official"}]}
                employment = await append_observation(session, scope=scope,
                    data=LeadObservationInput.model_validate({**base, "claim": "employment",
                        "person": {"full_name": person_name, "role": "Rice Purchasing Manager"}}),
                    now=datetime.now(timezone.utc))
                person = employment["person_id"]
                procurement = await append_observation(session, scope=scope,
                    data=LeadObservationInput.model_validate({**base, "claim": "procurement_scope",
                        "person": {"person_id": person}}), now=datetime.now(timezone.utc))
                references, contact = [employment["id"], procurement["id"]], None
                if index < 4:
                    channel = await append_observation(session, scope=scope,
                        data=LeadObservationInput.model_validate({**base, "claim": "channel_ownership",
                            "person": {"person_id": person},
                            "channel": {"type": "business_email", "value": f"purchaser{index+1}@buyer{index+1}.example.test",
                                        "person_id": person}}), now=datetime.now(timezone.utc))
                    references.append(channel["id"])
                    contact = channel["contact_id"]
                await append_lead_review(session, scope=scope, expected_version=2 + len(references),
                    data=LeadReviewInput(person_id=person, contact_id=contact, employment="accepted",
                        procurement_scope="accepted", channel_ownership="accepted" if contact else "uncertain",
                        observation_ids=references, rationale="Fictional purchasing identity and source ownership checked."),
                    now=datetime.now(timezone.utc))
    finally:
        await engine.dispose()
