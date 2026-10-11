"""Current native entity context is never a factual requirement/model citation."""
import pytest
from tests.test_live_model_adapter import fixture_basis,proposal,route
from buyeros_api.providers.live_model import ModelRequest,validate_live_proposal
from buyeros_api.services.fit import InventedEvidence

def native_context():
    value=fixture_basis();value['evidence'][0].update(requirement_id=None,stance='qualifies',is_inference=True,source_kind='research_page_excerpt')
    return value

def test_native_entity_context_can_prepare_but_cannot_prove_a_requirement():
    basis=native_context();request=ModelRequest('native-model-context',basis,route(),'local-owned-model-v1','US','en','company')
    value=proposal(basis);value.update(verdict='needs_review',citations=[])
    checked=validate_live_proposal(value,request.basis)
    assert checked['verdict']=='needs_review' and checked['evidence_ids']==[] and checked['supported_requirement_ids']==[] and checked['unknown_requirement_ids']==['sensors']
    assert request.basis['evidence'][0]['is_inference'] is True and request.basis['evidence'][0]['requirement_id'] is None

@pytest.mark.parametrize('mutation',['factual','supports','non-native','non-current'])
def test_only_current_inferred_native_entity_qualification_is_unassigned_context(mutation):
    basis=native_context();item=basis['evidence'][0]
    if mutation=='factual':item['is_inference']=False
    elif mutation=='supports':item['stance']='supports'
    elif mutation=='non-native':item['source_kind']='search_metadata'
    else:item['current']=False
    with pytest.raises((ValueError,InventedEvidence)):ModelRequest('native-model-context',basis,route(),'local-owned-model-v1','US','en','company')

def test_native_entity_context_remains_ineligible_for_factual_model_citation():
    basis=native_context();value=proposal(basis)
    with pytest.raises((ValueError,InventedEvidence)):validate_live_proposal(value,basis)
