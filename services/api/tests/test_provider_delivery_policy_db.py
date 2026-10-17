"""Provider grant is necessary, never sufficient, for synthetic sending."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4, uuid5, NAMESPACE_URL

import psycopg
import pytest

from buyeros_api.api.errors import ApiError
from tests.test_delivery_admission_db import admission_case, run, counts
from tests.test_lookup_quotes_db import WORKSPACE_A, PROJECT
from tests.test_api_projects_db import ADMIN
from tests.policy_activation_fixtures import approve_provider_fixture, owner_run


def test_unapproved_provider_account_or_contract_creates_no_hold_or_message(admission_case):
    _, dsn, args, authority = admission_case
    before = counts(dsn)
    for changed in ({"provider_name": "other"}, {"account_reference": "other"},
                    {"reviewed_contract_hash": "c" * 64}):
        with pytest.raises(ApiError) as error:
            run(dsn, args, replace(authority, **changed))
        assert (error.value.status_code, error.value.code) == (403, "POLICY_BLOCKED")
        assert counts(dsn) == before


def test_review_only_policy_can_approve_content_but_cannot_admit_send(admission_case):
    from tests.test_draft_approval_context_db import _review, _approval_payload
    from tests.test_lookup_quotes_db import REVIEWER, _h
    _, dsn, args, authority = admission_case
    client = admission_case[0]
    with psycopg.connect(dsn) as db:
        domain = db.execute("SELECT c.domain FROM companies c JOIN project_buyers b ON b.company_id=c.id "
                            "JOIN outreach_drafts d ON d.buyer_id=b.id WHERE d.id=%s", (args["draft_id"],)).fetchone()[0]
    approve_provider_fixture(dsn, WORKSPACE_A, PROJECT, uuid5(NAMESPACE_URL, ADMIN),
        purpose="outreach", domains=(domain,), actions=["delivery.review"],
        scope={"provider_name": authority.provider_name, "account_reference": authority.account_reference,
               "contract_sha256": authority.reviewed_contract_hash,
               "sender_identity_id": str(args["sender_identity_id"]), "recipient_refs": [str(args["recipient_ref"])]})
    reviewed = _review(client, str(args["draft_id"]), key="review-after-review-only-policy")
    assert reviewed.status_code == 200, reviewed.text
    approved = client.post(f"/v1/workspaces/{WORKSPACE_A}/drafts/{args['draft_id']}/approvals",
        json=_approval_payload(reviewed), headers=_h(REVIEWER, key="approve-review-only-policy",
        **{"If-Match": f'"{reviewed.json()["data"]["version"]}"'}))
    assert approved.status_code == 201, approved.text
    from uuid import UUID
    bindings = {**args, "approval_id": UUID(approved.json()["data"]["id"])}
    before = counts(dsn)
    with pytest.raises(ApiError) as error:
        run(dsn, bindings, authority)
    assert (error.value.status_code, error.value.code) == (403, "POLICY_BLOCKED")
    assert counts(dsn) == before


def test_foreign_recipient_cannot_be_added_to_provider_application(admission_case):
    from buyeros_api.api.policy_activation_schemas import ActivationSubmit
    from buyeros_api.services import policy_activation_service as service
    client, dsn, args, _ = admission_case
    with psycopg.connect(dsn) as db:
        row = db.execute("SELECT r.authority_id,r.authority_version,r.terms,d.id,d.version "
                         "FROM policy_activation_requests r JOIN policy_activation_resolutions s ON s.request_id=r.id "
                         "JOIN policy_decisions d ON d.id=s.decision_id WHERE d.purpose='outreach' "
                         "ORDER BY d.version DESC LIMIT 1").fetchone()
        before = db.execute("SELECT count(*) FROM policy_activation_requests").fetchone()[0]
    terms = {**row[2], "provider_scope": {**row[2]["provider_scope"], "recipient_refs": [str(uuid4())]}}
    case = {"dsn": dsn, "workspace": args["workspace_id"]}
    actor = service.PolicyActor(args["workspace_id"], uuid5(NAMESPACE_URL, ADMIN), frozenset({"workspace_admin"}), 1)
    async def submit(session):
        return await service.submit_activation(session, actor=actor, data=ActivationSubmit(
            client_request_id=uuid4(), authority_id=row[0], authority_version=row[1],
            expected_policy_id=row[3], expected_policy_version=row[4], terms=terms,
            request_deadline=datetime.now(timezone.utc)+timedelta(hours=1)),
            key="provider-foreign-recipient", now=datetime.now(timezone.utc))
    with pytest.raises(ApiError) as error:
        owner_run(case, submit, runtime=True)
    assert error.value.status_code == 404
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT count(*) FROM policy_activation_requests").fetchone()[0] == before
