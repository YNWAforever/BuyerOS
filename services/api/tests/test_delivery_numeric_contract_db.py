"""The durable liability must accept the same exact money type as its reservation."""
from pathlib import Path
import psycopg
from buyeros_api.db.delivery import DeliveryLiability
from buyeros_api.db.budget import BudgetReservation
from tests.test_api_projects_db import api
from tests.test_lookup_quotes_db import quote_case

def test_delivery_liability_uses_exact_original_reservation_money_precision(migrated):
    import buyeros_api
    assert Path(buyeros_api.__file__).resolve().parent==Path(__file__).resolve().parents[1]/'buyeros_api'
    expected=BudgetReservation.__table__.c.upper_bound.type
    declared=DeliveryLiability.__table__.c.max_liability.type
    assert (declared.precision,declared.scale)==(expected.precision,expected.scale)==(20,6)
    with psycopg.connect(migrated) as db:
        actual=db.execute("SELECT numeric_precision,numeric_scale FROM information_schema.columns WHERE table_schema='public' AND table_name='delivery_liabilities' AND column_name='max_liability'").fetchone()
        assert actual==(declared.precision,declared.scale), 'durable delivery liability narrows original reservation money'


def test_populated0048_money_expand_retains_original_unknown_hold_and_refuses_shrinking(quote_case,monkeypatch):
    from alembic import command
    from buyeros_api.settings import get_settings
    import tests.test_delivery_ledger_db as ledger
    import pytest
    client,dsn,buyers=quote_case
    monkeypatch.setenv('BUYEROS_DATABASE_URL',dsn);get_settings.cache_clear()
    try:
        command.downgrade(ledger.config(),'0048_c61_delivery_ledger')
        with monkeypatch.context() as context:
            context.setattr(ledger,'HEAD','0048_c61_delivery_ledger')
            with ledger.ledger_case(quote_case) as data:
                with ledger.tenant(dsn,str(data['args']['workspace_id'])) as db:
                    db.execute("UPDATE delivery_messages SET state='submitting' WHERE id=%s",(data['message'],))
                    db.execute("UPDATE delivery_messages SET state='unknown' WHERE id=%s",(data['message'],))
                with psycopg.connect(dsn,autocommit=True) as db:
                    db.execute("UPDATE provider_operations SET status='unknown' WHERE id=%s",(data['operation'],))
                def snapshot():
                    with psycopg.connect(dsn) as db:
                        row=db.execute('SELECT state,draft_revision_id,approval_id,actor_id,operation_id,recipient_ref,sender_identity_id,payload_digest,provider_ref FROM delivery_messages WHERE id=%s',(data['message'],)).fetchone()
                        liability=db.execute('SELECT operation_id,reservation_id,max_liability,currency,pricing_version FROM delivery_liabilities WHERE message_id=%s',(data['message'],)).fetchone()
                        hold=db.execute('SELECT remaining_hold,state FROM budget_reservations WHERE id=%s',(data['reservation'],)).fetchone()
                        return row,liability,hold
                before=snapshot()
                with psycopg.connect(dsn) as db:
                    assert db.execute("SELECT numeric_precision,numeric_scale FROM information_schema.columns WHERE table_name='delivery_liabilities' AND column_name='max_liability'").fetchone()==(18,6)
                command.upgrade(ledger.config(),'head')
                assert snapshot()==before
                with psycopg.connect(dsn) as db:
                    assert db.execute('SELECT version_num FROM alembic_version').fetchone()==('0052_private_document_storage',)
                    assert db.execute("SELECT numeric_precision,numeric_scale FROM information_schema.columns WHERE table_name='delivery_liabilities' AND column_name='max_liability'").fetchone()==(20,6)
                with pytest.raises(RuntimeError,match='retain delivery history'):command.downgrade(ledger.config(),'0048_c61_delivery_ledger')
                assert snapshot()==before
                with psycopg.connect(dsn) as db:
                    assert db.execute('SELECT version_num FROM alembic_version').fetchone()==('0052_private_document_storage',)
                    assert str(db.execute('SELECT remaining_hold FROM budget_reservations WHERE id=%s',(data['reservation'],)).fetchone()[0])=='0.010000'
    finally:
        # Keep the session fixture at its declared head even if an assertion fails.
        try:command.upgrade(ledger.config(),'head')
        finally:get_settings.cache_clear()
