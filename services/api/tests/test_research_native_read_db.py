"""Native evidence display revalidates original current review/source proof."""
import psycopg,pytest
from tests.test_research_native_basis_db import native_basis_case,review_case,page_case,run_case,project_api,admission_case,migrated
from tests.test_api_projects_db import _h
from tests.test_research_page_scope_db import URL
from tests.contract_validation import assert_contract_response

def read(c,route):
    root=f"/v1/workspaces/{c['workspace']}"
    return c['api'].get(root+(f"/evidence/{c['evidence']}" if route=='single' else f"/buyers/{c['buyer']}/evidence"),headers=_h())

def item(reply,route):return reply.json()['data'] if route=='single' else reply.json()['data']['items'][0]

@pytest.mark.parametrize('route',['single','list'])
def test_current_native_evidence_is_available_as_inference_without_more_GET(native_basis_case,route):
    c=native_basis_case;reply=read(c,route);assert reply.status_code==200,reply.text
    value=item(reply,route);assert value['status']=='available' and value['kind']=='inference'
    assert value['excerpt']==c['args']['excerpt'] and value['source_url']==URL
    assert c['transport'].calls==1

@pytest.mark.parametrize('route',['single','list'])
@pytest.mark.parametrize('mutation',['source','citation','alias','company','expiry','license','review_proof','metadata','finish'])
def test_native_evidence_read_masks_changed_or_unlicensed_prose_and_URL(native_basis_case,route,mutation):
    c=native_basis_case
    with psycopg.connect(c['dsn']) as db:
        if mutation=='source':db.execute("UPDATE source_documents SET excerpt='changed' WHERE id=%s",(c['page_source'],))
        elif mutation=='citation':db.execute("UPDATE evidence SET excerpt='sensor parts',translation='Unverified translation' WHERE id=%s",(c['evidence'],))
        elif mutation=='alias':db.execute('UPDATE company_aliases SET normalized_value=%s WHERE id=%s',('0'*64,c['review']['alias_id']))
        elif mutation=='company':db.execute("UPDATE companies SET display_name='Changed label' WHERE id=%s",(c['company'],))
        elif mutation=='expiry':db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c['page_source'],))
        elif mutation=='license':db.execute("UPDATE policy_decisions SET expires_at=now()-interval '1 second' WHERE id=%s",(c['policy'],))
        elif mutation=='review_proof':db.execute("UPDATE run_events SET payload=payload-'review_reason_hash' WHERE run_id=%s AND event_type='candidate.page_reviewed'",(c['run'],))
        elif mutation=='metadata':db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c['source'],))
        else:db.execute("UPDATE run_events SET payload=payload-'excerpt_digest' WHERE run_id=%s AND event_type='page.fetch.finished'",(c['run'],))
    reply=read(c,route);assert reply.status_code==200,reply.text;value=item(reply,route)
    assert value['status']=='access_blocked',value
    assert value['excerpt']=='Source unavailable' and 'source_url' not in value and 'translated_excerpt' not in value
    assert c['transport'].calls==1
