"""Validate sustained owned measurements; never adopts a numerical/live SLO."""
from collections import Counter
import math

DURATION_NS = 1_800_000_000_000
WAVES = 60
INTERVAL_NS = 30_000_000_000


def workload_complete(r):
    def integer(value, minimum=0):
        return type(value) is int and value >= minimum

    def finite(value):
        return type(value) in (int, float) and math.isfinite(value) and value >= 0

    try:
        if (r['schema'] != 'buyeros.owned-mixed-workload.v1' or r['complete'] is not True
                or r['error'] is not None or r['live_verified'] is not False
                or r['release_accepted'] is not False or r['paid_enabled'] is not False
                or r['provider_calls'] != 0 or r['send_calls'] != 0): return False
        start, end = r['start_ns'], r['end_ns']
        if not integer(start, 1) or not integer(end, 1) or not DURATION_NS <= end-start <= DURATION_NS+300_000_000_000: return False
        spaces = r['workspaces']
        if not isinstance(spaces, list) or len(spaces) != 10 or len(set(spaces)) != 10: return False
        if any(not isinstance(s, str) or not s for s in spaces): return False
        members = r['memberships']
        if len(members) != 10 or {m['workspace'] for m in members} != set(spaces): return False
        if any(m['active'] is not True or not m['id'] or not m['user'] for m in members): return False
        role = r['role']
        if role['superuser'] is not False or role['bypass'] is not False or role['rls'] is not True or not role['name'] or role['name'] == role['owner']: return False
        workers = r['owned_workers']
        if len(workers) != 2 or len({w['popen_pid'] for w in workers}) != 2: return False
        if any(not integer(w['popen_pid'], 1) or w['popen_pid'] not in w['tree_pids'] for w in workers): return False
        pids = {p for w in workers for p in w['tree_pids']}
        baseline = r['baseline_holds']
        if (len(baseline['operations']) != 2 or {o['status'] for o in baseline['operations']} != {'unknown', 'accepted'}
                or len({o['id'] for o in baseline['operations']}) != 2 or len({o['intent'] for o in baseline['operations']}) != 2
                or any((o['ref'] is not None if o['status'] == 'unknown' else not o['ref']) for o in baseline['operations'])
                or baseline['reservation']['state'] != 'active' or baseline['reservation']['remaining'] != '0.600000'
                or not baseline['reservation']['id'] or baseline['costs'] != []): return False
        rows = r['observations']
        if len(rows) != 1320 or any(len({x[k] for x in rows}) != 1320 for k in ('intent', 'task_id', 'outbox_id')): return False
        expected = Counter({(wave, space, kind): (3 if ordinal == 0 and kind == 'source.delete' else 1)
                            for wave in range(WAVES) for ordinal, space in enumerate(spaces)
                            for kind in ('source.delete', 'bulk.mutate')})
        if Counter((x['wave'], x['workspace'], x['kind']) for x in rows) != expected: return False
        for x in rows:
            timestamps = [x[k] for k in ('created_ns', 'publish_ns', 'start_ns', 'return_ns')]
            if any(not integer(t, 1) for t in timestamps) or timestamps != sorted(timestamps): return False
            if not start+x['wave']*INTERVAL_NS <= x['created_ns'] < start+x['wave']*INTERVAL_NS+15_000_000_000: return False
            if x['return_ns'] > end or x['generation'] != 1 or x['worker_pid'] not in pids: return False
            if x['outcome'] != 'done' or x['state'] != 'done' or x['durable_ok'] is not True: return False
            if not integer(x['queue_wait_ns']) or x['queue_wait_ns'] != x['start_ns']-x['publish_ns']: return False
            if not integer(x['execution_ns']) or x['execution_ns'] != x['return_ns']-x['start_ns']: return False
        publications, terminal, durable = (r[k] for k in ('publications', 'terminal', 'durable'))
        if any(len(items) != 1320 or len({x['intent'] for x in items}) != 1320 for items in (publications, terminal, durable)): return False
        pubs, final, results = ({x['intent']: x for x in items} for items in (publications, terminal, durable))
        task_events = [e for e in r['events'] if e['stage'] in ('started', 'return')]
        if any(e['stage'] == 'forbidden_provider_call' for e in r['events']): return False
        if len(task_events) != 2640: return False
        event_index = {(e['stage'], e['task_id']): e for e in task_events}
        if len(event_index) != 2640: return False
        member_users = {m['workspace']: m['user'] for m in members}
        for x in rows:
            pub, final_row, result = (items.get(x['intent']) for items in (pubs, final, results))
            if pub is None or final_row is None or result is None: return False
            if any(pub[k] != x[k] for k in ('workspace', 'generation', 'task_id')) or pub['at_ns'] != x['publish_ns']: return False
            if any(final_row[k] != x[k] for k in ('workspace', 'generation', 'kind', 'state')) or final_row['epoch'] != 1 or final_row['id'] != x['outbox_id']: return False
            for stage, at in [('started', 'start_ns'), ('return', 'return_ns')]:
                e = event_index.get((stage, x['task_id']))
                if e is None or any(e[k] != x[k] for k in ('intent', 'workspace', 'generation')) or e['pid'] != x['worker_pid'] or e['at_ns'] != x[at]: return False
                if stage == 'return' and e['outcome'] != 'done': return False
            if result['kind'] != x['kind']: return False
            if x['kind'] == 'source.delete':
                if result['object_key'] is not None: return False
            elif (result['status'] != 'completed' or result['processed'] != 1 or result['updated'] != 1
                  or result['blocked'] != 0 or result['version'] != 2 or result['owner'] != member_users[x['workspace']]): return False
        samples = r['samples']
        if len(samples) < 181: return False
        times = [s['at_ns'] for s in samples]
        if any(not integer(t, 1) for t in times) or times != sorted(set(times)): return False
        if times[0]-start > 15_000_000_000 or times[0] < start or times[-1] < start+DURATION_NS or times[-1] > end: return False
        if any(b-a > 15_000_000_000 for a, b in zip(times, times[1:])): return False
        owners = {w['popen_pid'] for w in workers}
        for sample in samples:
            if sample['holds'] != baseline: return False
            if any(not integer(sample['broker'][k]) for k in ('queued', 'unacked')): return False
            ids=[]
            for kind in ('queued', 'unacked'):
                task_ids=sample['broker'][kind+'_task_ids']
                if not isinstance(task_ids,list) or len(task_ids)!=sample['broker'][kind]: return False
                ids.extend(task_ids)
            published_ids={p['task_id'] for p in publications if p['at_ns']<=sample['at_ns']}
            if len(ids)!=len(set(ids)) or not set(ids)<=published_ids: return False
            resource = sample['resources']
            if {s['owner_pid'] for s in resource} != owners: return False
            for owner in owners:
                tree = [s for s in resource if s['owner_pid'] == owner]
                indexed = {s['pid']: s for s in tree}
                if len(tree) != len(indexed) or len(tree) > 16 or owner not in indexed: return False
                if indexed[owner]['depth'] != 0 or indexed[owner]['parent_pid'] is not None: return False
                for s in tree:
                    if s['pid'] not in pids or not integer(s['rss_bytes'], 1) or not integer(s['depth']) or s['depth'] > 4: return False
                    if s['method'] not in ('linux_proc_status_VmRSS', 'windows_GetProcessMemoryInfo_WorkingSetSize'): return False
                    if s['pid'] != owner:
                        parent = indexed.get(s['parent_pid'])
                        if parent is None or s['depth'] != parent['depth']+1: return False
                if tree[0]['method'].startswith('windows') and not any(s['depth'] > 0 for s in tree): return False
            queue = sample['spaces']
            if len(queue) != 10 or {s['workspace'] for s in queue} != set(spaces): return False
            for q in queue:
                states = ('ready', 'dispatched', 'done', 'failed', 'blocked')
                if any(not integer(q[k]) for k in states) or q['failed'] != 0 or q['blocked'] != 0: return False
                admitted = sum(x['workspace'] == q['workspace'] and x['created_ns'] <= sample['at_ns'] for x in rows)
                if sum(q[k] for k in states) != admitted: return False
                for k in ('ready', 'dispatched'):
                    age = q['oldest_'+k+'_seconds']
                    if (age is not None if q[k] == 0 else not finite(age)): return False
        return all(q['ready'] == q['dispatched'] == 0 for q in samples[-1]['spaces'])
    except (KeyError, TypeError, ValueError, AttributeError, IndexError):
        return False
