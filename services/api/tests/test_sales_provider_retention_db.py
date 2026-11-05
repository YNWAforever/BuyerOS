"""Task14 provider generations, retained projections and native financial repair."""
import psycopg
import pytest
from tests.test_xverum_dispatch_db import dispatch_case,thread_entry,native_dispatch
from tests.xverum_fixtures import credit_case,connection_case,provisional_pg,execution_api,pg


@pytest.mark.parametrize('role',['buyeros_api','buyeros_worker'])
def test_fix1_provider_purge_temp_shadow_guard_and_trigger(dispatch_case,role):
    from tests.sales_purge_security import check_shadowing
    c=dispatch_case
    check_shadowing(c,role,'xverum_stages','buyeros_purge_xverum_stage',c.admitted.id,'provider')


def test_fix1_expired_standalone_stage_drains_without_disconnect_and_preserves_unknown(dispatch_case):
    import uuid
    from buyeros_api.services.xverum_quotes import quote_search,confirm_quote
    from tests.test_xverum_dispatch_db import select_receipt,detail_quote,detail_admit
    from tests.test_sales_execution_db import pg_call
    from buyeros_api.db.session import tenant_session
    from buyeros_api.services.sales_retention import drain_pending
    from buyeros_api.services.xverum_dispatch import read_liability,reconcile_xverum,ReconciliationEvidence
    c=dispatch_case
    async def source(factory):
        async with factory() as s:q=await quote_search(s,c.scope,c.id,'Standalone expiry','people',c.buyer)
        async with factory() as s:return await confirm_quote(s,c.scope,q.id,q.fingerprint,'fix1-standalone')
    root=pg(c,source);select_receipt(c,root);native_dispatch(c)
    descendant=detail_admit(c,detail_quote(c,root));c.mode='lost';native_dispatch(c)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT count(*) FROM sales_tasks').fetchone()[0]==0
        assert db.execute('SELECT status FROM xverum_connections WHERE id=%s',(c.id,)).fetchone()[0]=='connected'
        assert db.execute('SELECT count(*) FROM sales_content_tombstones').fetchone()[0]==0
        db.execute("UPDATE xverum_tool_receipts SET expires_at=now()-interval '1 second' WHERE stage_id=%s",(root.id,))
        before=db.execute('SELECT held_credits FROM xverum_credit_reservations WHERE id=(SELECT reservation_id FROM xverum_receipts WHERE id=%s)',(descendant.id,)).fetchone()[0]
        assert before>0
    async def sweep(engine):
        async with tenant_session(engine,c.ws) as s:await drain_pending(s,c.ws)
    pg_call(c,sweep)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT projection,arguments FROM xverum_tool_receipts WHERE stage_id=ANY(%s)',([root.id,descendant.id],)).fetchall()==[(None,{})]*5
        assert db.execute("SELECT count(*) FROM xverum_quotes WHERE id IN(SELECT z.quote_id FROM xverum_credit_reservations z JOIN xverum_receipts r ON r.reservation_id=z.id WHERE r.id=ANY(%s)) AND (payload ? 'tool_plan' OR payload ? 'query' OR payload ? 'provider_ids')",([root.id,descendant.id],)).fetchone()[0]==0
        assert db.execute('SELECT held_credits FROM xverum_credit_reservations WHERE id=(SELECT reservation_id FROM xverum_receipts WHERE id=%s)',(descendant.id,)).fetchone()[0]==before
    async def repair(factory):
        async with factory() as s:value=await read_liability(s,c.scope,descendant.id)
        proof=ReconciliationEvidence(expected_version=value.receipt.version,evidence_ref=uuid.uuid4(),
            tool_receipt_id=value.tools[0].id,resolution='usage',authoritative_usage=1,provider_request_id='expiry-known-bill')
        for _ in range(2):
            async with factory() as s:result=await reconcile_xverum(s,c.scope,descendant.id,proof)
            assert result.held_credits==0 and result.credits_used==1
    pg(c,repair)
    pg_call(c,sweep)
    assert c.calls==2


@pytest.mark.parametrize('dispatched',[False,True,'unknown'])
def test_disconnect_physically_erases_old_generation_without_tombstoning_connection(dispatch_case,dispatched):
    from buyeros_api.services.xverum_connections import disconnect_xverum
    from buyeros_api.services.xverum_dispatch import read_liability,read_evidence
    from buyeros_api.api.errors import ApiError
    from tests.test_xverum_connections import headers
    c=dispatch_case
    if dispatched=='unknown':c.mode='lost'
    if dispatched:native_dispatch(c)
    async def disconnect(factory):
        async with factory() as s:
            with psycopg.connect(c.dsn) as db:
                version=db.execute('SELECT version FROM xverum_connections WHERE id=%s',(c.id,)).fetchone()[0]
            await disconnect_xverum(s,c.scope,version,'task14-disconnect')
        async with factory() as s:await read_liability(s,c.scope,c.admitted.id)
        with pytest.raises(ApiError):
            async with factory() as s:await read_evidence(s,c.scope,c.admitted.id)
        from buyeros_api.services.xverum_quotes import read_quote
        with psycopg.connect(c.dsn) as db:
            quote=db.execute('SELECT quote_id FROM xverum_credit_reservations WHERE id=(SELECT reservation_id FROM xverum_receipts WHERE id=%s)',(c.admitted.id,)).fetchone()[0]
        with pytest.raises(ApiError):
            async with factory() as s:await read_quote(s,c.scope,quote)
        if dispatched=='unknown':
            import uuid
            from buyeros_api.services.xverum_dispatch import reconcile_xverum,ReconciliationEvidence
            async with factory() as s:value=await read_liability(s,c.scope,c.admitted.id)
            assert value.receipt.held_credits>0
            proof=ReconciliationEvidence(expected_version=value.receipt.version,evidence_ref=uuid.uuid4(),
                tool_receipt_id=value.tools[0].id,resolution='usage',authoritative_usage=1,provider_request_id='purged-known-bill')
            for _ in range(2):
                async with factory() as s:result=await reconcile_xverum(s,c.scope,c.admitted.id,proof)
                assert result.credits_used==1 and result.held_credits==0
    pg(c,disconnect)
    root=c.path.rsplit('/connections',1)[0]
    assert c.client.get(root+f'/receipts/{c.admitted.id}/candidates',headers=headers()).status_code in {403,404,409}
    if not dispatched:
        native_dispatch(c)
        assert c.calls==0
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT projection,arguments FROM xverum_tool_receipts WHERE stage_id=%s',(c.admitted.id,)).fetchall()==[(None,{})]
        payload=db.execute('SELECT payload FROM xverum_quotes WHERE id IN(SELECT quote_id FROM xverum_credit_reservations WHERE id=(SELECT reservation_id FROM xverum_receipts WHERE id=%s))',(c.admitted.id,)).fetchone()[0]
        assert not {'query','provider_ids','tool_plan'}.intersection(payload)
        assert db.execute('SELECT count(*) FROM sales_content_tombstones WHERE target_id=%s',(c.id,)).fetchone()[0]==0


def test_share_revoked_between_provider_call_and_retention(dispatch_case,monkeypatch):
    from tests.test_xverum_dispatch_db import test_source_dependency_retention_and_readback
    test_source_dependency_retention_and_readback(dispatch_case,monkeypatch,'before_retention','revoke')
