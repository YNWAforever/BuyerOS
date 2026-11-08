"""Task10 HTTP, source closure, and real schema boundary checks."""
import uuid
import pytest
import psycopg
from tests.xverum_fixtures import credit_case, connection_case, provisional_pg, execution_api, pg, headers
from tests.test_xverum_dispatch_db import dispatch_case, thread_entry, native_dispatch, linked_task, select_receipt, shared_search
from tests.test_xverum_enrichment_db import journey, person_journey, propose


def test_http_proposal_native_cas_and_saved_business_fields(journey):
    c=journey
    root=f'/v1/workspaces/{c.ws}/projects/{c.project}/xverum/enrichment-proposals'
    body={'buyer_id':str(c.buyer),'receipt_ids':[str(c.detail.id)]}
    response=c.client.post(root,headers=headers(key='http-enrichment-create'),json=body)
    assert response.status_code==200,response.text
    proposal=response.json()['data']
    replay=c.client.post(root,headers=headers(key='http-enrichment-create'),json=body)
    assert replay.json()['data']==proposal
    apply={'proposal_id':proposal['id'],'buyer_version':1,'selected_fields':['industry']}
    response=c.client.post(root+'/'+proposal['id']+'/apply',headers=headers(key='http-enrichment-apply'),json=apply)
    assert response.status_code==200,response.text
    assert response.headers['etag']=='"2"'
    replay=c.client.post(root+'/'+proposal['id']+'/apply',headers=headers(key='http-enrichment-apply'),json=apply)
    assert replay.status_code==200 and replay.json()['data']==response.json()['data']
    native=c.client.get(f'/v1/workspaces/{c.ws}/buyers/{c.buyer}',headers=headers())
    assert native.status_code==200,native.text
    assert native.json()['data']['reviewed_enrichment'][0]['fields']=={'industry':'Synthetic procurement'}
    with psycopg.connect(c.dsn) as db:db.execute('UPDATE project_buyers SET version=version+1 WHERE id=%s',(c.buyer,))
    denied=c.client.post(root+'/'+proposal['id']+'/apply',headers=headers(key='http-enrichment-apply'),json=apply)
    assert denied.status_code==409,denied.text
    assert 'no-store' in denied.headers['cache-control']


def test_private_original_search_revocation_closes_saved_proposal(dispatch_case,monkeypatch):
    from buyeros_api.sales.contracts import XverumPersonDetail
    from buyeros_api.services.xverum_quotes import quote_details,confirm_quote
    from buyeros_api.services.xverum_enrichment import propose_enrichment,read_proposal
    from buyeros_api.services.sales_outputs import get_output
    from buyeros_api.db.sales_tasks import SalesTask
    from buyeros_api.api.errors import ApiError
    c=dispatch_case
    c.projections={'enrich_person_xverum':{**{k:None for k in XverumPersonDetail.model_fields},
        'full_name':'Synthetic Buyer','company_name':None,'evidence_summary':'Synthetic','experience':[]}}
    source,revoke,_=shared_search(c)
    task=linked_task(c,monkeypatch)
    async def details(factory):
        async with factory() as s:q=await quote_details(s,c.scope,source.id,['1'],False)
        async with factory() as s:return await confirm_quote(s,c.scope,q.id,q.fingerprint,'private-detail-stage',task_id=task,expected_task_version=1)
    detail=pg(c,details);select_receipt(c,detail)
    assert native_dispatch(c).state=='done'
    async def save(factory):
        async with factory() as s:
            proposal=await propose_enrichment(s,c.scope,c.buyer,[detail.id])
            assert proposal.identity_match=='unresolved'
            t=await s.get(SalesTask,task)
            oid=uuid.UUID(t.output_ids[0])
            assert (await get_output(s,c.scope,oid)).availability=='available'
            return proposal,oid
    proposal,oid=pg(c,save)
    revoke()
    async def denied(factory):
        with pytest.raises((ApiError,ValueError)):
            async with factory() as s:await read_proposal(s,c.scope,proposal.id)
        async with factory() as s:
            result=await get_output(s,c.scope,oid)
            assert result.availability=='unavailable' and result.content is None
    pg(c,denied)


