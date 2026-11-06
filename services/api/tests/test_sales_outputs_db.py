"""Task6 canonical outputs: real owned PostgreSQL and deterministic section validation."""
import importlib
import uuid
import pytest
from tests.test_sales_execution_db import execution_api, execution_pg, pg_call, pg_dispatch


def owner():
    assert importlib.util.find_spec('buyeros_api.services.sales_outputs'), 'canonical output owner missing'
    return importlib.import_module('buyeros_api.services.sales_outputs')


def test_section_assembly_requires_exact_set():
    service = owner()
    from buyeros_api.sales.contracts import SalesSectionCandidate
    summary = SalesSectionCandidate(kind='research_report', section='summary', complete=False,
        content={'summary':'SYNTHETIC','unknowns':[],'opportunities':[],'concerns':[]}, citations=[])
    findings = SalesSectionCandidate(kind='research_report',section='findings',complete=False,
        content={'findings':[]},citations=[])
    assert service.assemble_sections('research_report',[summary,findings]).content.summary == 'SYNTHETIC'
    for bad in ([summary], [summary,summary], [summary,findings,findings]):
        with pytest.raises(ValueError): service.assemble_sections('research_report',bad)


def test_markdown_renderer_cannot_emit_html_or_executable_links():
    service=owner()
    rendered=service.render_markdown('# Heading\n\n<script>alert(1)</script>\n[click](javascript:alert(1))\n![track](https://evil.test/x)')
    assert '<h2>Heading</h2>' in rendered
    assert '<script>' not in rendered and '<img' not in rendered and 'href=' not in rendered
    assert '&lt;script&gt;' in rendered


def test_full_model_proposal_accepts_only_selected_output_dependency():
    from buyeros_api.sales.context import snapshot_from_sources
    from buyeros_api.sales.contracts import SourceRef
    from buyeros_api.sales.registry import load_skill
    from buyeros_api.sales.model import validate_sales_proposal
    ref=SourceRef(id=uuid.uuid4(),version=2,kind='output',locator='output:'+str(uuid.uuid4()),retention_class='durable')
    ref=ref.model_copy(update={'locator':'output:'+str(ref.id)})
    context=snapshot_from_sources([ref],[{'ref':ref.model_dump(mode='json'),'excerpts':['SYNTHETIC']}],None,'')
    payload={'kind':'research_report','content':{'summary':'SYNTHETIC','unknowns':[],'opportunities':[],'concerns':[],'findings':[]},
        'citations':[ref.model_dump(mode='json')],'dependencies':[{'id':str(ref.id),'revision':2}],'native_refs':[]}
    assert validate_sales_proposal(payload,context,load_skill('sales-quick','1')).dependencies[0].revision==2
    payload['dependencies'][0]['revision']=3
    with pytest.raises(ValueError):validate_sales_proposal(payload,context,load_skill('sales-quick','1'))


def test_dependency_graph_has_shared_read_budget():
    import asyncio
    # A diamond graph must not multiply canonical reads without bound.
    with pytest.raises(ValueError,match='dependency read budget'):
        asyncio.run(owner().get_output(object(),object(),uuid.uuid4(),_budget=[64]))


def test_unavailable_output_scope_is_not_found(monkeypatch):
    import asyncio
    from buyeros_api.api.errors import ApiError
    service=owner()
    async def unavailable(*args):raise ValueError('inactive project')
    monkeypatch.setattr(service,'require_scope',unavailable)
    with pytest.raises(ApiError) as caught:asyncio.run(service.get_output(object(),object(),uuid.uuid4()))
    assert caught.value.status_code==404


@pytest.fixture
def outputs_pg(execution_pg, monkeypatch):
    service=owner()
    from buyeros_api.sales import actions
    monkeypatch.setattr(actions,'SECTION_OWNER',service.SECTION_OWNER)
    return execution_pg


