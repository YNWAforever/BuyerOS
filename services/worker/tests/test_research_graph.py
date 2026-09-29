"""T19 graph keeps checkpoint state minimal and stops at human review."""

import asyncio
import uuid

import pytest
from langgraph.checkpoint.memory import MemorySaver

from buyeros_worker.research_graph import build_research_graph, checkpoint_config

WS = uuid.UUID("11111111-1111-4111-8111-111111111111")
RUN = uuid.UUID("d0000000-0000-4000-8000-000000000019")
BUYER = uuid.UUID("e0000000-0000-4000-8000-000000000019")


class FixtureRunner:
    def __init__(self, *, hard=False):
        self.hard = hard
        self.calls = []

    async def load_basis(self, state):
        self.calls.append("load_basis")
        return {"basis_hash": "a" * 64}

    async def hard_exclusions(self, state):
        self.calls.append("hard_exclusions")
        return {"hard_excluded": self.hard}

    async def fit(self, state):
        self.calls.append("fit")
        return {"proposal_id": str(uuid.uuid5(uuid.NAMESPACE_URL, state["basis_hash"]))}

    async def verify(self, state):
        self.calls.append("verify")
        return {"verified": True}

    async def persist(self, state):
        self.calls.append("persist")
        return {"assessment_id": str(uuid.uuid5(uuid.NAMESPACE_URL,
            state["buyer_id"] + state["basis_hash"]))}


def _invoke(runner):
    async def work():
        graph = build_research_graph(MemorySaver(), runner)
        return await graph.ainvoke({"workspace_id": str(WS), "run_id": str(RUN),
            "buyer_id": str(BUYER), "workflow_version": "fit-v1", "attempt": 1},
            checkpoint_config(WS, RUN, "fit-v1", 1, BUYER))
    return asyncio.run(work())


def test_checkpoint_key_scopes_workspace_run_version_and_attempt():
    one = checkpoint_config(WS, RUN, "fit-v1", 1, BUYER)
    assert one["configurable"]["thread_id"] != checkpoint_config(WS, RUN, "fit-v1", 2, BUYER)["configurable"]["thread_id"]
    assert one["configurable"]["thread_id"] != checkpoint_config(uuid.uuid4(), RUN, "fit-v1", 1, BUYER)["configurable"]["thread_id"]
    assert one["configurable"]["thread_id"].startswith(f"{WS}:")


def test_graph_stops_at_review_with_id_only_checkpoint_state():
    runner = FixtureRunner()
    result = _invoke(runner)
    assert runner.calls == ["load_basis", "hard_exclusions", "fit", "verify", "persist"]
    assert result["assessment_id"] and result["next_action"] == "human_review"
    assert set(result) <= {"workspace_id", "run_id", "buyer_id", "workflow_version", "attempt",
                           "basis_hash", "hard_excluded", "proposal_id", "verified",
                           "assessment_id", "next_action"}


def test_hard_exclusion_bypasses_model_fit_node():
    runner = FixtureRunner(hard=True)
    result = _invoke(runner)
    assert runner.calls == ["load_basis", "hard_exclusions", "verify", "persist"]
    assert result["hard_excluded"] is True and result["next_action"] == "human_review"


def test_untrusted_fit_output_cannot_add_contact_or_send_action():
    class InjectingRunner(FixtureRunner):
        async def fit(self, state):
            self.calls.append("fit")
            return {"proposal_id": str(uuid.uuid4()), "send": "contact this buyer"}

    with pytest.raises(ValueError, match="invalid proposal_id"):
        _invoke(InjectingRunner())


def test_checkpoint_scope_mismatch_blocks_graph_before_business_callback():
    runner = FixtureRunner()
    async def work():
        graph = build_research_graph(MemorySaver(), runner)
        with pytest.raises(ValueError, match="checkpoint scope mismatch"):
            await graph.ainvoke({"workspace_id": str(WS), "run_id": str(RUN),
                "buyer_id": str(BUYER), "workflow_version": "fit-v1", "attempt": 1},
                checkpoint_config(uuid.uuid4(), RUN, "fit-v1", 1, BUYER))
    asyncio.run(work())
    assert runner.calls == []
