"""Read-only BuyerOS probes. Run with services/api/.venv/bin/python.

Pass the repository root as argv[1]. Uses fictional inputs and a fake SQL
connection: query counts are not latency measurements or PostgreSQL execution.
No credentials, network calls, database writes, or paid providers are used.
"""
import asyncio
import json
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

repo = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(repo / "services/api"))

from buyeros_api.api.auth import Principal
from buyeros_api.api.errors import ApiError
from buyeros_api.api.routes.workspaces import list_workspaces
from buyeros_api.execution.handlers.draft_generate import render_grounded_template
from buyeros_api.services.approval_service import current_approval_context


class Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def one_or_none(self):
        return self.value

    def all(self):
        return self.value


class Connection:
    def __init__(self, total):
        self.total = total
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def execute(self, *args, **kwargs):
        index = self.calls
        self.calls += 1
        if index == 0:
            return Result(uuid.UUID(int=1))
        if index == 1:
            return Result([(uuid.UUID(int=i + 10), f"Fictional workspace {i}")
                           for i in range(self.total)])
        if index % 2 == 0:
            return Result(None)  # set_config
        return Result(SimpleNamespace(id=uuid.UUID(int=index + 10000), roles=["viewer"]))


async def main():
    fanout = []
    for total, offset in [(1, 0), (10, 0), (100, 0), (1000, 0), (1000, 100)]:
        connection = Connection(total)
        with patch("buyeros_api.api.deps.get_engine",
                   return_value=SimpleNamespace(connect=lambda: connection)):
            response = await list_workspaces(
                SimpleNamespace(state=SimpleNamespace(request_id="audit-fictional")),
                offset=offset, limit=100,
                principal=Principal("https://fictional.invalid/", "audit-user"),
            )
        assert connection.calls == 2 + 2 * total
        fanout.append({"database_workspace_count": total, "offset": offset,
                       "limit": 100, "execute_calls": connection.calls,
                       "returned_items": len(response["data"]["items"])})

    facts = [{"id": str(uuid.UUID(int=1)), "approved": True,
              "value": "Fictional industrial sensors"}]
    evidence = [{"id": str(uuid.UUID(int=2)), "version": 1,
                 "stance": "supports", "excerpt": "Fictional buyer distributes sensors."}]
    common = {"facts": facts, "evidence": evidence, "language": "en", "kind": "initial"}
    first = render_grounded_template(**common, objective="Request a demonstration", tone="professional")
    second = render_grounded_template(**common, objective="Discuss procurement", tone="warm")
    style = {"same_subject": first["subject"] == second["subject"],
             "same_body": first["body"] == second["body"],
             "different_metadata": first["objective"] != second["objective"] and first["tone"] != second["tone"],
             "sample_count": 2, "route": first["route"]}
    assert all(style[key] for key in ("same_subject", "same_body", "different_metadata"))

    # The current edit_draft implementation sets these two fields. Exercise
    # the actual approval gate on that representation, without mocking a pass.
    edited = dict(first, grounding_status="needs_review", claims=[])
    try:
        await current_approval_context(None, workspace_id=uuid.UUID(int=3),
                                       project=None, draft=None,
                                       revision=SimpleNamespace(content=edited))
        raise AssertionError("Expected edited draft to require grounding")
    except ApiError as error:
        edit_gate = {"exception_type": type(error).__name__, "message": str(error),
                     "scope": "Actual approval gate; supplied edited-state fixture. Not a persisted full journey."}

    print(json.dumps({"workspace_query_fanout": fanout,
                      "draft_style_controls": style,
                      "edited_draft_approval_gate": edit_gate,
                      "limitations": ["No production traffic or PostgreSQL timing measured.",
                                      "No browser component mutation or end-to-end persistence exercised.",
                                      "These probes confirm existing behavior; they do not assert fixes are complete."]},
                     ensure_ascii=False, indent=2))


asyncio.run(main())