def test_enrichment_schema_roles_and_empty_downgrade(isolated_migrated):
    from alembic import command
    from tests.test_conversation_threads_db import config
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='xverum_enrichments'::regclass").fetchone()==(True,True)
        assert not db.execute("SELECT has_table_privilege('buyeros_worker','xverum_enrichments','INSERT')").fetchone()[0]
        assert not db.execute("SELECT has_column_privilege('buyeros_api','xverum_enrichments','proposal','UPDATE')").fetchone()[0]
        db.execute('SET LOCAL ROLE buyeros_api')
        assert db.execute('SELECT count(*) FROM xverum_enrichments').fetchone()[0]==0
    command.downgrade(config(),'0063_xverum_dispatch')
    command.upgrade(config(),'head')
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0067_conversation_buyer'
        for name in ('search','model','contact'):
            assert db.execute(f'SELECT public.buyeros_{name}_receipts_writable()').fetchone()[0]
        assert db.execute('SELECT public.buyeros_xverum_connections_ready()').fetchone()[0]


def test_populated_enrichment_downgrade_preserves_review(journey):
    from alembic import command
    from tests.test_conversation_threads_db import config
    c=journey;p=propose(c)
    # Immutable lifecycle dependencies now fence the downgrade at 0065.
    with pytest.raises(RuntimeError,match='0065 downgrade blocked'):
        command.downgrade(config(),'0063_xverum_dispatch')
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0067_conversation_buyer'
        assert db.execute('SELECT id FROM xverum_enrichments WHERE id=%s',(p.id,)).fetchone()[0]==p.id
        assert db.execute('SELECT count(*) FROM xverum_enrichment_dependencies WHERE enrichment_id=%s',(p.id,)).fetchone()[0]>0
        assert db.execute("SELECT relforcerowsecurity FROM pg_class WHERE oid='xverum_enrichments'::regclass").fetchone()[0]


def test_provider_evidence_context_uses_real_retained_owner(journey):
    from buyeros_api.services.xverum_dispatch import read_evidence
    from buyeros_api.sales.context import resolve_context
    from buyeros_api.sales.contracts import SourceRef
    c=journey
    async def run(factory):
        async with factory() as s:
            evidence=(await read_evidence(s,c.scope,c.detail.id))[0]
            ref=SourceRef(id=evidence['id'],version=1,kind='provider_evidence',locator='provider_evidence:'+evidence['id'],retention_class='durable')
            context=await resolve_context(s,c.scope,[ref])
            assert 'Synthetic procurement' in str(context._sources)
            assert 'Synthetic procurement' not in context.model_dump_json()
            assert context.connection_generations[c.id]==evidence['connection_generation']
    pg(c,run)


def test_cancelled_contacts_task_cannot_apply_native_fields(journey):
    from buyeros_api.services.xverum_enrichment import apply_enrichment
    from buyeros_api.api.errors import ApiError
    c=journey;p=propose(c)
    with psycopg.connect(c.dsn) as db:db.execute("UPDATE sales_tasks SET state='cancelled' WHERE id=%s",(c.task,))
    async def run(factory):
        with pytest.raises(ApiError):
            async with factory() as s:await apply_enrichment(s,c.scope,p.id,['company_name'],1,'cancelled-native-save')
    pg(c,run)


def test_later_native_person_edit_invalidates_enrichment_retry(person_journey):
    from buyeros_api.services.xverum_enrichment import apply_enrichment
    from buyeros_api.api.errors import ApiError
    c=person_journey;p=propose(c)
    async def save(factory):
        async with factory() as s:return await apply_enrichment(s,c.scope,p.id,['person_name','job_title'],1,'person-change-save')
    pg(c,save)
    with psycopg.connect(c.dsn) as db:db.execute("UPDATE people SET role='Later native edit'")
    async def denied(factory):
        with pytest.raises(ApiError):
            async with factory() as s:await apply_enrichment(s,c.scope,p.id,['person_name','job_title'],1,'person-change-save')
    pg(c,denied)


def test_contacts_output_review_uses_trusted_producer(journey):
    c=journey;p=propose(c)
    response=c.client.get(f'/v1/workspaces/{c.ws}/projects/{c.project}/sales-tasks/{c.task}/output-review',headers=headers())
    assert response.status_code==200,response.text
    assert response.json()['data']['candidate']['content']['id']==str(p.id)


