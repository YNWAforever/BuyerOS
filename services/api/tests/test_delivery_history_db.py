"""Scoped immutable history on the original restricted owned PostgreSQL fixture."""
import uuid
import psycopg,pytest
from buyeros_api.settings import get_settings
from tests.test_delivery_admission_db import admission_case, counts
from tests.test_delivery_reconciliation_db import reconciliation_case, select, apply
from tests.test_delivery_status_db import snapshot, assert_originals_retained
from tests.test_lookup_quotes_db import ADMIN,OPERATOR,REVIEWER,WORKSPACE_A,_h
from tests.test_api_tenant_isolation import WORKSPACE_B
from tests.contract_validation import assert_contract_response

def url(case,*,workspace=None,project=None,draft=None):
    args=case[2]
    return f"/v1/workspaces/{workspace or args['workspace_id']}/projects/{project or case[3].project_id}/drafts/{draft or args['draft_id']}/delivery-messages"

def read(case,**changes):
    reply=case[0].get(url(case,**changes),headers=_h(REVIEWER))
    assert reply.status_code==200,reply.text
    assert reply.headers['Cache-Control']=='private, no-store'
    assert_contract_response('DeliveryMessagePageResponse',reply.json())
    return reply.json()['data']

def test_retained_history_reads_original_unknown_then_persisted_accepted_without_provider_or_new_intent(reconciliation_case):
    case=reconciliation_case;before=snapshot(case[1],case[4]);money=counts(case[1])
    first=read(case);assert len(first['items'])==first['total']==1
    row=first['items'][0]
    assert row['id']==str(case[4].message_id) and row['state']=='unknown'
    assert row['draft_revision_id']==str(case[2]['draft_revision_id']) and row['approval_id']==str(case[2]['approval_id'])
    assert snapshot(case[1],case[4])==before and counts(case[1])==money
    chosen,reader,built=select(case);receipt=apply(case,chosen)
    result=read(case);assert result['items'][0]['state']==receipt.state=='accepted'
    assert reader.calls==built==['original-ref'] and counts(case[1])==money
    assert_originals_retained(before,snapshot(case[1],case[4]))
    assert not {'provider_ref','account_reference','intent_key','payload_digest','body','subject','recipient_email'} & set(result['items'][0])

@pytest.mark.parametrize('selector',['workspace','project','draft'])
def test_retained_history_foreign_selector_is404_and_matching_owned_metadata_succeeds(reconciliation_case,selector):
    case=reconciliation_case;before=snapshot(case[1],case[4]);value=WORKSPACE_B if selector=='workspace' else uuid.uuid4()
    reply=case[0].get(url(case,**{selector:value}),headers=_h(REVIEWER))
    assert (reply.status_code,reply.json()['code'])==(404,'NOT_FOUND')
    assert read(case)['items'][0]['id']==str(case[4].message_id) and snapshot(case[1],case[4])==before

def test_retained_history_revoked_membership_is404_with_current_other_member_owned_control(reconciliation_case):
    case=reconciliation_case;before=snapshot(case[1],case[4])
    with psycopg.connect(case[1]) as db:
        db.execute('UPDATE memberships SET active=false,version=version+1 WHERE workspace_id=%s AND user_id=%s',(WORKSPACE_A,case[2]['actor_id']))
    denied=case[0].get(url(case),headers=_h(REVIEWER));owned=case[0].get(url(case),headers=_h(ADMIN))
    assert (denied.status_code,denied.json()['code'])==(404,'NOT_FOUND')
    assert owned.status_code==200 and owned.json()['data']['items'][0]['id']==str(case[4].message_id)
    assert snapshot(case[1],case[4])==before

def test_retained_history_delivery_and_paid_and_reconciliation_gates_off_preserve_read_access(reconciliation_case,monkeypatch):
    case=reconciliation_case;before=snapshot(case[1],case[4])
    for key in ['BUYEROS_DELIVERY_ADMISSION_ENABLED','BUYEROS_PAID_ADMISSION_ENABLED','BUYEROS_RECONCILIATION_ENABLED']:
        monkeypatch.setenv(key,'false')
    get_settings.cache_clear()
    try:assert read(case)['items'][0]['state']=='unknown' and snapshot(case[1],case[4])==before
    finally:get_settings.cache_clear()

def test_retained_history_global_read_kill_switch_still_returns503(reconciliation_case,monkeypatch):
    case=reconciliation_case;before=snapshot(case[1],case[4]);monkeypatch.setenv('BUYEROS_LIVE_READ_ENABLED','false');get_settings.cache_clear()
    try:
        reply=case[0].get(url(case),headers=_h(REVIEWER))
        assert (reply.status_code,reply.json()['code'])==(503,'READ_DISABLED')
        assert snapshot(case[1],case[4])==before
    finally:get_settings.cache_clear()

@pytest.mark.parametrize('query',['offset=-1','limit=0','limit=101','limit=nope'])
def test_retained_history_bounds_are422_without_modifying_original(reconciliation_case,query):
    case=reconciliation_case;before=snapshot(case[1],case[4]);reply=case[0].get(url(case)+'?'+query,headers=_h(REVIEWER))
    assert (reply.status_code,reply.json()['code'])==(422,'INVALID_REQUEST')
    assert snapshot(case[1],case[4])==before

def test_retained_history_bounded_page_retains_exact_total_and_empty_offset(reconciliation_case):
    case=reconciliation_case;before=snapshot(case[1],case[4])
    pages=[case[0].get(url(case)+f'?offset={offset}&limit=1',headers=_h(REVIEWER)) for offset in [0,1]]
    for reply in pages:
        assert reply.status_code==200,reply.text
        assert_contract_response('DeliveryMessagePageResponse',reply.json())
    first,empty=[x.json()['data'] for x in pages]
    assert first['total']==empty['total']==1 and first['limit']==empty['limit']==1
    assert len(first['items'])==1 and empty['items']==[] and empty['offset']==1
    assert snapshot(case[1],case[4])==before

def test_retained_history_prior_approved_revision_survives_new_dirty_revision(reconciliation_case):
    case=reconciliation_case;before=snapshot(case[1],case[4]);path=f"/v1/workspaces/{WORKSPACE_A}/drafts/{case[2]['draft_id']}"
    original=case[0].get(path,headers=_h(OPERATOR));assert original.status_code==200,original.text
    draft=original.json()['data'];version=draft['version'];revision=draft['revision_number']
    edited=case[0].patch(path,json={'body':draft['body']+' Human follow-up edit.'},headers=_h(OPERATOR,key='history-new-draft-revision',**{'If-Match':f'"{version}"'}))
    assert edited.status_code==200,edited.text
    assert edited.json()['data']['revision_number']==revision+1
    row=read(case)['items'][0]
    assert row['revision_number']==revision and row['draft_revision_id']==str(case[2]['draft_revision_id'])
    assert row['approval_id']==str(case[2]['approval_id']) and row['state']=='unknown'
    assert snapshot(case[1],case[4])==before
