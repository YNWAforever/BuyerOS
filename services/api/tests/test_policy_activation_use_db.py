from datetime import timedelta, datetime
from uuid import uuid4
import inspect

import psycopg
import pytest

from buyeros_api.api.errors import ApiError
from buyeros_api.api.policy_activation_schemas import PolicyUseContext, MANUAL_DATA, MANUAL_ACTIONS
from buyeros_api.api.lead_schemas import LeadScope
from tests.policy_activation_fixtures import policy_case, owner_run
from tests.test_policy_activation_requests_db import request_data, submit
from tests.test_policy_activation_decisions_db import decide


def test_policy_proof_uses_one_fresh_snapshot_and_refreshes_pinned_owner_membership(policy_case):
    """Keep proof coherent and bounded without caching a revoked identity."""
    from sqlalchemy import select, event
    from buyeros_api.db.models import Membership
    from buyeros_api.services.policy_activation_read import latest_head, resolve_approved_policy_terms
    grant(policy_case)
    async def run(session):
        pinned = await session.scalar(select(Membership).where(
            Membership.workspace_id == policy_case["workspace"],
            Membership.user_id == policy_case["actors"]["owner"]))
        head = await latest_head(session, workspace_id=policy_case["workspace"],
                                 project_id=policy_case["project"], purpose="contact_research")
        calls = []
        def observed(*args):
            calls.append(1)
        engine = session.bind.sync_engine
        event.listen(engine, "before_cursor_execute", observed)
        try:
            assert await resolve_approved_policy_terms(session, head, policy_case["now"]) is not None
            with psycopg.connect(policy_case["dsn"]) as db:
                db.execute("UPDATE memberships SET active=false,version=version+1 WHERE user_id=%s",
                           (policy_case["actors"]["owner"],))
            assert await resolve_approved_policy_terms(session, head, policy_case["now"]) is None
            assert pinned.active is False and pinned.version == 2
        finally:
            event.remove(engine, "before_cursor_execute", observed)
        assert len(calls) == 2, "each proof must read one current joined snapshot, never cached authority"
    owner_run(policy_case, run, runtime=True)


def grant(case, purpose="contact_research", documents=()):
    data = request_data(case, purpose=purpose)
    terms = data.terms.model_copy(update={
        "allowed_actions": tuple(sorted(MANUAL_ACTIONS)),
        "allowed_sources": data.terms.allowed_sources.model_copy(update={"document_ids": tuple(documents)}),
    })
    request = submit(case, data.model_copy(update={"terms": terms}), key="submit-" + purpose)
    return decide(case, request, key="approve-" + purpose)


def context(case, **changes):
    return PolicyUseContext(**{
        "action": "lead.evidence.read", "project_id": case["project"],
        "source_domains": ("rice.example.test",), "data_categories": MANUAL_DATA, **changes,
    })


def gate(case, ctx=None, *, now=None, readonly=False):
    from buyeros_api.services import policy_service
    async def run(session):
        fn = policy_service.evaluate_current_policy_readonly if readonly else policy_service.evaluate_current_policy
        kwargs = {} if ctx is None else {"use_context": ctx}
        return await fn(session, {"workspace_id": case["workspace"], "project_id": case["project"]},
                        "contact_research", now or case["now"], **kwargs)
    return owner_run(case, run, runtime=True)


def test_manual_permit_cannot_admit_provider_enrichment_formal_draft_or_send(policy_case):
    grant(policy_case)
    assert gate(policy_case)["allowed"] is False
    for action in ("provider.search", "contact.enrich", "draft.generate", "export.contacts", "delivery.send"):
        assert not gate(policy_case, context(policy_case, action=action))["allowed"]
    assert gate(policy_case, context(policy_case))["allowed"]


def test_source_allowlist_is_exact_and_server_resolved(policy_case):
    grant(policy_case)
    for domain in ("rice.example.test.evil.test", "user@rice.example.test", "rice.example.test:443"):
        assert not gate(policy_case, context(policy_case, source_domains=(domain,)))["allowed"]
    assert not gate(policy_case, context(policy_case, project_id=uuid4()))["allowed"]


def test_expired_or_revoked_authority_blocks_next_read_and_write(policy_case):
    grant(policy_case)
    assert gate(policy_case, context(policy_case))["allowed"]
    with psycopg.connect(policy_case["dsn"]) as db:
        db.execute("UPDATE memberships SET active=false,version=version+1 WHERE user_id=%s",
                   (policy_case["actors"]["owner"],))
    assert not gate(policy_case, context(policy_case))["allowed"]
    assert not gate(policy_case, context(policy_case), now=policy_case["now"] + timedelta(days=60))["allowed"]