def save(c, key='task6-output-save', visibility='thread', summary=None):
    from buyeros_api.db.session import tenant_session
    from buyeros_api.sales.contracts import Scope
    from tests.test_buyer_review_db import OPERATOR
    scope=Scope(workspace_id=c.ws,project_id=c.project,actor_id=uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR))
    async def run(engine):
        async with tenant_session(engine,c.ws) as s:
            candidate=await owner().assemble_task(s,scope,uuid.UUID(c.task['id']))
            if summary is not None:
                from buyeros_api.sales.contracts import OutputCandidate
                data=candidate.model_dump(mode='json');data['content']['summary']=summary
                candidate=OutputCandidate.model_validate(data)
            return await owner().save_output(s,scope,uuid.UUID(c.task['id']),candidate,key+c.task['id'],visibility)
    return pg_call(c,run,worker=False)


def test_postgres_output_regeneration_keeps_old_revision(outputs_pg):
    c=outputs_pg
    import psycopg
    pg_dispatch(c,0)
    with pytest.raises(ValueError): save(c)
    pg_dispatch(c,1)
    from tests.test_conversation_threads_api import headers
    assert c.client.get(c.path,headers=headers()).json()['data']['state']=='ready_for_review'
    old=save(c)
    assert save(c)==old
    new=save(c,key='output-save-0002')
    assert new.id==old.id and new.revision==old.revision+1
    root=c.path.split('/sales-tasks')[0]+'/sales-outputs'
    from tests.test_conversation_threads_api import headers
    response=c.client.get(root+'/'+str(old.id),params={'revision':old.revision},headers=headers())
    assert response.status_code==200,response.text
    assert response.json()['data']['content']==old.content.model_dump(mode='json')
    assert response.headers['cache-control']=='no-store'
    assert c.client.get(c.path,headers=headers()).json()['data']['state']=='completed'
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT count(*) FROM sales_output_sections').fetchone()[0]==2
        assert db.execute('SELECT count(*) FROM sales_output_versions').fetchone()[0]==2


def test_default_storage_does_not_enable_live_execution():
    owner()
    from buyeros_api.sales import actions
    assert actions.SECTION_OWNER is not None
    assert actions.REGISTRATION is None and actions.ACCOUNTING_OWNER is not None
    with pytest.raises(Exception): actions.selected('US','en')


def test_postgres_invalid_native_filter_uses_native_error_envelope(outputs_pg):
    from tests.test_conversation_threads_api import headers
    c=outputs_pg
    for params in ({'native_id':str(uuid.uuid4())},{'native_surface':'buyer'},{'native_surface':'javascript','native_id':str(uuid.uuid4())}):
        response=c.client.get(output_root(c),params=params,headers=headers())
        assert response.status_code==422,response.text
        assert response.json()['code']=='INVALID_REQUEST' and response.headers['cache-control']=='no-store'


def completed(c,visibility='thread'):
    for index in range(len(c.steps)): pg_dispatch(c,index)
    return save(c,visibility=visibility)


def output_root(c):
    return c.path.split('/sales-tasks')[0]+'/sales-outputs'


def test_postgres_project_reopen_without_transcript_and_private_history(outputs_pg,monkeypatch):
    from tests.test_conversation_threads_api import headers
    from tests.test_buyer_review_db import VIEWER
    c=outputs_pg; private=completed(c); root=output_root(c)
    assert c.client.get(root+'/'+str(private.id),headers=headers(VIEWER)).status_code==404
    assert c.client.get(root,headers=headers(VIEWER)).json()['data']['total']==0
    shared=save(c,key='share-project-v1',visibility='project')
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED','false')
    response=c.client.get(root+'/'+str(shared.id),headers=headers(VIEWER))
    assert response.status_code==200,response.text
    assert response.json()['data']['availability']=='available'
    assert 'thread_id' not in response.text and 'task_id' not in response.text and c.task['id'] not in response.text
    assert c.client.get(c.path,headers=headers(VIEWER)).status_code==404
    history=c.client.get(root+'/'+str(shared.id)+'/versions',headers=headers(VIEWER))
    assert [x['revision'] for x in history.json()['data']['outputs']]==[2]
    assert c.client.get(root+'/'+str(shared.id)+'/versions/1',headers=headers(VIEWER)).status_code==404


