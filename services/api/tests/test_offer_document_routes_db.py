"""T16 document API: persisted state, authorization, replay, and deletion."""
import hashlib
import uuid

import psycopg
import pytest

from tests.test_buyer_review_db import (
    ADMIN, OPERATOR, PROJECT_A, PROJECT_B, VIEWER, WORKSPACE_A, WORKSPACE_B,
    _h, api,
)


@pytest.fixture
def doc_api(api, seeded):
    yield api
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("DELETE FROM offer_documents WHERE workspace_id=%s", (WORKSPACE_A,))


def _upload(client, *, subject=OPERATOR, key="offer-upload-001", body=b"Product: Sensor\n"):
    return client.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/offer-documents",
        headers=_h(subject=subject, key=key),
        files={"file": ("offer.txt", body, "text/plain")},
        data={"declared_sha256": hashlib.sha256(body).hexdigest()},
    )


def test_upload_requires_private_store_and_does_not_claim_success(doc_api):
    response = _upload(doc_api)
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "PROVIDER_UNAVAILABLE"


def test_upload_read_replay_and_delete_are_tenant_and_version_bound(doc_api, seeded, monkeypatch):
    from buyeros_api.api.routes import documents

    saved = {}
    class Store:
        async def put_private(self, body, *, digest, retention_seconds):
            key = f"tenants/{WORKSPACE_A}/{uuid.uuid4()}"
            saved[key] = body
            return key

        async def delete_private(self, key):
            saved.pop(key, None)

    monkeypatch.setattr(documents, "get_private_store", lambda workspace_id: Store())
    response = _upload(doc_api)
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["status"] == "quarantined" and data["sha256"] == hashlib.sha256(b"Product: Sensor\n").hexdigest()
    assert data["fact_candidates"] == []
    assert data["id"] and len(saved) == 1
    assert "object_key" not in data

    replay = _upload(doc_api)
    assert replay.status_code == 202 and replay.json()["data"]["id"] == data["id"]
    assert len(saved) == 1
    conflict = _upload(doc_api, body=b"Product: Other\n")
    assert conflict.status_code == 409 and len(saved) == 1
    assert _upload(doc_api, subject=VIEWER, key="offer-upload-viewer").status_code == 403

    url = f"/v1/workspaces/{WORKSPACE_A}/offer-documents/{data['id']}"
    read = doc_api.get(url, headers=_h(subject=VIEWER))
    assert read.status_code == 200 and read.json()["data"]["id"] == data["id"]
    assert doc_api.get(url.replace(WORKSPACE_A, WORKSPACE_B), headers=_h()).status_code == 404

    stale = doc_api.request("DELETE", url, headers=_h(key="offer-delete-001", **{"If-Match": '"2"'}), json={"reason": "obsolete"})
    assert stale.status_code == 412
    doc_api._transport.raise_server_exceptions = True
    deleted = doc_api.request("DELETE", url, headers=_h(key="offer-delete-001", **{"If-Match": '"1"'}), json={"reason": "obsolete"})
    assert deleted.status_code == 202, deleted.text
    assert deleted.json()["data"]["status"] == "deleted"
    assert deleted.json()["data"]["fact_candidates"] == []
    assert doc_api.get(url, headers=_h()).status_code == 404
    with psycopg.connect(seeded) as conn:
        row = conn.execute("SELECT status, object_key FROM offer_documents WHERE id=%s", (data["id"],)).fetchone()
        assert row == ("deleted", next(iter(saved)))


def test_foreign_project_and_bad_upload_fail_without_storing(doc_api, monkeypatch):
    from buyeros_api.api.routes import documents

    calls = []
    class Store:
        async def put_private(self, *args, **kwargs):
            calls.append("put")
            raise AssertionError("should not store")
    monkeypatch.setattr(documents, "get_private_store", lambda workspace_id: Store())
    bad = _upload(doc_api, body=b"MZ executable")
    assert bad.status_code == 400 and calls == []
    foreign = doc_api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_B}/offer-documents",
        headers=_h(key="offer-foreign-001"),
        files={"file": ("offer.txt", b"Product: X", "text/plain")},
        data={"declared_sha256": hashlib.sha256(b"Product: X").hexdigest()},
    )
    assert foreign.status_code == 404 and calls == []


