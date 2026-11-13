"""One-shot external mutations and a durable GitHub deployment intent ledger."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))


def transport():
    path=ROOT/'scripts/promotion_transport.py'
    assert path.is_file(),'no-retry transport and durable ledger are absent'
    spec=importlib.util.spec_from_file_location('promotion_transport_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def context(run=88):
    return {'schema':'buyeros.promotion-intent.v1','project_id':'prj_owned','source_sha':'a'*40,
            'deployment_id':'dpl_owned','bundle_sha256':'b'*64,'promotion_run_id':run,'runtime_run_id':77}


def alias_boundary(module,monkeypatch,*,override=None,lose_ack=False):
    """Use the real request serialization, with no network at the HTTP boundary."""
    requests=[];moved=False
    class Response:
        code=200
        def __init__(self,value):self.value=value
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,limit):return json.dumps(self.value).encode()
    class Opener:
        def open(self,request,timeout):
            nonlocal moved
            method=request.get_method();url=request.full_url
            body=json.loads(request.data) if request.data else None
            requests.append((method,url,body))
            if '/v9/projects/' in url:
                value={'id':'prj_owned','accountId':'team_owned','autoAssignCustomDomains':False}
            elif '/v4/aliases/' in url:
                value={'alias':module.CANONICAL_ALIAS,'projectId':'prj_owned',
                       'deploymentId':'dpl_owned' if moved else 'dpl_rollback','redirect':None}
            elif '/v13/deployments/' in url:
                value={'id':'dpl_owned','projectId':'prj_owned','ownerId':'team_owned',
                       'target':'production','readyState':'READY'}
            elif method=='POST' and '/v2/deployments/dpl_owned/aliases?' in url:
                moved=True
                if lose_ack:raise ConnectionResetError('accepted but acknowledgement lost')
                value={'alias':module.CANONICAL_ALIAS,'uid':'alias-owned','oldDeploymentId':'dpl_rollback'}
            else:raise AssertionError('unexpected request')
            if override:value=override(method,url,value,moved)
            return Response(value)
    monkeypatch.setattr(module.urllib.request,'build_opener',lambda *args:Opener())
    return requests


def assign(module):
    return module.single_assign_alias('prj_owned','team_owned','dpl_owned','dpl_rollback','private-token')


def test_connection_reset_after_acceptance_never_retries_http_post(monkeypatch):
    module=transport();requests=alias_boundary(module,monkeypatch,lose_ack=True)
    with pytest.raises(ConnectionResetError):assign(module)
    posts=[row for row in requests if row[0]=='POST']
    assert posts==[('POST','https://api.vercel.com/v2/deployments/dpl_owned/aliases?teamId=team_owned',
                    {'alias':'buyer-os-nu.vercel.app'})]
    assert all('private-token' not in row[1] and '/promote/' not in row[1] for row in requests)


def test_success_moves_only_canonical_alias_and_reads_controls_afterwards(monkeypatch):
    module=transport();requests=alias_boundary(module,monkeypatch)
    assert assign(module)['oldDeploymentId']=='dpl_rollback'
    assert [row[0] for row in requests]==['GET','GET','GET','POST','GET','GET']
    assert requests[3][2]=={'alias':'buyer-os-nu.vercel.app'}
    assert requests[-2][1].startswith('https://api.vercel.com/v9/projects/prj_owned?')
    assert requests[-1][1].startswith('https://api.vercel.com/v4/aliases/buyer-os-nu.vercel.app?')
    assert all('/promote/' not in row[1] for row in requests)


@pytest.mark.parametrize('path,changes',[
    ('/v9/projects/',{'autoAssignCustomDomains':True}),
    ('/v9/projects/',{'autoAssignCustomDomains':None}),
    ('/v9/projects/',{'accountId':'team_foreign'}),
    ('/v4/aliases/',{'deploymentId':'dpl_changed'}),
    ('/v4/aliases/',{'projectId':'prj_foreign'}),
    ('/v4/aliases/',{'alias':'sibling.vercel.app'}),
    ('/v4/aliases/',{'redirect':'elsewhere.test'}),
    ('/v13/deployments/',{'ownerId':'team_foreign'}),
    ('/v13/deployments/',{'projectId':'prj_foreign'}),
    ('/v13/deployments/',{'readyState':'BUILDING'}),
    ('/v13/deployments/',{'target':'preview'}),
    ('/v13/deployments/',{'autoAssignCustomDomains':True}),
])
def test_changed_or_unproven_scope_prevents_mutation(monkeypatch,path,changes):
    module=transport()
    requests=alias_boundary(module,monkeypatch,
        override=lambda method,url,value,moved:{**value,**changes} if path in url else value)
    with pytest.raises(ValueError):assign(module)
    assert not [row for row in requests if row[0]!='GET']


@pytest.mark.parametrize('path,changes',[
    ('/v2/deployments/',{'oldDeploymentId':'dpl_changed'}),
    ('/v2/deployments/',{'alias':'sibling.vercel.app'}),
    ('/v2/deployments/',{'uid':None}),
    ('/v9/projects/',{'autoAssignCustomDomains':True}),
    ('/v4/aliases/',{'deploymentId':'dpl_rollback'}),
])
def test_uncertain_ack_or_readback_stops_without_second_mutation(monkeypatch,path,changes):
    module=transport()
    requests=alias_boundary(module,monkeypatch,
        override=lambda method,url,value,moved:{**value,**changes} if moved and path in url else value)
    with pytest.raises(ValueError):assign(module)
    assert len([row for row in requests if row[0]=='POST'])==1


@pytest.mark.parametrize('path',['/v9/projects/','/v4/aliases/'])
def test_failed_readback_keeps_one_mutation_and_never_retries(monkeypatch,path):
    module=transport()
    def fail_after_assignment(method,url,value,moved):
        if moved and path in url:raise TimeoutError('readback unavailable')
        return value
    requests=alias_boundary(module,monkeypatch,override=fail_after_assignment)
    with pytest.raises(TimeoutError):assign(module)
    assert len([row for row in requests if row[0]=='POST'])==1


@pytest.mark.parametrize('position,value',[
    (0,'prj_owned/other'),(1,'team_owned?other=true'),(2,'dpl_owned/aliases'),
    (3,'dpl_owned'),(3,''),(4,''),
])
def test_invalid_or_identical_targets_make_no_requests(monkeypatch,position,value):
    module=transport();requests=alias_boundary(module,monkeypatch)
    args=['prj_owned','team_owned','dpl_owned','dpl_rollback','private-token'];args[position]=value
    with pytest.raises(ValueError):module.single_assign_alias(*args)
    assert requests==[]


def test_alias_transport_follows_no_redirects():
    module=transport()
    assert module.NoRedirect().redirect_request(None,None,307,'redirect',{},'https://other.test') is None


def test_new_workflow_run_cannot_bypass_unknown_project_intent():
    module=transport();records=[];posts=[]
    def get(path):
        if '/statuses' in path: return []
        return records
    def post(path,body):
        posts.append(body)
        record={'id':123,'payload':body['payload']};records.append(record)
        return record
    assert module.claim_promotion_intent(context(),get=get,post=post)==123
    with pytest.raises(ValueError): module.claim_promotion_intent(context(89),get=get,post=post)
    changed=context(90);changed['deployment_id']='dpl_new';changed['bundle_sha256']='c'*64
    with pytest.raises(ValueError): module.claim_promotion_intent(changed,get=get,post=post)
    assert len(posts)==1


def test_lost_intent_acknowledgement_still_blocks_next_dispatch():
    module=transport();records=[]
    def get(path): return [] if '/statuses' in path else records
    def post(path,body):
        records.append({'id':124,'payload':body['payload']})
        raise ConnectionResetError('intent committed but acknowledgement lost')
    with pytest.raises(ConnectionResetError): module.claim_promotion_intent(context(),get=get,post=post)
    with pytest.raises(ValueError): module.claim_promotion_intent(context(89),get=get,post=post)
    assert len(records)==1
