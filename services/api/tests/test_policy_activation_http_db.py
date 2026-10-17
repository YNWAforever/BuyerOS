from uuid import uuid4
import psycopg
import pytest

from buyeros_api.api.policy_activation_schemas import ActivationView
from tests.policy_activation_fixtures import policy_case, policy_api, policy_headers
from tests.test_policy_activation_requests_db import request_data
from tests.test_policy_activation_decisions_db import decision_data
from tests.contract_validation import assert_contract_response


def base(case):
    return f"/v1/workspaces/{case['workspace']}"


def test_contract_exposes_canonical_locator_and_exact_owner_decision(policy_api, policy_case):
    data = request_data(policy_case)
    authorities = policy_api.get(base(policy_case) + "/policy-controller-authorities",
        params={"project_id": str(policy_case["project"])}, headers=policy_headers(policy_case))
    assert authorities.status_code == 200, authorities.text
    assert len(authorities.json()["data"]["items"]) == 1
    assert_contract_response("AuthorityPageResponse", authorities.json())
    assert "designation_reference" not in authorities.text
    created = policy_api.post(base(policy_case) + "/policy-activation-requests",
        json=data.model_dump(mode="json"), headers=policy_headers(policy_case, key="http-submit-fixture-key"))
    assert created.status_code == 201, created.text
    request = ActivationView.model_validate(created.json()["data"])
    assert_contract_response("ActivationViewResponse", created.json())
    approved = policy_api.post(base(policy_case) + f"/policy-activation-requests/{request.id}/decisions",
        json=decision_data(request).model_dump(mode="json"),
        headers=policy_headers(policy_case, "owner", "http-approve-fixture-key"))
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["receipt"]["outcome"] == "approved"
    assert_contract_response("ActivationViewResponse", approved.json())
    history = policy_api.get(base(policy_case) + f"/policy-activation-requests/{request.id}",
                             headers=policy_headers(policy_case))
    assert history.status_code == 200 and history.json()["data"]["request_state"] == "approved"
    lookup = policy_api.get(base(policy_case) + "/policy-activation-requests",
        params={"project_id": str(policy_case["project"]), "client_request_id": str(data.client_request_id)},
        headers=policy_headers(policy_case))
    assert lookup.status_code == 200 and lookup.json()["data"]["items"][0]["id"] == str(request.id)
    assert_contract_response("ActivationPageResponse", lookup.json())


@pytest.mark.parametrize("role,status", [("viewer", 403), ("operator", 403), ("revoked", 404), ("foreign", 404)])
def test_http_roles_and_foreign_scope_are_denied_before_write(policy_api, policy_case, role, status):
    data = request_data(policy_case)
    assert policy_api.get(base(policy_case) + "/policy-controller-authorities",
        params={"project_id": str(policy_case["project"])}, headers=policy_headers(policy_case)).status_code == 200
    response = policy_api.post(base(policy_case) + "/policy-activation-requests",
        json=data.model_dump(mode="json"), headers=policy_headers(policy_case, role, "http-denied-fixture-key"))
    assert response.status_code == status, response.text
    with psycopg.connect(policy_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM policy_activation_requests").fetchone()[0] == 0


def test_http_actor_fields_cannot_be_forged_and_old_permitted_route_stays_closed(policy_api, policy_case):
    data = request_data(policy_case)
    body = {**data.model_dump(mode="json"), "actor_id": str(policy_case["actors"]["owner"])}
    forged = policy_api.post(base(policy_case) + "/policy-activation-requests",
        json=body, headers=policy_headers(policy_case, key="http-forged-fixture-key"))
    assert forged.status_code == 422, forged.text
    old = policy_api.post(base(policy_case) + "/policy-decisions", json={
        "subject_type": "project", "subject_id": str(policy_case["project"]),
        "controller_scope_id": str(policy_case["workspace"]), "purpose": "contact_research", "status": "permitted",
        "policy_version": "not-approved", "basis_reference": "fixture basis", "provenance": "client checkbox",
        "countries": ["GB"], "expires_at": data.terms.expires_at.isoformat(), "retention_days": 30,
    }, headers=policy_headers(policy_case, "owner", "http-old-permit-key"))
    assert old.status_code == 403 and old.json()["code"] == "POLICY_APPROVAL_REQUIRED"


def test_unknown_request_is_non_enumerating(policy_api, policy_case):
    assert policy_api.get(base(policy_case) + "/policy-controller-authorities",
        params={"project_id": str(policy_case["project"])}, headers=policy_headers(policy_case)).status_code == 200
    response = policy_api.get(base(policy_case) + f"/policy-activation-requests/{uuid4()}",
                              headers=policy_headers(policy_case))
    assert response.status_code == 404


def test_incomplete_http_terms_are_rejected_before_any_write(policy_api, policy_case):
    data = request_data(policy_case).model_dump(mode="json")
    del data["terms"]["deletion_plan"]
    response = policy_api.post(base(policy_case) + "/policy-activation-requests", json=data,
                               headers=policy_headers(policy_case, key="http-incomplete-fixture"))
    assert response.status_code == 422
    with psycopg.connect(policy_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM policy_activation_requests").fetchone() == (0,)
