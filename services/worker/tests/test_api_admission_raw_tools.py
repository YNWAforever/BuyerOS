"""Raw HTTP envelopes must authorize the exact resulting manifest/job."""
import copy,hashlib,json
import pytest
from tests.test_api_admitted_mixed_tools import positive as base,validate


def positive():return base()


def test_actual_http_envelopes_join_exact_manifest_job_and_canonical_owner():assert validate(positive())


@pytest.mark.parametrize('breakage',['missing_body','body_hash','manifest_response','manifest_count','manifest_digest','manifest_workspace','job_response','job_requested','job_project','response_request_id','body_owner','confirmation','duplicate_operation','missing_input_hash','accepted_no_ref','missing_hold_id'])
def test_raw_http_or_original_liability_rebinding_is_refused(breakage):
    r=positive();q=next(x for x in r['requests'] if x['status']==201);e=next(x for x in r['requests'] if x['status']==202)
    if breakage=='missing_body':q.pop('body')
    elif breakage=='body_hash':q['body_hash']='0'*64
    elif breakage=='manifest_response':q['response']['data']['id']='foreign-manifest'
    elif breakage=='manifest_count':q['response']['data']['count']=1
    elif breakage=='manifest_digest':q['response']['data']['digest']='d'*64
    elif breakage=='manifest_workspace':q['response']['data']['workspace_id']='foreign'
    elif breakage=='job_response':e['response']['data']['id']='foreign-job'
    elif breakage=='job_requested':e['response']['data']['requested']=1
    elif breakage=='job_project':e['response']['data']['project_id']='foreign'
    elif breakage=='response_request_id':q['response']['request_id']='foreign-request'
    elif breakage=='body_owner':
        q['body']['target']['owner_membership_id']='foreign'
        q['body_hash']=hashlib.sha256(json.dumps(q['body'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        pair=next(p for p in r['denial_pairs'] if p['owned_id']==q['id']);d=next(x for x in r['requests'] if x['id']==pair['denied_id']);d['body']=copy.deepcopy(q['body']);d['body_hash']=q['body_hash']
    elif breakage=='confirmation':
        e['body']['confirmation']=False;e['body_hash']=hashlib.sha256(json.dumps(e['body'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        for pair in r['denial_pairs']:
            if pair['owned_id']==e['id']:
                d=next(x for x in r['requests'] if x['id']==pair['denied_id']);d['body']=copy.deepcopy(e['body']);d['body_hash']=e['body_hash']
    else:
        h=r['baseline_holds']
        if breakage=='duplicate_operation':h['operations'][1]['id']=h['operations'][0]['id']
        elif breakage=='missing_input_hash':h['operations'][0]['input_hash']=''
        elif breakage=='accepted_no_ref':h['operations'][1]['ref']=None
        elif breakage=='missing_hold_id':h['reservation']['id']=''
        for s in r['samples']:s['holds']=copy.deepcopy(h)
    assert not validate(r)