@pytest.mark.parametrize('loss',['deleted','expired','revoked'])
def test_postgres_selected_output_exact_revision_and_source_loss(outputs_pg,loss):
    import psycopg
    from buyeros_api.db.session import tenant_session
    from buyeros_api.sales.context import resolve_context
    from buyeros_api.sales.contracts import Scope,SourceRef
    from tests.test_buyer_review_db import OPERATOR
    from tests.test_conversation_reply_db import DOCUMENT
    from tests.test_conversation_threads_api import headers
    c=outputs_pg; saved=completed(c)
    ref=SourceRef(id=saved.id,version=1,kind='output',locator='output:'+str(saved.id),retention_class='durable')
    scope=Scope(workspace_id=c.ws,project_id=c.project,actor_id=uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR))
    async def resolve(engine):
        async with tenant_session(engine,c.ws) as s: return await resolve_context(s,scope,[ref])
    context=pg_call(c,resolve,worker=False)
    assert len(context._sources)==1 and 'SYNTHETIC' in str(context._sources)
    with psycopg.connect(c.dsn) as db:
        if loss=='deleted': db.execute("UPDATE offer_documents SET status='deleted',deleted_at=now() WHERE id=%s",(DOCUMENT,))
        elif loss=='expired': db.execute("UPDATE offer_documents SET retention_until=now()-interval '1 day' WHERE id=%s",(DOCUMENT,))
        else: db.execute('UPDATE memberships SET active=false WHERE user_id=%s',(scope.actor_id,))
    with pytest.raises(Exception): pg_call(c,resolve,worker=False)
    response=c.client.get(output_root(c)+'/'+str(saved.id),headers=headers())
    if loss!='revoked':
        assert response.status_code==200,response.text
        data=response.json()['data']
        assert data['availability']=='unavailable' and data['content'] is None
        assert data['citations']==data['dependencies']==data['native_refs']==[]
    else: assert response.status_code in (403,404)


def test_postgres_readback_failure_never_completes(outputs_pg,monkeypatch):
    c=outputs_pg
    for index in range(len(c.steps)): pg_dispatch(c,index)
    service=owner()
    async def missing(*args,**kwargs): raise ValueError('synthetic canonical readback failure')
    monkeypatch.setattr(service,'get_output',missing)
    with pytest.raises(ValueError,match='canonical readback'):save(c)
    import psycopg
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT count(*) FROM sales_output_versions').fetchone()[0]==0
        assert db.execute('SELECT state FROM sales_tasks WHERE id=%s',(c.task['id'],)).fetchone()[0]=='ready_for_review'


@pytest.mark.parametrize('loss',[None,'deleted','revoked','share'])
def test_postgres_native_buyer_action_is_invoked_versioned_idempotent_and_linked(outputs_pg,loss):
    import psycopg
    from tests.test_conversation_threads_api import headers
    from tests.test_buyer_review_db import VIEWER
    c=outputs_pg;saved=completed(c);company,buyer=uuid.uuid4(),uuid.uuid4()
    with psycopg.connect(c.dsn) as db:
        db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES(%s,%s,'SYNTHETIC','SYNTHETIC')",(company,c.ws))
        db.execute('INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES(%s,%s,%s,%s)',(buyer,c.ws,c.project,company))
    payload={'id':str(uuid.uuid4()),'capability':'buyers.review','arguments':{
        'refs':[{'surface':'buyer','id':str(buyer),'revision':1}],'purpose':'Explicit human note',
        'output':{'id':str(saved.id),'revision':saved.revision},'mutation':{'note':'SYNTHETIC NOTE'}},
        'source_versions':[{'id':str(saved.id),'version':1,'kind':'output','locator':'output:'+str(saved.id),'retention_class':'durable'}]}
    path=output_root(c)+'/native-actions'
    denied=c.client.post(path,headers=headers(VIEWER,key='viewer-native-edit'),json=payload)
    assert denied.status_code==403,denied.text
    first=c.client.post(path,headers=headers(key='native-buyer-edit'),json=payload)
    assert first.status_code==200,first.text
    replay=c.client.post(path,headers=headers(key='native-buyer-edit'),json=payload)
    assert replay.status_code==200 and replay.json()['data']==first.json()['data'],replay.text
    stale=c.client.post(path,headers=headers(key='native-buyer-stale'),json=payload)
    assert stale.status_code==412,stale.text
    latest=c.client.get(output_root(c)+'/'+str(saved.id),headers=headers()).json()['data']
    assert latest['revision']==2 and latest['native_refs']==[first.json()['data']]
    listed=c.client.get(output_root(c),params={'native_surface':'buyer','native_id':str(buyer)},headers=headers())
    assert listed.json()['data']['total']==1
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT note,version FROM project_buyers WHERE id=%s',(buyer,)).fetchone()==('SYNTHETIC NOTE',2)
    assert_second_native_replay(c,payload,loss)


