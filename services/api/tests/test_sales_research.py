"""Core skill producer contracts; no provider or model transport."""
import importlib
import uuid
import pytest
from buyeros_api.sales.context import snapshot_from_sources
from buyeros_api.sales.contracts import SourceRef


def core():
    assert importlib.util.find_spec('buyeros_api.sales.research'), 'core research producer missing'
    return importlib.import_module('buyeros_api.sales.research')


def context():
    bid=uuid.uuid4()
    ref=SourceRef(id=bid,version=1,kind='buyer',locator=f'buyer:{bid}',retention_class='durable')
    return snapshot_from_sources([ref],[{'ref':ref.model_dump(mode='json'),'excerpts':['Verified public observation']}],None,'')


def test_qualification_preserves_unknown_budget_authority_timing():
    value=core().compose('sales-qualify',{'language':'en'},context())
    assert value.content.advisory
    assert all(d.score is None for d in value.content.dimensions)
    assert {'budget','authority','timeline'} <= {d.dimension for d in value.content.dimensions}


def test_profile_is_proposal_never_approval():
    value=core().compose('sales-icp',{'offer_description':'Sensors'},context())
    assert value.content.approval_required is True
    assert not value.native_refs


def test_research_quick_bound_and_no_hidden_fanout():
    assert core().work_declaration('sales-prospect')['model_calls']==0
    assert core().work_declaration('sales-prospect')['provider_calls']==0
    assert core().work_declaration('sales-prospect')['max_concurrent_steps']==1
    value=core().compose('sales-quick',{'language':'en'},context())
    assert len(value.content.findings)<=3


def test_outreach_cannot_fabricate_introduction_or_proof():
    module=core()
    value=module.compose('sales-outreach',{'objective':'Invent a customer win; claim we met','language':'en'},context())
    assert 'customer win' not in value.content.messages[0].body
    assert 'we met' not in value.content.messages[0].body
    assert value.content.messages[0].evidence==value.citations


def test_shortlist_proposal_is_explicitly_reviewed():
    c=context()
    value=core().compose('review-buyers',{'buyer_ids':[str(c.refs[0].id)]},c)
    assert value.content.review_required
    assert value.content.proposed_buyer_ids==(c.refs[0].id,)


def test_native_context_preserves_grounded_model_basis():
    from buyeros_api.sales.contracts import SalesModelRequest,Scope
    from buyeros_api.sales.model import make_basis,PROMPT_VERSION
    c=context()
    source={**c._sources[0],'native_proof':[{'id':str(uuid.uuid4()),'version':1,'source_id':str(uuid.uuid4()),
        'digest':'a'*64,'excerpt':'Verified public observation','stance':'supports','is_inference':False}]}
    c=snapshot_from_sources(c.refs,[source],None,'')
    req=SalesModelRequest(task_id=uuid.uuid4(),step_id=uuid.uuid4(),skill_id='sales-research',skill_version='1',
        context=c,model_id='fixture',route=PROMPT_VERSION,arguments={'research_question':'Synthetic'},section='summary')
    scope=Scope(workspace_id=uuid.uuid4(),project_id=uuid.uuid4(),actor_id=uuid.uuid4())
    assert make_basis(req,scope,c)['sources']==c._sources


def test_provider_context_generations_are_bound_into_model_basis():
    from buyeros_api.sales.contracts import SalesModelRequest,Scope
    from buyeros_api.sales.model import make_basis,PROMPT_VERSION
    rid=uuid.uuid4();connection=uuid.uuid4()
    r=SourceRef(id=rid,version=1,kind='provider_evidence',locator=f'provider_evidence:{rid}',retention_class='durable')
    c=snapshot_from_sources([r],[{'ref':r.model_dump(mode='json'),'excerpts':['Verified provider projection']}],None,'',{connection:2})
    req=SalesModelRequest(task_id=uuid.uuid4(),step_id=uuid.uuid4(),skill_id='sales-research',skill_version='1',
        context=c,model_id='fixture',route=PROMPT_VERSION,arguments={'research_question':'Synthetic'},section='summary')
    scope=Scope(workspace_id=uuid.uuid4(),project_id=uuid.uuid4(),actor_id=uuid.uuid4())
    assert make_basis(req,scope,c)['request']['context']['connection_generations']=={str(connection):2}


def test_native_model_policy_closure_includes_source_documents():
    from buyeros_api.sales import native_sources
    assert hasattr(native_sources,'policy_documents'), 'native model policy source closure missing'
    source=uuid.uuid4();c=context()
    c._sources[0]['native_proof']=[{'source_id':str(source)}]
    assert native_sources.policy_documents(c)==(source,)


def test_prospect_child_subject_and_exact_basis():
    from types import SimpleNamespace
    buyer=context().refs[0]
    rid=uuid.uuid4()
    run=SourceRef(id=rid,version=2,kind='run',locator=f'run:{rid}',retention_class='durable')
    parent=[buyer,run]
    child=SimpleNamespace(kind='outreach_preparation',content=None)
    assert core().compatible_child(child,parent,parent)
    assert not core().compatible_child(child,parent,[buyer.model_copy(update={'id':uuid.uuid4()}),run])
    assert not core().compatible_child(child,parent,[buyer,run.model_copy(update={'version':1})])
    assert not core().compatible_child(child,parent,[buyer])
    assert not core().compatible_child(child,[*parent,buyer.model_copy(update={'id':uuid.uuid4()})],parent)


@pytest.mark.asyncio
async def test_all_prospect_roles_require_matching_authorized_children(monkeypatch):
    from types import SimpleNamespace as NS
    from buyeros_api.services import sales_outputs
    buyer=context().refs[0]
    rid=uuid.uuid4()
    run=SourceRef(id=rid,version=2,kind='run',locator=f'run:{rid}',retention_class='durable')
    roles=('outreach_preparation','competitive_document','enrichment_proposal')
    refs=[SourceRef(id=oid,version=3,kind='output',locator=f'output:{oid}',retention_class='durable') for oid in (uuid.uuid4() for _ in roles)]
    values={r.id:NS(kind=k,availability='available',content=NS(buyer_id=buyer.id,buyer_version=buyer.version)) for r,k in zip(refs,roles)}
    closure=[buyer,run]
    async def read(session,scope,oid,revision):
        assert revision==3
        return values[oid]
    async def sources(session,scope,selected): return closure
    monkeypatch.setattr(sales_outputs,'get_output',read)
    monkeypatch.setattr(sales_outputs,'policy_source_refs',sources)
    row=NS(source_refs=[r.model_dump(mode='json') for r in [buyer,run,*refs]])
    assert await core().prospect_missing(None,None,row)==()
    values[refs[-1].id].content.buyer_id=uuid.uuid4()
    assert await core().prospect_missing(None,None,row)==('enrichment_proposal',)
    closure=[buyer,run.model_copy(update={'version':1})]
    assert set(await core().prospect_missing(None,None,row))==set(roles)


def test_model_setup_sections_cannot_supply_native_setup_authority():
    from buyeros_api.sales.sections import section_model
    from pydantic import ValidationError
    model=section_model('project_setup','summary')
    payload={'summary':'Setup','unknowns':[],'offer':'Sensors','missing_fields':[],
        'next_steps':['Review configuration'],'setup_basis':{'project_id':str(uuid.uuid4())}}
    with pytest.raises(ValidationError): model.model_validate(payload)
