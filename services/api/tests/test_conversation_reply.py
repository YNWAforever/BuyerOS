"""Stage 2 fixture-only response contract: no provider, spend or tools."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app
from buyeros_api.api.errors import ApiError
from buyeros_api.services.conversation_reply import Grounding, ROUTE, reply_from_grounding

REF = {"id": "document:a3000000-0000-4000-8000-000000000001", "label": "Offer document",
       "locator": {"surface": "document", "id": "a3000000-0000-4000-8000-000000000001"}}
GROUNDING = Grounding(citations=[REF], excerpts=["Private approved excerpt"])
CANDIDATE = {"text": "Review the cited approved source before deciding.", "citations": [REF],
             "status": "needs_review", "fixture": True}


def test_live_admission_stays_closed_and_route_has_no_tools():
    assert ROUTE.route_id is None and not ROUTE.permitted_tools and ROUTE.repair_limit == 0
    with pytest.raises(ApiError, match="admission is unavailable") as exc:
        reply_from_grounding(GROUNDING)
    assert exc.value.status_code == 503


def test_fixture_reply_contains_only_review_text_and_selected_locator_refs():
    result = reply_from_grounding(GROUNDING, fixture_candidate=deepcopy(CANDIDATE))
    assert result == CANDIDATE
    assert "Private approved excerpt" not in str(result)


@pytest.mark.parametrize("mutation", ["tool_calls", "refusal", "foreign", "locator", "body", "label", "duplicate", "empty", "long", "success", "live"])
def test_fixture_refuses_tools_refusal_invented_citations_and_unreviewed_success(mutation):
    candidate = deepcopy(CANDIDATE)
    if mutation in {"tool_calls", "refusal"}:
        candidate[mutation] = [{"name": "start_research"}]
    elif mutation == "foreign":
        candidate["citations"][0]["id"] += "foreign"
    elif mutation == "locator":
        candidate["citations"][0]["locator"] = {"url": "https://foreign.invalid"}
    elif mutation == "body":
        candidate["citations"][0]["body"] = "Private approved excerpt"
    elif mutation == "label":
        candidate["citations"][0]["label"] = "Private document name"
    elif mutation == "duplicate":
        candidate["citations"] *= 2
    elif mutation == "empty":
        candidate["citations"] = []
    elif mutation == "long":
        candidate["text"] = "x" * 4001
    elif mutation == "success":
        candidate["status"] = "approved"
    else:
        candidate["fixture"] = False
    with pytest.raises(ApiError) as exc:
        reply_from_grounding(GROUNDING, fixture_candidate=candidate)
    assert exc.value.code == "CONVERSATION_REPLY_UNVERIFIED"


@pytest.mark.parametrize("flag", [None, "false", "TRUE", "1"])
def test_flag_off_has_no_new_route(flag, monkeypatch):
    monkeypatch.delenv("NEXT_PUBLIC_CONVERSATION_HOME", raising=False)
    if flag is not None:
        monkeypatch.setenv("NEXT_PUBLIC_CONVERSATION_HOME", flag)
    paths = {route.path for route in create_app().routes if hasattr(route, "path")}
    assert not any("conversation-reply" in path for path in paths)
    # The optional-route client exemption must not swallow membership NOT_FOUND errors.
    response = TestClient(create_app()).post(
        "/v1/workspaces/11111111-1111-4111-8111-111111111111/projects/22222222-2222-4222-8222-222222222222/conversation-reply")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
    assert response.json()["message"] == "request failed"


def test_flag_on_endpoint_requires_authentication(monkeypatch):
    monkeypatch.setenv("NEXT_PUBLIC_CONVERSATION_HOME", "true")
    response = TestClient(create_app()).post(
        "/v1/workspaces/11111111-1111-4111-8111-111111111111/projects/22222222-2222-4222-8222-222222222222/conversation-reply",
        json={"question": "What can I use?", "source_ids": [REF["id"]], "language": "en"})
    assert response.status_code == 401


def test_conversation_post_respects_the_existing_live_read_kill_switch(monkeypatch):
    from types import SimpleNamespace
    from buyeros_api.api.auth import get_principal
    from buyeros_api.api.routes import conversation
    monkeypatch.setenv("NEXT_PUBLIC_CONVERSATION_HOME", "true")
    monkeypatch.setattr(conversation, "get_settings", lambda: SimpleNamespace(live_read_enabled=False))
    app = create_app()
    app.dependency_overrides[get_principal] = lambda: object()
    response = TestClient(app).post(
        "/v1/workspaces/11111111-1111-4111-8111-111111111111/projects/22222222-2222-4222-8222-222222222222/conversation-reply",
        json={"question": "Review?", "source_ids": [REF["id"]], "language": "en"})
    assert response.status_code == 503 and response.json()["code"] == "READ_DISABLED"
