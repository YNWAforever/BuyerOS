"""Independent delivery schema/ledger boundary in owned PG; no network or admission route."""
import contextlib,uuid
import psycopg,pytest
from alembic import command
from alembic.config import Config
from buyeros_api.settings import get_settings
from tests.conftest import ALEMBIC_INI,SERVICE_ROOT,runtime_role_dsn
from tests.test_api_projects_db import api
from tests.test_lookup_quotes_db import quote_case,WORKSPACE_A
from tests.test_api_tenant_isolation import WORKSPACE_B
from tests.test_delivery_preparation_db import approved,prepare

HEAD='0052_private_document_storage';PREVIOUS='0047_c61_legacy_source_privacy'
TABLES=('delivery_messages','delivery_events','delivery_liabilities')

def config():
    cfg=Config(str(ALEMBIC_INI));cfg.set_main_option('script_location',str(SERVICE_ROOT/'alembic'));return cfg

def require_schema(dsn):
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT to_regclass('public.delivery_messages')").fetchone()[0] is not None,'independent delivery schema missing'
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]==HEAD

@contextlib.contextmanager
def ledger_case(quote_case):
    client,dsn,buyers=quote_case;require_schema(dsn);client,dsn,buyers,args=approved(quote_case);prepared=prepare(client,args)
    message,operation,reservation,liability,account=(uuid.uuid4() for _ in range(5));key='delivery:ledger:'+uuid.uuid4().hex
    try:
        with psycopg.connect(dsn,autocommit=True) as db:
            project=db.execute('SELECT project_id FROM outreach_drafts WHERE id=%s',(args['draft_id'],)).fetchone()[0]
            db.execute("INSERT INTO provider_operations(id,workspace_id,intent_key,capability,input_hash,status,provider_name,account_reference) VALUES (%s,%s,%s,'delivery',%s,'intent','resend','owned-fake-account')",(operation,WORKSPACE_A,key,prepared.intent.payload_digest))
            db.execute("INSERT INTO budget_accounts(id,workspace_id,scope,scope_id,category,currency,period,period_start,period_end,approved_limit,settled_spend) VALUES (%s,%s,'workspace',%s,'all','USD',to_char(now(),'YYYY-MM'),date_trunc('month',now()),date_trunc('month',now())+interval '1 month',10,0)",(account,WORKSPACE_A,WORKSPACE_A))
            db.execute("INSERT INTO budget_reservations(id,workspace_id,account_id,operation_id,intent_key,price_version,currency,origin_period_start,upper_bound,remaining_hold,state) VALUES (%s,%s,%s,%s,%s,'delivery-fixture-v1','USD',date_trunc('month',now()),0.01,0.01,'active')",(reservation,WORKSPACE_A,account,operation,str(operation)))
            db.execute("INSERT INTO delivery_messages(id,workspace_id,project_id,draft_id,draft_revision_id,revision_number,recipient_ref,sender_identity_id,approval_id,actor_id,operation_id,intent_key,provider_name,account_reference,payload_digest,state) VALUES (%s,%s,%s,%s,%s,1,%s,%s,%s,%s,%s,%s,'resend','owned-fake-account',%s,'prepared')",(message,WORKSPACE_A,project,args['draft_id'],args['draft_revision_id'],args['recipient_ref'],args['sender_identity_id'],args['approval_id'],args['actor_id'],operation,key,prepared.intent.payload_digest))
            db.execute("INSERT INTO delivery_liabilities(id,workspace_id,message_id,operation_id,reservation_id,max_liability,currency,pricing_version) VALUES (%s,%s,%s,%s,%s,0.01,'USD','delivery-fixture-v1')",(liability,WORKSPACE_A,message,operation,reservation))
        yield dict(client=client,dsn=dsn,args=args,message=message,operation=operation,reservation=reservation,liability=liability,key=key)
    finally:
        with psycopg.connect(dsn,autocommit=True) as db:
            db.execute('DELETE FROM delivery_events WHERE message_id=%s',(message,))
            db.execute('DELETE FROM delivery_liabilities WHERE message_id=%s',(message,))
            db.execute('DELETE FROM delivery_messages WHERE id=%s',(message,))
            db.execute('DELETE FROM budget_reservations WHERE id=%s',(reservation,))
            db.execute('DELETE FROM budget_accounts WHERE id=%s',(account,))
            db.execute('DELETE FROM provider_operations WHERE id=%s',(operation,))

def tenant(dsn,workspace):
    db=psycopg.connect(runtime_role_dsn(dsn));db.execute("SELECT set_config('app.workspace_id',%s,true)",(workspace,));return db

