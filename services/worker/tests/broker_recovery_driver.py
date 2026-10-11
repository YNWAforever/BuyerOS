"""Validate raw owned recovery denominators; this never grants live acceptance."""
from datetime import datetime
from decimal import Decimal

CASES = ('redelivery', 'lease', 'unknown', 'accepted')


def captures_complete(captures):
    try:
        if len(captures) != 4 or {c['name'] for c in captures} != set(CASES):
            return False
        for c in captures:
            if c['complete'] is not True or c['live_verified'] is not False or c['release_accepted'] is not False:
                return False
            role = c['role']
            if role['superuser'] is not False or role['bypass'] is not False or role['rls'] is not True or role['name'] == role['owner']:
                return False
            workers = c['owned_workers']
            if len(workers) != 2 or len({w['popen_pid'] for w in workers}) != 2:
                return False
            owned = {p for w in workers for p in w['tree_pids']}
            events = c['events']
            if not events or any(e['pid'] not in owned for e in events):
                return False
            snapshots = {s['label']: s for s in c['snapshots']}
            inflight, final = snapshots['inflight']['outbox'], snapshots['final']['outbox']
            if (inflight['state'], inflight['generation'], inflight['epoch']) != ('dispatched', 1, 1):
                return False
            if any(s['outbox'][key] != inflight[key] for s in c['snapshots'] for key in ('id', 'key', 'workspace', 'epoch')):
                return False
            if (final['state'], final['generation']) != ('done', 2 if c['name'] == 'lease' else 1):
                return False
            starts = [e for e in events if e['stage'] == 'started' and e['intent'] == inflight['key']]
            first = starts[0]
            def matching_return(start, outcome):
                return any(e['stage'] == 'return' and e['outcome'] == outcome
                           and all(e[key] == start[key] for key in ('pid', 'task_id', 'generation', 'intent'))
                           for e in events[events.index(start) + 1:])
            replacements = [e for e in starts[1:] if e['pid'] in workers[1]['tree_pids']]
            if first['generation'] != 1:
                return False
            if c['broker_final'] != dict(unacked=[], queued=0):
                return False
            if c['name'] == 'lease':
                expired = snapshots['expired']
                if datetime.fromisoformat(expired['db_now']) < datetime.fromisoformat(expired['lease_expires']):
                    return False
                if not any(e['generation']==2 and matching_return(e, 'done') for e in replacements):
                    return False
                if not matching_return(first, 'stale'):
                    return False
            else:
                kill = c['killed']
                if kill['pid'] != first['pid'] or kill['pid'] not in workers[0]['tree_pids'] or kill['popen_pid'] != workers[0]['popen_pid'] or kill['exit_code'] is None:
                    return False
                if first['task_id'] not in c['broker_before']['unacked']:
                    return False
                want = {'redelivery':'done','unknown':'unknown','accepted':'duplicate'}[c['name']]
                if not any(e['redelivered'] is True and e['task_id']==first['task_id']
                           and e['generation']==first['generation'] and e['pid']!=first['pid']
                           and matching_return(e, want) for e in replacements):
                    return False
            if c['name'] in ('unknown','accepted'):
                submits = [e for e in events if e['stage']=='submit']
                if len(submits)!=1 or submits[0]['intent']!=snapshots['inflight']['provider']['intent']:
                    return False
                original = snapshots['inflight']
                for s in c['snapshots']:
                    if (s['provider']['id'],s['provider']['intent'],s['reservation']['id']) != (original['provider']['id'],original['provider']['intent'],original['reservation']['id']):
                        return False
                    if s['label'] not in ('settled','settled_duplicate') and (s['reservation']['state']!='active' or Decimal(s['reservation']['remaining'])!=Decimal('0.300000') or s['costs']):
                        return False
                    if s['label']=='settled_duplicate' and (s['reservation']['state']!='settled' or Decimal(s['reservation']['remaining'])!=0 or s['costs']!=['0.100000']):
                        return False
                if c['name']=='unknown':
                    if (snapshots['final']['provider']['status'],snapshots['final']['provider']['ref'])!=('unknown',None) or any(e['stage']=='status' for e in events):
                        return False
                else:
                    ref=snapshots['final']['provider']['ref']
                    if not ref or snapshots['final']['provider']['status']!='accepted':
                        return False
                    denied=snapshots['epoch_denied']
                    if denied['selector_epoch']!=2 or not any(e['stage']=='return' and e['task_id']=='old-epoch' and e['outcome']=='stale' for e in events):
                        return False
                    statuses=[e for e in events if e['stage']=='status']
                    if [(e['ref'],e['outcome'],e['runtime_epoch']) for e in statuses]!=[(ref,'accepted',1),(ref,'not_found',3)]:
                        return False
                    settled=snapshots['settled']
                    if snapshots['pending']['selector_epoch']!=1 or settled['selector_epoch']!=3:
                        return False
                    duplicate=snapshots['settled_duplicate']
                    if duplicate['selector_epoch']!=3 or any(duplicate[k]!=settled[k] for k in ('provider','reservation','costs')):
                        return False
                    if settled['provider']['status']!='not_found' or settled['reservation']['state']!='settled' or Decimal(settled['reservation']['remaining'])!=0 or settled['costs']!=['0.100000']:
                        return False
                    reconcile='contact.reconcile:'+original['provider']['id']
                    reconciliations=[e for e in events if e['stage']=='started' and e['intent']==reconcile
                                     and e['generation']==3 and e['pid'] in workers[1]['tree_pids']]
                    if not any(matching_return(a, 'reconciled') and matching_return(b, 'duplicate')
                               and a['task_id']!=b['task_id'] and events.index(a)<events.index(b)
                               for a in reconciliations for b in reconciliations):
                        return False
        return True
    except (KeyError, TypeError, ValueError, IndexError, ArithmeticError):
        return False
