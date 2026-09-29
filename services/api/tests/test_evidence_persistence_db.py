"""T17 canonical buyer persistence with immutable, context-bound source evidence."""
import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from buyeros_api.api.deps import async_database_url
from buyeros_api.db.session import tenant_session
from buyeros_api.db.buyers import Company, Evidence, ProjectBuyer, SourceDocument
from buyeros_api.db.runs import RawCandidate
from buyeros_api.services.buyer_read import view as buyer_view
from buyeros_api.services.buyer_view import evidence_data
from buyeros_api.services.evidence_service import persist_candidate_evidence, repair_candidate_mapping
from tests.conftest import runtime_role_dsn
from tests.icp_fixtures import REQUIREMENT_ID, valid_icp_payload

WS_A = uuid.UUID("11111111-1111-4111-8111-111111111111")
WS_B = uuid.UUID("22222222-2222-4222-8222-222222222222")
PROJECT_A = uuid.UUID("a0000000-0000-4000-8000-000000000001")


def _setup(seeded):
    icp_id, run_id, operation_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    source_id, second_source_id, foreign_id, expired_id = (uuid.uuid4() for _ in range(4))
    now = datetime.now(timezone.utc)
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO icp_versions(id,workspace_id,project_id,number,content,content_hash,approved_at,basis_offer_revision) "
            "VALUES (%s,%s,%s,1,%s::jsonb,%s,now(),1)",
            (icp_id, WS_A, PROJECT_A, json.dumps(valid_icp_payload()), "sha256:" + "a" * 64),
        )
        conn.execute("UPDATE projects SET active_icp_version_id=%s WHERE id=%s", (icp_id, PROJECT_A))
        conn.execute(
            "INSERT INTO search_runs(id,workspace_id,project_id,icp_version_id,status,limits,target_companies,raw_result_count) "
            "VALUES (%s,%s,%s,%s,'running','{}'::jsonb,10,0)",
            (run_id, WS_A, PROJECT_A, icp_id),
        )
        conn.execute(
            "INSERT INTO provider_operations(id,workspace_id,intent_key,capability,input_hash,status) "
            "VALUES (%s,%s,%s,'account_search',%s,'accepted')",
            (operation_id, WS_A, f"research:{run_id}", "b" * 64),
        )
        for source, workspace, expiry, excerpt in (
            (source_id, WS_A, now + timedelta(days=1), "Acme GmbH distributes industrial sensors."),
            (second_source_id, WS_A, now + timedelta(days=1), "Acme Trading AG distributes industrial sensors."),
            (foreign_id, WS_B, now + timedelta(days=1), "Acme GmbH distributes industrial sensors."),
            (expired_id, WS_A, now - timedelta(seconds=1), "Acme GmbH distributes industrial sensors."),
        ):
            conn.execute(
                "INSERT INTO source_documents(id,workspace_id,project_id,run_id,permission_purpose,"
                "canonical_url,digest,retrieved_at,language,storage_mode,excerpt,retention_until) "
                "VALUES (%s,%s,%s,%s,'account_research',%s,%s,%s,'en','excerpt_only',%s,%s)",
                (source, workspace, PROJECT_A if workspace == WS_A else None,
                 run_id if workspace == WS_A else None,
                 f"https://example.org/{source}", hashlib.sha256(excerpt.encode()).hexdigest(),
                 now, excerpt, expiry),
            )
    return run_id, operation_id, source_id, second_source_id, foreign_id, expired_id


@pytest.fixture
def t17_scope(seeded):
    ids = _setup(seeded)
    try:
        yield (seeded, *ids)
    finally:
        with psycopg.connect(seeded, autocommit=True) as conn:
            conn.execute("UPDATE projects SET active_icp_version_id=NULL WHERE id=%s", (PROJECT_A,))
            for table in (
                "evidence", "human_reviews", "fit_assessments", "audit_events", "company_aliases",
                "raw_candidates", "run_events", "project_buyers", "source_documents",
                "companies", "search_runs", "provider_operations", "icp_versions",
            ):
                conn.execute(
                    f"DELETE FROM {table} WHERE workspace_id IN (%s,%s)", (WS_A, WS_B),
                )
            conn.execute(
                "DELETE FROM memberships WHERE user_id IN (SELECT id FROM users WHERE issuer=%s)",
                ("https://alias-correction.buyeros.test/",),
            )
            conn.execute("DELETE FROM users WHERE issuer=%s",
                         ("https://alias-correction.buyeros.test/",))


