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


def test_connection_reset_after_acceptance_never_retries_http_post(monkeypatch):
    module=transport();accepted=[]
    class Opener:
        def open(self,request,timeout):
            accepted.append((request.get_method(),request.full_url,request.data))
            raise ConnectionResetError('accepted but acknowledgement lost')
    monkeypatch.setattr(module.urllib.request,'build_opener',lambda *args:Opener())
    with pytest.raises(ConnectionResetError):
        module.single_promote('prj_owned','team_owned','dpl_owned','private-token')
    assert len(accepted)==1 and accepted[0][0]=='POST'
    assert 'private-token' not in accepted[0][1]


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
