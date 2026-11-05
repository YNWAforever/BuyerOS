"""Synthetic real HTTP serialization, never a live provider call."""
import asyncio
import hashlib
import json
import uuid
from dataclasses import replace
from copy import deepcopy
import httpx
import pytest
from buyeros_api.providers.live_model import canonical_json, ModelResponseUnknown
from buyeros_api.providers.opencode_model import OpenCodeGoModelClient
from buyeros_api.sales.contracts import ContextSnapshot, SourceRef
from tests.test_sales_context import UID


def sample():
    from buyeros_api.sales.model import make_basis
    from buyeros_api.sales.context import snapshot_from_sources
    from buyeros_api.sales.contracts import SalesModelRequest, Scope
    ref = SourceRef(id=UID,version=1,kind='document',locator='document:'+str(UID),retention_class='durable')
    context = snapshot_from_sources([ref], [{'ref':ref.model_dump(mode='json'),'excerpts':['SYNTHETIC selected evidence']}], 1, 'a'*64)
    request = SalesModelRequest(task_id=UID,step_id=UID,skill_id='sales-quick',skill_version='1',context=context,
        model_id='synthetic-model',route='sales-grounded.v1',arguments={'research_question':'Synthetic question'})
    basis = make_basis(request, Scope(workspace_id=UID,project_id=UID,actor_id=UID),context)
    proposal = {'kind':'research_report','content':{'summary':'Review selected evidence','unknowns':[],
        'findings':[], 'opportunities':[], 'concerns':[]},'citations':[ref.model_dump(mode='json')],
        'dependencies':[], 'native_refs':[]}
    return basis, proposal, context

@pytest.mark.parametrize('mutation', ['authority','tool','citation','oversize','native','dependency'])
def test_strict_sales_proposals(mutation):
    from buyeros_api.sales.model import validate_sales_proposal
    from buyeros_api.sales.registry import load_skill
    basis, proposal, context = sample()
    if mutation == 'authority': proposal['approved'] = True
    if mutation == 'tool': proposal['tool_calls'] = [{'name':'send'}]
    if mutation == 'citation': proposal['citations'][0]['version'] = 2
    if mutation == 'oversize': proposal['content']['summary'] = 'x'*4001
    if mutation == 'native': proposal['native_refs'] = [{'surface':'buyer','id':str(UID),'revision':1}]
    if mutation == 'dependency': proposal['dependencies'] = [{'id':str(UID),'revision':1}]
    with pytest.raises(ValueError): validate_sales_proposal(proposal, context, load_skill('sales-quick','1'))

