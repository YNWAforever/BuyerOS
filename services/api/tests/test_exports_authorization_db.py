"""T26 audited export: current-policy content gate and zero delivery side effects."""
import csv
import io
import uuid

import psycopg

from tests.test_api_projects_db import api
from tests.test_draft_approval_context_db import _addressed_case, _approval_payload, _approve, _review
from tests.test_lookup_quotes_db import OPERATOR, REVIEWER, WORKSPACE_A, PROJECT, _h, quote_case
from tests.contract_validation import assert_contract_response


def _permit(db, purpose):
    db.execute(
        "INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,controller_scope_id,"
        "purpose,status,policy_version,basis_reference,provenance,countries,expires_at,"
        "retention_days,decision_author_id) VALUES (%s,%s,'project',%s,%s,%s,'permitted',"
        "'fixture-v1','fixture','fixture',ARRAY['US'],now()+interval '1 day',1,%s)",
        (uuid.uuid4(), WORKSPACE_A, PROJECT, WORKSPACE_A, purpose,
         uuid.uuid5(uuid.NAMESPACE_URL, REVIEWER)),
    )


def _buyer_body(buyers):
    return {"selection": {"kind": "explicit", "buyers": [
        {"id": buyer_id, "version": 1} for buyer_id, _ in buyers]},
        "purpose": "export_accounts", "include_contact_data": False, "format": "csv"}


def test_buyer_export_excludes_blocked_row_then_revocation_blocks_download(quote_case):
    api, dsn, buyers = quote_case
    with psycopg.connect(dsn, autocommit=True) as db:
        _permit(db, "export_accounts")
        db.execute("UPDATE companies SET display_name=%s WHERE id=%s",
                   ("   \t=HYPERLINK(\"x\")\n\u4e2d\u6587", buyers[0][1]))
        db.execute("INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,"
                   "controller_scope_id,purpose,status,policy_version,basis_reference,provenance,"
                   "countries,expires_at,retention_days,decision_author_id) VALUES "
                   "(%s,%s,'company',%s,%s,'export_accounts','blocked','fixture-v1',"
                   "'fixture','fixture',ARRAY['US'],now()+interval '1 day',1,%s)",
                   (uuid.uuid4(), WORKSPACE_A, buyers[1][1], WORKSPACE_A,
                    uuid.uuid5(uuid.NAMESPACE_URL, REVIEWER)))
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/exports"
    created = api.post(path, json=_buyer_body(buyers), headers=_h(OPERATOR, key="buyer-export-001"))
    assert created.status_code == 202, created.text
    assert_contract_response("ExportJobResponse", created.json())
    job = created.json()["data"]
    assert job["status"] == "ready" and job["record_count"] == 1
    assert job["requested_record_count"] == 2 and len(job["excluded_records"]) == 1
    content_path = f"/v1/workspaces/{WORKSPACE_A}/exports/{job['id']}/content"
    content = api.get(content_path, headers=_h(OPERATOR))
    assert content.status_code == 200, content.text
    records = list(csv.DictReader(io.StringIO(content.text)))
    assert len(records) == 1 and records[0]["data_mode"] == "live"
    assert "contact_value" not in records[0]
    assert records[0]["display_name"].startswith("'   \t=")
    assert "\u4e2d\u6587" in records[0]["display_name"]
    other_actor = api.get(content_path, headers=_h(REVIEWER))
    assert other_actor.status_code in {403, 404}
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE policy_decisions SET status='blocked',version=version+1 "
                   "WHERE workspace_id=%s AND subject_type='project' AND purpose='export_accounts'",
                   (WORKSPACE_A,))
    revoked = api.get(content_path, headers=_h(OPERATOR))
    assert revoked.status_code == 403 and revoked.json()["code"] == "POLICY_BLOCKED"
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT count(*) FROM outcome_events WHERE workspace_id=%s",
                          (WORKSPACE_A,)).fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM outbox_events WHERE event_type LIKE 'delivery.%%'",
                          ).fetchone()[0] == 0


