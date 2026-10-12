"""Strict short-burst owned API evidence; no sustained/live/SLO acceptance."""
from collections import Counter


def capture_complete(r):
    def integer(x):return type(x) is int and x>=0
    try:
        if r['schema']!='buyeros.owned-api-admission.v1' or r['complete'] is not True or r['error'] is not None:return False
        if any(r[k] is not False for k in ['live_verified','release_accepted','paid_enabled','delivery_enabled']):return False
        if r['provider_calls']!=0 or r['send_calls']!=0 or r['auth_method']!='real_RS256_local_JWKS':return False
        members=r['members'];spaces=[m['workspace'] for m in members]
        if len(members)!=10 or len(set(spaces))!=10 or any(not m[k] for m in members for k in ['workspace','project','actor','membership']):return False
        if len({m['actor'] for m in members})!=10:return False
        indexed={m['workspace']:m for m in members}
        for name in ['api_role','worker_role']:
            role=r[name]
            if role['superuser'] is not False or role['bypass'] is not False or role['owner'] is not False or role['rls'] is not True:return False
        workers=r['workers'];owners={w['popen_pid'] for w in workers};pids={p for w in workers for p in w['tree_pids']}
        if len(workers)!=2 or len(owners)!=2 or any(w['popen_pid'] not in w['tree_pids'] for w in workers):return False
        requests=r['requests']
        if len(requests)!=110 or len({q['id'] for q in requests})!=110 or len({q['request_id'] for q in requests})!=110:return False
        if len({q['key'] for q in requests})!=110:return False
        reqs={q['id']:q for q in requests}
        for q in requests:
            if q['workspace'] not in indexed or q['project']!=indexed[q['workspace']]['project'] or q['wave'] not in range(3):return False
            if not q['request_id'] or q['header_request_id']!=q['request_id'] or q['method']!='POST' or not q['key']:return False
            if not isinstance(q['body_hash'],str) or len(q['body_hash'])!=64:return False
            if not integer(q['started_ns']) or not integer(q['returned_ns']) or q['returned_ns']<q['started_ns']:return False
        expected_pairs=Counter()
        for s in spaces:
            for kind,wave in [('foreign_preview',0),('foreign_execute',0),('inactive',1),('viewer',2),('stale',2)]:expected_pairs[kind,s,wave]=1
        pairs=r['denial_pairs'];actual=Counter()
        denied=set();accepted=set()
        for pair in pairs:
            d,o=reqs[pair['denied_id']],reqs[pair['owned_id']];kind=pair['kind'];actual[kind,d['workspace'],d['wave']]+=1
            if pair['before']!=pair['after'] or not isinstance(pair['before'],dict) or not pair['before']:return False
            if pair['denied_id'] in denied:return False
            denied.add(pair['denied_id']);accepted.add(pair['owned_id'])
            if any(d[k]!=o[k] for k in ['method','path','workspace','project','wave','stage','body_hash']):return False
            status,code={'foreign_preview':(404,'NOT_FOUND'),'foreign_execute':(404,'NOT_FOUND'),'inactive':(404,'NOT_FOUND'),'viewer':(403,'PERMISSION_DENIED'),'stale':(412,'STALE_REVISION')}[kind]
            if (d['status'],d['code'])!=(status,code) or o['status']!=(201 if kind=='foreign_preview' else 202) or o['code'] is not None:return False
            if o['actor']!=indexed[o['workspace']]['actor']:return False
            if (d['actor']==o['actor']) != (kind not in ['foreign_preview','foreign_execute']):return False
            if kind=='stale' and d['if_match']==o['if_match']:return False
        if actual!=expected_pairs:return False
        bulk=r['bulk'];sources=r['sources'];buyers=r['buyers'];publications=r['publications'];terminal=r['terminal']
        if len(bulk)!=30 or Counter((b['wave'],b['workspace']) for b in bulk)!=Counter({(w,s):1 for w in range(3) for s in spaces}):return False
        if len({b['job_id'] for b in bulk})!=30 or len({b['manifest_id'] for b in bulk})!=30:return False
        expected_source=Counter({(w,s):3 if i==0 else 1 for w in range(3) for i,s in enumerate(spaces)})
        if len(sources)!=36 or Counter((s['wave'],s['workspace']) for s in sources)!=expected_source or len({s['id'] for s in sources})!=36:return False
        if len(publications)!=138 or any(len({p[k] for p in publications})!=138 for k in ['intent','task_id','outbox_id']):return False
        if len(terminal)!=138 or len({t['id'] for t in terminal})!=138:return False
        pubs={p['outbox_id']:p for p in publications};final={t['id']:t for t in terminal}
        raw=r['events'];events=[e for e in raw if e['stage'] in ['started','return']]
        if any(e['stage']=='forbidden_provider_call' for e in raw) or len(events)!=276:return False
        event_index={(e['stage'],e['task_id']):e for e in events}
        if len(event_index)!=276:return False
        used_pids=set()
        for p in publications:
            f=final[p['outbox_id']]
            if any(f[k]!=p[k] for k in ['intent','workspace','kind','generation']) or f['state']!='done' or f['epoch']!=1 or p['generation']!=1:return False
            a,b=event_index['started',p['task_id']],event_index['return',p['task_id']]
            if any(e[k]!=p[k] for e in [a,b] for k in ['intent','workspace','generation']):return False
            if a['pid']!=b['pid'] or a['pid'] not in pids or b['outcome']!='done':return False
            if not p['at_ns']<=a['at_ns']<=b['at_ns']:return False
            used_pids.add(a['pid'])
        if any(not used_pids.intersection(w['tree_pids']) for w in workers):return False
        claimed=set();selected=set();owned_requests=set()
        for b in bulk:
            m=indexed[b['workspace']];count=303 if b['workspace']==spaces[0] else 101
            if b['actor']!=m['actor'] or b['project']!=m['project'] or b['count']!=count:return False
            if b['status']!='completed' or b['processed']!=count or b['updated']!=count or b['conflicts']!=0 or b['blocked']!=0:return False
            if len(b['buyer_ids'])!=count or len(set(b['buyer_ids']))!=count or selected.intersection(b['buyer_ids']):return False
            selected.update(b['buyer_ids'])
            if len(b['outbox_ids'])!=(count+49)//50:return False
            for oid in b['outbox_ids']:
                if oid in claimed or pubs[oid]['kind']!='bulk.mutate' or pubs[oid]['workspace']!=b['workspace'] or pubs[oid]['wave']!=b['wave']:return False
                claimed.add(oid)
            base=f"/v1/workspaces/{b['workspace']}/projects/{b['project']}/bulk-manifests"
            for key,stage,status,path in [('preview_id','preview',201,base),('execute_id','execute',202,base+'/'+b['manifest_id']+'/execute')]:
                q=reqs[b[key]];owned_requests.add(b[key])
                if q['stage']!=stage or q['status']!=status or q['path']!=path or q['code'] is not None:return False
                if any(q[k]!=b[k] for k in ['workspace','project','actor','wave']):return False
        if len(owned_requests)!=60 or denied|owned_requests!=set(reqs):return False
        for s in sources:
            oid=s['outbox_id'];p=pubs[oid]
            if oid in claimed or p['kind']!='source.delete' or p['workspace']!=s['workspace'] or p['wave']!=s['wave']:return False
            if s['object_key'] is not None or s['excerpt'] is not None or s['tombstoned'] is not True:return False
            claimed.add(oid)
        if claimed!=set(pubs) or len(buyers)!=3636 or len({b['id'] for b in buyers})!=3636 or {b['id'] for b in buyers}!=selected:return False
        jobs={b['job_id']:b for b in bulk}
        for b in buyers:
            j=jobs[b['job_id']]
            if b['id'] not in j['buyer_ids'] or b['workspace']!=j['workspace'] or b['status']!='updated' or b['version']!=2 or b['owner']!=j['actor']:return False
        baseline=r['baseline_holds']
        if {o['status'] for o in baseline['operations']}!={'unknown','accepted'} or len(baseline['operations'])!=2:return False
        if baseline['reservation']['state']!='active' or baseline['reservation']['remaining']!='0.600000' or baseline['costs']!=[]:return False
        samples=r['samples']
        if len(samples)<2:return False
        times=[s['at_ns'] for s in samples]
        if times!=sorted(set(times)):return False
        task_ids={p['task_id'] for p in publications}
        for s in samples:
            if s['holds']!=baseline or {x['workspace'] for x in s['spaces']}!=set(spaces) or len(s['spaces'])!=10:return False
            if any(not integer(x[k]) for x in s['spaces'] for k in ['ready','dispatched','done']):return False
            resources=s['resources']
            if {x['owner_pid'] for x in resources}!=owners or any(x['pid'] not in pids or not integer(x['rss_bytes']) or x['rss_bytes']==0 or x['method'] not in ['linux_proc_status_VmRSS','windows_GetProcessMemoryInfo_WorkingSetSize'] for x in resources):return False
            ids=[]
            for kind in ['queued','unacked']:
                q=s['broker'];values=q[kind+'_task_ids']
                if not integer(q[kind]) or len(values)!=q[kind] or not set(values)<=task_ids:return False
                ids.extend(values)
            if len(ids)!=len(set(ids)):return False
        return True
    except (KeyError,TypeError,ValueError,IndexError):return False