def test_same_name_subsidiaries_require_explicit_detail_selection(dispatch_case):
    from buyeros_api.sales.contracts import XverumCompanyCard
    from buyeros_api.services.xverum_enrichment import propose_enrichment
    from buyeros_api.api.errors import ApiError
    c=dispatch_case
    cards=[{**{k:None for k in XverumCompanyCard.model_fields},'id':str(i),
        'company_name':'Synthetic','website':'https://'+host} for i,host in ((1,'synthetic.example'),(2,'subsidiary.example'))]
    c.projections={'search_company_xverum':{'result_type':'company','results':cards,'total_count':2,'page':1,'page_size':5}}
    assert native_dispatch(c).state=='done'
    async def denied(factory):
        with pytest.raises(ApiError) as caught:
            async with factory() as s:await propose_enrichment(s,c.scope,c.buyer,[c.admitted.id])
        assert caught.value.code=='IDENTITY_SELECTION_REQUIRED'
    pg(c,denied)
    assert c.calls==1
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT version FROM project_buyers WHERE id=%s',(c.buyer,)).fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM xverum_enrichments').fetchone()[0]==0


@pytest.fixture
def standalone_provider_source(dispatch_case):
    from buyeros_api.services.xverum_dispatch import read_evidence
    from buyeros_api.sales.contracts import SourceRef
    c=dispatch_case;c.company_cards=True
    assert native_dispatch(c).state=='done'
    async def read(factory):
        async with factory() as s:
            evidence=(await read_evidence(s,c.scope,c.admitted.id))[0]
            return SourceRef(id=evidence['id'],version=1,kind='provider_evidence',
                locator='provider_evidence:'+evidence['id'],retention_class='durable')
    c.source_ref=pg(c,read)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT task_id FROM xverum_stages WHERE id=%s',(c.admitted.id,)).fetchone()==(None,)
    return c


def unrelated_native_buyer_edit(c):
    response=c.client.patch(f'/v1/workspaces/{c.ws}/buyers/{c.buyer}',
        headers=headers(version=1,key='fix1-unrelated-edit'),json={'note':'Unrelated native edit'})
    assert response.status_code==200,response.text
    assert response.headers['etag']=='"2"'


@pytest.mark.parametrize('consumer',['read','context','model_policy'])
def test_fix1_standalone_provider_source_rejects_unrelated_buyer_revision(standalone_provider_source,monkeypatch,consumer):
    from types import SimpleNamespace
    from buyeros_api.services.xverum_dispatch import read_evidence
    from buyeros_api.sales.context import resolve_context
    from buyeros_api.execution.sales_tasks import configuration
    from buyeros_api.sales import actions
    from buyeros_api.services import policy_service
    from buyeros_api.api.errors import ApiError
    c=standalone_provider_source;policy_calls=[]
    # Isolate source admission from unavailable live model registration. The
    # provider/current-source checks and PostgreSQL reads remain real.
    monkeypatch.setattr(actions,'selected',lambda *args:SimpleNamespace(policy_binding=None))
    original=policy_service.evaluate_current_policy
    async def policy(session,subject,purpose,*args,**kwargs):
        if purpose=='account_research':
            policy_calls.append(purpose)
            return {'allowed':True}
        return await original(session,subject,purpose,*args,**kwargs)
    monkeypatch.setattr(policy_service,'evaluate_current_policy',policy)
    async def consume(factory):
        async with factory() as s:
            if consumer=='read':return await read_evidence(s,c.scope,c.admitted.id)
            if consumer=='context':return await resolve_context(s,c.scope,[c.source_ref])
            return await configuration(s,c.scope,SimpleNamespace(arguments={'language':'en'},
                source_refs=[c.source_ref.model_dump(mode='json')]))
    assert pg(c,consume)
    policy_calls.clear()
    unrelated_native_buyer_edit(c)
    with pytest.raises(ApiError) as caught:pg(c,consume)
    assert caught.value.code=='STALE_REVISION'
    assert policy_calls==[] and c.calls==1