def test_addressed_draft_copy_uses_same_guard_and_suppression_revokes(quote_case):
    api, dsn, buyers = quote_case
    draft_id, contact_id = _addressed_case(api, dsn, buyers)
    review = _review(api, draft_id)
    assert review.status_code == 200, review.text
    approval = _approve(api, draft_id, _approval_payload(review))
    assert approval.status_code == 201, approval.text
    draft = api.get(f"/v1/workspaces/{WORKSPACE_A}/drafts/{draft_id}",
                    headers=_h(OPERATOR)).json()["data"]
    path = f"/v1/workspaces/{WORKSPACE_A}/drafts/{draft_id}/exports"
    created = api.post(path, json={"revision_id": draft["revision_id"],
                                   "approval_id": approval.json()["data"]["id"],
                                   "format": "clipboard"},
                       headers=_h(OPERATOR, key="draft-export-001",
                                  **{"If-Match": f'"{draft["version"]}"'}))
    assert created.status_code == 202, created.text
    assert_contract_response("ExportJobResponse", created.json())
    job = created.json()["data"]
    assert job["kind"] == "draft_text" and job["record_count"] == 1
    content_path = f"/v1/workspaces/{WORKSPACE_A}/exports/{job['id']}/content"
    copied = api.get(content_path, headers=_h(OPERATOR))
    assert copied.status_code == 200 and "Industrial sensors" in copied.text
    assert "recipient@fixture.example" in copied.text
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("INSERT INTO suppressions(id,workspace_id,subject_key_hash,subject_type,"
                   "subject_id,controller_scope_id,purpose,purposes,reason,active,actor_id) "
                   "VALUES (%s,%s,%s,'contact_point',%s,%s,'export_contacts',"
                   "ARRAY['export_contacts'],'Fixture opt out',true,%s)",
                   (uuid.uuid4(), WORKSPACE_A, "e" * 64, contact_id, WORKSPACE_A,
                    uuid.uuid5(uuid.NAMESPACE_URL, REVIEWER)))
    revoked = api.get(content_path, headers=_h(OPERATOR))
    assert revoked.status_code == 403 and revoked.json()["code"] == "POLICY_BLOCKED"
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT count(*) FROM outcome_events WHERE workspace_id=%s",
                          (WORKSPACE_A,)).fetchone()[0] == 0


def test_export_rejects_missing_or_foreign_snapshot(quote_case):
    api, dsn, buyers = quote_case
    with psycopg.connect(dsn, autocommit=True) as db:
        _permit(db, "export_accounts")
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/exports"
    body = _buyer_body(buyers)
    body["selection"] = {"kind": "snapshot", "snapshot_id": str(uuid.uuid4()),
                         "excluded_ids": []}
    response = api.post(path, json=body, headers=_h(OPERATOR, key="snapshot-export-001"))
    assert response.status_code == 404 and response.json()["code"] == "NOT_FOUND"


def test_snapshot_owner_and_expiry_are_checked_before_export(quote_case):
    api, dsn, buyers = quote_case
    with psycopg.connect(dsn, autocommit=True) as db:
        _permit(db, "export_accounts")
        foreign_id, expired_id = uuid.uuid4(), uuid.uuid4()
        for snapshot_id, actor, expiry in (
            (foreign_id, REVIEWER, "now()+interval '1 day'"),
            (expired_id, OPERATOR, "now()-interval '1 second'"),
        ):
            db.execute("INSERT INTO buyer_snapshots(id,workspace_id,project_id,filter_hash,"
                       "actor_user_id,expires_at) VALUES (%s,%s,%s,%s,%s," + expiry + ")",
                       (snapshot_id, WORKSPACE_A, PROJECT, "sha256:" + "a" * 64,
                        uuid.uuid5(uuid.NAMESPACE_URL, actor)))
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/exports"
    for snapshot_id in (foreign_id, expired_id):
        body = _buyer_body(buyers)
        body["selection"] = {"kind": "snapshot", "snapshot_id": str(snapshot_id),
                             "excluded_ids": []}
        response = api.post(path, json=body,
                            headers=_h(OPERATOR, key=f"snapshot-check-{snapshot_id}"))
        assert response.status_code == 404 and response.json()["code"] == "NOT_FOUND"


