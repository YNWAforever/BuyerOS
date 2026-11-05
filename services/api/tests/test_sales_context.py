"""Synthetic Task4 intake and selected-context tests; no database acceptance."""
import asyncio
import json
import uuid
from types import SimpleNamespace
import pytest
from buyeros_api.sales.contracts import TaskInput, Scope, SourceRef

UID = uuid.UUID('a3000000-0000-4000-8000-000000000001')
SCOPE = Scope(workspace_id=UID, project_id=UID, actor_id=UID)

def test_guided_missing_offer_accepts_intake_but_not_execution():
    from buyeros_api.sales.registry import load_skill, validate_arguments
    from buyeros_api.sales.planning import plan_task
    from buyeros_api.sales.context import empty_context
    task = TaskInput(thread_id=UID, skill_id='first-project', skill_version='1',
        user_message='Help define my offer', arguments={}, source_refs=[])
    plan = plan_task(load_skill(task.skill_id, '1'), task.arguments, empty_context())
    assert plan.missing_inputs == ('offer_description',) and not plan.steps
    with pytest.raises(ValueError):
        validate_arguments(load_skill(task.skill_id, '1'), {})
    ready = plan_task(load_skill(task.skill_id, '1'), {'offer_description':'Synthetic offer'}, empty_context())
    assert not ready.missing_inputs and ready.steps

@pytest.mark.parametrize('arguments', [{'offer_description':None}, {'offer_description':''},
    {'actor_id':str(UID)}, {'offer_description':3}, {'approved':True}])
def test_partial_intake_rejects_invalid_supplied_values(arguments):
    with pytest.raises(ValueError):
        TaskInput(thread_id=UID, skill_id='first-project', skill_version='1',
            user_message='Synthetic', arguments=arguments, source_refs=[])


def test_selected_context_uses_current_authority_and_only_selected_excerpts(monkeypatch):
    from buyeros_api.sales import context
    calls = []
    async def authorize(session, scope): calls.append(('authority', scope))
    async def resolve(session, **kwargs):
        calls.append(kwargs['source_ids'])
        return SimpleNamespace(sources=[{'citation':{'id':'document:'+str(UID)}, 'excerpts':['SELECTED']}],
            profile_id=str(UID), profile_hash='a'*64, offer_revision=2, paid_eligible=True)
    monkeypatch.setattr(context, 'require_scope', authorize)
    monkeypatch.setattr(context, 'resolve_sources', resolve)
    ref = SourceRef(id=UID,version=2,kind='document',locator='document:'+str(UID),retention_class='durable')
    class RetainedSession:
        async def scalar(self, statement, params):
            assert params['ws'] == SCOPE.workspace_id and params['ids'] == [UID]
            return False  # No tombstone or elapsed policy in this unit fixture.
    session = RetainedSession()
    snapshot = asyncio.run(context.resolve_context(session, SCOPE, [ref]))
    assert calls == [('authority', SCOPE), ['document:'+str(UID)]]
    assert 'SELECTED' not in snapshot.model_dump_json()
    assert snapshot._sources[0]['excerpts'] == ['SELECTED']
    with pytest.raises(ValueError):
        asyncio.run(context.resolve_context(session, SCOPE, [ref.model_copy(update={'version':1})]))


def test_mixed_drive_context_rejected_before_source_resolution(monkeypatch):
    from buyeros_api.sales import context
    source_calls = []
    async def forbidden(*args, **kwargs):
        source_calls.append((args, kwargs))
        pytest.fail('restricted selection reached source materialization')
    monkeypatch.setattr(context, 'resolve_sources', forbidden)
    refs = [SourceRef(id=UID, version=1, kind='document',locator='document:'+str(UID),retention_class='durable'),
        SourceRef(id=uuid.uuid4(),version=1,kind='drive',locator='drive:synthetic',retention_class='zero_content')]
    with pytest.raises(ValueError): asyncio.run(context.resolve_context(object(), SCOPE, refs))
    assert source_calls == []  # Source-resolver boundary only; no receipt persistence proof.

