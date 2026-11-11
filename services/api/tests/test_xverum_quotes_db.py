"""Owned PostgreSQL acceptance for staged Xverum admission."""
import importlib.util
import psycopg
import pytest
from tests.xverum_fixtures import credit_case, connection_case, provisional_pg, execution_api, pg, headers
from tests.test_xverum_dispatch_db import dispatch_case, thread_entry, native_dispatch, select_receipt


@pytest.mark.parametrize('target',['company','people'])
def test_search_ceiling_and_confirmation(credit_case,target):
    from buyeros_api.services.xverum_quotes import quote_search, confirm_quote
    c=credit_case
    async def run(factory):
        async with factory() as s:
            q=await quote_search(s,c.scope,c.id,'Synthetic',target,c.buyer)
            assert q.max_credits==5 and not q.provider_ids
            assert q.tool_plan[0].arguments.page_size==5
        async with factory() as s:
            receipt=await confirm_quote(s,c.scope,q.id,q.fingerprint,'search-one')
            assert receipt.dispatch_state=='queued'
        async with factory() as s:
            replay=await confirm_quote(s,c.scope,q.id,q.fingerprint,'search-one')
            assert receipt==replay
    pg(c,run)


@pytest.mark.parametrize('when',['before_confirmation','replay','final_connection_recheck'])
def test_same_rate_tariff_version_swap_rejects_old_quote(credit_case,monkeypatch,when):
    import uuid
    from decimal import Decimal
    from buyeros_api.services import xverum_quotes as quotes
    from buyeros_api.api.errors import ApiError
    c=credit_case
    with psycopg.connect(c.dsn) as db:
        db.execute("INSERT INTO xverum_tariffs(id,workspace_id,account_id,version,usd_per_credit) VALUES(%s,%s,%s,'fixture-v2',0.01)",
            (uuid.uuid4(),c.ws,c.account))

    def swap():
        with psycopg.connect(c.dsn) as db:
            db.execute("UPDATE xverum_connections SET tariff_version='fixture-v2' WHERE id=%s",(c.id,))
            assert db.execute('SELECT generation,version FROM xverum_connections WHERE id=%s',(c.id,)).fetchone()==(1,1)
            assert db.execute('SELECT count(DISTINCT usd_per_credit) FROM xverum_tariffs WHERE account_id=%s',(c.account,)).fetchone()[0]==1

    if when=='final_connection_recheck':
        original=quotes.capacity
        async def swap_after_capacity(*args,**kwargs):
            await original(*args,**kwargs)
            # Real owner transaction changes only the tariff version after USD
            # admission and before the real locking connection read.
            swap()
        monkeypatch.setattr(quotes,'capacity',swap_after_capacity)

    async def run(factory):
        async with factory() as s:
            q=await quotes.quote_search(s,c.scope,c.id,'Synthetic','company',c.buyer)
            assert q.tariff_version=='fixture-v1'
        if when=='replay':
            async with factory() as s:await quotes.confirm_quote(s,c.scope,q.id,q.fingerprint,'tariff-swap')
        if when!='final_connection_recheck':swap()
        async with factory() as s:
            # Catch inside the caller transaction: final-check rejection must
            # roll back its savepoint without relying on caller rollback.
            with pytest.raises(ApiError) as err:
                await quotes.confirm_quote(s,c.scope,q.id,q.fingerprint,'tariff-swap')
            assert err.value.code=='XVERUM_QUOTE_INVALID'
    pg(c,run)
    existing=1 if when=='replay' else 0
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT count(*),coalesce(sum(remaining_hold),0) FROM budget_reservations').fetchone()==(existing,Decimal('0.05')*existing)
        assert db.execute('SELECT count(*),coalesce(sum(held_credits),0) FROM xverum_credit_reservations').fetchone()==(existing,5*existing)
        assert db.execute('SELECT count(*) FROM xverum_receipts').fetchone()[0]==existing
        if existing:
            assert db.execute('SELECT price_version FROM budget_reservations').fetchone()[0]=='fixture-v1'


@pytest.mark.parametrize('change',['query','generation','expiry','extended_expiry','ids','fingerprint'])
def test_changed_quote_cannot_confirm(credit_case,change):
    from buyeros_api.services.xverum_quotes import quote_search,confirm_quote
    from buyeros_api.api.errors import ApiError
    c=credit_case
    async def create(factory):
        async with factory() as s:return await quote_search(s,c.scope,c.id,'Synthetic','company',c.buyer)
    q=pg(c,create)
    with psycopg.connect(c.dsn) as db:
        if change=='query':db.execute("UPDATE xverum_quotes SET payload=jsonb_set(payload,'{query}','\"changed\"') WHERE id=%s",(q.id,))
        if change=='generation':db.execute('UPDATE xverum_connections SET generation=2 WHERE id=%s',(c.id,))
        if change=='expiry':db.execute("UPDATE xverum_quotes SET expires_at=now()-interval '1 second' WHERE id=%s",(q.id,))
        if change=='extended_expiry':db.execute("UPDATE xverum_quotes SET expires_at=now()+interval '1 hour' WHERE id=%s",(q.id,))
        if change=='ids':db.execute("UPDATE xverum_quotes SET payload=jsonb_set(payload,'{provider_ids}','[\"1\"]') WHERE id=%s",(q.id,))
    async def confirm(factory):
        with pytest.raises(ApiError):
            async with factory() as s:await confirm_quote(s,c.scope,q.id,'b'*64 if change=='fingerprint' else q.fingerprint,'changed')
    pg(c,confirm)


