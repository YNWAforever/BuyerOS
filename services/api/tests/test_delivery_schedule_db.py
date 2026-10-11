"""Bounded retained scheduling on restricted owned PG; zero real-provider requests."""
import asyncio, importlib, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import psycopg, pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.services.delivery_reconciliation import DeliveryReconciliationSelection
from tests.test_delivery_admission_db import admission_case, worker_dsn, dispatch_flags
from tests.test_delivery_reconciliation_db import reconciliation_case, Reader
from tests.test_delivery_status_db import snapshot, assert_originals_retained
from tests.test_lookup_quotes_db import WORKSPACE_A


def module():
    path=Path(__file__).resolve().parents[1]/'buyeros_api/services/delivery_schedule.py'
    assert path.is_file(), 'canonical retained batch service missing'
    return importlib.import_module('buyeros_api.services.delivery_schedule')


def one(case, reader=None, message=None):
    mod=module();reader=reader or Reader(case);calls=[]
    def factory(ref):
        assert ref=='original-ref';calls.append(ref);return reader
    selection=DeliveryReconciliationSelection(case[-1],factory)
    return mod.RetainedDeliveryTarget(case[2]['workspace_id'],message or case[4].message_id,selection),reader,calls


def batch(rows):
    return module().RetainedDeliverySchedule(rows,datetime.now(timezone.utc)+timedelta(minutes=1))


def run(case, selected):
    async def body():
        engine=create_async_engine(async_database_url(worker_dsn(case[1])))
        try:return await module().reconcile_retained_delivery_schedule(engine,selected)
        finally:await engine.dispose()
    return asyncio.run(body())


def test_canonical_retained_batch_service_is_available_without_worker_dependencies():
    assert callable(module().reconcile_retained_delivery_schedule)


def test_retained_batch_original_accepted_GET_deduplicates_without_POST_outbox_money_or_lock(reconciliation_case):
    case=reconciliation_case;row,reader,calls=one(case);selected=batch([row]);before=snapshot(case[1],case[4]);first=run(case,selected);second=run(case,selected);after=snapshot(case[1],case[4])
    assert reader.calls==calls==['original-ref','original-ref'] and first['status']==second['status']=='completed'
    assert first['results'][0]['state']==second['results'][0]['state']=='accepted' and second['results'][0]['replayed']
    assert first['results'][0]['event_id']==second['results'][0]['event_id'] and len(after['events'])==1
    assert_originals_retained(before,after)


def test_retained_batch_missing_message_is404_and_later_owned_message_still_succeeds(reconciliation_case):
    case=reconciliation_case;missing,bad_reader,bad_calls=one(case,message=uuid.uuid4());owned,reader,calls=one(case);before=snapshot(case[1],case[4]);result=run(case,batch([missing,owned]));after=snapshot(case[1],case[4])
    assert result['status']=='partial' and result['attempted']==2 and result['results'][0]['status_code']==404
    assert result['results'][1]['state']=='accepted' and bad_reader.calls==bad_calls==[] and reader.calls==calls==['original-ref']
    assert_originals_retained(before,after)


def test_retained_batch_survives_new_send_role_policy_and_runtime_revocation(reconciliation_case,monkeypatch):
    case=reconciliation_case;row,reader,calls=one(case);dispatch_flags(monkeypatch,paid=False,delivery=False,cloudflare=False)
    with psycopg.connect(case[1]) as db:
        db.execute('UPDATE memberships SET active=false,version=version+1 WHERE workspace_id=%s AND user_id=%s',(WORKSPACE_A,case[2]['actor_id']))
        db.execute("UPDATE policy_decisions SET status='blocked',version=version+1 WHERE workspace_id=%s AND purpose='outreach'",(WORKSPACE_A,))
        db.execute('UPDATE worker_runtime_control SET enabled=false,epoch=epoch+1 WHERE singleton=1')
    before=snapshot(case[1],case[4]);result=run(case,batch([row]));after=snapshot(case[1],case[4])
    assert result['status']=='completed' and result['results'][0]['state']=='accepted' and reader.calls==calls==['original-ref'];assert_originals_retained(before,after)


def test_retained_batch_cancellation_never_retries_or_records_receipt(reconciliation_case):
    case=reconciliation_case;row,reader,calls=one(case,Reader(case,error=asyncio.CancelledError()));before=snapshot(case[1],case[4])
    with pytest.raises(asyncio.CancelledError):run(case,batch([row]))
    assert reader.calls==calls==['original-ref'] and snapshot(case[1],case[4])==before


def test_retained_batch_expiry_after_first_GET_blocks_later_row_before_factory(reconciliation_case):
    case=reconciliation_case;late,late_reader,late_calls=one(case,message=uuid.uuid4());selected=None
    def expire():object.__setattr__(selected.targets[1].selection.authority,'valid_until',datetime.now(timezone.utc)-timedelta(seconds=1))
    first,reader,calls=one(case,Reader(case,before_result=expire));selected=batch([first,late]);before=snapshot(case[1],case[4]);result=run(case,selected);after=snapshot(case[1],case[4])
    assert result['status']=='partial' and result['results'][0]['state']=='accepted' and result['results'][1]['status_code']==503
    assert reader.calls==calls==['original-ref'] and late_reader.calls==late_calls==[] and len(after['events'])==1;assert_originals_retained(before,after)