def test_delivery_tables_force_tenant_rls_and_deny_mutating_immutable_bindings(seeded):
    migrated=seeded
    require_schema(migrated)
    with psycopg.connect(migrated) as db:
        rows=db.execute('SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname=ANY(%s)',(list(TABLES),)).fetchall()
    assert len(rows)==3 and all(rls and force for _,rls,force in rows)
    with tenant(migrated,WORKSPACE_A) as db:
        role=db.execute('SELECT current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone();assert role[1] is role[2] is False
        assert db.execute("SELECT has_table_privilege(current_user,'delivery_events','UPDATE'),has_table_privilege(current_user,'delivery_events','DELETE'),has_column_privilege(current_user,'delivery_messages','approval_id','UPDATE')").fetchone()==(False,False,False)

def test_delivery_owned_control_foreign_rls_and_cross_workspace_fk(quote_case):
    with ledger_case(quote_case) as data:
        with tenant(data['dsn'],WORKSPACE_A) as db:
            assert db.execute('SELECT id FROM delivery_messages WHERE id=%s',(data['message'],)).fetchone()[0]==data['message']
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with db.transaction():db.execute('UPDATE delivery_messages SET operation_id=%s WHERE id=%s',(uuid.uuid4(),data['message']))
        with tenant(data['dsn'],WORKSPACE_B) as db:
            assert db.execute('SELECT id FROM delivery_messages WHERE id=%s',(data['message'],)).fetchall()==[]
            with pytest.raises(psycopg.errors.ForeignKeyViolation):
                with db.transaction():db.execute("INSERT INTO delivery_liabilities(id,workspace_id,message_id,operation_id,reservation_id,max_liability,currency,pricing_version) VALUES (%s,%s,%s,%s,%s,0.01,'USD','delivery-fixture-v1')",(uuid.uuid4(),WORKSPACE_B,data['message'],data['operation'],data['reservation']))

def test_delivery_event_identity_and_message_status_cannot_regress(quote_case):
    with ledger_case(quote_case) as data:
        ref=str(uuid.uuid4())
        with tenant(data['dsn'],WORKSPACE_A) as db:
            db.execute("UPDATE delivery_messages SET state='submitting' WHERE id=%s",(data['message'],))
            db.execute("UPDATE delivery_messages SET state='accepted',provider_ref=%s WHERE id=%s",(ref,data['message']))
            db.execute("UPDATE delivery_messages SET state='delivered' WHERE id=%s",(data['message'],))
            with pytest.raises(psycopg.errors.CheckViolation):
                with db.transaction():db.execute("UPDATE delivery_messages SET state='accepted' WHERE id=%s",(data['message'],))
            params=(uuid.uuid4(),WORKSPACE_A,data['message'],'evt-own-001',ref,'a'*64)
            sql="INSERT INTO delivery_events(id,workspace_id,message_id,provider_name,account_reference,external_event_id,provider_ref,state,body_digest,occurred_at) VALUES (%s,%s,%s,'resend','owned-fake-account',%s,%s,'delivered',%s,now())"
            db.execute(sql,params)
            with pytest.raises(psycopg.errors.UniqueViolation):
                with db.transaction():db.execute(sql,(uuid.uuid4(),*params[1:]))
            assert db.execute('SELECT count(*) FROM delivery_events WHERE message_id=%s',(data['message'],)).fetchone()[0]==1
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with db.transaction():db.execute('DELETE FROM delivery_events WHERE message_id=%s',(data['message'],))

def test_delivery_populated_rollback_refuses_and_retains_unknown_hold_and_canonical_refs(quote_case,monkeypatch):
    with ledger_case(quote_case) as data:
        with tenant(data['dsn'],WORKSPACE_A) as db:
            db.execute("UPDATE delivery_messages SET state='submitting' WHERE id=%s",(data['message'],));db.execute("UPDATE delivery_messages SET state='unknown' WHERE id=%s",(data['message'],))
        monkeypatch.setenv('BUYEROS_DATABASE_URL',data['dsn']);get_settings.cache_clear()
        try:
            with pytest.raises(Exception,match='retain delivery history'):command.downgrade(config(),PREVIOUS)
            with psycopg.connect(data['dsn']) as db:
                row=db.execute('SELECT state,draft_revision_id,approval_id,actor_id FROM delivery_messages WHERE id=%s',(data['message'],)).fetchone()
                assert row==('unknown',data['args']['draft_revision_id'],data['args']['approval_id'],data['args']['actor_id'])
                assert str(db.execute('SELECT remaining_hold FROM budget_reservations WHERE id=%s',(data['reservation'],)).fetchone()[0])=='0.010000'
                assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]==HEAD
        finally:get_settings.cache_clear()

def test_delivery_empty_downgrade_and_reupgrade_uses_existing_uuid_schema(migrated,monkeypatch):
    require_schema(migrated);monkeypatch.setenv('BUYEROS_DATABASE_URL',migrated);get_settings.cache_clear()
    try:
        command.downgrade(config(),PREVIOUS)
        with psycopg.connect(migrated) as db:
            assert db.execute("SELECT to_regclass('public.delivery_messages')").fetchone()[0] is None
            assert all(db.execute('SELECT buyeros_'+service+'_receipts_writable()').fetchone()[0] for service in ('search','model','contact'))
    finally:command.upgrade(config(),HEAD);get_settings.cache_clear()
    require_schema(migrated)