def assert_second_native_replay(c,payload,loss=None):
    from copy import deepcopy
    import psycopg
    from tests.test_conversation_threads_api import headers
    from tests.test_conversation_reply_db import DOCUMENT
    from tests.test_buyer_review_db import OPERATOR,ADMIN
    second=deepcopy(payload);second['id']=str(uuid.uuid4())
    args=second['arguments'];args['refs'][0]['revision']=2
    args['output']['revision']=2;second['source_versions'][0]['version']=2
    surface=args['refs'][0]['surface']
    args['mutation']=({'note':'SECOND NOTE'} if surface=='buyer' else
        {'operation':'remove','buyers':args['mutation']['buyers']} if surface=='list' else
        {'subject':'Second','body':'Second'})
    actor=ADMIN if loss=='share' else OPERATOR
    if loss=='share':
        with psycopg.connect(c.dsn) as db:
            db.execute('''INSERT INTO conversation_thread_shares(id,workspace_id,project_id,thread_id,owner_user_id,grantee_user_id,granted_by,role)
                SELECT %s,workspace_id,project_id,id,owner_user_id,%s,owner_user_id,'editor'
                FROM conversation_threads WHERE id=(SELECT thread_id FROM sales_tasks WHERE id=%s)''',
                (uuid.uuid4(),uuid.uuid5(uuid.NAMESPACE_URL,actor),c.task['id']))
    path=output_root(c)+'/native-actions';request_headers=headers(actor,version=2,key='native-second-edit')
    response=c.client.post(path,headers=request_headers,json=second)
    assert response.status_code==200,response.text
    assert response.json()['data']['revision']==3
    replay=c.client.post(path,headers=request_headers,json=second)
    assert replay.status_code==200,replay.text
    assert replay.json()['data']==response.json()['data']
    with psycopg.connect(c.dsn) as db:
        table,column={'buyer':('project_buyers','version'),'list':('buyer_lists','version'),
            'draft':('outreach_drafts','state_version')}[surface]
        assert db.execute(f'SELECT {column} FROM {table} WHERE id=%s',(args['refs'][0]['id'],)).fetchone()[0]==3
        assert db.execute('SELECT count(*) FROM sales_output_versions WHERE output_id=%s',(args['output']['id'],)).fetchone()[0]==3
        if surface=='draft':
            assert db.execute('SELECT count(*) FROM draft_revisions WHERE draft_id=%s',(args['refs'][0]['id'],)).fetchone()[0]==3
        if loss=='deleted': db.execute("UPDATE offer_documents SET status='deleted',deleted_at=now() WHERE id=%s",(DOCUMENT,))
        elif loss=='revoked': db.execute('UPDATE memberships SET active=false WHERE user_id=%s',(uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR),))
        elif loss=='share':
            db.execute('DELETE FROM conversation_thread_shares WHERE thread_id=(SELECT thread_id FROM sales_tasks WHERE id=%s)',(c.task['id'],))
    if loss:
        denied=c.client.post(path,headers=request_headers,json=second)
        assert denied.status_code in (403,404,409),denied.text
        with psycopg.connect(c.dsn) as db:
            assert db.execute(f'SELECT {column} FROM {table} WHERE id=%s',(args['refs'][0]['id'],)).fetchone()[0]==3
            assert db.execute('SELECT count(*) FROM sales_output_versions WHERE output_id=%s',(args['output']['id'],)).fetchone()[0]==3


