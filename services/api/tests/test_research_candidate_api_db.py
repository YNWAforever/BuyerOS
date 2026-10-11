"""Authenticated native review API; actual restricted PG and synthetic page only."""
import uuid
import psycopg,pytest
from tests.test_research_candidate_review_db import review_case,page_case,run_case,project_api,admission_case,migrated
from tests.test_api_projects_db import _h
from tests.contract_validation import assert_contract_response
from buyeros_api.api.routes.runs import selected_run_capability

@pytest.fixture
def candidate_api(review_case):
    c=review_case
    previous=c['api'].app.dependency_overrides[selected_run_capability]
    c['api'].app.dependency_overrides[selected_run_capability]=lambda:(c['cap'],'test')
    try:yield c
    finally:c['api'].app.dependency_overrides[selected_run_capability]=previous

def url(c):return f"/v1/workspaces/{c['workspace']}/runs/{c['run']}/candidates/{c['raw']}"
def body(c):return {k:str(v) if isinstance(v,uuid.UUID) else v for k,v in c['args'].items() if k in {'company_id','page_source_id','expected_page_digest','expected_company_hash','excerpt','reason'}}
def post(c,**kw):return c['api'].post(url(c)+'/review',json=kw.pop('payload',body(c)),headers=kw.pop('headers',_h(key='candidate-review-http')),**kw)
def context(c):return c['api'].get(url(c)+'/review-context',params={'company_id':str(c['company'])},headers=_h())

def test_review_API_derives_canonical_actor_replays_once_and_matches_contract(candidate_api):
    c=candidate_api;a=post(c);assert a.status_code==200,a.text
    assert_contract_response('ResearchCandidateReviewResponse',a.json())
    assert post(c).json()['data']==a.json()['data'];assert c['transport'].calls==1
    with psycopg.connect(c['dsn']) as db:
        assert db.execute("SELECT count(*) FROM audit_events WHERE subject_type='raw_candidate' AND subject_id=%s AND actor_id=%s",(str(c['raw']),c['actor'])).fetchone()==(1,)
        assert db.execute('SELECT count(*) FROM fit_assessments WHERE project_buyer_id=%s',(a.json()['data']['buyer_id'],)).fetchone()==(0,)

def test_review_context_returns_current_source_and_independent_company_hash_without_writes(candidate_api):
    c=candidate_api;reply=context(c);assert reply.status_code==200,reply.text
    assert_contract_response('ResearchCandidateReviewContextResponse',reply.json())
    value=reply.json()['data'];assert value['company']['id']==str(c['company']) and value['company']['hash']==c['args']['expected_company_hash']
    assert value['page']['id']==str(c['page_source']) and value['page']['digest']==c['args']['expected_page_digest'] and value['page']['excerpt']==c['args']['excerpt']
    assert value['entity_status']=='needs_review' and value['fit_status']=='needs_review'
    with psycopg.connect(c['dsn']) as db:assert db.execute('SELECT count(*) FROM company_aliases WHERE raw_candidate_id=%s',(c['raw'],)).fetchone()==(0,)

@pytest.mark.parametrize('mutation',['expired-source','unanchored-company'])
def test_review_context_rejects_ineligible_current_basis(candidate_api,mutation):
    c=candidate_api
    with psycopg.connect(c['dsn']) as db:
        if mutation=='expired-source':db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c['page_source'],))
        else:db.execute('UPDATE companies SET legal_name=%s WHERE id=%s',('Unanchored Independent Company',c['company']))
    reply=context(c);assert reply.status_code==409,reply.text

def test_review_API_requires_idempotency_key(candidate_api):
    c=candidate_api;headers=_h();headers.pop('Idempotency-Key');reply=post(c,headers=headers);assert reply.status_code==400,reply.text

def test_review_API_revoked_reviewer_cannot_replay_cached_result(candidate_api):
    c=candidate_api;assert post(c).status_code==200
    with psycopg.connect(c['dsn']) as db:db.execute("UPDATE memberships SET roles='{operator}' WHERE workspace_id=%s AND user_id=%s",(c['workspace'],c['actor']))
    reply=post(c);assert reply.status_code==403,reply.text

def test_review_API_stale_source_cannot_replay_cached_result(candidate_api):
    c=candidate_api;assert post(c).status_code==200
    with psycopg.connect(c['dsn']) as db:db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c['page_source'],))
    reply=post(c);assert reply.status_code==409,reply.text

def test_review_API_foreign_candidate_is_not_found(candidate_api):
    c=candidate_api;reply=c['api'].post(url(c).replace(str(c['raw']),str(uuid.uuid4()))+'/review',json=body(c),headers=_h());assert reply.status_code==404,reply.text

def test_review_API_unselected_capability_stays_503(candidate_api):
    c=candidate_api;c['api'].app.dependency_overrides[selected_run_capability]=lambda:(None,'production')
    reply=post(c);assert reply.status_code==503,reply.text

@pytest.mark.parametrize('extra',['actor_id','capability','reviewed','permission_allowed'])
def test_review_API_rejects_client_identity_and_permission_fields(candidate_api,extra):
    c=candidate_api;reply=post(c,payload={**body(c),extra:str(c['actor'])});assert reply.status_code==422,reply.text

def test_review_API_changed_hash_conflicts_without_new_mapping(candidate_api):
    c=candidate_api;assert post(c).status_code==200
    reply=post(c,payload={**body(c),'expected_company_hash':'0'*64});assert reply.status_code==409,reply.text


@pytest.mark.parametrize('material',['alias','evidence','buyer'])
def test_review_context_rejects_changed_accepted_mapping_material(candidate_api,material):
    c=candidate_api;reply=post(c);assert reply.status_code==200,reply.text
    result=reply.json()['data']
    with psycopg.connect(c['dsn']) as db:
        if material=='alias':db.execute('UPDATE company_aliases SET normalized_value=%s WHERE id=%s',('0'*64,result['alias_id']))
        elif material=='evidence':db.execute('UPDATE evidence SET content_hash=%s WHERE id=%s',('0'*64,result['evidence_id']))
        else:db.execute('UPDATE project_buyers SET company_id=%s WHERE id=%s',(c['sibling'],result['buyer_id']))
    value=context(c);assert value.status_code==409,value.text


@pytest.mark.parametrize('condition',['stale-basis','unselected-provider'])
def test_review_error_matches_declared_recovery_contract(candidate_api,condition):
    c=candidate_api
    if condition=='unselected-provider':
        c['api'].app.dependency_overrides[selected_run_capability]=lambda:(None,'production')
        reply=post(c);assert reply.status_code==503,reply.text
    else:
        reply=post(c,payload={**body(c),'expected_company_hash':'0'*64});assert reply.status_code==409,reply.text
    assert_contract_response('ApiError',reply.json())


@pytest.mark.parametrize('material',['citation-excerpt','missing-review-proof'])
def test_review_context_requires_frozen_original_quote_proof(candidate_api,material):
    c=candidate_api;reply=post(c);assert reply.status_code==200,reply.text
    with psycopg.connect(c['dsn']) as db:
        if material=='citation-excerpt':db.execute("UPDATE evidence SET excerpt='sensor parts' WHERE id=%s",(reply.json()['data']['evidence_id'],))
        else:db.execute("UPDATE run_events SET payload=payload-'review_reason_hash' WHERE run_id=%s AND event_type='candidate.page_reviewed'",(c['run'],))
    value=context(c);assert value.status_code==409,value.text