def test_missing_tariff_blocks_without_reservation(credit_case):
    from buyeros_api.services.xverum_quotes import quote_search
    from buyeros_api.api.errors import ApiError
    c=credit_case
    with psycopg.connect(c.dsn) as db:db.execute('DELETE FROM xverum_tariffs')
    async def run(factory):
        with pytest.raises(ApiError) as err:
            async with factory() as s:await quote_search(s,c.scope,c.id,'Synthetic','company',c.buyer)
        assert err.value.code=='XVERUM_TARIFF_REQUIRED'
    pg(c,run)


def test_quote_owner_requires_real_migration(isolated_seeded):
    with psycopg.connect(isolated_seeded) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == '0070_turn_rate_windows'
    assert importlib.util.find_spec('buyeros_api.services.xverum_quotes')


def test_authenticated_staged_routes_and_readback(credit_case,monkeypatch):
    from tests.test_buyer_review_db import VIEWER
    c=credit_case
    path=c.path.removesuffix('/connections')
    body={'stage':'search','connection_id':str(c.id),'buyer_id':str(c.buyer),'query':'Synthetic','target':'company'}
    assert c.client.post(path+'/quotes',json=body).status_code==401
    assert c.client.post(path+'/quotes',json=body,headers=headers(VIEWER)).status_code==404
    response=c.client.post(path+'/quotes',json=body,headers=headers(key='create-quote'))
    assert response.status_code==200,response.text
    q=response.json()['data']
    assert response.headers['cache-control']=='no-store'
    replay=c.client.post(path+'/quotes',json=body,headers=headers(key='create-quote'))
    assert replay.json()['data']==q
    approved=c.client.post(path+'/quotes/'+q['id']+'/approve',json={'quote_id':q['id'],'fingerprint':q['fingerprint']},headers=headers(key='approve-quote'))
    assert approved.status_code==200,approved.text
    receipt=approved.json()['data']
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED','false')
    read=c.client.get(path+'/receipts/'+receipt['id'],headers=headers())
    assert read.status_code==200 and read.json()['data']['held_credits']==5
    assert read.headers['etag']=='"1"' and read.json()['data']['version']==1


def dispatched_search(c,target,key):
    from buyeros_api.services.xverum_quotes import quote_search,confirm_quote
    c.company_cards=True
    async def admit(factory):
        async with factory() as s:q=await quote_search(s,c.scope,c.id,'Synthetic',target,c.buyer)
        async with factory() as s:return await confirm_quote(s,c.scope,q.id,q.fingerprint,key)
    receipt=pg(c,admit);select_receipt(c,receipt)
    assert native_dispatch(c).state=='done' and c.calls==1
    return receipt


@pytest.mark.parametrize('target,ids,email,credits',[('company',['1'],False,4),('people',['1','2','3'],False,12),('people',['1','2','3'],True,18)])
def test_detail_only_selected_returned_identities(dispatch_case,target,ids,email,credits):
    from buyeros_api.services.xverum_quotes import confirm_quote,quote_details
    from buyeros_api.api.errors import ApiError
    c=dispatch_case;r=dispatched_search(c,target,'search-details')
    async def run(factory):
        async with factory() as s:
            detail=await quote_details(s,c.scope,r.id,ids,email)
            assert detail.max_credits==credits and set(detail.provider_ids)==set(ids)
        for bad in (['99'],['1','1'],['1','2','3','4']):
            with pytest.raises(ApiError):
                async with factory() as s:await quote_details(s,c.scope,r.id,bad,email)
        async with factory() as s:await confirm_quote(s,c.scope,detail.id,detail.fingerprint,'detail-admit')
    pg(c,run)


def test_detail_confirmation_rechecks_search_evidence(dispatch_case):
    from buyeros_api.services.xverum_quotes import confirm_quote,quote_details
    from buyeros_api.api.errors import ApiError
    c=dispatch_case;r=dispatched_search(c,'company','source-search')
    async def run(factory):
        async with factory() as s:detail=await quote_details(s,c.scope,r.id,['1'],False)
        with psycopg.connect(c.dsn) as db:db.execute("UPDATE xverum_receipts SET returned_ids='[]' WHERE id=%s",(r.id,))
        with pytest.raises(ApiError):
            async with factory() as s:await confirm_quote(s,c.scope,detail.id,detail.fingerprint,'detail-source-change')
    pg(c,run)
