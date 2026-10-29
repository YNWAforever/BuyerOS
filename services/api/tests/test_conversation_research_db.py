"""Chat research confirmations use the existing startRun admission, never a fork."""
import psycopg
import pytest
from buyeros_api.api.routes.runs import selected_run_capability
from buyeros_api.settings import get_settings
from tests.test_run_admission_integration_db import admission_case, project_api, _request, _post, _count, CAPABILITY
from tests.test_buyer_review_db import WORKSPACE_A, PROJECT_A, VIEWER, _h


def test_research_proposal_reads_do_not_start_and_confirmation_replays_one_queued_intent(admission_case, monkeypatch):
    client,dsn=admission_case
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME','true')
    root=f'/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}'
    assert client.get(root,headers=_h()).status_code==200
    assert client.get(root+'/icp-versions',headers=_h()).status_code==200
    assert _count(dsn,'search_runs')==_count(dsn,'outbox_events')==0
    body=_request();body['limits'].update(max_duration_seconds=300,provider_concurrency=1)
    first=_post(client,key='conversation-confirm',body=body)
    assert first.status_code==202,first.text
    assert _post(client,key='conversation-confirm',body=body).json()['data']['id']==first.json()['data']['id']
    assert _count(dsn,'search_runs')==_count(dsn,'outbox_events')==1
    with psycopg.connect(dsn) as db:
        limits=db.execute('SELECT limits FROM search_runs WHERE id=%s',(first.json()['data']['id'],)).fetchone()[0]
        assert limits['max_duration_seconds']==300 and limits['provider_concurrency']==1


@pytest.mark.parametrize('gate',['missing-key','admission-off','provider','policy','budget','stale','forbidden'])
def test_chat_confirmation_inherits_all_run_gate_errors_without_inserting_work(admission_case,monkeypatch,gate):
    client,dsn=admission_case
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME','true')
    headers=_h(key='conversation-gate');body=_request();expected=409
    if gate=='missing-key':headers.pop('Idempotency-Key',None);expected=400
    elif gate=='admission-off':
        monkeypatch.setenv('BUYEROS_PAID_ADMISSION_ENABLED','false');get_settings.cache_clear()
        client.app.dependency_overrides[selected_run_capability]=lambda:(None,'production');expected=503
    elif gate=='provider':
        monkeypatch.setenv('BUYEROS_PAID_ADMISSION_ENABLED','true');get_settings.cache_clear()
        client.app.dependency_overrides[selected_run_capability]=lambda:(None,'production');expected=503
    elif gate=='forbidden':
        with psycopg.connect(dsn) as db:db.execute("UPDATE memberships SET roles=ARRAY['viewer'] WHERE user_id=(SELECT id FROM users WHERE subject=%s)",('auth0|operator-a',))
        expected=403
    else:
        with psycopg.connect(dsn) as db:
            if gate=='policy':db.execute('DELETE FROM policy_activation_resolutions WHERE workspace_id=%s',(WORKSPACE_A,))
            elif gate=='budget':db.execute('UPDATE budget_accounts SET approved_limit=0 WHERE workspace_id=%s',(WORKSPACE_A,))
            else:db.execute('UPDATE projects SET offer_revision=2 WHERE id=%s',(PROJECT_A,));expected=412
    try:
        result=client.post(f'/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/runs',headers=headers,json=body)
        assert result.status_code==expected,result.text
        assert _count(dsn,'search_runs')==_count(dsn,'outbox_events')==0
    finally:get_settings.cache_clear()