def test_delivery_no_tenant_context_fails_closed_and_owned_receipt_guards_remain_writable(quote_case):
    with ledger_case(quote_case) as data:
        with psycopg.connect(runtime_role_dsn(data['dsn'])) as db:
            assert db.execute('SELECT id FROM delivery_messages').fetchall()==[]
            for service in ('search','model','contact'):
                assert db.execute('SELECT buyeros_'+service+'_receipts_writable()').fetchone()==(True,)
            db.execute("SELECT set_config('app.workspace_id',%s,true)",(WORKSPACE_A,))
            assert db.execute('SELECT id FROM delivery_messages WHERE id=%s',(data['message'],)).fetchone()==(data['message'],)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with db.transaction():db.execute('UPDATE delivery_liabilities SET max_liability=0 WHERE id=%s',(data['liability'],))

@pytest.mark.parametrize('state,target,allowed',[
    ('unknown','submitting',False),('unknown','accepted',True),('accepted','unknown',False),
    ('delivered','accepted',False),('delivered','bounced',True),('bounced','delivered',False),
    ('complained','delivered',False),('unsubscribed','accepted',False),('failed','submitting',False),
])
def test_delivery_durable_states_refuse_unknown_resend_and_terminal_regression(quote_case,state,target,allowed):
    with ledger_case(quote_case) as data:
        with tenant(data['dsn'],WORKSPACE_A) as db:
            db.execute("UPDATE delivery_messages SET state='submitting' WHERE id=%s",(data['message'],))
            if state in ('unknown','failed'):
                db.execute('UPDATE delivery_messages SET state=%s WHERE id=%s',(state,data['message']))
            else:
                db.execute("UPDATE delivery_messages SET state='accepted',provider_ref=%s WHERE id=%s",('owned-ref-001',data['message']))
                if state!='accepted':db.execute('UPDATE delivery_messages SET state=%s WHERE id=%s',(state,data['message']))
            statement='UPDATE delivery_messages SET state=%s,provider_ref=COALESCE(provider_ref,%s) WHERE id=%s'
            if allowed:db.execute(statement,(target,'owned-ref-001',data['message']))
            else:
                with pytest.raises(psycopg.errors.CheckViolation):
                    with db.transaction():db.execute(statement,(target,'owned-ref-001',data['message']))
            assert db.execute('SELECT state FROM delivery_messages WHERE id=%s',(data['message'],)).fetchone()==(target if allowed else state,)

def test_delivery_original_reference_and_event_account_cannot_be_rebound(quote_case):
    with ledger_case(quote_case) as data:
        with tenant(data['dsn'],WORKSPACE_A) as db:
            db.execute("UPDATE delivery_messages SET state='submitting' WHERE id=%s",(data['message'],))
            db.execute("UPDATE delivery_messages SET state='accepted',provider_ref='original-ref' WHERE id=%s",(data['message'],))
            for ref in ('replacement-ref',None):
                with pytest.raises(psycopg.errors.CheckViolation):
                    with db.transaction():db.execute('UPDATE delivery_messages SET provider_ref=%s WHERE id=%s',(ref,data['message']))
            with pytest.raises(psycopg.errors.ForeignKeyViolation):
                with db.transaction():db.execute("INSERT INTO delivery_events(id,workspace_id,message_id,provider_name,account_reference,external_event_id,provider_ref,state,body_digest,occurred_at) VALUES (%s,%s,%s,'resend','foreign-account','evt-foreign','original-ref','accepted',%s,now())",(uuid.uuid4(),WORKSPACE_A,data['message'],'b'*64))
            assert db.execute('SELECT provider_ref FROM delivery_messages WHERE id=%s',(data['message'],)).fetchone()==('original-ref',)
            assert db.execute('SELECT count(*) FROM delivery_events WHERE message_id=%s',(data['message'],)).fetchone()==(0,)

def test_delivery_liability_cannot_borrow_another_operation_hold(quote_case):
    with ledger_case(quote_case) as data:
        with tenant(data['dsn'],WORKSPACE_A) as db:
            with pytest.raises(psycopg.errors.ForeignKeyViolation):
                with db.transaction():db.execute("INSERT INTO delivery_liabilities(id,workspace_id,message_id,operation_id,reservation_id,max_liability,currency,pricing_version) VALUES (%s,%s,%s,%s,%s,0,'USD','wrong-price')",(uuid.uuid4(),WORKSPACE_A,data['message'],data['operation'],data['reservation']))
            assert str(db.execute('SELECT remaining_hold FROM budget_reservations WHERE id=%s',(data['reservation'],)).fetchone()[0])=='0.010000'

def test_delivery_models_register_exact_migrated_columns(migrated):
    from buyeros_api.db.base import Base
    from sqlalchemy.orm import configure_mappers
    configure_mappers()
    with psycopg.connect(migrated) as db:
        for table in TABLES:
            actual={row[0]:row[1]=='YES' for row in db.execute("SELECT column_name,is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",(table,)).fetchall()}
            assert actual=={column.name:column.nullable for column in Base.metadata.tables[table].columns}
