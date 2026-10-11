"""Incomplete fleet/window/queue evidence must never become capacity acceptance."""
import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def validator(report):
    path = Path(__file__).with_name('mixed_workload_driver.py')
    if not path.exists():
        return False
    spec = importlib.util.spec_from_file_location('mixed_driver', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.workload_complete(report)


def positive():
    # Hand-derived1320 denominator:60*(tenant0:3+1; other9:1+1).
    spaces = [f'00000000-0000-0000-0000-{i:012d}' for i in range(1, 11)]
    start = 10_000_000_000
    rows = []
    for wave in range(60):
        for ordinal, space in enumerate(spaces):
            for kind, count in [('source.delete', 3 if ordinal == 0 else 1), ('bulk.mutate', 1)]:
                for index in range(count):
                    key = f'{wave}:{space}:{kind}:{index}'
                    at = start + wave * 30_000_000_000
                    rows.append(dict(intent=key, workspace=space, wave=wave, kind=kind,
                                     outbox_id=key, task_id=key, generation=1,
                                     created_ns=at, publish_ns=at+1_000_000,
                                     start_ns=at+2_000_000, return_ns=at+3_000_000,
                                     worker_pid=101, outcome='done', state='done',
                                     queue_wait_ns=1_000_000, execution_ns=1_000_000,
                                     durable_ok=True))
    holds = dict(operations=[dict(id='original-unknown', intent='unknown-key', status='unknown', ref=None),
                             dict(id='original-accepted', intent='accepted-key', status='accepted', ref='original-ref')],
                 reservation=dict(id='original-reservation', state='active', remaining='0.600000'), costs=[])
    samples = []
    for second in range(0, 1801, 10):
        admitted = [r for r in rows if r['created_ns'] <= start+second*1_000_000_000]
        samples.append(dict(at_ns=start+second*1_000_000_000,
                            spaces=[dict(workspace=s, ready=0, dispatched=0, done=sum(r['workspace']==s for r in admitted), failed=0, blocked=0, oldest_ready_seconds=None, oldest_dispatched_seconds=None) for s in spaces],
                            broker=dict(queued=0, unacked=0), holds=copy.deepcopy(holds),
                            resources=[dict(owner_pid=p, pid=p, parent_pid=None, depth=0, rss_bytes=1_000_000, method='linux_proc_status_VmRSS') for p in (101, 102)]))
    publications = [dict(intent=r['intent'], workspace=r['workspace'], generation=1, task_id=r['task_id'], at_ns=r['publish_ns']) for r in rows]
    events = [dict(stage=stage, intent=r['intent'], workspace=r['workspace'], generation=1, task_id=r['task_id'], pid=101, at_ns=r[at], outcome='done') for r in rows for stage, at in [('started', 'start_ns'), ('return', 'return_ns')]]
    terminal = [dict(intent=r['intent'], workspace=r['workspace'], id=r['outbox_id'], generation=1, epoch=1, kind=r['kind'], state='done') for r in rows]
    durable = [dict(intent=r['intent'], kind=r['kind'], object_key=None) if r['kind']=='source.delete' else dict(intent=r['intent'], kind=r['kind'], status='completed', processed=1, updated=1, blocked=0, owner=r['workspace'], version=2) for r in rows]
    return dict(schema='buyeros.owned-mixed-workload.v1', complete=True, error=None,
                live_verified=False, release_accepted=False, paid_enabled=False,
                start_ns=start, end_ns=start+1_800_000_000_000,
                owned_workers=[dict(popen_pid=101, tree_pids=[101]), dict(popen_pid=102, tree_pids=[102])],
                role=dict(name='buyeros_api', superuser=False, bypass=False, owner='postgres', rls=True),
                workspaces=spaces, memberships=[dict(workspace=s, id=s, user=s, active=True) for s in spaces],
                baseline_holds=holds, provider_calls=0, send_calls=0,
                observations=rows, samples=samples, publications=publications,
                events=events, terminal=terminal, durable=durable)


def test_complete_ten_workspace_thirty_minute_mixed_denominator_is_accepted():
    report = positive()
    assert len(report['observations']) == 1320
    assert validator(report)


@pytest.mark.parametrize('breakage', [
    'short_window', 'missing_workspace', 'duplicate_workspace', 'missing_wave',
    'all_admitted_at_start', 'missing_bulk', 'missing_source', 'missing_observation',
    'duplicate_intent', 'duplicate_task', 'foreign_workspace', 'wrong_generation',
    'foreign_worker', 'return_before_start', 'wrong_queue_wait', 'wrong_duration',
    'failed_result', 'missing_durable_result', 'missing_membership', 'revoked_member',
    'superuser', 'bypass', 'table_owner', 'rls_off', 'paid_enabled', 'provider_called',
    'hold_released', 'unknown_changed', 'accepted_ref_changed', 'cost_added',
    'missing_samples', 'sample_gap', 'missing_resource_owner', 'invalid_rss',
    'missing_queue_space', 'wrong_queue_count', 'negative_broker', 'positive_zero_age',
    'release_claim', 'incomplete',
])
def test_incomplete_or_rebound_measurement_is_refused(breakage):
    r = positive(); first = r['observations'][0]; sample = r['samples'][50]
    if breakage == 'short_window': r['end_ns'] -= 1
    elif breakage == 'missing_workspace': r['workspaces'].pop()
    elif breakage == 'duplicate_workspace': r['workspaces'][-1] = r['workspaces'][0]
    elif breakage == 'missing_wave': r['observations'] = [x for x in r['observations'] if x['wave'] != 59]
    elif breakage == 'all_admitted_at_start':
        for row in r['observations']: row['created_ns'] = r['start_ns']
    elif breakage == 'missing_bulk': r['observations'] = [x for x in r['observations'] if x['kind'] != 'bulk.mutate']
    elif breakage == 'missing_source': r['observations'] = [x for x in r['observations'] if x['kind'] != 'source.delete']
    elif breakage == 'missing_observation': r['observations'].pop()
    elif breakage == 'duplicate_intent': first['intent'] = r['observations'][1]['intent']
    elif breakage == 'duplicate_task': first['task_id'] = r['observations'][1]['task_id']
    elif breakage == 'foreign_workspace': first['workspace'] = 'foreign'
    elif breakage == 'wrong_generation': first['generation'] = 2
    elif breakage == 'foreign_worker': first['worker_pid'] = 999
    elif breakage == 'return_before_start': first['return_ns'] = first['start_ns']-1
    elif breakage == 'wrong_queue_wait': first['queue_wait_ns'] = 0
    elif breakage == 'wrong_duration': first['execution_ns'] = 0
    elif breakage == 'failed_result': first['state'] = 'failed'
    elif breakage == 'missing_durable_result': first['durable_ok'] = False
    elif breakage == 'missing_membership': r['memberships'].pop()
    elif breakage == 'revoked_member': r['memberships'][0]['active'] = False
    elif breakage == 'superuser': r['role']['superuser'] = True
    elif breakage == 'bypass': r['role']['bypass'] = True
    elif breakage == 'table_owner': r['role']['owner'] = r['role']['name']
    elif breakage == 'rls_off': r['role']['rls'] = False
    elif breakage == 'paid_enabled': r['paid_enabled'] = True
    elif breakage == 'provider_called': r['provider_calls'] = 1
    elif breakage == 'hold_released': sample['holds']['reservation']['remaining'] = '0.000000'
    elif breakage == 'unknown_changed': sample['holds']['operations'][0]['status'] = 'intent'
    elif breakage == 'accepted_ref_changed': sample['holds']['operations'][1]['ref'] = 'new-ref'
    elif breakage == 'cost_added': sample['holds']['costs'] = ['0.100000']
    elif breakage == 'missing_samples': r['samples'] = r['samples'][:1]
    elif breakage == 'sample_gap': del r['samples'][50:55]
    elif breakage == 'missing_resource_owner': sample['resources'].pop()
    elif breakage == 'invalid_rss': sample['resources'][0]['rss_bytes'] = 0
    elif breakage == 'missing_queue_space': sample['spaces'].pop()
    elif breakage == 'wrong_queue_count': sample['spaces'][0]['done'] += 1
    elif breakage == 'negative_broker': sample['broker']['unacked'] = -1
    elif breakage == 'positive_zero_age': sample['spaces'][0]['oldest_ready_seconds'] = 0
    elif breakage == 'release_claim': r['release_accepted'] = True
    elif breakage == 'incomplete': r['complete'] = False
    assert not validator(r), breakage


@pytest.mark.parametrize('breakage', ['different_task_start', 'different_workspace_return',
    'duplicate_return', 'missing_publication', 'wrong_terminal_epoch', 'bulk_owner_changed',
    'source_object_retained'])
def test_summarized_pass_requires_matching_raw_execution_and_durable_receipts(breakage):
    r = positive()
    if breakage == 'different_task_start': r['events'][0]['task_id'] = 'unrelated-task'
    elif breakage == 'different_workspace_return': r['events'][1]['workspace'] = 'foreign'
    elif breakage == 'duplicate_return': r['events'].append(copy.deepcopy(r['events'][1]))
    elif breakage == 'missing_publication': r['publications'].pop()
    elif breakage == 'wrong_terminal_epoch': r['terminal'][0]['epoch'] = 2
    elif breakage == 'bulk_owner_changed': next(x for x in r['durable'] if x['kind']=='bulk.mutate')['owner'] = 'foreign-user'
    elif breakage == 'source_object_retained': r['durable'][0]['object_key'] = 'still-retained'
    assert not validator(r)
