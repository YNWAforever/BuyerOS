import importlib
import importlib.util
from datetime import timedelta, timezone
from uuid import UUID, uuid4

import psycopg
import pytest
from buyeros_api.api.errors import ApiError
from buyeros_api.api.policy_activation_schemas import ActivationSubmit
from tests.policy_activation_fixtures import policy_case, owner_run, provision_fixture_authority, current_terms


def service():
    name = "buyeros_api.services.policy_activation_service"
    assert importlib.util.find_spec(name) is not None, "native activation request service is not implemented"
    return importlib.import_module(name)


def actor(case, role="requester"):
    m = service()
    # Deliberately claim admin even for a viewer: the service must refresh DB roles.
    return m.PolicyActor(case["workspace"], case["actors"][role], frozenset({"workspace_admin"}), 1)


def request_data(case, *, reference=None, purpose="contact_research"):
    authority = provision_fixture_authority(case)
    return ActivationSubmit(
        client_request_id=reference or uuid4(), authority_id=UUID(authority["authority_id"]), authority_version=1,
        expected_policy_id=None, expected_policy_version=None, terms=current_terms(case, purpose),
        request_deadline=case["now"] + timedelta(days=2),
    )


def submit(case, data, key="submit-policy-fixture-key", role="requester"):
    m = service()
    async def run(session):
        return await m.submit_activation(session, actor=actor(case, role), data=data, key=key, now=case["now"])
    return owner_run(case, run, runtime=True)


def test_submit_never_creates_permitted_policy(policy_case):
    m = service()
    data = request_data(policy_case)
    result = submit(policy_case, data)
    assert result.request_state == "submitted" and result.effective_status == "unknown"
    assert result.requester_id == policy_case["actors"]["requester"]
    with psycopg.connect(policy_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM policy_activation_requests").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM policy_decisions").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM audit_events WHERE action='policy.activation.submitted'").fetchone()[0] == 1


def test_same_key_replays_and_changed_body_conflicts(policy_case):
    service()
    data = request_data(policy_case)
    first = submit(policy_case, data)
    replay = submit(policy_case, data)
    assert first.receipt == replay.receipt and first.id == replay.id
    changed = data.model_copy(update={"request_deadline": data.request_deadline + timedelta(hours=1)})
    with pytest.raises(ApiError) as caught:
        submit(policy_case, changed)
    assert caught.value.status_code == 409


def test_new_key_with_same_client_reference_does_not_duplicate_request(policy_case):
    service()
    data = request_data(policy_case)
    first = submit(policy_case, data, "first-policy-operation-key")
    other = submit(policy_case, data, "second-policy-operation-key")
    assert first.id == other.id and first.receipt == other.receipt
    with psycopg.connect(policy_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM policy_activation_requests").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM audit_events WHERE action='policy.activation.submitted'").fetchone()[0] == 1


def test_unknown_first_response_is_resolved_by_client_reference(policy_case):
    m = service()
    data = request_data(policy_case)
    result = submit(policy_case, data)  # Simulate losing this response after commit.
    async def run(session):
        return await m.find_activation(session, actor=actor(policy_case), project_id=policy_case["project"],
                                       client_request_id=data.client_request_id, now=policy_case["now"])
    restored = owner_run(policy_case, run, runtime=True)
    assert restored.id == result.id and restored.terms_hash == result.terms_hash


@pytest.mark.parametrize("role,status", [("viewer", 403), ("operator", 403), ("reviewer", 403), ("revoked", 404), ("foreign", 404)])
def test_foreign_request_and_source_lookup_does_not_enumerate(policy_case, role, status):
    m = service()
    data = request_data(policy_case)
    with pytest.raises(ApiError) as caught:
        submit(policy_case, data, "invalid-actor-request-key", role)
    assert caught.value.status_code == status
    async def read(session):
        return await m.get_activation(session, actor=actor(policy_case, role), request_id=uuid4(), now=policy_case["now"])
    with pytest.raises(ApiError) as caught:
        owner_run(policy_case, read, runtime=True)
    assert caught.value.status_code == status


def test_unknown_or_foreign_document_cannot_enter_request_scope(policy_case):
    service()
    data = request_data(policy_case)
    terms = data.terms.model_copy(update={
        "allowed_sources": data.terms.allowed_sources.model_copy(update={"document_ids": (uuid4(),)})
    })
    with pytest.raises(ApiError) as caught:
        submit(policy_case, data.model_copy(update={"terms": terms}))
    assert caught.value.status_code in {404, 422}


def test_same_reference_with_offset_deadline_replays_the_same_application(policy_case):
    service()
    data = request_data(policy_case)
    data = data.model_copy(update={"request_deadline": data.request_deadline.astimezone(timezone(timedelta(hours=8)))})
    first = submit(policy_case, data, "offset-first-operation-key")
    other = submit(policy_case, data, "offset-second-operation-key")
    assert first.id == other.id
