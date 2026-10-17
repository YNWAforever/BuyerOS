from uuid import uuid4
import psycopg
import pytest

from buyeros_api.api.errors import ApiError
from buyeros_api.api.policy_activation_schemas import ActivationDecision, ActivationWithdrawal
from tests.policy_activation_fixtures import policy_case, owner_run
from tests.test_policy_activation_requests_db import service, actor, request_data, submit


def test_membership_refresh_cannot_reuse_a_stale_identity_map_value(policy_case):
    """A deactivation committed by another transaction must be seen, not cached."""
    from buyeros_api.api.errors import ApiError
    m = service()
    stale = m.PolicyActor(policy_case["workspace"], policy_case["actors"]["requester"],
                          frozenset({"workspace_admin"}), 1)
    async def run(session):
        assert (await m.refresh_actor_membership(session, stale)).roles
        with psycopg.connect(policy_case["dsn"], autocommit=True) as db:
            db.execute("UPDATE memberships SET active=false,version=version+1 "
                       "WHERE workspace_id=%s AND user_id=%s", (policy_case["workspace"], stale.user_id))
        with pytest.raises(ApiError) as caught:
            await m.refresh_actor_membership(session, stale)
        assert caught.value.status_code == 404
    owner_run(policy_case, run, runtime=True)


def decision_data(request, action="approve"):
    return ActivationDecision(action=action, terms_hash=request.terms_hash,
                              expected_policy_id=None, expected_policy_version=None,
                              reason="synthetic exact-content review, no outreach")


def decide(case, request, *, role="owner", action="approve", key="decide-policy-fixture-key", now=None):
    m = service()
    assert hasattr(m, "decide_activation"), "atomic controller decision is not implemented"
    async def run(session):
        return await m.decide_activation(session, actor=actor(case, role), request_id=request.id,
            data=decision_data(request, action), key=key, now=now or case["now"])
    return owner_run(case, run, runtime=True)


def test_designated_owner_approves_one_exact_request(policy_case):
    request = submit(policy_case, request_data(policy_case))
    approved = decide(policy_case, request)
    replay = decide(policy_case, request)
    assert approved.receipt == replay.receipt
    assert approved.request_state == "approved" and approved.effective_status == "permitted"
    assert approved.receipt.policy_version == 1
    with psycopg.connect(policy_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM policy_activation_resolutions").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM policy_decisions WHERE status='permitted'").fetchone()[0] == 1
        assert db.execute("SELECT decision_author_id FROM policy_decisions").fetchone()[0] == policy_case["actors"]["owner"]
        assert db.execute("SELECT count(*) FROM audit_events WHERE action='policy.activation.approved'").fetchone()[0] == 1


def test_real_owner_can_request_and_approve_without_fabricated_second_person(policy_case):
    request = submit(policy_case, request_data(policy_case), role="owner")
    assert decide(policy_case, request).receipt.outcome == "approved"


def test_nondesignated_admin_cannot_approve(policy_case):
    request = submit(policy_case, request_data(policy_case))
    with pytest.raises(ApiError) as caught:
        decide(policy_case, request, role="unqualified")
    assert caught.value.status_code == 403


@pytest.mark.parametrize("fault", ["audit", "invalidation"])
def test_audit_or_invalidation_failure_rolls_back_everything(policy_case, monkeypatch, fault):
    m = service()
    request = submit(policy_case, request_data(policy_case))
    assert hasattr(m, "decide_activation"), "atomic controller decision is not implemented"
    if fault == "audit":
        def unavailable(*args, **kwargs):
            raise RuntimeError("synthetic audit unavailable")
        monkeypatch.setattr(m, "append_audit", unavailable)
    else:
        from buyeros_api.services import approval_service
        async def unavailable(*args, **kwargs):
            raise RuntimeError("synthetic invalidation unavailable")
        monkeypatch.setattr(approval_service, "invalidate_approvals_for_subject", unavailable)
    with pytest.raises(RuntimeError, match="synthetic"):
        decide(policy_case, request)
    with psycopg.connect(policy_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM policy_activation_resolutions").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM policy_decisions").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM idempotency_records WHERE operation_id='decidePolicyActivationRequest'").fetchone()[0] == 0


def append_block(case, *, version=1):
    from datetime import timedelta
    with psycopg.connect(case["dsn"]) as db:
        db.execute(
            "INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,controller_scope_id,"
            "purpose,status,policy_version,basis_reference,provenance,countries,expires_at,retention_days,"
            "decision_author_id,version,created_at) "
            "VALUES(%s,%s,'project',%s,%s,'contact_research','blocked','blocked-v1','fixture basis',"
            "'fixture provenance',ARRAY['GB'],%s,30,%s,%s,now()-interval '1 hour')",
            (uuid4(), case["workspace"], case["project"], case["workspace"],
             case["now"] + timedelta(days=10), case["actors"]["owner"], version),
        )


def test_stale_head_cannot_be_approved(policy_case):
    request = submit(policy_case, request_data(policy_case))
    append_block(policy_case)
    with pytest.raises(ApiError) as caught:
        decide(policy_case, request)
    assert caught.value.status_code == 412


def test_earlier_transaction_timestamp_cannot_hide_later_blocked_version(policy_case):
    m = service()
    request = submit(policy_case, request_data(policy_case))
    approved = decide(policy_case, request)
    append_block(policy_case, version=2)
    async def read(session):
        return await m.get_activation(session, actor=actor(policy_case), request_id=request.id, now=policy_case["now"])
    current = owner_run(policy_case, read, runtime=True)
    assert current.effective_status == "blocked"
    assert current.receipt == approved.receipt  # history version must not become the new head version


def test_reject_and_pending_withdraw_never_create_permission(policy_case):
    m = service()
    first = submit(policy_case, request_data(policy_case))
    assert decide(policy_case, first, action="reject").receipt.outcome == "rejected"
    other = submit(policy_case, request_data(policy_case), key="other-policy-submit-key")
    assert hasattr(m, "withdraw_activation"), "pending withdrawal is not implemented"
    async def run(session):
        return await m.withdraw_activation(session, actor=actor(policy_case), request_id=other.id,
            data=ActivationWithdrawal(terms_hash=other.terms_hash, reason="synthetic withdrawal"),
            key="withdraw-pending-policy-key", now=policy_case["now"])
    withdrawn = owner_run(policy_case, run, runtime=True)
    assert withdrawn.receipt.outcome == "withdrawn"
    with psycopg.connect(policy_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM policy_decisions").fetchone()[0] == 0
