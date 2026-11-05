"""Synthetic administrator configuration on the identity-gated owned cluster."""
import uuid
import pytest
import psycopg
from tests.test_xverum_connections import connection_case, provisional_pg, execution_api, pg, headers


@pytest.fixture
def credit_case(connection_case,monkeypatch):
    c = connection_case
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED','true')
    monkeypatch.setenv('BUYEROS_SALES_WORKSPACE_IDS',str(c.ws))
    c.buyer = uuid.uuid4()
    with psycopg.connect(c.dsn) as db:
        company = uuid.uuid4()
        db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES(%s,%s,'Synthetic','Synthetic')", (company,c.ws))
        db.execute('INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES(%s,%s,%s,%s)', (c.buyer,c.ws,c.project,company))
        db.execute('UPDATE xverum_credit_accounts SET credit_limit=100 WHERE id=%s',(c.account,))
        db.execute('INSERT INTO xverum_credit_limits(id,workspace_id,project_id,credit_limit) VALUES(%s,%s,NULL,100),(%s,%s,%s,100)',(uuid.uuid4(),c.ws,uuid.uuid4(),c.ws,c.project))
        db.execute("INSERT INTO xverum_tariffs(id,workspace_id,account_id,version,usd_per_credit) VALUES(%s,%s,%s,'fixture-v1',0.01)",(uuid.uuid4(),c.ws,c.account))
    async def budgets(factory):
        from buyeros_api.services.budget_service import ensure_period_accounts
        async with factory() as session:
            await ensure_period_accounts(session,c.ws,c.project,None,'contact_lookup')
    pg(c,budgets)
    with psycopg.connect(c.dsn) as db:
        db.execute('UPDATE budget_accounts SET approved_limit=100 WHERE workspace_id=%s',(c.ws,))
    return c