def test_postgres_outputs_force_rls_and_rollback(outputs_pg):
    import psycopg
    from alembic import command
    from tests.test_conversation_threads_db import config
    from tests.conftest import runtime_role_dsn
    c=outputs_pg; completed(c)
    tables=('sales_outputs','sales_output_versions','sales_output_sections','sales_output_dependencies','sales_output_native_links')
    with psycopg.connect(c.dsn) as db:
        for table in tables:
            assert db.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(table,)).fetchone()==(True,True)
            assert not db.execute('SELECT has_table_privilege(%s,%s,%s)',('buyeros_worker',table,'DELETE')).fetchone()[0]
            assert db.execute('SELECT has_table_privilege(%s,%s,%s)',('buyeros_worker',table,'INSERT')).fetchone()[0]==(table=='sales_output_sections')
    with psycopg.connect(runtime_role_dsn(c.dsn)) as db:
        assert db.execute('SELECT count(*) FROM sales_outputs').fetchone()[0]==0
        db.execute("SELECT set_config('app.workspace_id',%s,true)",(str(uuid.uuid4()),))
        assert db.execute('SELECT count(*) FROM sales_output_versions').fetchone()[0]==0
    with pytest.raises(RuntimeError,match='preserve populated'): command.downgrade(config(),'0060_sales_tasks')
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0065_sales_lifecycle'
        assert db.execute('SELECT count(*) FROM sales_output_versions').fetchone()[0]==1
        assert all(db.execute('SELECT relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(t,)).fetchone()[0] for t in tables)


def test_postgres_empty_0061_roundtrip(isolated_migrated):
    import psycopg
    from alembic import command
    from tests.test_conversation_threads_db import config
    command.downgrade(config(),'0060_sales_tasks')
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute("SELECT to_regclass('sales_outputs')").fetchone()[0] is None
        assert db.execute('SELECT public.buyeros_model_receipts_writable()').fetchone()[0]
    command.upgrade(config(),'head')
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute('SELECT public.buyeros_model_receipts_writable()').fetchone()[0]


def test_postgres_selected_output_reaches_real_reviewed_dispatch(outputs_pg):
    from tests.test_conversation_threads_api import headers,create
    c=outputs_pg;saved=completed(c);thread=create(c.client)
    ref={'id':str(saved.id),'version':1,'kind':'output','locator':'output:'+str(saved.id),'retention_class':'durable'}
    root=c.path.split('/sales-tasks')[0]+'/sales-tasks'
    created=c.client.post(root,headers=headers(version=thread['version']),json={'thread_id':thread['id'],
        'skill_id':'sales-quick','skill_version':'1','user_message':'Reuse only selected saved output',
        'arguments':{'research_question':'SYNTHETIC'},'source_refs':[ref]})
    assert created.status_code==201,created.text
    task=created.json()['data'];path=root+'/'+task['id']
    proposal={'id':str(uuid.uuid4()),'capability':'research.read','arguments':{'refs':[],'purpose':'SYNTHETIC'},'source_versions':[ref]}
    preview=c.client.post(path+'/execution-preview',headers=headers(),json=proposal)
    assert preview.status_code==200,preview.text
    review=c.client.post(path+'/reviews',headers=headers(version=1,key='selected-output-review'),
        json={'proposal':proposal,'fingerprint':preview.json()['data']['fingerprint']})
    assert review.status_code==200,review.text
    admitted=c.client.post(path+'/steps',headers=headers(version=1,key='selected-output-admit'),
        json={'proposal':proposal,'review_id':review.json()['data']['id']})
    assert admitted.status_code==200,admitted.text
    import psycopg
    with psycopg.connect(c.dsn) as db:
        steps=db.execute('SELECT s.id,s.outbox_id FROM sales_steps s JOIN sales_executions p ON p.id=s.execution_id WHERE p.task_id=%s ORDER BY s.section',(task['id'],)).fetchall()
    c.steps=steps;c.task=task;c.path=path
    derived=completed(c)
    assert [(d.id,d.revision) for d in derived.dependencies]==[(saved.id,1)]
    with psycopg.connect(c.dsn) as db:
        original_parent=db.execute('SELECT task_id FROM sales_outputs WHERE id=%s',(saved.id,)).fetchone()[0]
        original_execution=db.execute('SELECT id FROM sales_executions WHERE task_id=%s',(original_parent,)).fetchone()[0]
        # A valid execution ID from another task must not bind this step's receipt.
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            db.execute("UPDATE sales_output_sections SET execution_id=%s,section='foreign' WHERE step_id=%s",(original_execution,c.steps[0][0]))


@pytest.mark.parametrize('surface',['list','draft'])
def test_postgres_native_list_and_draft_owning_services(outputs_pg,surface):
    import psycopg
    from psycopg.types.json import Jsonb
    from tests.test_conversation_threads_api import headers
    from tests.test_buyer_review_db import OPERATOR
    c=outputs_pg;saved=completed(c);buyer,company,target,revision_id=uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),uuid.uuid4()
    with psycopg.connect(c.dsn) as db:
        db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES(%s,%s,'SYNTHETIC','SYNTHETIC')",(company,c.ws))
        db.execute('INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES(%s,%s,%s,%s)',(buyer,c.ws,c.project,company))
        if surface=='list':
            db.execute("INSERT INTO buyer_lists(id,workspace_id,project_id,name) VALUES(%s,%s,%s,'SYNTHETIC')",(target,c.ws,c.project))
        else:
            db.execute("INSERT INTO outreach_drafts(id,workspace_id,project_id,buyer_id,current_revision,state) VALUES(%s,%s,%s,%s,1,'draft')",(target,c.ws,c.project,buyer))
            content={'subject':'Original','body':'Original','value_proposition_fact_ids':[],'evidence_refs':[]}
            db.execute("INSERT INTO draft_revisions(id,workspace_id,draft_id,revision_number,content,content_hash,evidence_ids,offer_fact_ids) VALUES(%s,%s,%s,1,%s,%s,'[]','[]')",(revision_id,c.ws,target,Jsonb(content),'a'*64))
            db.execute("INSERT INTO approvals(id,workspace_id,draft_id,revision_number,draft_revision_id,content_hash,context_fingerprint,approver_id) VALUES(%s,%s,%s,1,%s,%s,%s,%s)",
                (uuid.uuid4(),c.ws,target,revision_id,'a'*64,'b'*64,uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR)))
    payload={'id':str(uuid.uuid4()),'capability':'lists.propose' if surface=='list' else 'drafts.prepare','arguments':{
        'refs':[{'surface':surface,'id':str(target),'revision':1}],'purpose':'Explicit synthetic edit',
        'output':{'id':str(saved.id),'revision':1},
        'mutation':{'operation':'add','buyers':[{'surface':'buyer','id':str(buyer),'revision':1}]} if surface=='list' else {'subject':'Revised','body':'Revised'}},
        'source_versions':[{'id':str(saved.id),'version':1,'kind':'output','locator':'output:'+str(saved.id),'retention_class':'durable'}]}
    response=c.client.post(output_root(c)+'/native-actions',headers=headers(key='native-list-draft'),json=payload)
    assert response.status_code==200,response.text
    replay=c.client.post(output_root(c)+'/native-actions',headers=headers(key='native-list-draft'),json=payload)
    assert replay.status_code==200 and replay.json()['data']==response.json()['data']
    with psycopg.connect(c.dsn) as db:
        if surface=='list':
            assert db.execute('SELECT count(*) FROM list_memberships WHERE list_id=%s',(target,)).fetchone()[0]==1
            assert db.execute('SELECT version FROM project_buyers WHERE id=%s',(buyer,)).fetchone()[0]==1
        else:
            assert db.execute('SELECT state_version,current_revision,state FROM outreach_drafts WHERE id=%s',(target,)).fetchone()==(2,2,'draft')
            assert db.execute('SELECT invalidated_reason FROM approvals WHERE draft_id=%s',(target,)).fetchone()[0]=='draft_edited'
            assert db.execute("SELECT content->>'body' FROM draft_revisions WHERE id=%s",(revision_id,)).fetchone()[0]=='Original'
    assert_second_native_replay(c,payload)


