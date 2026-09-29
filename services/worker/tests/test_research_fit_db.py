"""T19 fit consumes T18 persisted evidence and commits one immutable assessment."""

import asyncio
import uuid

import psycopg

from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.ext.asyncio import create_async_engine

from buyeros_worker.fit_runner import FitDomainRunner
from buyeros_worker.research_graph import build_research_graph, checkpoint_config
from tests.test_discovery_runner_db import (ACTOR_ID, PROJECT_A, RUN_ID, WS_A,
                                               SearchFixture, _execute, discovery_case)


def test_discovered_evidence_becomes_one_grounded_fit_assessment(discovery_case):
    owner_dsn, runtime_dsn = discovery_case
    assert _execute(runtime_dsn, SearchFixture(owner_dsn)) == "done"
    with psycopg.connect(owner_dsn) as db:
        buyer_id = db.execute("SELECT id FROM project_buyers WHERE project_id=%s", (PROJECT_A,)).fetchone()[0]

    async def work():
        engine = create_async_engine(runtime_dsn.replace("postgresql://", "postgresql+psycopg://", 1))
        try:
            runner = FitDomainRunner(engine, uuid.UUID(WS_A), uuid.UUID(RUN_ID), buyer_id)
            graph = build_research_graph(MemorySaver(), runner)
            initial = {"workspace_id": WS_A, "run_id": RUN_ID, "buyer_id": str(buyer_id),
                       "workflow_version": "fit-v1", "attempt": 1}
            config = checkpoint_config(WS_A, RUN_ID, "fit-v1", 1, buyer_id)
            first = await graph.ainvoke(initial, config)
            second = await graph.ainvoke(initial, config)
            assert first["assessment_id"] == second["assessment_id"]
        finally:
            await engine.dispose()
    asyncio.run(work())

    with psycopg.connect(owner_dsn) as db:
        rows = db.execute("SELECT verdict,evidence_ids,assessment_details,fit_algorithm_version "
                          "FROM fit_assessments WHERE run_id=%s", (RUN_ID,)).fetchall()
        assert len(rows) == 1
        verdict, evidence_ids, details, version = rows[0]
        assert verdict == "match" and len(evidence_ids) == 1 and version == "fit-v1"
        assert details["supported_requirement_ids"] and details["next_action"] == "human_review"
        assert "secret" not in details["rationale"].lower()


def test_expired_source_cannot_produce_match(discovery_case):
    owner_dsn, runtime_dsn = discovery_case
    assert _execute(runtime_dsn, SearchFixture(owner_dsn)) == "done"
    with psycopg.connect(owner_dsn, autocommit=True) as db:
        buyer_id = db.execute("SELECT id FROM project_buyers WHERE project_id=%s", (PROJECT_A,)).fetchone()[0]
        db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' "
                   "WHERE run_id=%s", (RUN_ID,))

    async def work():
        engine = create_async_engine(runtime_dsn.replace("postgresql://", "postgresql+psycopg://", 1))
        try:
            runner = FitDomainRunner(engine, uuid.UUID(WS_A), uuid.UUID(RUN_ID), buyer_id)
            graph = build_research_graph(MemorySaver(), runner)
            result = await graph.ainvoke({"workspace_id": WS_A, "run_id": RUN_ID,
                "buyer_id": str(buyer_id), "workflow_version": "fit-v1", "attempt": 1},
                checkpoint_config(WS_A, RUN_ID, "fit-v1", 1, buyer_id))
            assert result["assessment_id"]
        finally:
            await engine.dispose()
    asyncio.run(work())
    with psycopg.connect(owner_dsn) as db:
        assert db.execute("SELECT verdict FROM fit_assessments WHERE run_id=%s", (RUN_ID,)).fetchone()[0] == "needs_review"


def test_discovery_hands_off_to_checkpointed_fit_worker(discovery_case):
    owner_dsn, runtime_dsn = discovery_case
    assert _execute(runtime_dsn, SearchFixture(owner_dsn)) == "done"
    with psycopg.connect(owner_dsn, autocommit=True) as db:
        status, stage = db.execute("SELECT status,stage FROM search_runs WHERE id=%s", (RUN_ID,)).fetchone()
        assert (status, stage) == ("running", "fit")
        fit_intent = db.execute("SELECT intent_key FROM outbox_events WHERE workspace_id=%s "
                                "AND event_type='run.fit' AND state='ready'", (WS_A,)).fetchone()[0]
        db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
        db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 "
                   "WHERE intent_key=%s", (fit_intent,))
    try:
        from buyeros_worker.tasks import execute_intent_sync
        checkpoint_dsn = runtime_dsn.replace("buyeros_api:test-only", "buyeros_worker:test-only", 1)
        result = execute_intent_sync(fit_intent, WS_A, 1, environment="test",
                                     checkpoint_dsn=checkpoint_dsn)
        with psycopg.connect(owner_dsn) as db:
            reason = db.execute("SELECT terminal_reason FROM search_runs WHERE id=%s", (RUN_ID,)).fetchone()[0]
            assert result == "done", reason
            assert db.execute("SELECT status FROM search_runs WHERE id=%s", (RUN_ID,)).fetchone()[0] == "completed"
            assert db.execute("SELECT count(*) FROM fit_assessments WHERE run_id=%s", (RUN_ID,)).fetchone()[0] == 1
            assert db.execute("SELECT state FROM outbox_events WHERE intent_key=%s", (fit_intent,)).fetchone()[0] == "done"
    finally:
        with psycopg.connect(owner_dsn, autocommit=True) as db:
            db.execute("ALTER ROLE buyeros_worker NOLOGIN")