def test_url_ingestion_requires_exact_current_source_permission(doc_api, seeded, monkeypatch):
    source_url = "https://example.com/offer"
    url = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/offer-ingestions"
    payload = {
        "source_url": source_url,
        "max_cost": {"amount": "0.000000", "currency": "USD"},
        "purpose": "offer_research",
    }
    denied = doc_api.post(url, headers=_h(key="offer-url-001"), json=payload)
    assert denied.status_code == 403 and denied.json()["code"] == "POLICY_BLOCKED"
    with psycopg.connect(seeded, autocommit=True) as conn:
        assert conn.execute(
            "SELECT count(*) FROM async_jobs WHERE kind='offer_ingestion' AND workspace_id=%s",
            (WORKSPACE_A,),
        ).fetchone()[0] == 0
        conn.execute(
            "INSERT INTO policy_decisions"
            "(id,workspace_id,subject_type,subject_id,controller_scope_id,purpose,status,"
            "policy_version,basis_reference,provenance,countries,expires_at,retention_days,decision_author_id)"
            " VALUES (%s,%s,'project',%s,%s,'offer_research','permitted',"
            "'fixture-reviewed',%s,'fixture-only','{HK}',now()+interval '1 day',1,%s)",
            (str(uuid.uuid4()), WORKSPACE_A, PROJECT_A, WORKSPACE_A, source_url,
             str(uuid.uuid5(uuid.NAMESPACE_URL, ADMIN))),
        )
    from buyeros_api.api.routes import documents
    monkeypatch.setattr(documents, "get_private_store", lambda workspace_id: object())
    accepted = doc_api.post(url, headers=_h(key="offer-url-001"), json=payload)
    assert accepted.status_code == 202, accepted.text
    job = accepted.json()["data"]
    assert job["kind"] == "offer_ingestion" and job["status"] == "queued"
    assert doc_api.post(url, headers=_h(key="offer-url-001"), json=payload).json()["data"]["id"] == job["id"]
    with psycopg.connect(seeded) as conn:
        document = conn.execute(
            "SELECT status,sha256,source_url FROM offer_documents WHERE workspace_id=%s AND kind='url'",
            (WORKSPACE_A,),
        ).fetchone()
        assert document == ("queued", None, source_url)
    wrong = doc_api.post(
        url, headers=_h(key="offer-url-other"),
        json={**payload, "source_url": "https://example.com/other"},
    )
    assert wrong.status_code == 403 and wrong.json()["code"] == "POLICY_BLOCKED"


def test_reviewed_profile_document_reference_goes_stale_on_delete(doc_api, seeded, monkeypatch):
    import json
    from tests.icp_fixtures import valid_icp_payload
    from buyeros_api.api.routes import documents

    class Store:
        async def put_private(self, body, *, digest, retention_seconds):
            return f"tenants/{WORKSPACE_A}/{uuid.uuid4()}"
    monkeypatch.setattr(documents, "get_private_store", lambda workspace_id: Store())
    uploaded = _upload(doc_api, key="offer-profile-doc")
    assert uploaded.status_code == 202
    document_id = uploaded.json()["data"]["id"]
    candidate_id = str(uuid.uuid4())
    candidate = {
        "id": candidate_id, "field": "product", "value": "Sensor",
        "provenance": "document_excerpt", "source_document_id": document_id,
        "excerpt": "Sensor", "approved": False,
    }
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute(
            "UPDATE offer_documents SET status='ready',fact_candidates=%s::jsonb,version=2 WHERE id=%s",
            (json.dumps([candidate]), document_id),
        )
    project_url = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}"
    project = doc_api.get(project_url, headers=_h()).json()["data"]
    body = valid_icp_payload()
    body["basis_offer_revision"] = project["offer_revision"]
    body["offer_document_ids"] = [document_id]
    body["offer_facts"].append(candidate)
    saved = doc_api.post(
        f"{project_url}/icp-versions", json=body, headers=_h(key="profile-with-document"),
    )
    assert saved.status_code == 201, saved.text
    profile = saved.json()["data"]
    approved = doc_api.post(
        f"/v1/workspaces/{WORKSPACE_A}/icp-versions/{profile['id']}/approve",
        json={"content_hash": profile["content_hash"], "confirmation": True,
              "expected_project_version": project["version"]},
        headers=_h(subject="auth0|reviewer-a", key="approve-with-document",
                   **{"If-Match": f'"{profile["number"]}"'}),
    )
    assert approved.status_code == 200, approved.text
    deleted = doc_api.request(
        "DELETE", f"/v1/workspaces/{WORKSPACE_A}/offer-documents/{document_id}",
        headers=_h(key="delete-reviewed-doc", **{"If-Match": '"2"'}),
        json={"reason": "source withdrawn"},
    )
    assert deleted.status_code == 202, deleted.text
    current = doc_api.get(project_url, headers=_h()).json()["data"]
    assert current["active_icp_version_id"] is None
    assert current["offer_revision"] == project["offer_revision"] + 1
    assert current["version"] == project["version"] + 2


def test_offer_document_list_paginates_from_persisted_rows(doc_api, monkeypatch):
    from buyeros_api.api.routes import documents
    class Store:
        async def put_private(self, body, *, digest, retention_seconds):
            return f"tenants/{WORKSPACE_A}/{uuid.uuid4()}"
    monkeypatch.setattr(documents, "get_private_store", lambda workspace_id: Store())
    for n in range(3):
        assert _upload(
            doc_api, key=f"offer-page-{n:03d}", body=f"Product: Sensor {n}\n".encode(),
        ).status_code == 202
    url = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/offer-documents"
    first = doc_api.get(url, headers=_h(subject=VIEWER), params={"offset": 0, "limit": 2})
    assert first.status_code == 200, first.text
    assert first.json()["data"]["total"] == 3
    assert len(first.json()["data"]["items"]) == 2
    second = doc_api.get(url, headers=_h(subject=VIEWER), params={"offset": 2, "limit": 2})
    assert second.status_code == 200
    assert len(second.json()["data"]["items"]) == 1
    assert second.json()["data"]["items"][0]["id"] not in {
        item["id"] for item in first.json()["data"]["items"]
    }