def test_actual_approved_source_resolver_excludes_sibling_facts(monkeypatch):
    from buyeros_api.sales import context
    from buyeros_api.services import conversation_reply
    from buyeros_api.db.icp import canonical_hash
    profile_id, selected_id, sibling_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    content={'offer_facts':[
        {'id':str(selected_id),'field':'offer','value':'SELECTED_ONLY','provenance':'user_entered','approved':True},
        {'id':str(sibling_id),'field':'offer','value':'SIBLING_SECRET','provenance':'user_entered','approved':True}],
        'offer_document_ids':[]}
    profile=SimpleNamespace(id=profile_id,approved_at=True,approved_by=UID,superseded_at=None,
        basis_offer_revision=1,content=content,content_hash=canonical_hash(content))
    project=SimpleNamespace(status='active',active_icp_version_id=profile_id,offer_revision=1)
    queries=[]
    class Session:
        async def scalar(self, statement, params):
            assert params['ws'] == SCOPE.workspace_id and params['ids'] == [selected_id]
            return False  # Lifecycle gate has separate real PostgreSQL coverage.
        async def execute(self, statement):
            queries.append(str(statement))
            value=project if len(queries)==1 else profile
            return SimpleNamespace(scalar_one_or_none=lambda:value)
    async def authority(*args): pass
    async def document_check(*args, **kwargs): assert kwargs['document_ids']==[]
    monkeypatch.setattr(context,'require_scope',authority)
    monkeypatch.setattr(conversation_reply,'validate_offer_document_refs',document_check)
    ref=SourceRef(id=selected_id,version=1,kind='project_fact',locator=f'fact:profile:{profile_id}:{selected_id}',retention_class='durable')
    snapshot=asyncio.run(context.resolve_context(Session(),SCOPE,[ref]))
    assert 'SELECTED_ONLY' in json.dumps(snapshot._sources)
    assert 'SIBLING_SECRET' not in json.dumps(snapshot._sources)
    assert len(queries)==2 and all('conversation_thread' not in query for query in queries)


def test_partial_schema_matches_runtime_and_full_execution_stays_required():
    import jsonschema
    from buyeros_api.sales.contracts import contract_schemas, SalesModelRequest
    from buyeros_api.sales.context import empty_context
    schemas=contract_schemas()
    validator=jsonschema.Draft202012Validator({'$ref':'#/components/schemas/TaskInput','components':{'schemas':schemas}})
    data=dict(thread_id=str(UID),skill_id='first-project',skill_version='1',user_message='Synthetic',arguments={},source_refs=[])
    validator.validate(data)
    for arguments in ({'offer_description':None},{'offer_description':3},{'actor_id':str(UID)}):
        assert list(validator.iter_errors({**data,'arguments':arguments}))
    with pytest.raises(ValueError):
        SalesModelRequest(task_id=UID,step_id=UID,skill_id='first-project',skill_version='1',
            context=empty_context(),model_id='synthetic-model',route='sales-grounded.v1',arguments={})

def test_section_plan_respects_smaller_parent_bounds():
    from buyeros_api.sales.planning import plan_task
    from buyeros_api.sales.context import empty_context
    from buyeros_api.sales.registry import load_skill
    skill=load_skill('sales-prospect','1')
    arguments={'buyer_id':str(UID),'objective':'Synthetic','bounds':{'max_model_calls':1}}
    with pytest.raises(ValueError): plan_task(skill,arguments,empty_context())
    plan=plan_task(skill,{**arguments,'bounds':{'max_model_calls':2}},empty_context())
    assert len(plan.steps)==2 and plan.bounds.max_model_calls==2
    assert plan.input_token_budget==12000 and plan.output_token_budget==2000
    assert all(step.max_output_tokens==1000 and step.deadline_seconds==30 for step in plan.steps)
