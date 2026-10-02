"""One domain owner callable without importing the legacy broker transport."""
import asyncio
import json
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import pytest

from tests.conftest import WS_A, PROJECT_A, seed_outbox

EXECUTOR = Path(__file__).resolve().parents[2] / "api/buyeros_api/execution/domain_executor.py"


def executor_module():
    assert EXECUTOR.is_file(), "CF01 transport-independent executor missing"
    from buyeros_api.execution import domain_executor
    return domain_executor


def test_clean_api_import_does_not_load_celery_redis_or_worker():
    executor_module()
    code = "import sys; import buyeros_api.execution.domain_executor; " \
        "assert not any(n.split('.')[0] in {'celery', 'redis', 'buyeros_worker'} for n in sys.modules)"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("state,generation,expected", [
    ("done", 1, "duplicate"), ("dispatched", 2, "stale"), ("ready", 1, "not_dispatched"),
])
def test_async_entrypoint_rejects_terminal_stale_and_unclaimed_intents(
        migrated, worker_database_url, state, generation, expected):
    executor = executor_module()
    outbox_id, key = uuid.uuid4(), f"cf01:{uuid.uuid4()}"
    with psycopg.connect(migrated, autocommit=True) as db:
        seed_outbox(db, intent_key=key, event_type="bulk.mutate", payload={"job_id": str(uuid.uuid4())},
                    state=state, generation=1, outbox_id=str(outbox_id))

    async def run():
        from buyeros_api.execution.engine import create_engine
        engine = create_engine()
        try:
            return await executor.run_domain_intent(engine, uuid.UUID(WS_A), outbox_id, generation)
        finally:
            await engine.dispose()

    assert asyncio.run(run()) == expected
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT state, fencing_generation FROM outbox_events WHERE id=%s",
                          (outbox_id,)).fetchone() == (state, 1)


def test_async_entrypoint_does_not_read_another_tenant(migrated, worker_database_url):
    executor = executor_module()
    outbox_id, key = uuid.uuid4(), f"cf01:{uuid.uuid4()}"
    with psycopg.connect(migrated, autocommit=True) as db:
        seed_outbox(db, intent_key=key, state="dispatched", generation=1, outbox_id=str(outbox_id))

    async def run():
        from buyeros_api.execution.engine import create_engine
        engine = create_engine()
        try:
            return await executor.run_domain_intent(engine, uuid.uuid4(), outbox_id, 1)
        finally:
            await engine.dispose()

    assert asyncio.run(run()) == "unknown_intent"


def test_envelope_is_strict_and_rejects_unsafe_generation():
    executor_module()
    from buyeros_api.api.worker_schemas import ClaimBatch, JobEnvelope
    from pydantic import ValidationError
    envelope = dict(v=1, workspace_id=WS_A, outbox_id=str(uuid.uuid4()), generation=1, runtime_epoch=1)
    assert json.loads(ClaimBatch(items=[JobEnvelope(**envelope)], next_cursor=None,
                                runtime_epoch=1).model_dump_json())["items"][0]["v"] == 1
    for changes in ({"url": "https://provider.invalid"}, {"generation": True},
                    {"generation": 2**53}, {"generation": 0}, {"runtime_epoch": -1}, {"v": True}):
        with pytest.raises(ValidationError):
            JobEnvelope(**(envelope | changes))


def test_claim_cycle_interface_is_bounded_and_not_a_publisher():
    executor_module()
    from buyeros_api.execution import dispatcher
    assert callable(getattr(dispatcher, "claim_cycle", None)), "CF01 ID-only async claim interface missing"
    for bad in ({"max_total": 11}, {"time_budget_seconds": 11}, {"epoch": 0}, {"backend": "other"}):
        async def run():
            return await dispatcher.claim_cycle(object(), **({"backend": "cloudflare", "epoch": 1} | bad))
        with pytest.raises(ValueError):
            asyncio.run(run())


@pytest.mark.parametrize("revoked", [False, True])
def test_bulk_intent_async_and_legacy_have_identical_durable_results(
        migrated, worker_database_url, revoked):
    executor = executor_module()
    user, member = uuid.uuid4(), uuid.uuid4()
    jobs = []
    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute("INSERT INTO users(id, issuer, subject) VALUES (%s, 'https://fixture.invalid/', %s)",
                   (user, f"cf01|{user}"))
        db.execute("INSERT INTO memberships(id, workspace_id, user_id, roles, active) "
                   "VALUES (%s,%s,%s, '{workspace_admin}', %s)", (member, WS_A, user, not revoked))
        for _ in range(2):
            job, company, buyer, outbox = (uuid.uuid4() for _ in range(4))
            key = f"cf01:bulk:{job}"
            db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) "
                       "VALUES (%s,%s,'Fictional CF01','Fictional CF01')", (company, WS_A))
            db.execute("INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES (%s,%s,%s,%s)",
                       (buyer, WS_A, PROJECT_A, company))
            db.execute("INSERT INTO async_jobs(id,workspace_id,project_id,actor_user_id,kind,operation,command,requested,status) "
                       "VALUES (%s,%s,%s,%s,'bulk_mutation','assignBuyerOwners',%s::jsonb,1,'queued')",
                       (job, WS_A, PROJECT_A, user, json.dumps({"owner_membership_id": str(member), "reason": "Fixture assignment"})))
            db.execute("INSERT INTO async_job_items(id,workspace_id,job_id,buyer_id,ordinal,expected_version,status) "
                       "VALUES (%s,%s,%s,%s,0,1,'pending')", (uuid.uuid4(), WS_A, job, buyer))
            seed_outbox(db, intent_key=key, event_type="bulk.mutate", payload={"job_id": str(job)},
                        state="dispatched", generation=1, outbox_id=str(outbox))
            jobs.append((job, buyer, outbox, key))

    async def run():
        from buyeros_api.execution.engine import create_engine
        engine = create_engine()
        try:
            assert await executor.run_domain_intent(engine, uuid.UUID(WS_A), jobs[0][2], 1) == "done"
            assert await executor.run_domain_intent(engine, uuid.UUID(WS_A), jobs[0][2], 1) == "duplicate"
        finally:
            await engine.dispose()

    asyncio.run(run())
    from buyeros_worker.tasks import execute_intent_sync
    assert execute_intent_sync(jobs[1][3], WS_A, 1) == "done"
    assert execute_intent_sync(jobs[1][3], WS_A, 1) == "duplicate"
    with psycopg.connect(migrated) as db:
        results = []
        for job, buyer, outbox, _ in jobs:
            results.append((
                db.execute("SELECT status,processed,updated,blocked FROM async_jobs WHERE id=%s", (job,)).fetchone(),
                db.execute("SELECT owner_user_id,version FROM project_buyers WHERE id=%s", (buyer,)).fetchone(),
                db.execute("SELECT state FROM outbox_events WHERE id=%s", (outbox,)).fetchone(),
                db.execute("SELECT status,reason_code FROM async_job_items WHERE job_id=%s", (job,)).fetchone(),
            ))
        assert results[0] == results[1]
        assert results[0][0] == ("completed", 1, 0 if revoked else 1, 1 if revoked else 0)
        assert results[0][1] == (None, 1) if revoked else results[0][1] == (user, 2)
        assert results[0][2] == ("done",)
