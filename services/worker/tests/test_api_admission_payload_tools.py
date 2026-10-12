"""Original outbox payload must cause the same admitted job/source result."""
import copy
import pytest
from tests.test_api_admitted_mixed_tools import positive as base,validate


def positive():
    r=base();pubs={p['outbox_id']:p for p in r['publications']};final={t['id']:t for t in r['terminal']}
    for b in r['bulk']:
        for oid in b['outbox_ids']:
            pubs[oid]['payload']={'job_id':b['job_id']};final[oid]['payload']={'job_id':b['job_id']}
    for s in r['sources']:
        pubs[s['outbox_id']]['payload']={'source_document_id':s['id']};final[s['outbox_id']]['payload']={'source_document_id':s['id']}
    return r


def test_original_outbox_payload_joins_same_admitted_job_and_source():assert validate(positive())


@pytest.mark.parametrize('breakage',['missing_payload','different_job','different_source','terminal_payload','extra_payload_scope'])
def test_borrowed_outbox_payload_is_refused(breakage):
    r=positive();pub=r['publications'][0];terminal=next(t for t in r['terminal'] if t['id']==pub['outbox_id'])
    if breakage=='missing_payload':pub.pop('payload')
    elif breakage=='different_job':pub['payload']=terminal['payload']={'job_id':'foreign-job'}
    elif breakage=='different_source':
        s=r['sources'][0];pub=next(p for p in r['publications'] if p['outbox_id']==s['outbox_id']);terminal=next(t for t in r['terminal'] if t['id']==s['outbox_id']);pub['payload']=terminal['payload']={'source_document_id':'foreign-source'}
    elif breakage=='terminal_payload':terminal['payload']={'job_id':'foreign-job'}
    elif breakage=='extra_payload_scope':pub['payload']=terminal['payload']={'job_id':r['bulk'][0]['job_id'],'workspace_id':'foreign'}
    assert not validate(r)
