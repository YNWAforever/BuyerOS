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
            returns = [e for e in events if e['stage'] == 'return' and e['intent'] == inflight['key']]
            first = starts[0]
            if c['broker_final'] != dict(unacked=[], queued=0):
                return False
            if c['name'] == 'lease':
                expired = snapshots['expired']
                if datetime.fromisoformat(expired['db_now']) < datetime.fromisoformat(expired['lease_expires']):
                    return False
                if not any(e['generation']==2 and e['outcome']=='done' for e in returns):
                    return False
                if not any(e['pid']==first['pid'] and e['generation']==1 and e['outcome']=='stale' for e in returns):
                    return False
            else:
                kill = c['killed']
                if kill['pid'] != first['pid'] or kill['pid'] not in workers[0]['tree_pids'] or kill['popen_pid'] != workers[0]['popen_pid'] or kill['exit_code'] is None:
                    return False
                if first['task_id'] not in c['broker_before']['unacked']:
                    return False
                if not any(e['redelivered'] is True and e['task_id']==first['task_id'] and e['pid']!=first['pid'] for e in starts[1:]):
                    return False
                want = {'redelivery':'done','unknown':'unknown','accepted':'duplicate'}[c['name']]
                if not any(e['outcome']==want and e['pid']!=first['pid'] for e in returns):
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
                    if [(e['ref'],e['outcome']) for e in statuses]!=[(ref,'accepted'),(ref,'not_found')]:
                        return False
                    settled=snapshots['settled']
                    if settled['provider']['status']!='not_found' or settled['reservation']['state']!='settled' or Decimal(settled['reservation']['remaining'])!=0 or settled['costs']!=['0.100000']:
                        return False
        return True
    except (KeyError, TypeError, ValueError, IndexError, ArithmeticError):
        return False
