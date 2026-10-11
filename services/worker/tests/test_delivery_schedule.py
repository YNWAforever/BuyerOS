"""C61-20 bounded retained GET scheduling; no production selection or POST."""
import asyncio, importlib, uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from buyeros_api.api.errors import ApiError
from buyeros_api.services.delivery_status import DeliveryStatusAuthority, DeliveryStatusReceipt
from buyeros_api.services.delivery_reconciliation import DeliveryReconciliationSelection


def module():
    path=Path(__file__).resolve().parents[1]/'buyeros_worker/delivery_schedule.py'
    assert path.is_file(), 'retained delivery worker scheduler missing'
    return importlib.import_module('buyeros_worker.delivery_schedule')


def target(mod, *, workspace=None, message=None):
    ws=workspace or uuid.uuid4(); mid=message or uuid.uuid4()
    authority=DeliveryStatusAuthority(ws,'resend','owned-account','a'*64,'b'*64,True,datetime.now(timezone.utc)+timedelta(minutes=5))
    return mod.RetainedDeliveryTarget(ws,mid,DeliveryReconciliationSelection(authority,lambda ref:None))


def schedule(mod, targets):
    return mod.RetainedDeliverySchedule(targets,datetime.now(timezone.utc)+timedelta(minutes=1))


def test_default_retained_schedule_refuses_before_engine_config_or_provider(monkeypatch):
    mod=module()
    def deny(*args,**kwargs):raise AssertionError('unselected schedule must do zero IO')
    monkeypatch.setattr(mod,'with_engine',deny); monkeypatch.setattr(mod,'get_settings',deny)
    assert mod.run_retained_delivery_schedule_sync()=={'status':'unavailable','attempted':0,'results':[]}


def test_retained_schedule_never_accepts_broker_ids_accounts_or_authority():
    mod=module()
    with pytest.raises(TypeError):mod.run_retained_delivery_schedule_sync(workspace_id=str(uuid.uuid4()))


def test_retained_schedule_copies_original_authority_and_caller_list():
    mod=module();original=target(mod); supplied=[original];selected=schedule(mod,supplied)
    supplied.clear();object.__setattr__(original.selection.authority,'account_reference','tampered-account')
    assert len(selected.targets)==1 and selected.targets[0].selection.authority.account_reference=='owned-account'


@pytest.mark.parametrize('fault',['untyped','workspace','message','foreign-authority','expired','reader','duplicate','too-many'])
def test_invalid_retained_schedule_refuses_entire_batch_before_io(monkeypatch,fault):
    mod=module();good=target(mod);bad=good
    if fault=='untyped':bad={}
    elif fault=='workspace':bad=replace(good,workspace_id=str(good.workspace_id))
    elif fault=='message':bad=replace(good,message_id=uuid.UUID(int=0))
    elif fault=='foreign-authority':bad=replace(good,selection=replace(good.selection,authority=replace(good.selection.authority,workspace_id=uuid.uuid4())))
    elif fault=='expired':bad=replace(good,selection=replace(good.selection,authority=replace(good.selection.authority,valid_until=datetime.now(timezone.utc)-timedelta(seconds=1))))
    elif fault=='reader':bad=replace(good,selection=replace(good.selection,reader_factory=None))
    rows=[good,bad] if fault!='too-many' else [target(mod) for _ in range(101)]
    if fault=='duplicate':rows=[good,good]
    def deny(*args,**kwargs):raise AssertionError('invalid batch must do zero IO')
    monkeypatch.setattr(mod,'with_engine',deny)
    with pytest.raises((ValueError,ApiError)):
        selected=schedule(mod,rows);monkeypatch.setattr(mod,'selected_retained_delivery_schedule',lambda:selected);mod.run_retained_delivery_schedule_sync()


def test_retained_batch_executes_sequential_gets_without_new_send_flags(monkeypatch):
    from types import SimpleNamespace
    mod=module();rows=[target(mod),target(mod)];selected=schedule(mod,rows);active=0;peak=0;calls=[]
    async def observe(engine,*,workspace_id,message_id,selection):
        nonlocal active,peak
        active+=1;peak=max(peak,active);await asyncio.sleep(0);calls.append((workspace_id,message_id,selection));active-=1
        return DeliveryStatusReceipt(message_id,None,'unknown',False)
    async def engine(body):return await body(object())
    monkeypatch.setattr(mod,'with_engine',engine);monkeypatch.setattr(mod.core,'reconcile_delivery_status',observe)
    monkeypatch.setattr(mod,'selected_retained_delivery_schedule',lambda:selected)
    monkeypatch.setattr(mod,'get_settings',lambda:SimpleNamespace(reconciliation_enabled=True,paid_dispatch_enabled=False,delivery_dispatch_enabled=False,celery_execution_enabled=False))
    result=mod.run_retained_delivery_schedule_sync()
    assert result['attempted']==len(calls)==2 and peak==1 and [r['state'] for r in result['results']]==['unknown','unknown']
    assert [(x[0],x[1]) for x in calls]==[(x.workspace_id,x.message_id) for x in rows]