def test_postgres_authored_revision_keeps_prior_content(outputs_pg):
    from tests.test_conversation_threads_api import headers
    c=outputs_pg;old=completed(c)
    new=save(c,key='reviewed-revision',summary='SYNTHETIC REVISED')
    assert new.revision==old.revision+1 and new.content.summary=='SYNTHETIC REVISED'
    prior=c.client.get(output_root(c)+'/'+str(old.id)+'/versions/1',headers=headers())
    assert prior.json()['data']['content']['summary']=='SYNTHETIC'


def test_full_assembly_rejects_cross_section_coverage():
    from buyeros_api.sales.contracts import SalesSectionCandidate
    from tests.test_sales_registry import valid_cases
    from buyeros_api.sales.sections import section_groups
    _,kind,content=valid_cases()['sales-report']
    children=[SalesSectionCandidate(kind=kind,section=section,complete=False,citations=[],
        content={field:content[field] for field in fields}) for section,fields in section_groups(kind).items()]
    assert owner().assemble_sections(kind,children).content.scope
    data=children[0].model_dump(mode='json');data['content']['unavailable_buyer_ids']=[]
    children[0]=SalesSectionCandidate.model_validate(data)
    with pytest.raises(ValueError,match='every selected buyer'): owner().assemble_sections(kind,children)