def _candidate(registry_id="DE-HRB-123", path="acme"):
    return {
        "source_url": f"https://www.example.org/{path}?utm_source=fixture",
        "legal_name": "Acme GmbH" if path == "acme" else "Acme Trading AG",
        "display_name": "Acme" if path == "acme" else "Acme Trading",
        "domain": "example.org",
        "registry_id": registry_id,
        "external_ref": path,
        "assessment": {"verdict": "match", "rationale": "Source states product distribution."},
    }


def _source(source_id, legal_name="Acme GmbH"):
    return [{
        "source_document_id": str(source_id),
        "excerpt": f"{legal_name} distributes industrial sensors.",
        "stance": "supports", "requirement_id": REQUIREMENT_ID, "is_inference": False,
    }]


def test_replay_does_not_duplicate_company_buyer_evidence_or_assessment(t17_scope):
    seeded, run_id, operation_id, source_id, second_source_id, _, _ = t17_scope

    async def persist(candidate, sources):
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
        try:
            async with tenant_session(engine, WS_A) as session:
                return await persist_candidate_evidence(session, run_id, operation_id, candidate, sources)
        finally:
            await engine.dispose()

    buyer_id = asyncio.run(persist(_candidate(), _source(source_id)))
    assert asyncio.run(persist(_candidate(), _source(source_id))) == buyer_id
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT count(*) FROM companies WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM project_buyers WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM raw_candidates WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM evidence WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM fit_assessments WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == 1
        assert conn.execute("SELECT raw_result_count FROM search_runs WHERE id=%s", (run_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM run_events WHERE run_id=%s", (run_id,)).fetchone()[0] == 1

    # A shared web domain is a hint. Distinct registry identities stay distinct.
    second = asyncio.run(persist(_candidate("DE-HRB-999", "trading"), _source(second_source_id, "Acme Trading AG")))
    assert second != buyer_id
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT count(*) FROM companies WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM project_buyers WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == 2


def test_foreign_expired_and_unanchored_sources_cannot_support_a_match(t17_scope):
    seeded, run_id, operation_id, _, _, foreign_id, expired_id = t17_scope

    async def attempt(sources):
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
        try:
            async with tenant_session(engine, WS_A) as session:
                return await persist_candidate_evidence(session, run_id, operation_id, _candidate(), sources)
        finally:
            await engine.dispose()

    for bad in (
        _source(foreign_id),
        _source(expired_id),
        [{**_source(expired_id)[0], "excerpt": "An invented claim."}],
    ):
        with pytest.raises(ValueError):
            asyncio.run(attempt(bad))
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT count(*) FROM companies WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == 0


def test_provider_intent_must_bind_run_and_contact_hints_do_not_persist(t17_scope):
    seeded, run_id, operation_id, source_id, _, _, _ = t17_scope
    wrong_operation = uuid.uuid4()
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO provider_operations(id,workspace_id,intent_key,capability,input_hash,status) "
            "VALUES (%s,%s,%s,'account_search',%s,'accepted')",
            (wrong_operation, WS_A, f"research:{uuid.uuid4()}", "c" * 64),
        )

    async def persist(op_id, candidate):
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
        try:
            async with tenant_session(engine, WS_A) as session:
                return await persist_candidate_evidence(session, run_id, op_id, candidate, _source(source_id))
        finally:
            await engine.dispose()

    candidate = _candidate()
    candidate["contacts"] = [
        {"name": f"Person {i}", "email": f"person{i}@example.org"} for i in range(3)
    ]
    with pytest.raises(ValueError, match="provider operation"):
        asyncio.run(persist(wrong_operation, candidate))
    buyer_id = asyncio.run(persist(operation_id, candidate))
    assert buyer_id
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT count(*) FROM companies WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM project_buyers WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == 1
        raw = conn.execute("SELECT raw_payload::text FROM raw_candidates WHERE workspace_id=%s", (WS_A,)).fetchone()[0]
        assert "person0@" not in raw and "person1@" not in raw and "person2@" not in raw


def test_26_observations_resolve_to_24_registry_entities(t17_scope):
    seeded, run_id, operation_id, _, _, _, _ = t17_scope
    prepared = []
    now = datetime.now(timezone.utc)
    with psycopg.connect(seeded, autocommit=True) as conn:
        for index in range(26):
            entity = index % 24
            source_id = uuid.uuid4()
            name = f"Company {entity:02d} GmbH"
            excerpt = f"{name} distributes industrial sensors."
            conn.execute(
                "INSERT INTO source_documents(id,workspace_id,project_id,run_id,permission_purpose,"
                "canonical_url,digest,retrieved_at,language,storage_mode,excerpt,retention_until) "
                "VALUES (%s,%s,%s,%s,'account_research',%s,%s,%s,'en','excerpt_only',%s,%s)",
                (source_id, WS_A, PROJECT_A, run_id, f"https://example.org/company/{index}",
                 hashlib.sha256(excerpt.encode()).hexdigest(), now, excerpt, now + timedelta(days=1)),
            )
            candidate = {
                "source_url": f"https://example.org/company/{index}", "legal_name": name,
                "display_name": name, "domain": f"company-{entity}.example.org",
                "registry_id": f"DE-HRB-{entity:03d}", "external_ref": f"fixture-{index}",
            }
            prepared.append((candidate, _source(source_id, name)))

    async def persist_all():
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
        try:
            result = []
            for candidate, claims in prepared:
                async with tenant_session(engine, WS_A) as session:
                    result.append(await persist_candidate_evidence(
                        session, run_id, operation_id, candidate, claims,
                    ))
            return result
        finally:
            await engine.dispose()

    buyers = asyncio.run(persist_all())
    assert len(buyers) == 26 and len(set(buyers)) == 24
    with psycopg.connect(seeded) as conn:
        for table, expected in (("raw_candidates", 26), ("companies", 24),
                                ("project_buyers", 24), ("evidence", 26),
                                ("company_aliases", 26), ("run_events", 26)):
            assert conn.execute(f"SELECT count(*) FROM {table} WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == expected
        assert conn.execute("SELECT raw_result_count FROM search_runs WHERE id=%s", (run_id,)).fetchone()[0] == 26


def test_concurrent_replay_keeps_one_canonical_relation(t17_scope):
    seeded, run_id, operation_id, source_id, _, _, _ = t17_scope

    async def persist_twice():
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
        async def once():
            async with tenant_session(engine, WS_A) as session:
                return await persist_candidate_evidence(
                    session, run_id, operation_id, _candidate(), _source(source_id),
                )
        try:
            return await asyncio.gather(once(), once())
        finally:
            await engine.dispose()

    first, second = asyncio.run(persist_twice())
    assert first == second
    with psycopg.connect(seeded) as conn:
        for table in ("companies", "project_buyers", "raw_candidates", "company_aliases", "evidence"):
            assert conn.execute(f"SELECT count(*) FROM {table} WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == 1


def test_reviewer_can_auditably_split_wrong_alias_without_rewriting_old_evidence(t17_scope):
    seeded, run_id, operation_id, source_id, _, _, _ = t17_scope
    actor_id, outsider_id, target_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(seeded, autocommit=True) as conn:
        for user_id, role in ((actor_id, "reviewer"), (outsider_id, "viewer")):
            conn.execute("INSERT INTO users(id,issuer,subject) VALUES (%s,'https://alias-correction.buyeros.test/',%s)",
                         (user_id, str(user_id)))
            conn.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) "
                         "VALUES (%s,%s,%s,%s,true)",
                         (uuid.uuid4(), WS_A, user_id, [role]))
        conn.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name,domain,registry_id) "
                     "VALUES (%s,%s,'Acme GmbH','Acme correction','example.org','DE-HRB-9999')",
                     (target_id, WS_A))

    async def persist():
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
        try:
            async with tenant_session(engine, WS_A) as session:
                return await persist_candidate_evidence(
                    session, run_id, operation_id, _candidate(), _source(source_id),
                )
        finally:
            await engine.dispose()

    old_buyer = asyncio.run(persist())
    with psycopg.connect(seeded) as conn:
        raw_id = conn.execute("SELECT id FROM raw_candidates WHERE run_id=%s", (run_id,)).fetchone()[0]
        old_evidence_id = conn.execute("SELECT id FROM evidence WHERE raw_candidate_id=%s", (raw_id,)).fetchone()[0]

    async def repair(actor, company):
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
        try:
            async with tenant_session(engine, WS_A) as session:
                await repair_candidate_mapping(session, raw_id, company, actor,
                                               "Registry link was verified against the wrong entity")
        finally:
            await engine.dispose()

    with pytest.raises(ValueError):
        asyncio.run(repair(outsider_id, target_id))
    asyncio.run(repair(actor_id, target_id))
    corrected_buyer = asyncio.run(persist())
    assert corrected_buyer != old_buyer

    async def inspect_historical():
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
        try:
            async with tenant_session(engine, WS_A) as session:
                old = (await session.execute(select(ProjectBuyer).where(
                    ProjectBuyer.workspace_id == WS_A, ProjectBuyer.id == old_buyer,
                ))).scalar_one()
                company = (await session.execute(select(Company).where(
                    Company.workspace_id == WS_A, Company.id == old.company_id,
                ))).scalar_one()
                row = (await session.execute(
                    select(Evidence, SourceDocument, RawCandidate.canonical_company_id)
                    .join(SourceDocument, SourceDocument.id == Evidence.source_document_id)
                    .join(RawCandidate, RawCandidate.id == Evidence.raw_candidate_id)
                    .where(Evidence.workspace_id == WS_A, Evidence.id == old_evidence_id)
                )).one()
                return await buyer_view(session, workspace_id=WS_A, buyer=old, company=company), evidence_data(
                    row[0], row[1], mapped_company_id=row[2],
                )
        finally:
            await engine.dispose()

    old_view, old_citation = asyncio.run(inspect_historical())
    assert old_view["fit"]["freshness"] == "stale"
    assert old_citation["status"] == "stale"
    assert old_citation["excerpt"] == "Source unavailable"
    with psycopg.connect(seeded) as conn:
        aliases = conn.execute(
            "SELECT company_id, superseded_at, decision_state FROM company_aliases "
            "WHERE raw_candidate_id=%s ORDER BY created_at, id", (raw_id,),
        ).fetchall()
        assert len(aliases) == 2
        assert sum(row[1] is None for row in aliases) == 1
        assert any(row[0] == target_id and row[1] is None and row[2] == "reviewed_split" for row in aliases)
        assert conn.execute("SELECT canonical_company_id FROM raw_candidates WHERE id=%s", (raw_id,)).fetchone()[0] == target_id
        assert conn.execute("SELECT company_id FROM evidence WHERE id=%s", (old_evidence_id,)).fetchone()[0] != target_id
        assert conn.execute("SELECT count(*) FROM evidence WHERE raw_candidate_id=%s", (raw_id,)).fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM audit_events WHERE workspace_id=%s AND action='canonical_alias.repaired'", (WS_A,)).fetchone()[0] == 1
        assert conn.execute("SELECT raw_result_count FROM search_runs WHERE id=%s", (run_id,)).fetchone()[0] == 1


def test_per_query_intent_must_belong_to_immutable_run_plan(t17_scope):
    seeded, run_id, _, source_id, _, _, _ = t17_scope
    planned = "a" * 24
    wrong = "b" * 24
    good_operation, bad_operation = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("UPDATE search_runs SET execution_snapshot=%s::jsonb WHERE id=%s",
                     (json.dumps({"query_plan": {"schema": "query-plan.v1",
                        "queries": [{"id": planned}]}}), run_id))
        for operation, query_id in ((good_operation, planned), (bad_operation, wrong)):
            conn.execute(
                "INSERT INTO provider_operations(id,workspace_id,intent_key,capability,input_hash,status) "
                "VALUES (%s,%s,%s,'account_search',%s,'accepted')",
                (operation, WS_A, f"research:{run_id}:{query_id}", "b" * 64),
            )

    async def persist(operation):
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
        try:
            async with tenant_session(engine, WS_A) as session:
                return await persist_candidate_evidence(session, run_id, operation,
                    _candidate(), _source(source_id))
        finally:
            await engine.dispose()

    with pytest.raises(ValueError, match="accepted search provider operation"):
        asyncio.run(persist(bad_operation))
    buyer_id = asyncio.run(persist(good_operation))
    assert buyer_id is not None