def test_one_blocked_retained_row_does_not_hide_later_owned_success_or_log_provider_details(monkeypatch):
    from types import SimpleNamespace
    mod=module();rows=[target(mod),target(mod)];selected=schedule(mod,rows);calls=[]
    async def observe(engine,*,workspace_id,message_id,selection):
        calls.append(message_id)
        if message_id==rows[0].message_id:raise ApiError(404,'NOT_FOUND','secret must not enter scheduler result')
        return DeliveryStatusReceipt(message_id,uuid.uuid4(),'accepted',True)
    async def engine(body):return await body(object())
    monkeypatch.setattr(mod,'with_engine',engine);monkeypatch.setattr(mod.core,'reconcile_delivery_status',observe)
    monkeypatch.setattr(mod,'selected_retained_delivery_schedule',lambda:selected)
    monkeypatch.setattr(mod,'get_settings',lambda:SimpleNamespace(reconciliation_enabled=True))
    result=mod.run_retained_delivery_schedule_sync()
    assert calls==[r.message_id for r in rows] and result['attempted']==2
    assert result['status']=='partial' and result['results'][0]['code']=='NOT_FOUND' and result['results'][1]['state']=='accepted'
    assert 'secret' not in str(result)


def test_expired_retained_schedule_and_independent_pause_do_no_io(monkeypatch):
    from types import SimpleNamespace
    mod=module();selected=schedule(mod,[target(mod)])
    monkeypatch.setattr(mod,'selected_retained_delivery_schedule',lambda:selected)
    def deny(*args,**kwargs):raise AssertionError('paused schedule must do zero IO')
    monkeypatch.setattr(mod,'with_engine',deny)
    monkeypatch.setattr(mod,'get_settings',lambda:SimpleNamespace(reconciliation_enabled=False))
    assert mod.run_retained_delivery_schedule_sync()=={'status':'paused','attempted':0,'results':[]}
    monkeypatch.setattr(mod,'get_settings',lambda:SimpleNamespace(reconciliation_enabled=True))
    object.__setattr__(selected,'valid_until',datetime.now(timezone.utc)-timedelta(seconds=1))
    with pytest.raises(ApiError):mod.run_retained_delivery_schedule_sync()


def test_retained_schedule_cancellation_propagates_without_retry(monkeypatch):
    from types import SimpleNamespace
    mod=module();selected=schedule(mod,[target(mod)]);calls=[]
    async def observe(*args,**kwargs):calls.append(1);raise asyncio.CancelledError()
    async def engine(body):return await body(object())
    monkeypatch.setattr(mod,'with_engine',engine);monkeypatch.setattr(mod.core,'reconcile_delivery_status',observe)
    monkeypatch.setattr(mod,'selected_retained_delivery_schedule',lambda:selected)
    monkeypatch.setattr(mod,'get_settings',lambda:SimpleNamespace(reconciliation_enabled=True))
    with pytest.raises(asyncio.CancelledError):mod.run_retained_delivery_schedule_sync()
    assert calls==[1]


def test_native_periodic_retained_task_has_no_broker_payload_or_autoretry():
    from buyeros_worker.app import build_app
    from buyeros_worker import tasks
    entry=build_app().conf.beat_schedule['buyeros-retained-delivery-status']
    assert entry['task']=='buyeros.reconcile_retained_deliveries' and entry['schedule']>=30 and not entry.get('args') and not entry.get('kwargs')
    assert tasks.reconcile_retained_deliveries.name==entry['task'] and tasks.reconcile_retained_deliveries.max_retries==0
    with pytest.raises(TypeError):tasks.reconcile_retained_deliveries.run(workspace_id=str(uuid.uuid4()))


def test_one_late_expired_authority_does_not_block_another_retained_tenant(monkeypatch):
    from types import SimpleNamespace
    mod=module();rows=[target(mod),target(mod),target(mod)];selected=schedule(mod,rows);calls=[]
    async def observe(engine,*,workspace_id,message_id,selection):
        calls.append(message_id)
        if len(calls)==1:object.__setattr__(active.targets[1].selection.authority,'valid_until',datetime.now(timezone.utc)-timedelta(seconds=1))
        return DeliveryStatusReceipt(message_id,None,'unknown',False)
    active=None
    original=mod.core.reconcile_retained_delivery_schedule
    async def capture(engine,batch):
        nonlocal active
        active=batch;return await original(engine,batch)
    async def engine(body):return await body(object())
    monkeypatch.setattr(mod.core,'reconcile_retained_delivery_schedule',capture)
    monkeypatch.setattr(mod.core,'reconcile_delivery_status',observe)
    monkeypatch.setattr(mod,'with_engine',engine)
    monkeypatch.setattr(mod,'selected_retained_delivery_schedule',lambda:selected)
    monkeypatch.setattr(mod,'get_settings',lambda:SimpleNamespace(reconciliation_enabled=True))
    result=mod.run_retained_delivery_schedule_sync()
    assert calls==[rows[0].message_id,rows[2].message_id]
    assert result['results'][1]['status_code']==503 and result['results'][2]['state']=='unknown'