def test_postgres_review_save_preview_actual_routes(outputs_pg):
    from tests.test_conversation_threads_api import headers
    c=outputs_pg
    assert c.client.get(c.path+'/output-review',headers=headers()).status_code==409
    for i in range(len(c.steps)):pg_dispatch(c,i)
    review=c.client.get(c.path+'/output-review',headers=headers())
    assert review.status_code==200,review.text
    data=review.json()['data']
    assert data['visibility']=='thread' and data['project_id']==str(c.project)
    payload={'task_id':c.task['id'],'expected_task_revision':data['task_revision'],'candidate':data['candidate']}
    key='http-canonical-save'
    response=c.client.post(output_root(c),headers=headers(version=data['task_revision'],key=key),json=payload)
    assert response.status_code==200,response.text
    saved=response.json()['data']
    replay=c.client.post(output_root(c),headers=headers(version=data['task_revision'],key=key),json=payload)
    assert replay.status_code==200 and replay.json()['data']==saved
    stale=c.client.post(output_root(c),headers=headers(version=data['task_revision'],key='different-http-key'),json=payload)
    assert stale.status_code==409
    preview=c.client.get(output_root(c)+'/'+saved['id']+'/preview',headers=headers())
    assert preview.status_code==200 and 'SYNTHETIC' in preview.text
    assert preview.headers['content-security-policy']=="default-src 'none'; sandbox"
    assert preview.headers['cache-control']=='no-store'


@pytest.mark.parametrize('fault',['missing','basis','projection','claim','plan','intake'])
def test_postgres_full_assembly_rejects_changed_durable_binding(outputs_pg,fault):
    import psycopg
    c=outputs_pg
    for i in range(len(c.steps)):pg_dispatch(c,i)
    with psycopg.connect(c.dsn) as db:
        if fault=='missing': db.execute('DELETE FROM sales_output_sections WHERE step_id=%s',(c.steps[0][0],))
        elif fault in ('basis','projection'):
            db.execute('UPDATE sales_output_sections SET '+fault+"_hash=repeat('f',64) WHERE step_id=%s",(c.steps[0][0],))
        elif fault=='claim':db.execute('UPDATE sales_output_sections SET claim_id=%s WHERE step_id=%s',(uuid.uuid4(),c.steps[0][0]))
        elif fault=='plan':db.execute("UPDATE sales_executions SET plan=jsonb_set(plan,'{steps,0,section}',to_jsonb('foreign'::text)) WHERE task_id=%s",(c.task['id'],))
        else:db.execute('UPDATE sales_executions SET intake_revision=intake_revision+1 WHERE task_id=%s',(c.task['id'],))
    with pytest.raises(ValueError):save(c)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT count(*) FROM sales_output_versions').fetchone()[0]==0
        assert db.execute('SELECT state FROM sales_tasks WHERE id=%s',(c.task['id'],)).fetchone()[0]=='ready_for_review'


def test_postgres_source_thread_share_revocation_blocks_selected_reuse(outputs_pg):
    import psycopg
    from buyeros_api.db.session import tenant_session
    from buyeros_api.sales.context import resolve_context
    from buyeros_api.sales.contracts import Scope,SourceRef
    from tests.test_buyer_review_db import OPERATOR,VIEWER
    c=outputs_pg;saved=completed(c)
    viewer=uuid.uuid5(uuid.NAMESPACE_URL,VIEWER);actor=uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR)
    with psycopg.connect(c.dsn) as db:
        thread=db.execute('SELECT thread_id FROM sales_tasks WHERE id=%s',(c.task['id'],)).fetchone()[0]
        db.execute("INSERT INTO conversation_thread_shares(id,workspace_id,project_id,thread_id,owner_user_id,grantee_user_id,granted_by,role) VALUES(%s,%s,%s,%s,%s,%s,%s,'viewer')",
            (uuid.uuid4(),c.ws,c.project,thread,actor,viewer,actor))
    scope=Scope(workspace_id=c.ws,project_id=c.project,actor_id=viewer)
    ref=SourceRef(id=saved.id,version=1,kind='output',locator='output:'+str(saved.id),retention_class='durable')
    async def resolve(engine):
        async with tenant_session(engine,c.ws) as s:return await resolve_context(s,scope,[ref])
    assert pg_call(c,resolve,worker=False).refs==(ref,)
    with psycopg.connect(c.dsn) as db:db.execute('DELETE FROM conversation_thread_shares WHERE grantee_user_id=%s',(viewer,))
    with pytest.raises(Exception):pg_call(c,resolve,worker=False)


