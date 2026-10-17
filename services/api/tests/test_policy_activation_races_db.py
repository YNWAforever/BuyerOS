import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time

import psycopg
import pytest
from sqlalchemy import update

from buyeros_api.api.errors import ApiError
from buyeros_api.api.policy_activation_schemas import ActivationWithdrawal
from buyeros_api.db.models import Membership
from buyeros_api.services.membership_admin import lock_membership_admin
from tests.policy_activation_fixtures import policy_case, owner_run
from tests.test_policy_activation_requests_db import service, actor, request_data, submit
from tests.test_policy_activation_decisions_db import decide


@pytest.mark.parametrize("rival", ["reject", "withdraw"])
def test_approve_reject_withdraw_race_has_one_resolution(policy_case, rival):
    request = submit(policy_case, request_data(policy_case))
    m = service()
    assert hasattr(m, "decide_activation"), "atomic decisions are not implemented"
    def call(action):
        try:
            if action == "withdraw":
                async def work(session):
                    return await m.withdraw_activation(session, actor=actor(policy_case), request_id=request.id,
                        data=ActivationWithdrawal(terms_hash=request.terms_hash, reason="synthetic withdrawal"),
                        key="race-policy-withdraw", now=policy_case["now"])
                return owner_run(policy_case, work, runtime=True)
            return decide(policy_case, request, action=action, key="race-policy-" + action)
        except ApiError as error:
            return error
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(call, ("approve", rival)))
    assert len([r for r in rows if not isinstance(r, ApiError)]) == 1
    assert [r.status_code for r in rows if isinstance(r, ApiError)] == [409]
    with psycopg.connect(policy_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM policy_activation_resolutions").fetchone()[0] == 1


def test_different_keys_same_approval_return_one_resolution(policy_case):
    request = submit(policy_case, request_data(policy_case))
    first = decide(policy_case, request, key="approve-original-operation")
    second = decide(policy_case, request, key="approve-other-operation")
    assert first.receipt == second.receipt
    with psycopg.connect(policy_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM policy_decisions").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM audit_events WHERE action='policy.activation.approved'").fetchone()[0] == 1


def test_membership_revocation_serializes_before_approval_commit(policy_case):
    request = submit(policy_case, request_data(policy_case))
    assert hasattr(service(), "decide_activation"), "atomic decisions are not implemented"
    locked, release = Event(), Event()
    async def holder(session):
        await lock_membership_admin(session, policy_case["workspace"])
        locked.set()
        await asyncio.to_thread(release.wait, 8)
        await session.execute(update(Membership).where(
            Membership.workspace_id == policy_case["workspace"],
            Membership.user_id == policy_case["actors"]["owner"],
        ).values(active=False, version=2))
    with ThreadPoolExecutor(max_workers=2) as pool:
        held = pool.submit(owner_run, policy_case, holder)
        assert locked.wait(5)
        pending = pool.submit(decide, policy_case, request)
        try:
            waiting = False
            deadline = time.monotonic() + 5
            with psycopg.connect(policy_case["dsn"], autocommit=True) as db:
                while time.monotonic() < deadline and not pending.done():
                    waiting = db.execute(
                        "SELECT EXISTS(SELECT 1 FROM pg_locks l JOIN pg_stat_activity a ON a.pid=l.pid "
                        "WHERE a.datname=current_database() AND a.usename='buyeros_api' "
                        "AND l.locktype='advisory' AND NOT l.granted)"
                    ).fetchone()[0]
                    if waiting:
                        break
                    time.sleep(0.02)
            assert waiting, "approval must wait behind the real membership-admin transaction"
        finally:
            release.set()
        held.result(timeout=5)
        with pytest.raises(ApiError) as caught:
            pending.result(timeout=5)
        assert caught.value.status_code == 404
    with psycopg.connect(policy_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM policy_decisions").fetchone()[0] == 0
