"""Bounded discoverable native candidates, with no metadata→company promotion."""
import uuid
import psycopg,pytest
from tests.test_research_candidate_api_db import candidate_api,review_case,page_case,run_case,project_api,admission_case,migrated
from tests.test_api_projects_db import _h
from tests.contract_validation import assert_contract_response

def root(c):return f"/v1/workspaces/{c['workspace']}/runs/{c['run']}/candidates"
def get(c,**params):return c['api'].get(root(c),params=params,headers=_h())

def test_candidate_list_is_scoped_bounded_and_does_not_infer_entities(candidate_api):
    c=candidate_api;reply=get(c);assert reply.status_code==200,reply.text
    assert_contract_response('ResearchCandidatePageResponse',reply.json());data=reply.json()['data']
    assert data['total']==1 and data['limit']==20 and data['offset']==0 and len(data['items'])==1
    item=data['items'][0];assert item['raw_candidate_id']==str(c['raw']) and item['mapping_status']=='unmapped'
    assert item['company_id'] is None and item['page_source_id']==str(c['page_source']) and item['source_status']=='page_available'
    assert 'excerpt' not in item and 'provider' not in item
    with psycopg.connect(c['dsn']) as db:assert db.execute('SELECT canonical_company_id FROM raw_candidates WHERE id=%s',(c['raw'],)).fetchone()==(None,)
    assert c['transport'].calls==1

@pytest.mark.parametrize('which',['source','license'])
def test_candidate_list_redacts_expired_or_unlicensed_source_details(candidate_api,which):
    c=candidate_api
    with psycopg.connect(c['dsn']) as db:
        if which=='source':db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE run_id=%s",(c['run'],))
        else:db.execute("UPDATE policy_decisions SET expires_at=now()-interval '1 second' WHERE id=%s",(c['policy'],))
    reply=get(c);assert reply.status_code==200,reply.text
    item=reply.json()['data']['items'][0];assert item['source_status']=='unavailable' and item['page_source_id'] is None and item['title'] is None and item['source_url'] is None

def test_candidate_list_rejects_limit_above100(candidate_api):
    c=candidate_api;reply=get(c,limit=101);assert reply.status_code==422,reply.text

def test_candidate_list_foreign_run_is_not_found(candidate_api):
    c=candidate_api;reply=c['api'].get(root(c).replace(str(c['run']),str(uuid.uuid4())),headers=_h());assert reply.status_code==404,reply.text

def test_candidate_list_pagination_of101_observations_returns100_then1(candidate_api):
    c=candidate_api;extra=[uuid.uuid4() for _ in range(100)]
    try:
        with psycopg.connect(c['dsn']) as db:
            for i,value in enumerate(extra):db.execute("INSERT INTO raw_candidates(id,workspace_id,run_id,source_url,normalized_url,merge_state,raw_payload) VALUES(%s,%s,%s,%s,%s,'unmapped','{}')",(value,c['workspace'],c['run'],f'https://unverified.example.test/{i}',f'https://unverified.example.test/{i}'))
        first=get(c,limit=100);assert first.status_code==200,first.text
        second=get(c,offset=100,limit=100);assert second.status_code==200,second.text
        a,b=first.json()['data'],second.json()['data'];assert a['total']==b['total']==101 and len(a['items'])==100 and len(b['items'])==1
        assert len({x['raw_candidate_id'] for x in a['items']+b['items']})==101
        assert all(x['source_url'] is None and x['title'] is None for x in a['items']+b['items'] if x['raw_candidate_id']!=str(c['raw']))
    finally:
        with psycopg.connect(c['dsn']) as db:db.execute('DELETE FROM raw_candidates WHERE id=ANY(%s)',(extra,))


def test_candidate_list_incomplete_original_page_claim_is_awaiting_reconciliation_without_GET(candidate_api):
    c=candidate_api
    with psycopg.connect(c['dsn']) as db:
        db.execute('DELETE FROM receipt_source_bindings WHERE source_id=%s',(c['page_source'],))
        db.execute('DELETE FROM source_documents WHERE id=%s',(c['page_source'],))
        db.execute("DELETE FROM run_events WHERE run_id=%s AND event_type='page.fetch.finished'",(c['run'],))
    reply=get(c);assert reply.status_code==200,reply.text
    item=reply.json()['data']['items'][0];assert item['source_status']=='awaiting_reconciliation' and item['page_source_id'] is None
    assert c['transport'].calls==1


def test_candidate_list_query_count_does_not_grow_from1_to101(candidate_api):
    import asyncio
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import create_async_engine
    from buyeros_api.api.deps import async_database_url
    from buyeros_api.db.session import tenant_session
    from buyeros_api.services.research_candidate_list import list_research_candidates
    from tests.cutover_fixtures import role_dsn
    c=candidate_api;extra=[uuid.uuid4() for _ in range(100)];counts=[]
    async def measure():
        engine=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_api')));statements=[]
        event.listen(engine.sync_engine,'before_cursor_execute',lambda *args:statements.append(1))
        try:
            async with tenant_session(engine,c['workspace']) as session:
                start=len(statements)
                page=await list_research_candidates(session,workspace_id=c['workspace'],run_id=c['run'],project_id=c['project'],offset=0,limit=100)
                counts.append(len(statements)-start);return page
        finally:await engine.dispose()
    try:
        assert asyncio.run(measure())['total']==1
        with psycopg.connect(c['dsn']) as db:
            for i,value in enumerate(extra):db.execute("INSERT INTO raw_candidates(id,workspace_id,run_id,source_url,normalized_url,merge_state,raw_payload) VALUES(%s,%s,%s,%s,%s,'unmapped','{}')",(value,c['workspace'],c['run'],f'https://unverified.example.test/{i}',f'https://unverified.example.test/{i}'))
        assert asyncio.run(measure())['total']==101
        assert counts[0]==counts[1] and 0<counts[0]<=8,counts
        print('ACTUAL_CANDIDATE_LIST_SQL_COUNTS='+str(counts))
    finally:
        with psycopg.connect(c['dsn']) as db:db.execute('DELETE FROM raw_candidates WHERE id=ANY(%s)',(extra,))