def test_postgres_section_sink_exact_replay_and_conflict(outputs_pg):
    from sqlalchemy import select
    from types import SimpleNamespace
    from buyeros_api.db.session import tenant_session
    from buyeros_api.db.sales_execution import SalesExecution,SalesStep
    from buyeros_api.db.sales_outputs import SalesOutputSection
    from buyeros_api.sales.contracts import Scope,SourceRef,SalesSectionCandidate
    from buyeros_api.sales.context import resolve_context
    from buyeros_api.sales.model import make_basis
    from buyeros_api.execution.sales_tasks import request_for
    from buyeros_api.services.sales_tasks import task_row
    from tests.test_buyer_review_db import OPERATOR
    c=outputs_pg;pg_dispatch(c,0)
    scope=Scope(workspace_id=c.ws,project_id=c.project,actor_id=uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR))
    async def check(engine):
        async with tenant_session(engine,c.ws) as s:
            row=await task_row(s,scope,uuid.UUID(c.task['id']),edit=True)
            parent=(await s.execute(select(SalesExecution).where(SalesExecution.task_id==row.id))).scalar_one()
            step=(await s.execute(select(SalesStep).where(SalesStep.id==c.steps[0][0]))).scalar_one()
            receipt=(await s.execute(select(SalesOutputSection).where(SalesOutputSection.step_id==step.id))).scalar_one()
            current=await resolve_context(s,scope,[SourceRef.model_validate(r) for r in row.source_refs])
            basis=make_basis(request_for(row,current,c.item,step.id,step.section),scope,current)
            candidate=SalesSectionCandidate.model_validate(receipt.candidate)
            assert await owner().SECTION_OWNER.save_section(s,scope,parent,step,basis,candidate)==receipt.id
            foreign=SimpleNamespace(**{col.name:getattr(step,col.name) for col in SalesStep.__table__.columns})
            foreign.claim_id=uuid.uuid4()
            with pytest.raises(ValueError,match='replay conflict'):
                await owner().SECTION_OWNER.save_section(s,scope,parent,foreign,basis,candidate)
            assert row.state!='completed'
    pg_call(c,check,worker=False)


def test_postgres_concurrent_canonical_save_and_dependency_tampering(outputs_pg):
    from concurrent.futures import ThreadPoolExecutor
    from tests.test_conversation_threads_api import headers
    import psycopg
    c=outputs_pg
    for i in range(len(c.steps)):pg_dispatch(c,i)
    data=c.client.get(c.path+'/output-review',headers=headers()).json()['data']
    payload={'task_id':c.task['id'],'expected_task_revision':data['task_revision'],'candidate':data['candidate']}
    def submit():return c.client.post(output_root(c),headers=headers(version=data['task_revision'],key='concurrent-output-save'),json=payload)
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:submit(),range(2)))
    assert all(r.status_code==200 for r in results),[r.text for r in results]
    assert results[0].json()['data']==results[1].json()['data']
    current=c.client.get(c.path,headers=headers()).json()['data']
    payload['expected_task_revision']=current['revision']
    payload['candidate']['dependencies']=[{'id':str(uuid.uuid4()),'revision':1}]
    bad=c.client.post(output_root(c),headers=headers(version=current['revision'],key='invented-dependency'),json=payload)
    assert bad.status_code==409,bad.text
    with psycopg.connect(c.dsn) as db:assert db.execute('SELECT count(*) FROM sales_output_versions').fetchone()[0]==1
