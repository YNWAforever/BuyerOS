"""T19 fit workflow: checkpoint IDs only, with business effects behind a runner.

The graph is never a source of provider or policy authority. The runner must
re-read current tenant-scoped business rows before each durable operation.
"""

import re
import uuid
from typing import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph


class ResearchState(TypedDict, total=False):
    workspace_id: str
    run_id: str
    buyer_id: str
    workflow_version: str
    attempt: int
    basis_hash: str
    hard_excluded: bool
    proposal_id: str
    verified: bool
    assessment_id: str
    next_action: str


def checkpoint_config(workspace_id, run_id, workflow_version: str, attempt: int,
                      buyer_id=None) -> dict:
    workspace = uuid.UUID(str(workspace_id))
    run = uuid.UUID(str(run_id))
    if not re.fullmatch(r"fit-v[1-9][0-9]*", workflow_version):
        raise ValueError("invalid workflow version")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ValueError("invalid workflow attempt")
    buyer_suffix = f":{uuid.UUID(str(buyer_id))}" if buyer_id is not None else ""
    return {"configurable": {
        "thread_id": f"{workspace}:{run}:{workflow_version}:{attempt}{buyer_suffix}",
        "checkpoint_ns": "",
    }}


def _shape(value, key: str, kind) -> dict:
    if not isinstance(value, dict) or set(value) != {key} or not isinstance(value[key], kind):
        raise ValueError(f"invalid {key} workflow result")
    return value


def build_research_graph(checkpointer, provider_runner):
    """Compile a bounded per-buyer fit graph with no contact or send edge.

    ``provider_runner`` owns scoped reads, model budgeting if activated,
    citation verification and idempotent assessment persistence. This graph
    checkpoints only identifiers, flags and a basis hash.
    """
    graph = StateGraph(ResearchState)

    async def validate(state: ResearchState, config: RunnableConfig) -> dict:
        expected = checkpoint_config(state["workspace_id"], state["run_id"],
                                     state["workflow_version"], state["attempt"],
                                     state["buyer_id"])
        if config.get("configurable", {}).get("thread_id") != expected["configurable"]["thread_id"]:
            raise ValueError("checkpoint scope mismatch")
        uuid.UUID(state["buyer_id"])
        return {}

    async def load_basis(state: ResearchState) -> dict:
        result = _shape(await provider_runner.load_basis(state), "basis_hash", str)
        if not re.fullmatch(r"[0-9a-f]{64}", result["basis_hash"]):
            raise ValueError("invalid basis hash")
        return result

    async def hard_exclusions(state: ResearchState) -> dict:
        result = _shape(await provider_runner.hard_exclusions(state), "hard_excluded", bool)
        return result

    async def fit(state: ResearchState) -> dict:
        result = _shape(await provider_runner.fit(state), "proposal_id", str)
        uuid.UUID(result["proposal_id"])
        return result

    async def verify(state: ResearchState) -> dict:
        result = _shape(await provider_runner.verify(state), "verified", bool)
        if result["verified"] is not True:
            raise ValueError("fit citation verification failed")
        return result

    async def persist(state: ResearchState) -> dict:
        result = _shape(await provider_runner.persist(state), "assessment_id", str)
        uuid.UUID(result["assessment_id"])
        return {**result, "next_action": "human_review"}

    graph.add_node("validate", validate)
    graph.add_node("load_basis", load_basis)
    graph.add_node("hard_exclusions", hard_exclusions)
    graph.add_node("fit", fit)
    graph.add_node("verify", verify)
    graph.add_node("persist", persist)
    graph.add_edge(START, "validate")
    graph.add_edge("validate", "load_basis")
    graph.add_edge("load_basis", "hard_exclusions")
    graph.add_conditional_edges("hard_exclusions", lambda state: "verify" if state["hard_excluded"] else "fit")
    graph.add_edge("fit", "verify")
    graph.add_edge("verify", "persist")
    graph.add_edge("persist", END)
    return graph.compile(checkpointer=checkpointer)
