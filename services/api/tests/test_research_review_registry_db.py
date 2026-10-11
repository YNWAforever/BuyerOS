"""Public review consumes actual current pure selector; owned licensed page only."""
from dataclasses import replace
import psycopg,pytest
from buyeros_api.api.routes.runs import selected_run_capability
from buyeros_api.providers import registry
from buyeros_api.providers.registry import ProviderRegistry
from tests.test_research_candidate_review_db import review_case,page_case,run_case,project_api,admission_case,migrated
from tests.test_research_candidate_api_db import post,context
from tests.contract_validation import assert_contract_response

@pytest.fixture
def selected_review_case(review_case,monkeypatch):
    c=review_case;calls=[]
    item=registry.DEFAULT_REGISTRY.registration('search')
    def forbidden_factory():
        calls.append('factory');raise AssertionError('manual review must not construct a provider')
    monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry((replace(item,factory=forbidden_factory),)))
    old=c['api'].app.dependency_overrides.pop(selected_run_capability,None)
    try:yield {**c,'factory_calls':calls,'registration':item}
    finally:
        if old is not None:c['api'].app.dependency_overrides[selected_run_capability]=old
        else:c['api'].app.dependency_overrides.pop(selected_run_capability,None)

@pytest.mark.parametrize('port',['context','review'])
def test_actual_selected_review_uses_current_typed_registration_without_provider_factory(selected_review_case,port):
    c=selected_review_case
    assert selected_run_capability()[1]=='production'
    reply=context(c) if port=='context' else post(c)
    assert reply.status_code==200,reply.text
    assert_contract_response('ResearchCandidateReviewContextResponse' if port=='context' else 'ResearchCandidateReviewResponse',reply.json())
    if port=='review':
        assert post(c).json()['data']==reply.json()['data']
    assert c['factory_calls']==[] and c['transport'].calls==1
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT count(*) FROM company_aliases WHERE raw_candidate_id=%s',(c['raw'],)).fetchone()==((0 if port=='context' else 1),)
        assert db.execute('SELECT count(*) FROM fit_assessments WHERE run_id=%s',(c['run'],)).fetchone()==(0,)
        assert db.execute('SELECT count(*) FROM model_receipts WHERE workspace_id=%s',(c['workspace'],)).fetchone()==(0,)

@pytest.mark.parametrize('gate',['registry-empty','stale-planning','forged-planning','extra-planning','direct-production-capability','invalid-environment'])
def test_public_review_blocks_unbound_or_changed_registry_scope_without_writes(selected_review_case,monkeypatch,gate):
    c=selected_review_case;planning,environment=selected_run_capability()
    if gate=='registry-empty':monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry(()))
    else:
        if gate=='stale-planning':monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry((replace(c['registration'],sandbox_evidence=('synthetic:changed-review',)),)))
        elif gate=='forged-planning':planning={**planning,'price_version':'forged-price'}
        elif gate=='extra-planning':planning={**planning,'extra_authority':True}
        elif gate=='direct-production-capability':planning=c['cap']
        elif gate=='invalid-environment':environment='preview'
        c['api'].app.dependency_overrides[selected_run_capability]=lambda:(planning,environment)
    for reply in [context(c),post(c)]:
        assert reply.status_code==503,reply.text
        assert_contract_response('ApiError',reply.json())
    assert c['factory_calls']==[] and c['transport'].calls==1
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT count(*) FROM company_aliases WHERE raw_candidate_id=%s',(c['raw'],)).fetchone()==(0,)
        assert db.execute('SELECT count(*) FROM model_receipts WHERE workspace_id=%s',(c['workspace'],)).fetchone()==(0,)