@pytest.fixture
def generic_provider_output(standalone_provider_source,monkeypatch):
    """Seed a valid historical generic revision via runtime-role storage.

    This tests canonical read/source policy, not the already accepted model
    execution/section producer. The research task is created by its real owner.
    """
    from buyeros_api.db.sales_tasks import SalesTask
    from buyeros_api.db.conversation_threads import ConversationThread
    from buyeros_api.db.sales_outputs import SalesOutput,SalesOutputVersion,SalesOutputDependency
    from buyeros_api.sales.contracts import TaskInput,OutputCandidate
    from buyeros_api.sales.context import resolve_context
    from buyeros_api.services.sales_tasks import create_task
    from buyeros_api.services.sales_outputs import get_output
    c=standalone_provider_source;contacts_task=linked_task(c,monkeypatch)
    async def seed(factory):
        async with factory() as s:
            parent=await s.get(SalesTask,contacts_task)
            thread=await s.get(ConversationThread,parent.thread_id)
            data=TaskInput(thread_id=thread.id,skill_id='sales-research',skill_version='1',
                user_message='Research selected synthetic source',arguments={'research_question':'Synthetic question'},
                source_refs=[c.source_ref])
            task=await create_task(s,c.scope,data,'fix1-research-task',thread.version)
            context=await resolve_context(s,c.scope,[c.source_ref])
            candidate=OutputCandidate(kind='research_report',content={'summary':'Synthetic provider research',
                'unknowns':[],'opportunities':[],'concerns':[],'findings':[]},
                citations=[c.source_ref],dependencies=[],native_refs=[])
            output=SalesOutput(workspace_id=c.ws,project_id=c.project,thread_id=thread.id,task_id=task.id,revision=1)
            s.add(output);await s.flush()
            s.add(SalesOutputVersion(workspace_id=c.ws,output_id=output.id,revision=1,visibility='thread',
                candidate=candidate.model_dump(mode='json'),source_refs=[c.source_ref.model_dump(mode='json')],
                context_digest=context.digest,intake_revision=1))
            await s.flush()
            s.add(SalesOutputDependency(workspace_id=c.ws,output_id=output.id,revision=1,
                kind=c.source_ref.kind,source_id=c.source_ref.id,source_revision=1))
            await s.flush()
            assert (await get_output(s,c.scope,output.id)).availability=='available'
            return output.id
    c.generic_output=pg(c,seed)
    return c


@pytest.mark.parametrize('consumer',['output','model_policy_source'])
def test_fix1_generic_derived_output_rejects_unrelated_buyer_revision(generic_provider_output,consumer):
    from buyeros_api.sales.contracts import SourceRef
    from buyeros_api.services.sales_outputs import get_output,policy_source_refs
    c=generic_provider_output
    ref=SourceRef(id=c.generic_output,version=1,kind='output',
        locator='output:'+str(c.generic_output),retention_class='durable')
    async def policy_sources(factory):
        async with factory() as s:return await policy_source_refs(s,c.scope,[ref])
    assert pg(c,policy_sources)==[c.source_ref]
    unrelated_native_buyer_edit(c)
    if consumer=='model_policy_source':
        with pytest.raises(ValueError,match='output policy sources unavailable'):pg(c,policy_sources)
    else:
        async def read(factory):
            async with factory() as s:return await get_output(s,c.scope,c.generic_output,1)
        saved=pg(c,read)
        assert saved.availability=='unavailable' and saved.content is None
        assert not saved.citations and not saved.dependencies and not saved.native_refs


def test_fix1_mutation_proof_is_not_ordinary_or_transferable_source_authority(journey):
    from buyeros_api.services.xverum_enrichment import apply_enrichment
    from buyeros_api.services.xverum_dispatch import read_evidence
    from buyeros_api.sales.context import resolve_context
    from buyeros_api.sales.contracts import SourceRef
    from buyeros_api.api.errors import ApiError
    from pydantic import ValidationError
    c=journey;p=propose(c);unapplied=propose(c)
    async def run(factory):
        async with factory() as s:
            parent=(await read_evidence(s,c.scope,c.search.id))[0]
            parent_ref=SourceRef(id=parent['id'],version=1,kind='provider_evidence',
                locator='provider_evidence:'+parent['id'],retention_class='durable')
            await apply_enrichment(s,c.scope,p.id,['company_name'],1,'fix1-proved-save')
        for _ in range(2):
            async with factory() as s:
                assert (await apply_enrichment(s,c.scope,p.id,['company_name'],1,'fix1-proved-save')).revision==2
        # Even the exact source stays stale to ordinary callers. A durable proof
        # is consumed explicitly only by the server's own producer/readback path.
        for ref,proof_id in ((p.source_refs[0],None),(p.source_refs[0],unapplied.id),
                             (parent_ref,p.id),(p.source_refs[0],uuid.uuid4())):
            with pytest.raises(ApiError):
                async with factory() as s:await resolve_context(s,c.scope,[ref],_enrichment_id=proof_id)
        async with factory() as s:
            assert (await resolve_context(s,c.scope,list(p.source_refs),_enrichment_id=p.id)).refs==p.source_refs
    pg(c,run)
    # Neither client source refs nor public contracts can supply the internal ID.
    with pytest.raises(ValidationError):
        SourceRef.model_validate({**p.source_refs[0].model_dump(mode='json'),'_enrichment_id':str(p.id)})
