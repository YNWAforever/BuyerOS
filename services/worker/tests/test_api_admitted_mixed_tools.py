"""Hand-derived positive and corrupt API/task/durable admission evidence."""
import copy
import importlib.util
from pathlib import Path
import pytest


def validate(r):
    path=Path(__file__).with_name('api_admission_driver.py')
    if not path.exists():return False
    spec=importlib.util.spec_from_file_location('admission',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m.capture_complete(r)


def positive():
    members=[dict(workspace=f'w{i}',project=f'p{i}',actor=f'u{i}',membership=f'm{i}') for i in range(10)]
    workers=[dict(popen_pid=101,tree_pids=[101]),dict(popen_pid=102,tree_pids=[102])]
    requests=[]; pairs=[]; bulk=[]; sources=[]; pubs=[]; events=[]; terminal=[]; buyers=[]
    def request(wave,m,stage,status,actor=None,code=None,version=1):
        rid=f'r{len(requests)}';path=f"/v1/workspaces/{m['workspace']}/projects/{m['project']}/bulk-manifests"
        if stage=='execute':path+=f"/manifest-{wave}-{m['workspace']}/execute"
        row=dict(id=rid,request_id=rid,header_request_id=rid,wave=wave,workspace=m['workspace'],project=m['project'],
                 actor=actor or m['actor'],method='POST',path=path,stage=stage,status=status,code=code,
                 body_hash='a'*64,key='key-'+rid,if_match=f'"{version}"' if stage=='execute' else None,
                 started_ns=100+len(requests)*10,returned_ns=109+len(requests)*10)
        requests.append(row);return rid
    def delivery(intent,wave,m,kind):
        n=len(pubs);pid=101+n%2;at=2000+n*10
        p=dict(intent=intent,workspace=m['workspace'],wave=wave,kind=kind,outbox_id='o'+str(n),task_id='t'+str(n),generation=1,at_ns=at)
        pubs.append(p)
        events.extend([dict(stage=s,intent=intent,workspace=m['workspace'],generation=1,task_id=p['task_id'],pid=pid,at_ns=at+d,**({'outcome':'done'} if s=='return' else {})) for s,d in [('started',1),('return',2)]])
        terminal.append(dict(id=p['outbox_id'],intent=intent,workspace=m['workspace'],kind=kind,state='done',generation=1,epoch=1))
        return p['outbox_id']
    for wave in range(3):
        for i,m in enumerate(members):
            denied=[]
            if wave==0:denied.append(('foreign_preview',request(wave,m,'preview',404,actor=members[(i+1)%10]['actor'],code='NOT_FOUND')))
            preview=request(wave,m,'preview',201)
            if wave==0:denied.append(('foreign_execute',request(wave,m,'execute',404,actor=members[(i+1)%10]['actor'],code='NOT_FOUND')))
            if wave==1:denied.append(('inactive',request(wave,m,'execute',404,code='NOT_FOUND')))
            if wave==2:
                denied.append(('viewer',request(wave,m,'execute',403,code='FORBIDDEN')))
                denied.append(('stale',request(wave,m,'execute',412,code='STALE_REVISION',version=999)))
            accepted=request(wave,m,'execute',202)
            for kind,rid in denied:
                pairs.append(dict(kind=kind,denied_id=rid,owned_id=preview if kind=='foreign_preview' else accepted,
                                  before=dict(jobs=[],outbox=[],manifest_version=1),after=dict(jobs=[],outbox=[],manifest_version=1)))
            count=303 if i==0 else 101;job=f'j{wave}-{i}';ids=[f'b{wave}-{i}-{n}' for n in range(count)]
            outboxes=[delivery(f'bulk:{job}:{offset}',wave,m,'bulk.mutate') for offset in range(0,count,50)]
            bulk.append(dict(wave=wave,workspace=m['workspace'],project=m['project'],actor=m['actor'],
                             preview_id=preview,execute_id=accepted,manifest_id=f"manifest-{wave}-{m['workspace']}",digest='a'*64,
                             job_id=job,count=count,status='completed',processed=count,updated=count,conflicts=0,blocked=0,
                             buyer_ids=ids,outbox_ids=outboxes))
            buyers.extend(dict(id=b,workspace=m['workspace'],job_id=job,status='updated',version=2,owner=m['actor']) for b in ids)
            for n in range(3 if i==0 else 1):
                sid=f's{wave}-{i}-{n}';o=delivery('source:'+sid,wave,m,'source.delete')
                sources.append(dict(id=sid,workspace=m['workspace'],wave=wave,outbox_id=o,object_key=None,excerpt=None,tombstoned=True))
    holds=dict(operations=[dict(id='held-unknown',status='unknown',intent='held1',ref=None,input_hash='b'*64),dict(id='held-accepted',status='accepted',intent='held2',ref='retained',input_hash='c'*64)],reservation=dict(id='hold',state='active',remaining='0.600000'),costs=[])
    samples=[dict(at_ns=at,holds=copy.deepcopy(holds),spaces=[dict(workspace=m['workspace'],ready=0,dispatched=0,done=0) for m in members],resources=[dict(owner_pid=p['popen_pid'],pid=p['popen_pid'],rss_bytes=1000,method='proc_vmRSS') for p in workers],broker=dict(queued=0,unacked=0,queued_task_ids=[],unacked_task_ids=[])) for at in [1,6000]]
    return dict(schema='buyeros.owned-api-admission.v1',complete=True,error=None,live_verified=False,release_accepted=False,
                paid_enabled=False,delivery_enabled=False,provider_calls=0,send_calls=0,auth_method='real_RS256_local_JWKS',
                members=members,workers=workers,api_role=dict(superuser=False,bypass=False,rls=True,owner=False),worker_role=dict(superuser=False,bypass=False,rls=True,owner=False),
                requests=requests,denial_pairs=pairs,bulk=bulk,sources=sources,publications=pubs,events=events,terminal=terminal,buyers=buyers,baseline_holds=holds,samples=samples)


def test_complete_owned_api_task_and_durable_chain_is_accepted():
    r=positive()
    assert len(r['requests'])==110 and len(r['denial_pairs'])==50 and len(r['publications'])==138 and len(r['buyers'])==3636
    assert validate(r)


@pytest.mark.parametrize('breakage',[
    'missing_request','missing_pair','wrong_error','foreign_success','different_body','wrong_route','missing_request_id',
    'rebound_request_id','negative_wrote','missing_workspace','missing_wave','missing_chunk','duplicate_task','foreign_worker',
    'missing_return','wrong_generation','wrong_epoch','wrong_owner','missing_buyer','duplicate_buyer','wrong_count',
    'missing_source','retained_object','hold_release','accepted_changed','cost_added','provider_call','paid_flag',
    'missing_resource','missing_queue_space','wrong_broker_count','foreign_broker_id','missing_worker','auth_override','superuser'])
def test_incomplete_or_rebound_api_admission_is_refused(breakage):
    r=positive()
    if breakage=='missing_request':r['requests'].pop()
    elif breakage=='missing_pair':r['denial_pairs'].pop()
    elif breakage=='wrong_error':r['requests'][0]['code']='INVALID_REQUEST'
    elif breakage=='foreign_success':r['requests'][0]['status']=201
    elif breakage=='different_body':r['requests'][0]['body_hash']='d'*64
    elif breakage=='wrong_route':r['requests'][0]['path']='/wrong'
    elif breakage=='missing_request_id':r['requests'][0]['request_id']=None
    elif breakage=='rebound_request_id':r['requests'][0]['header_request_id']='different'
    elif breakage=='negative_wrote':r['denial_pairs'][0]['after']['jobs']=['unexpected']
    elif breakage=='missing_workspace':r['members'].pop()
    elif breakage=='missing_wave':r['bulk']=[x for x in r['bulk'] if x['wave']!=2]
    elif breakage=='missing_chunk':r['bulk'][0]['outbox_ids'].pop()
    elif breakage=='duplicate_task':r['publications'][0]['task_id']=r['publications'][1]['task_id']
    elif breakage=='foreign_worker':r['events'][0]['pid']=999
    elif breakage=='missing_return':r['events'].pop()
    elif breakage=='wrong_generation':r['events'][0]['generation']=2
    elif breakage=='wrong_epoch':r['terminal'][0]['epoch']=2
    elif breakage=='wrong_owner':r['buyers'][0]['owner']='foreign'
    elif breakage=='missing_buyer':r['buyers'].pop()
    elif breakage=='duplicate_buyer':r['buyers'][0]['id']=r['buyers'][1]['id']
    elif breakage=='wrong_count':r['bulk'][0]['count']=302
    elif breakage=='missing_source':r['sources'].pop()
    elif breakage=='retained_object':r['sources'][0]['object_key']='retained'
    elif breakage=='hold_release':r['samples'][0]['holds']['reservation']['remaining']='0'
    elif breakage=='accepted_changed':r['samples'][0]['holds']['operations'][1]['ref']='new'
    elif breakage=='cost_added':r['samples'][0]['holds']['costs']=[1]
    elif breakage=='provider_call':r['provider_calls']=1
    elif breakage=='paid_flag':r['paid_enabled']=True
    elif breakage=='missing_resource':r['samples'][0]['resources'].pop()
    elif breakage=='missing_queue_space':r['samples'][0]['spaces'].pop()
    elif breakage=='wrong_broker_count':r['samples'][0]['broker']['queued']=1
    elif breakage=='foreign_broker_id':r['samples'][0]['broker'].update(queued=1,queued_task_ids=['foreign'])
    elif breakage=='missing_worker':r['workers'].pop()
    elif breakage=='auth_override':r['auth_method']='principal_override'
    elif breakage=='superuser':r['api_role']['superuser']=True
    assert not validate(r)