def test_shorter_source_deadline_wins_after_reload(policy_case):
    document = uuid4()
    deadline = policy_case["now"] + timedelta(minutes=10)
    with psycopg.connect(policy_case["dsn"]) as db:
        db.execute("INSERT INTO offer_documents(id,workspace_id,project_id,kind,filename,media_type,status,"
                   "sha256,retention_until) VALUES(%s,%s,%s,'upload','synthetic.txt','text/plain','ready',%s,%s)",
                   (document, policy_case["workspace"], policy_case["project"], "c" * 64, deadline))
    grant(policy_case, "account_research", (document,))
    grant(policy_case, "contact_research", (document,))
    from buyeros_api.services import lead_evidence_service as service
    assert hasattr(service, "authorize_native_policy_use"), "native source-bound authorization is not implemented"
    scope = LeadScope(workspace_id=policy_case["workspace"], project_id=policy_case["project"],
                      buyer_id=None, company_id=None, membership_version=1,
                      actor_id=policy_case["actors"]["requester"], roles=frozenset({"workspace_admin"}))
    async def run(session):
        return await service.authorize_native_policy_use(session, scope, action="lead.evidence.read",
                                                         source_ids=(document,), now=policy_case["now"])
    receipt = owner_run(policy_case, run, runtime=True)
    assert receipt.deadline == deadline
    with psycopg.connect(policy_case["dsn"]) as db:
        db.execute("UPDATE offer_documents SET retention_until=now()-interval '1 day' WHERE id=%s", (document,))
    with pytest.raises(ApiError) as caught:
        owner_run(policy_case, run, runtime=True)
    assert caught.value.status_code == 403


def test_policy_receipt_read_does_not_wait_on_parent_and_cannot_authorize_write(policy_case):
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool
    from tests.conftest import runtime_role_dsn
    from buyeros_api.db.session import tenant_session
    from buyeros_api.services import policy_service
    grant(policy_case)
    async def parent(session):
        await policy_service.policy_workspace_lock(session, policy_case["workspace"])
        engine = create_async_engine(
            runtime_role_dsn(policy_case["dsn"]).replace("postgresql://", "postgresql+psycopg://", 1),
            poolclass=NullPool)
        try:
            async def read():
                async with tenant_session(engine, policy_case["workspace"], read_only=True) as snapshot:
                    return await policy_service.evaluate_current_policy_readonly(
                        snapshot, {"workspace_id": policy_case["workspace"], "project_id": policy_case["project"]},
                        "contact_research", policy_case["now"], use_context=context(policy_case))
            assert (await asyncio.wait_for(read(), 3))["allowed"]
            with pytest.raises(ValueError, match="read-only"):
                await policy_service.evaluate_current_policy_readonly(
                    session, {"workspace_id": policy_case["workspace"], "project_id": policy_case["project"]},
                    "contact_research", policy_case["now"], use_context=context(policy_case))
        finally:
            await engine.dispose()
    owner_run(policy_case, parent, runtime=True)


def test_worker_without_manual_context_denies_without_reading_controller_tables(policy_case):
    from sqlalchemy import text
    from buyeros_api.services.policy_service import evaluate_current_policy
    grant(policy_case)
    async def run(session):
        await session.execute(text("SET LOCAL ROLE buyeros_worker"))
        assert await session.scalar(text("SELECT current_user")) == "buyeros_worker"
        assert not await session.scalar(text(
            "SELECT has_table_privilege(current_user,'public.policy_activation_resolutions','SELECT')"))
        return await evaluate_current_policy(session,
            {"workspace_id": policy_case["workspace"], "project_id": policy_case["project"]},
            "contact_research", policy_case["now"])
    assert not owner_run(policy_case, run)["allowed"]


def test_policy_gate_cannot_use_request_start_time_after_a_wait_crosses_expiry(policy_case, monkeypatch):
    from buyeros_api.services import policy_service
    grant(policy_case)
    class AfterWait(datetime):
        @classmethod
        def now(cls, tz=None):
            return policy_case["now"] + timedelta(days=20)
    monkeypatch.setattr(policy_service, "datetime", AfterWait)
    assert not gate(policy_case, context(policy_case))["allowed"]


def test_native_source_deadline_is_rechecked_after_authorization_wait(policy_case, monkeypatch):
    from buyeros_api.services import policy_service, lead_evidence_service as service
    document = uuid4()
    with psycopg.connect(policy_case["dsn"]) as db:
        db.execute("INSERT INTO offer_documents(id,workspace_id,project_id,kind,filename,media_type,status,sha256,retention_until)"
                   " VALUES(%s,%s,%s,'upload','owned.txt','text/plain','ready',%s,%s)",
                   (document, policy_case["workspace"], policy_case["project"], "e" * 64,
                    policy_case["now"] + timedelta(minutes=10)))
    grant(policy_case, "account_research", (document,))
    grant(policy_case, "contact_research", (document,))
    class AfterWait(datetime):
        @classmethod
        def now(cls, tz=None):
            return policy_case["now"] + timedelta(minutes=11)
    monkeypatch.setattr(policy_service, "datetime", AfterWait)
    monkeypatch.setattr(service, "datetime", AfterWait)
    scope = LeadScope(workspace_id=policy_case["workspace"], project_id=policy_case["project"],
                      buyer_id=None, company_id=None, actor_id=policy_case["actors"]["requester"],
                      membership_version=1, roles=frozenset({"workspace_admin"}))
    async def run(session):
        return await service.authorize_native_policy_use(session, scope, action="lead.evidence.read",
            source_ids=(document,), now=policy_case["now"])
    with pytest.raises(ApiError) as caught:
        owner_run(policy_case, run, runtime=True)
    assert caught.value.status_code == 403
