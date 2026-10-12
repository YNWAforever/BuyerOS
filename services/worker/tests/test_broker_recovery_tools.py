"""A PASS receipt cannot hide missing broker, fencing, or liability evidence."""
import copy
import importlib.util
from pathlib import Path
import sys

import pytest


def validate(captures):
    path = Path(__file__).with_name('broker_recovery_driver.py')
    if not path.exists():
        return False
    spec = importlib.util.spec_from_file_location('owned_recovery_driver', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.captures_complete(captures)


def receipts():
    # Hand-derived receipt: one task/intent survives hard loss; lease owner1
    # loses to generation2; a single accepted fixture submit keeps USD0.30.
    captures = []
    for name in ['redelivery', 'lease', 'unknown', 'accepted']:
        events = [dict(stage='started', pid=101, task_id='t1', generation=1,
                       intent='lookup', redelivered=False)]
        events += [dict(stage='started', pid=202, task_id='t2' if name == 'lease' else 't1',
                        generation=2 if name == 'lease' else 1, intent='lookup',
                        redelivered=name != 'lease')]
        events += [dict(stage='return', pid=202, task_id=events[-1]['task_id'],
                        generation=events[-1]['generation'], intent='lookup',
                        outcome='unknown' if name == 'unknown' else 'duplicate' if name == 'accepted' else 'done')]
        if name == 'lease':
            events += [dict(stage='return', pid=101, task_id='t1', generation=1,
                            intent='lookup', outcome='stale')]
        if name in ['unknown', 'accepted']:
            events += [dict(stage='submit', pid=101, intent='provider-key')]
        outbox = dict(id='o1', key='lookup', workspace='w1', state='done', generation=2 if name == 'lease' else 1, epoch=1)
        snapshots = [dict(label='inflight', outbox={**outbox, 'state':'dispatched', 'generation':1},
                          db_now='2026-10-12T00:00:01+00:00', lease_expires='2026-10-12T00:00:02+00:00'),
                     dict(label='final', outbox=outbox)]
        if name == 'lease':
            snapshots.insert(1, dict(label='expired', outbox={**outbox,'state':'dispatched','generation':1},
                                    db_now='2026-10-12T00:00:03+00:00', lease_expires='2026-10-12T00:00:02+00:00'))
        if name in ['unknown', 'accepted']:
            for snapshot in snapshots:
                snapshot.update(provider=dict(id='p1', intent='provider-key', status='submitting' if snapshot['label']=='inflight' else name, ref=None if name=='unknown' else 'fixture:one'),
                                reservation=dict(id='r1', state='active', remaining='0.300000'), costs=[])
        if name == 'accepted':
            snapshots += [dict(label='epoch_denied', outbox=outbox, selector_epoch=2,
                               provider=dict(id='p1', intent='provider-key', status='accepted', ref='fixture:one'),
                               reservation=dict(id='r1', state='active', remaining='0.300000'), costs=[]),
                          dict(label='pending', outbox=outbox, selector_epoch=1,
                               provider=dict(id='p1', intent='provider-key', status='accepted', ref='fixture:one'),
                               reservation=dict(id='r1', state='active', remaining='0.300000'), costs=[]),
                          dict(label='settled', outbox=outbox, selector_epoch=3,
                               provider=dict(id='p1', intent='provider-key', status='not_found', ref='fixture:one'),
                               reservation=dict(id='r1', state='settled', remaining='0.000000'), costs=['0.100000'])]
            events += [dict(stage='return', pid=202, task_id='old-epoch', generation=1, intent='reconcile', outcome='stale'),
                       dict(stage='status', pid=202, ref='fixture:one', outcome='accepted', runtime_epoch=1),
                       dict(stage='status', pid=202, ref='fixture:one', outcome='not_found', runtime_epoch=3)]
            duplicate = copy.deepcopy(snapshots[-1])
            duplicate['label'] = 'settled_duplicate'
            snapshots.append(duplicate)
            for task_id, outcome in [('settle', 'reconciled'), ('settle-again', 'duplicate')]:
                events += [dict(stage='started', pid=202, task_id=task_id, generation=3,
                                intent='contact.reconcile:p1', redelivered=False),
                           dict(stage='return', pid=202, task_id=task_id, generation=3,
                                intent='contact.reconcile:p1', outcome=outcome)]
        captures.append(dict(name=name, complete=True, live_verified=False, release_accepted=False,
                             role=dict(name='runtime', superuser=False, bypass=False, owner='migration', rls=True),
                             owned_workers=[dict(popen_pid=101, tree_pids=[101]),dict(popen_pid=202,tree_pids=[202])],
                             events=events, snapshots=snapshots,
                             broker_before=dict(unacked=['t1']), broker_final=dict(unacked=[],queued=0),
                             killed=None if name=='lease' else dict(pid=101,popen_pid=101,exit_code=1)))
    return captures


def test_complete_recovery_requires_all_four_positive_owned_controls():
    assert validate(receipts())


@pytest.mark.parametrize('breakage', ['missing-case','duplicate-case','no-redelivery','wrong-task',
                                     'unowned-pid','no-unacked','missing-kill','unexpired','old-finalizer',
                                     'second-submit','released-unknown','changed-operation','status-submit',
                                     'missing-status','epoch-not-denied','selector-regression','double-cost','cost-after-duplicate','privileged','live'])
def test_incomplete_recovery_never_earns_source_acceptance(breakage):
    data=copy.deepcopy(receipts())
    if breakage=='missing-case':data.pop()
    elif breakage=='duplicate-case':data[3]=copy.deepcopy(data[2])
    elif breakage=='no-redelivery':data[0]['events'][1]['redelivered']=False
    elif breakage=='wrong-task':data[0]['events'][1]['task_id']='another'
    elif breakage=='unowned-pid':data[0]['events'][1]['pid']=999
    elif breakage=='no-unacked':data[0]['broker_before']['unacked']=[]
    elif breakage=='missing-kill':data[0]['killed']=None
    elif breakage=='unexpired':data[1]['snapshots'][1]['db_now']='2026-10-12T00:00:01+00:00'
    elif breakage=='old-finalizer':data[1]['events'][-1]['outcome']='done'
    elif breakage=='second-submit':data[2]['events'].append(dict(stage='submit',pid=202,intent='provider-key'))
    elif breakage=='released-unknown':data[2]['snapshots'][-1]['reservation']['remaining']='0.000000'
    elif breakage=='changed-operation':data[2]['snapshots'][-1]['provider']['id']='p2'
    elif breakage=='status-submit':data[3]['events'].append(dict(stage='submit',pid=202,intent='new-key'))
    elif breakage=='missing-status':data[3]['events']=[e for e in data[3]['events'] if e['stage']!='status']
    elif breakage=='epoch-not-denied':next(e for e in data[3]['events'] if e.get('task_id')=='old-epoch')['outcome']='accepted'
    elif breakage=='selector-regression':data[3]['snapshots'][-1]['selector_epoch']=1
    elif breakage=='double-cost':data[3]['snapshots'][-1]['costs']=['0.100000','0.100000']
    elif breakage=='cost-after-duplicate':
        extra=copy.deepcopy(data[3]['snapshots'][-1]);extra['label']='settled_duplicate'
        extra['costs']=['0.100000','0.100000'];data[3]['snapshots'].append(extra)
    elif breakage=='privileged':data[0]['role']['bypass']=True
    elif breakage=='live':data[0]['live_verified']=True
    assert not validate(data)


@pytest.mark.parametrize('name', ['redelivery', 'lease', 'unknown', 'accepted'])
@pytest.mark.parametrize('field,value', [('task_id', 'unrelated'), ('generation', 999), ('pid', 101)])
def test_recovery_completion_must_match_replacement_execution(name, field, value):
    data = receipts()
    capture = next(c for c in data if c['name'] == name)
    completed = next(e for e in capture['events'] if e['stage'] == 'return' and e['intent'] == 'lookup' and e['pid'] == 202)
    completed[field] = value
    assert not validate(data)


def test_late_lease_finalizer_must_match_original_task():
    data = receipts()
    data[1]['events'][-1]['task_id'] = 'unrelated'
    assert not validate(data)


@pytest.mark.parametrize('breakage', ['missing-snapshot', 'missing-return', 'wrong-intent',
                                     'wrong-generation', 'wrong-task', 'wrong-provider-state'])
def test_duplicate_settlement_requires_matching_execution_and_unchanged_snapshot(breakage):
    data = receipts()
    capture = data[3]
    duplicate = next(e for e in capture['events'] if e.get('task_id') == 'settle-again' and e['stage'] == 'return')
    if breakage == 'missing-snapshot':
        capture['snapshots'] = [s for s in capture['snapshots'] if s['label'] != 'settled_duplicate']
    elif breakage == 'missing-return': capture['events'].remove(duplicate)
    elif breakage == 'wrong-intent': duplicate['intent'] = 'another-operation'
    elif breakage == 'wrong-generation': duplicate['generation'] = 999
    elif breakage == 'wrong-task': duplicate['task_id'] = 'unrelated'
    else: capture['snapshots'][-1]['provider']['status'] = 'unknown'
    assert not validate(data)


def runner():
    path=Path(__file__).resolve().parents[3]/'scripts/benchmark-broker-recovery.py'
    spec=importlib.util.spec_from_file_location('owned_broker_runner',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('variable',['BUYEROS_TEST_DATABASE_URL','BUYEROS_DATABASE_URL','DATABASE_URL','BUYEROS_WORKER_DATABASE_URL'])
def test_recovery_runner_refuses_each_inherited_database_before_child(variable,monkeypatch,tmp_path,capsys):
    for key in ['BUYEROS_TEST_DATABASE_URL','BUYEROS_DATABASE_URL','DATABASE_URL','BUYEROS_WORKER_DATABASE_URL']:
        monkeypatch.delenv(key,raising=False)
    monkeypatch.setenv(variable,'postgresql://do-not-use.invalid/database')
    target=tmp_path/'fresh'
    monkeypatch.setattr(sys,'argv',['runner','--output-dir',str(target)])
    with pytest.raises(SystemExit) as result:runner().main()
    assert result.value.code==2 and not target.exists()
    assert 'unset inherited database '+variable in capsys.readouterr().err


def test_recovery_runner_preserves_existing_receipts_before_child(monkeypatch,tmp_path,capsys):
    for key in ['BUYEROS_TEST_DATABASE_URL','BUYEROS_DATABASE_URL','DATABASE_URL','BUYEROS_WORKER_DATABASE_URL']:
        monkeypatch.delenv(key,raising=False)
    sentinel=tmp_path/'report.json'; sentinel.write_bytes(b'original evidence')
    monkeypatch.setattr(sys,'argv',['runner','--output-dir',str(tmp_path)])
    with pytest.raises(SystemExit) as result:runner().main()
    assert result.value.code==2 and sentinel.read_bytes()==b'original evidence'
    assert 'retain previous evidence' in capsys.readouterr().err
