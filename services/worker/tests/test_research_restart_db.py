"""T19 Postgres checkpoint ownership, restart and tenant scope."""

import asyncio
import uuid

import psycopg
import pytest

from buyeros_worker.checkpoints import open_checkpoint_saver
from buyeros_worker.research_graph import build_research_graph, checkpoint_config
from tests.conftest import WS_A, WS_B

RUN = uuid.UUID("d0000000-0000-4000-8000-000000000019")
BUYER = uuid.UUID("e0000000-0000-4000-8000-000000000019")


class CrashFit:
    def __init__(self, calls, failure_node=None):
        self.calls = calls
        self.failure_node = failure_node

    def record(self, node):
        self.calls.append(node)
        if self.failure_node == node:
            raise RuntimeError(f"worker killed at {node} boundary")

    async def load_basis(self, state):
        self.record("load_basis")
        return {"basis_hash": "a" * 64}

    async def hard_exclusions(self, state):
        self.record("hard_exclusions")
        return {"hard_excluded": False}

    async def fit(self, state):
        self.record("fit")
        return {"proposal_id": str(uuid.uuid5(uuid.NAMESPACE_URL, state["basis_hash"]))}

    async def verify(self, state):
        self.record("verify")
        return {"verified": True}

    async def persist(self, state):
        self.record("persist")
        return {"assessment_id": str(BUYER)}


@pytest.mark.parametrize("failure_node", ["load_basis", "hard_exclusions", "fit", "verify", "persist"])
def test_postgres_checkpoint_resumes_only_uncommitted_node_and_hides_other_tenant(
        migrated, worker_database_url, failure_node):
    config = checkpoint_config(WS_A, RUN, "fit-v1", 1, BUYER)
    initial = {"workspace_id": WS_A, "run_id": str(RUN), "buyer_id": str(BUYER),
               "workflow_version": "fit-v1", "attempt": 1}
    calls = []
    worker_dsn = worker_database_url.replace("buyeros_api:test-only", "buyeros_worker:test-only", 1)
    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")

    async def run():
        async with open_checkpoint_saver(worker_dsn, WS_A) as saver:
            graph = build_research_graph(saver, CrashFit(calls, failure_node=failure_node))
            with pytest.raises(RuntimeError, match="worker killed"):
                await graph.ainvoke(initial, config)
        nodes = ["load_basis", "hard_exclusions", "fit", "verify", "persist"]
        failed_at = nodes.index(failure_node)
        assert calls == nodes[:failed_at + 1]
        async with open_checkpoint_saver(worker_dsn, WS_B) as saver:
            assert await saver.aget_tuple(config) is None
        async with open_checkpoint_saver(worker_dsn, WS_A) as saver:
            graph = build_research_graph(saver, CrashFit(calls))
            result = await graph.ainvoke(None, config)
            assert result["assessment_id"] == str(BUYER)
            assert result["next_action"] == "human_review"
            assert await graph.ainvoke(None, config) == result
        assert calls == nodes[:failed_at + 1] + nodes[failed_at:]

    try:
        asyncio.run(run())
        with psycopg.connect(migrated) as db:
            version = db.execute("SELECT max(v) FROM buyeros_graph.checkpoint_migrations").fetchone()[0]
            assert version == 9
    finally:
        with psycopg.connect(migrated, autocommit=True) as db:
            for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                db.execute(f"DELETE FROM buyeros_graph.{table} WHERE thread_id LIKE %s", (WS_A + ":%",))
            db.execute("ALTER ROLE buyeros_worker NOLOGIN")