def test_contact_export_requires_valid_current_contact_and_expires(quote_case):
    api, dsn, buyers = quote_case
    contact_id = uuid.uuid4()
    with psycopg.connect(dsn, autocommit=True) as db:
        for purpose in ("export_accounts", "export_contacts", "outreach"):
            _permit(db, purpose)
        db.execute("INSERT INTO contact_points(id,workspace_id,company_id,type,normalized_value,"
                   "validity,checked_at,quarantined) VALUES (%s,%s,%s,'business_email',"
                   "'contact@fixture.example','provider_marked_valid',now(),false)",
                   (contact_id, WORKSPACE_A, buyers[0][1]))
    body = _buyer_body(buyers)
    body.update({"purpose": "export_contacts", "include_contact_data": True})
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/exports"
    created = api.post(path, json=body, headers=_h(OPERATOR, key="contact-export-001"))
    assert created.status_code == 202, created.text
    job = created.json()["data"]
    assert job["record_count"] == 1 and job["requested_record_count"] == 2
    assert len(job["excluded_records"]) == 1
    content_path = f"/v1/workspaces/{WORKSPACE_A}/exports/{job['id']}/content"
    content = api.get(content_path, headers=_h(OPERATOR))
    assert content.status_code == 200 and "contact@fixture.example" in content.text
    replay = api.post(path, json=body, headers=_h(OPERATOR, key="contact-export-001"))
    assert replay.status_code == 202 and replay.json()["data"]["id"] == job["id"]
    changed = api.post(path, json={**body, "include_contact_data": False, "purpose": "export_accounts"},
                       headers=_h(OPERATOR, key="contact-export-001"))
    assert changed.status_code == 409
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE contact_points SET validity='unverified_public',version=version+1 "
                   "WHERE id=%s", (contact_id,))
    denied = api.get(content_path, headers=_h(OPERATOR))
    assert denied.status_code == 403 and denied.json()["code"] == "POLICY_BLOCKED"
    status = api.get(f"/v1/workspaces/{WORKSPACE_A}/exports/{job['id']}",
                     headers=_h(OPERATOR))
    assert status.status_code == 200 and status.json()["data"]["status"] == "revoked"
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE export_jobs SET expires_at=now()-interval '1 second',state='ready' "
                   "WHERE id=%s", (job["id"],))
    expired = api.get(content_path, headers=_h(OPERATOR))
    assert expired.status_code == 403
    status = api.get(f"/v1/workspaces/{WORKSPACE_A}/exports/{job['id']}",
                     headers=_h(OPERATOR))
    assert status.json()["data"]["status"] == "expired"


def test_content_authorizer_rechecks_membership_under_current_lock(quote_case):
    """A stale route-level membership read cannot authorize later content release."""
    import asyncio
    import pytest
    from buyeros_api.api.deps import tenant_scoped
    from buyeros_api.api.errors import ApiError
    from buyeros_api.services.export_service import authorize_export_content

    api, dsn, buyers = quote_case
    with psycopg.connect(dsn, autocommit=True) as db:
        _permit(db, "export_accounts")
    created = api.post(f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/exports",
                       json=_buyer_body([buyers[0]]),
                       headers=_h(OPERATOR, key="member-revocation-export"))
    assert created.status_code == 202, created.text
    export_id = uuid.UUID(created.json()["data"]["id"])
    actor_id = uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR)
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE memberships SET active=false,version=version+1 "
                   "WHERE workspace_id=%s AND user_id=%s", (WORKSPACE_A, actor_id))

    async def authorize_after_revocation():
        async with tenant_scoped(uuid.UUID(WORKSPACE_A)) as session:
            return await authorize_export_content(session, workspace_id=uuid.UUID(WORKSPACE_A),
                actor_id=actor_id, export_id=export_id)

    with pytest.raises(ApiError) as denied:
        asyncio.run(authorize_after_revocation())
    assert denied.value.status_code == 403
