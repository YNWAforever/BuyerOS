"""Offline service orchestration and transport, not persistence/RLS proof."""
import asyncio
import uuid
from types import SimpleNamespace
from copy import deepcopy
import pytest
from buyeros_api.sales.contracts import Scope
from buyeros_api.api.errors import ApiError
from tests.test_sales_context import UID


def row():
    return SimpleNamespace(id=UID, thread_id=UID,workspace_id=UID,project_id=UID,
        skill_id='first-project',skill_version='1',message_sequence=1, revision=1,
        state='needs_input',context_digest=None,output_ids=[],pending_review=None,
        user_message='Help define offer',arguments={},source_refs=[],
        intake_history=[{'id':str(UID),'revision':1,'user_message':'Help define offer','arguments':{},'source_refs':[]}])


@pytest.mark.parametrize("reuse_create_key", [False, True])
def test_same_task_followup_is_versioned_idempotent_and_reloadable(monkeypatch, reuse_create_key):
    from buyeros_api.sales.contracts import TaskFollowup
    from buyeros_api.services import sales_tasks as service
    current = row()
    if reuse_create_key:
        current.intake_history[0]["id"] = str(uuid.uuid5(UID,"synthetic-followup"))
    events = []
    auth = []
    async def task_row(*args, **kwargs):
        auth.append(kwargs)
        return current
    async def begin(*args, **kwargs): return SimpleNamespace(replay=False)
    async def event(*args): events.append(args)
    class Session:
        async def flush(self): pass
    monkeypatch.setattr(service,'task_row',task_row)
    monkeypatch.setattr(service,'begin_idempotency',begin)
    monkeypatch.setattr(service,'complete_idempotency',lambda *args: None)
    monkeypatch.setattr(service,'append_event',event)
    scope = Scope(workspace_id=UID,project_id=UID,actor_id=UID)
    data = TaskFollowup(user_message='Offer supplied', arguments={'offer_description':'Synthetic offer'})
    async def run():
        result = await service.followup_task(Session(),scope,UID,data,'synthetic-followup',1)
        assert result.id == UID and result.state == 'ready_for_review' and result.revision == 2
        assert result.intake[0].user_message == 'Help define offer'
        assert result.intake[1].user_message == 'Offer supplied' and result.intake[1].revision == 2
        assert result.missing_inputs == ()
        replay = await service.followup_task(Session(),scope,UID,data,'synthetic-followup',1)
        assert replay == result and len(events) == 1
        assert service.detail(current) == result
        with pytest.raises(ApiError) as stale:
            await service.followup_task(Session(),scope,UID,data,'another-followup',1)
        assert stale.value.code == 'STALE_REVISION'
        changed = data.model_copy(update={'user_message':'Changed intent'})
        with pytest.raises(ApiError) as conflict:
            await service.followup_task(Session(),scope,UID,changed,'synthetic-followup',1)
        assert conflict.value.code == 'IDEMPOTENCY_CONFLICT'
    asyncio.run(run())
    assert all(item == {'edit':True} for item in auth)


def test_revoked_followup_never_reaches_idempotency(monkeypatch):
    from buyeros_api.sales.contracts import TaskFollowup
    from buyeros_api.services import sales_tasks as service
    async def denied(*args, **kwargs): raise ApiError(404,'NOT_FOUND','not found')
    async def forbidden(*args, **kwargs): pytest.fail('revoked access reached replay')
    monkeypatch.setattr(service,'task_row',denied)
    monkeypatch.setattr(service,'begin_idempotency',forbidden)
    with pytest.raises(ApiError) as error:
        asyncio.run(service.followup_task(object(),Scope(workspace_id=UID,project_id=UID,actor_id=UID),UID,
            TaskFollowup(user_message='Synthetic',arguments={}), 'synthetic-followup',1))
    assert error.value.status_code == 404


