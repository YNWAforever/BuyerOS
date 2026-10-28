"""Actual authenticated HTTP + forced tenant RLS, synthetic approved facts only."""
import uuid
from copy import deepcopy

import psycopg
import pytest
from psycopg.types.json import Jsonb

from buyeros_api.db.icp import canonical_hash
from buyeros_api.services.conversation_reply import reply_from_grounding
from tests.icp_fixtures import FACT_ID, valid_icp_payload
from tests.test_buyer_review_db import api, _h, OPERATOR, VIEWER, ADMIN, WORKSPACE_A, WORKSPACE_B, PROJECT_A, PROJECT_B

PROFILE = "c5000000-0000-4000-8000-000000000001"
DOCUMENT = "c3000000-0000-4000-8000-000000000001"
SOURCE = f"fact:profile:{PROFILE}:{FACT_ID}"
PATH = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/conversation-reply"


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("NEXT_PUBLIC_CONVERSATION_HOME", "true")


@pytest.fixture
def conversation_api(enabled, api, seeded):
    content = valid_icp_payload()
    content["offer_document_ids"] = [DOCUMENT]
    fact = content["offer_facts"][0]
    fact.update(provenance="document_excerpt", source_document_id=DOCUMENT, excerpt="Approved source excerpt")
    content["offer_facts"].append({"id":str(uuid.uuid4()),"field":"other", "value":"UNSELECTED_FACT_BODY", "provenance":"user_entered", "approved":False})
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("INSERT INTO offer_documents(id,workspace_id,project_id,kind,filename,media_type,status,sha256,retention_until,fact_candidates) VALUES(%s,%s,%s,'upload','private.txt','text/plain','ready',%s,now()+interval '1 day',%s)",
            (DOCUMENT, WORKSPACE_A, PROJECT_A, "a" * 64, Jsonb([fact])))
        conn.execute("INSERT INTO icp_versions(id,workspace_id,project_id,number,basis_offer_revision,content,content_hash,approved_by,approved_at) VALUES(%s,%s,%s,1,1,%s,%s,%s,now())",
            (PROFILE, WORKSPACE_A, PROJECT_A, Jsonb(content), canonical_hash(content), uuid.uuid5(uuid.NAMESPACE_URL, ADMIN)))
        conn.execute("UPDATE projects SET active_icp_version_id=%s WHERE id=%s", (PROFILE, PROJECT_A))
    yield api, seeded


def ask(client, sources=None, **changes):
    return client.post(PATH, headers=_h(), json={"question": "Which sources support the offer?",
        "source_ids": sources if sources is not None else [SOURCE], "language": "en", **changes})


def fixture_reply(grounding):
    assert grounding.excerpts == ["Industrial sensors", "Industrial sensors"]
    return reply_from_grounding(grounding, fixture_candidate={"text": "Review the cited approved offer source.",
        "status": "needs_review", "fixture": True, "citations": deepcopy(grounding.citations)})


def test_selected_approved_sources_return_only_refs_under_fixture_override(conversation_api, monkeypatch):
    client, dsn = conversation_api
    from buyeros_api.api.routes import conversation
    monkeypatch.setattr(conversation, "reply_from_grounding", fixture_reply)
    result = ask(client, [SOURCE, f"document:{DOCUMENT}"])
    assert result.status_code == 200, result.text
    assert result.headers["cache-control"] == "no-store"
    data = result.json()["data"]
    assert [ref["id"] for ref in data["citations"]] == [SOURCE, f"document:{DOCUMENT}"]
    assert "Industrial sensors" not in result.text and "Approved source excerpt" not in result.text
    with psycopg.connect(dsn) as conn:
        assert conn.execute("SELECT count(*) FROM async_jobs WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM budget_reservations WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == 0


def test_valid_sources_with_live_admission_closed_are_honestly_unavailable(conversation_api):
    client, _ = conversation_api
    result = ask(client)
    assert result.status_code == 503 and result.json()["code"] == "CONVERSATION_MODEL_UNAVAILABLE"
    assert "data" not in result.json()


@pytest.mark.parametrize("mutation", ["foreign_project", "foreign_workspace", "missing_fact", "candidate", "inference", "unapproved", "superseded", "stale_offer", "hash", "expired", "deleted", "document_candidate", "empty", "partial", "duplicate", "tools", "body", "membership", "viewer"])
def test_unavailable_sources_permissions_and_extra_inputs_never_reach_generation(conversation_api, monkeypatch, mutation):
    client, dsn = conversation_api
    from buyeros_api.api.routes import conversation
    def forbidden(*args, **kwargs):
        pytest.fail("invalid sources must never reach generation")
    monkeypatch.setattr(conversation, "reply_from_grounding", forbidden)
    sources, changes, headers, target = [SOURCE], {}, _h(), PATH
    with psycopg.connect(dsn, autocommit=True) as conn:
        if mutation == "foreign_project":
            target = PATH.replace(PROJECT_A, PROJECT_B)
        elif mutation == "foreign_workspace":
            target = PATH.replace(WORKSPACE_A, WORKSPACE_B).replace(PROJECT_A, PROJECT_B)
        elif mutation == "missing_fact":
            sources = [f"fact:profile:{PROFILE}:{uuid.uuid4()}"]
        elif mutation in {"candidate", "document_candidate"}:
            sources = [f"fact:document:{DOCUMENT}:{FACT_ID}"]
        elif mutation == "unapproved":
            conn.execute("UPDATE icp_versions SET approved_by=NULL,approved_at=NULL WHERE id=%s", (PROFILE,))
        elif mutation == "superseded":
            conn.execute("UPDATE icp_versions SET superseded_at=now() WHERE id=%s", (PROFILE,))
        elif mutation == "stale_offer":
            conn.execute("UPDATE projects SET offer_revision=2 WHERE id=%s", (PROJECT_A,))
        elif mutation in {"hash", "inference"}:
            content = conn.execute("SELECT content FROM icp_versions WHERE id=%s", (PROFILE,)).fetchone()[0]
            content["offer_facts"][0]["provenance"] = "model_inference"
            conn.execute("UPDATE icp_versions SET content=%s,content_hash=%s WHERE id=%s",
                (Jsonb(content), canonical_hash(content) if mutation == "inference" else "sha256:" + "0" * 64, PROFILE))
        elif mutation == "expired":
            conn.execute("UPDATE offer_documents SET retention_until=now()-interval '1 second' WHERE id=%s", (DOCUMENT,))
        elif mutation == "deleted":
            conn.execute("UPDATE offer_documents SET status='deleted' WHERE id=%s", (DOCUMENT,))
        elif mutation == "empty":
            sources = []
        elif mutation == "partial":
            sources += [f"document:{uuid.uuid4()}"]
        elif mutation == "duplicate":
            sources *= 2
        elif mutation in {"tools", "body"}:
            changes[mutation] = "untrusted"
        elif mutation == "membership":
            conn.execute("UPDATE memberships SET active=false WHERE user_id=%s", (uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR),))
        elif mutation == "viewer":
            headers = _h(VIEWER)
    response = client.post(target, headers=headers, json={"question": "Please review.", "source_ids": sources, "language": "en", **changes})
    assert response.status_code in {403, 404, 422}, response.text
    assert "data" not in response.json()