@pytest.mark.parametrize('bad', [None,'invalid-json','tool','wrong-model','over-tokens'])
def test_sales_actual_transport_serialization(bad):
    from buyeros_api.sales.model import ROUTE
    basis, proposal, _ = sample()
    proposal = summary_child(proposal)
    calls = []
    def transport(request):
        calls.append(request)
        payload = json.loads(request.content)
        assert payload['tools'] == [] and payload['tool_choice'] == 'none' and payload['parallel_tool_calls'] is False
        assert payload['max_tokens'] == 1000 and payload['stream'] is False
        assert 'SYNTHETIC selected evidence' not in payload['messages'][0]['content']
        assert 'SYNTHETIC selected evidence' in payload['messages'][1]['content']
        assert 'sales' in payload['messages'][0]['content']
        assert request.extensions['timeout']['read'] == 30
        message = {'role':'assistant','content':'invalid' if bad=='invalid-json' else json.dumps(proposal)}
        if bad=='tool': message['tool_calls'] = [{'function':{'name':'send'}}]
        return httpx.Response(200,json={'id':'synthetic-receipt','model':'other' if bad=='wrong-model' else 'synthetic-model',
            'choices':[{'finish_reason':'stop','message':message}],
            'usage':{'prompt_tokens':6001 if bad=='over-tokens' else 500,'completion_tokens':100}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            client = OpenCodeGoModelClient(api_key='synthetic-not-real',http=http,model_id='synthetic-model')
            if bad:
                with pytest.raises(ModelResponseUnknown): await client.complete(basis,replace(ROUTE,route_id='sales-grounded.v1'))
            else:
                result = await client.complete(basis,replace(ROUTE,route_id='sales-grounded.v1'))
                assert result['assessment'] == proposal
    asyncio.run(run())
    assert len(calls) == 1

def test_default_sales_and_conversation_registrations_remain_unselected():
    from buyeros_api.sales import model
    from buyeros_api.services import conversation_admission
    assert model.REGISTRATION is None and model.ROUTE.route_id is None
    assert conversation_admission.REGISTRATION is None
    assert conversation_admission.selected_configuration('US','en') is None


def test_sales_transport_rejects_expanded_route_before_http():
    from buyeros_api.sales.model import ROUTE
    basis,_,_=sample()
    async def run():
        def forbidden(request): pytest.fail('oversized admission reached HTTP')
        async with httpx.AsyncClient(transport=httpx.MockTransport(forbidden)) as http:
            client=OpenCodeGoModelClient(api_key='synthetic-not-real',http=http,model_id='synthetic-model')
            with pytest.raises(ValueError):
                await client.complete(basis,replace(ROUTE,route_id='sales-grounded.v1',repair_limit=1))
    asyncio.run(run())


def test_nested_native_identity_cannot_be_invented():
    from buyeros_api.sales.model import validate_sales_proposal
    from buyeros_api.sales.registry import load_skill
    from buyeros_api.sales.context import empty_context
    proposal={'kind':'pipeline_report','content':{'summary':'Synthetic','unknowns':[],
        'as_of':'2026-11-05T00:00:00Z','scope':[str(UID)],'rows':[{'buyer':{'surface':'buyer','id':str(UID),'revision':1},
        'stage':None,'advisory_score':None,'value':None,'next_action':None}],
        'unavailable_buyer_ids':[],'methodology':'Synthetic'},'citations':[],'dependencies':[],'native_refs':[]}
    with pytest.raises(ValueError): validate_sales_proposal(proposal,empty_context(),load_skill('sales-report','1'))


def test_model_client_rechecks_task_selection_before_transport(monkeypatch):
    from types import SimpleNamespace
    from buyeros_api.sales import model
    from buyeros_api.sales.contracts import SalesModelRequest, Scope
    from buyeros_api.services import sales_tasks
    basis,_,context=sample()
    request=SalesModelRequest.model_validate(basis['request'])
    async def task_row(*args, **kwargs):
        return SimpleNamespace(skill_id=request.skill_id,skill_version=request.skill_version,
            arguments=request.arguments,source_refs=[],state='ready_for_review',context_digest=context.digest)
    monkeypatch.setattr(sales_tasks,'task_row',task_row)
    async def forbidden(*args): pytest.fail('changed selection reached source fetch')
    monkeypatch.setattr(model,'resolve_context',forbidden)
    with pytest.raises(ValueError):
        asyncio.run(model.SalesModelClient(object(),Scope.model_validate(basis['scope'])).complete(request))

def test_model_arguments_cannot_smuggle_restricted_source():
    from buyeros_api.sales.contracts import SalesModelRequest
    basis,_,_=sample()
    value=deepcopy(basis['request'])
    value.update(skill_id='sales-followup',arguments={'buyer_id':str(UID),'profile_id':str(UID),
        'objective':'Synthetic','scenario':'post_meeting','interaction_ref':{
            'id':str(UID),'version':1,'kind':'drive','locator':'drive:synthetic','retention_class':'zero_content'}})
    with pytest.raises(ValueError): SalesModelRequest.model_validate(value)


def test_sales_response_transport_cannot_expand_route():
    from buyeros_api.sales.model import ROUTE
    from buyeros_api.providers.live_model import ResponsesModelClient
    basis,_,_=sample()
    async def run():
        def forbidden(request): pytest.fail('unbounded sales route reached HTTP')
        async with httpx.AsyncClient(transport=httpx.MockTransport(forbidden)) as http:
            client=ResponsesModelClient(api_key='synthetic-not-real',http=http,model_id='synthetic-model',token_counter=lambda payload:100)
            with pytest.raises(ValueError):
                await client.complete(basis,replace(ROUTE,route_id='sales-grounded.v1',max_output_tokens=2000))
    asyncio.run(run())


def test_model_client_default_unavailable_and_synthetic_usage_receipt(monkeypatch):
    from types import SimpleNamespace
    from buyeros_api.sales import model
    from buyeros_api.sales.contracts import SalesModelRequest, Scope
    from buyeros_api.services import sales_tasks
    from buyeros_api.providers.model_receipts import sales_usage_receipt
    from buyeros_api.api.errors import ApiError
    basis,proposal,context=sample()
    proposal=summary_child(proposal)
    request=SalesModelRequest.model_validate(basis['request'])
    scope=Scope.model_validate(basis['scope'])
    async def task_row(*args, **kwargs):
        return SimpleNamespace(skill_id=request.skill_id,skill_version=request.skill_version,arguments=request.arguments,
            source_refs=[ref.model_dump(mode='json') for ref in context.refs],state='ready_for_review',context_digest=context.digest)
    async def resolve(*args): return context
    monkeypatch.setattr(sales_tasks,'task_row',task_row)
    monkeypatch.setattr(model,'resolve_context',resolve)
    calls=[]
    def transport(req):
        calls.append(req)
        return httpx.Response(200,json={'id':'synthetic-receipt','model':request.model_id,
            'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(proposal)}}],
            'usage':{'prompt_tokens':500,'completion_tokens':100}})
    async def run():
        with pytest.raises(ApiError) as unavailable: await model.SalesModelClient(object(),scope).complete(request)
        assert unavailable.value.code=='SALES_MODEL_UNAVAILABLE'
        assert calls==[]
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            client=OpenCodeGoModelClient(api_key='synthetic-not-real',http=http,model_id=request.model_id)
            result=await model.SalesModelClient(object(),scope,fixture_transport=client).complete(request)
        receipt=sales_usage_receipt(result,request)
        assert receipt['usage']=={'input_tokens':500,'output_tokens':100,'cost':None}
        assert 'SYNTHETIC selected evidence' not in json.dumps(receipt) and 'content' not in receipt
        assert len(calls)==1
    asyncio.run(run())

def test_typed_action_is_only_an_allowlisted_untrusted_proposal():
    from buyeros_api.sales.model import validate_sales_proposal
    from buyeros_api.sales.registry import load_skill
    basis,_,context=sample()
    skill=load_skill('sales-quick','1')
    action={'id':str(UID),'capability':'research.read','arguments':{'refs':[],'purpose':'Synthetic review'},
        'source_versions':[ref.model_dump(mode='json') for ref in context.refs]}
    assert validate_sales_proposal(action,context,skill).capability=='research.read'
    for mutation in ({'approved':True},{'capability':'get_email_xverum'},
        {'arguments':{'refs':[],'purpose':'Synthetic','actor_id':str(UID)}}):
        with pytest.raises(ValueError): validate_sales_proposal({**action,**mutation},context,skill)

def test_section_selection_is_explicit_code_owned_and_serialized():
    from buyeros_api.sales.model import make_basis, prompt_schema
    from buyeros_api.sales.contracts import SalesModelRequest, Scope
    basis,_,context=sample()
    data={**basis['request'],'section':'findings'}
    request=SalesModelRequest.model_validate(data)
    selected=make_basis(request,Scope.model_validate(basis['scope']),context)
    assert selected['request']['section']=='findings'
    assert 'Current section: findings' in prompt_schema(selected)[0]
    with pytest.raises(ValueError):
        make_basis(request.model_copy(update={'section':'send_emails'}),Scope.model_validate(basis['scope']),context)

@pytest.mark.parametrize('section', ['problem','solution','terms','proof_points','followup'])
def test_r1_proposal_sections_use_bounded_shapes_and_reach_transport(section):
    from buyeros_api.sales.model import make_basis, ROUTE, validate_proposal
    from buyeros_api.sales.contracts import SalesModelRequest, Scope, OutputCandidate
    from tests.test_sales_registry import valid_cases, SOURCE
    basis,_,context=sample()
    args,kind,content=valid_cases()['sales-proposal']
    ref=context.refs[0].model_dump(mode='json')
    args=json.loads(json.dumps(args).replace(json.dumps(SOURCE),json.dumps(ref)))
    content=json.loads(json.dumps(content).replace(json.dumps(SOURCE),json.dumps(ref)))
    fields={'problem':['summary','unknowns','problem','assumptions'],'solution':['solution'],
        'terms':['terms'],'proof_points':['proof_points'],'followup':['followup']}[section]
    child={'kind':kind,'section':section,'content':{key:content[key] for key in fields},'citations':[ref],'complete':False}
    request=SalesModelRequest.model_validate({**basis['request'],'skill_id':'sales-proposal','arguments':args,'section':section})
    selected=make_basis(request,Scope.model_validate(basis['scope']),context)
    calls=[]
    def transport(req):
        calls.append(req)
        assert len(req.content)<=6000
        payload=json.loads(req.content)
        assert payload['max_tokens']==1000 and payload['tools']==[]
        assert req.extensions['timeout']['read']==30
        return httpx.Response(200,json={'id':'synthetic-section','model':request.model_id,
            'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(child)}}],
            'usage':{'prompt_tokens':len(req.content),'completion_tokens':100}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            client=OpenCodeGoModelClient(api_key='synthetic-only',http=http,model_id=request.model_id)
            result=await client.complete(selected,replace(ROUTE,route_id=request.route))
            assert result['assessment']==child
    asyncio.run(run())
    assert len(calls)==1
    for bad in ({**child,'complete':True},{**child,'section':'summary'},
        {**child,'content':{**child['content'],'send_now':True}}):
        with pytest.raises(ValueError): validate_proposal(bad,selected)
    with pytest.raises(ValueError): OutputCandidate.model_validate(child)


@pytest.mark.parametrize('skill_id', ['understand-documents','sales-contacts','sales-report','review-buyers'])
def test_r2_scalar_and_list_native_identities_fail_closed(skill_id):
    from tests.test_sales_registry import valid_cases
    from buyeros_api.sales.context import empty_context
    from buyeros_api.sales.registry import load_skill
    from buyeros_api.sales.model import validate_sales_proposal
    _,kind,content=valid_cases()[skill_id]
    # Empty evidence leaves identity assertions independently schema-valid.
    if skill_id=='understand-documents': content={**content,'findings':[]}
    if skill_id=='sales-contacts': content={**content,'source_refs':[]}
    if skill_id=='review-buyers': content={**content,'assessments':[]}
    candidate={'kind':kind,'content':content,'citations':[],'dependencies':[],'native_refs':[]}
    with pytest.raises(ValueError): validate_sales_proposal(candidate,empty_context(),load_skill(skill_id,'1'))



def summary_child(proposal):
    return {'kind':'research_report','section':'summary','complete':False,
        'content':{key:proposal['content'][key] for key in ('summary','unknowns','opportunities','concerns')},
        'citations':proposal['citations']}


SUPPORTED_SECTIONS = [
    ('sales-quick','summary'),('sales-quick','findings'),
    ('sales-qualify','summary'),('sales-outreach','summary'),('sales-outreach','messages'),
    ('sales-followup','summary'),('sales-followup','messages'),
    ('sales-prep','cheat_sheet'),('sales-prep','agenda'),('sales-prep','next_steps'),
    ('sales-objections','summary'),('sales-objections','responses'),
    ('sales-icp','summary'),('sales-competitors','summary'),('first-project','summary'),
]


@pytest.mark.parametrize('skill_id,section',SUPPORTED_SECTIONS)
def test_r1_other_supported_child_shapes_reach_bounded_transport(skill_id,section):
    from buyeros_api.sales.model import make_basis, ROUTE, validate_proposal
    from buyeros_api.sales.contracts import SalesModelRequest, Scope
    from buyeros_api.sales.sections import section_groups
    from tests.test_sales_registry import valid_cases, SOURCE
    basis,_,context=sample()
    args,kind,content=valid_cases()[skill_id]
    ref=context.refs[0].model_dump(mode='json')
    args=json.loads(json.dumps(args).replace(json.dumps(SOURCE),json.dumps(ref)))
    content=json.loads(json.dumps(content).replace(json.dumps(SOURCE),json.dumps(ref)))
    child={'kind':kind,'section':section,'complete':False,'citations':[ref],
        'content':{key:content[key] for key in section_groups(kind)[section]}}
    request=SalesModelRequest.model_validate({**basis['request'],'skill_id':skill_id,'section':section,'arguments':args})
    selected=make_basis(request,Scope.model_validate(basis['scope']),context)
    calls=[]
    def transport(req):
        calls.append(req)
        assert len(req.content)<=6000
        return httpx.Response(200,json={'id':'synthetic-child','model':request.model_id,
            'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(child)}}],
            'usage':{'prompt_tokens':len(req.content),'completion_tokens':100}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            result=await OpenCodeGoModelClient(api_key='synthetic-only',http=http,model_id=request.model_id).complete(
                selected,replace(ROUTE,route_id=request.route))
            assert result['assessment']==child
    asyncio.run(run())
    assert len(calls)==1
    with pytest.raises(ValueError): validate_proposal({**child,'content':{**child['content'],'unexpected':True}},selected)


def test_r1_child_projection_excludes_unrelated_arguments_and_keeps_full_validation():
    from buyeros_api.sales.model import make_basis, wire_basis
    from buyeros_api.sales.contracts import SalesModelRequest, Scope
    from tests.test_sales_registry import valid_cases, SOURCE
    basis,_,context=sample()
    args,_,_=valid_cases()['sales-proposal']
    args=json.loads(json.dumps(args).replace(json.dumps(SOURCE),json.dumps(context.refs[0].model_dump(mode='json'))))
    args['pain_points']=['PRIVATE_UNRELATED_PAIN']
    request=SalesModelRequest.model_validate({**basis['request'],'skill_id':'sales-proposal','section':'terms','arguments':args})
    selected=make_basis(request,Scope.model_validate(basis['scope']),context)
    wire=wire_basis(selected)
    assert 'pain_points' not in wire['arguments'] and 'PRIVATE_UNRELATED_PAIN' not in json.dumps(wire)
    assert wire['arguments']['terms']==args['terms']
    with pytest.raises(ValueError):
        make_basis(request.model_copy(update={'arguments':{'terms':args['terms']}}),Scope.model_validate(basis['scope']),context)


def test_r1_oversized_single_section_fails_without_transport_or_truncation():
    from buyeros_api.sales.model import make_basis, ROUTE, wire_basis
    from buyeros_api.sales.contracts import SalesModelRequest, Scope
    basis,_,context=sample()
    request=SalesModelRequest.model_validate({**basis['request'],'skill_id':'first-project',
        'arguments':{'offer_description':'漢'*4000}})
    selected=make_basis(request,Scope.model_validate(basis['scope']),context)
    assert wire_basis(selected)['arguments']['offer_description']=='漢'*4000
    async def run():
        def forbidden(req): pytest.fail('oversized child reached transport')
        async with httpx.AsyncClient(transport=httpx.MockTransport(forbidden)) as http:
            client=OpenCodeGoModelClient(api_key='synthetic-only',http=http,model_id=request.model_id)
            with pytest.raises(ValueError,match='budget'):
                await client.complete(selected,replace(ROUTE,route_id=request.route))
    asyncio.run(run())