def test_disabled_admission_keeps_discovery_followup_readback(monkeypatch):
    from contextlib import asynccontextmanager
    from fastapi.testclient import TestClient
    from buyeros_api.api.app import create_app
    from buyeros_api.api.auth import get_principal
    from buyeros_api.api.routes import sales_tasks as routes
    from buyeros_api.sales.contracts import TaskCollectionPage
    calls=[]
    @asynccontextmanager
    async def access(*args, **kwargs):
        calls.append(kwargs)
        yield object(),UID
    async def listing(*args): return TaskCollectionPage(items=[routes.service.detail(row())],total=1,offset=0,limit=50)
    async def followup(*args): return routes.service.detail(row())
    monkeypatch.setattr(routes,'access',access)
    monkeypatch.setattr(routes.service,'list_tasks',listing)
    monkeypatch.setattr(routes.service,'followup_task',followup)
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED','false')
    app=create_app(); app.dependency_overrides[get_principal]=lambda: object()
    client=TestClient(app)
    path=f'/v1/workspaces/{UID}/projects/{UID}/sales-tasks'
    for response in [client.get(path+'?thread_id='+str(UID)),
        client.post(path+f'/{UID}/followups',json={'user_message':'Synthetic','arguments':{}},
            headers={'If-Match':'"1"','Idempotency-Key':'synthetic-followup'})]:
        assert response.status_code == 200, response.text
        assert response.headers['cache-control']=='no-store'
    assert calls == [{'sales':True,'admission':False,'locks':False}, {'sales':True,'admission':False}]


def large_proposal_inputs():
    ref={'id':str(UID),'version':1,'kind':'document','locator':'document:'+str(UID),'retention_class':'durable'}
    original={'buyer_id':str(UID),'profile_id':str(UID),'pain_points':['漢'*4000]*10}
    term={'price':{'amount':'100.00','currency':'USD'},'scope':'漢'*4000,
        'exclusions':'漢'*4000,'timeline':'漢'*4000,'evidence':[ref]}
    return original,{'terms':[term]*3}


@pytest.mark.parametrize('invalid', ['bytes','nul'])
def test_r4_merged_intake_rejected_before_row_mutation(monkeypatch,invalid):
    import json
    from buyeros_api.sales.contracts import TaskFollowup
    from buyeros_api.services import sales_tasks as service
    from buyeros_api.sales.registry import load_skill, validate_intake
    original,delta=large_proposal_inputs()
    if invalid=='nul':
        original={**original,'pain_points':['bad\x00value']};delta={}
    current=row();current.skill_id='sales-proposal';current.arguments=original
    current.intake_history[0]['arguments']=deepcopy(original)
    before=deepcopy(vars(current))
    if invalid=='bytes':
        assert len(json.dumps(original,ensure_ascii=False).encode())<131072
        assert len(json.dumps(delta,ensure_ascii=False).encode())<131072
        assert len(json.dumps({**original,**delta},ensure_ascii=False).encode())>131072
        validate_intake(load_skill('sales-proposal','1'),{**original,**delta})
    async def task_row(*args,**kwargs): return current
    async def begin(*args,**kwargs): pytest.fail('invalid effective intake reached idempotency flush')
    async def forbidden(*args,**kwargs): pytest.fail('invalid effective intake reached planning or writes')
    monkeypatch.setattr(service,'task_row',task_row)
    monkeypatch.setattr(service,'begin_idempotency',begin)
    monkeypatch.setattr(service,'intake_plan',forbidden)
    class Session:
        def add(self,*args): pytest.fail('dependency added')
        async def flush(self): pytest.fail('row flushed')
    with pytest.raises(ApiError) as error:
        asyncio.run(service.followup_task(Session(),Scope(workspace_id=UID,project_id=UID,actor_id=UID),UID,
            TaskFollowup(user_message='Synthetic delta',arguments=delta),'synthetic-merged',1))
    assert error.value.code==('INPUT_LIMIT' if invalid=='bytes' else 'INVALID_REQUEST')
    assert vars(current)==before



def test_r4_storage_size_accounts_for_jsonb_numeric_expansion():
    from buyeros_api.services.sales_tasks import jsonb_storage_size
    assert jsonb_storage_size({'amount':1e20}) >= len('{"amount": 100000000000000000000}'.encode())
    assert jsonb_storage_size({'amount':1e-7}) >= len('{"amount": 0.0000001}'.encode())
    assert jsonb_storage_size({'value':'漢','escaped':'\n'}) == len('{"value": "漢", "escaped": "\\n"}'.encode())
