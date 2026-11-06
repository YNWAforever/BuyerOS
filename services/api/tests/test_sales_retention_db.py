"""Task14 purge contract and current dependency enforcement."""
import importlib
import uuid
import pytest
from tests.test_sales_execution_db import execution_api, execution_pg, pg_call, pg_dispatch
from tests.test_sales_outputs_db import outputs_pg, save


@pytest.mark.parametrize('visibility',['thread','project'])
def test_fix1_root_after_fifty_descendants_is_immediately_unreadable(outputs_pg,visibility):
    import psycopg
    from tests.test_sales_core_journey_db import new_task
    from tests.test_sales_tasks_api import SALES_ROOT
    from tests.test_conversation_threads_api import headers
    from tests.test_buyer_review_db import OPERATOR
    from buyeros_api.db.session import tenant_session
    from buyeros_api.sales.contracts import Scope
    from buyeros_api.services.sales_retention import purge_sales_content,drain_pending
    c=outputs_pg;pg_dispatch(c,0);pg_dispatch(c,1)
    root=save(c,visibility=visibility)
    child=new_task(c.client,'first-project',{'offer_description':'Derived fixture'},[
        {'id':str(root.id),'kind':'output','version':1,'locator':'output:'+str(root.id),'retention_class':'durable'}])
    response=c.client.post(SALES_ROOT+'/'+child['id']+'/core-preparation',headers=headers(version=1))
    assert response.status_code==200,response.text
    derived=response.json()['data'];base=SALES_ROOT.replace('sales-tasks','sales-outputs')
    exports=[]
    for output in (str(root.id),derived['id']):
        response=c.client.post(base+'/'+output+'/exports',headers=headers(version=1),
            json={'revision':1,'format':'markdown','approved':True})
        assert response.status_code==200,response.text
        exports.append(response.json()['data']['id'])
    with psycopg.connect(c.dsn) as db:
        thread=min(uuid.UUID(c.task['thread_id']),uuid.UUID(child['thread_id']))
        for n in range(51):
            task=uuid.UUID(int=n+1)
            db.execute('''INSERT INTO sales_tasks(id,workspace_id,project_id,thread_id,owner_user_id,actor_id,
              client_message_id,intent_fingerprint,message_sequence,skill_id,skill_version,user_message,
              arguments,source_refs,intake_history,state,revision,event_sequence,output_ids)
              SELECT %s,workspace_id,project_id,%s,owner_user_id,actor_id,%s,intent_fingerprint,%s,
              skill_id,skill_version,user_message,arguments,source_refs,intake_history,'ready_for_review',revision,event_sequence,'[]'
              FROM sales_tasks WHERE id=%s''',(task,thread,uuid.uuid4(),100+n,c.task['id']))
            db.execute('''INSERT INTO sales_task_dependencies(id,workspace_id,project_id,thread_id,task_id,source_id,source_version,kind,retention_class)
              SELECT %s,workspace_id,project_id,thread_id,id,%s,1,'output','durable' FROM sales_tasks WHERE id=%s''',(uuid.uuid4(),root.id,task))
    async def first(engine):
        async with tenant_session(engine,c.ws) as s:
            return await purge_sales_content(s,Scope(workspace_id=c.ws,project_id=c.project,
                actor_id=uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR)),uuid.UUID(c.task['id']))
    receipt=pg_call(c,first,worker=False)
    assert len(receipt.affected_ids)==50 and uuid.UUID(c.task['id']) not in receipt.affected_ids
    with psycopg.connect(c.dsn) as db:
        assert db.execute("SELECT count(*) FROM sales_output_versions WHERE candidate ? 'content'").fetchone()[0]==2
    for output in (str(root.id),derived['id']):
        for suffix in ('','/versions/1'):
            response=c.client.get(base+'/'+output+suffix,headers=headers())
            assert response.status_code==200,response.text
            assert response.json()['data']['content'] is None
        assert c.client.post(base+'/'+output+'/exports',headers=headers(version=1),
            json={'revision':1,'format':'markdown','approved':True}).status_code!=200
    for export in exports:
        assert c.client.get(f'/v1/workspaces/{c.ws}/exports/{export}/content',headers=headers()).status_code!=200
    async def rest(engine):
        async with tenant_session(engine,c.ws) as s:return await drain_pending(s,c.ws)
    assert pg_call(c,rest)==3
    with psycopg.connect(c.dsn) as db:
        assert db.execute("SELECT count(*) FROM sales_output_versions WHERE candidate ? 'content'").fetchone()[0]==0


@pytest.mark.parametrize('role',['buyeros_api','buyeros_worker'])
def test_fix1_task_purge_temp_shadow_guard_and_trigger(execution_pg,role):
    from tests.sales_purge_security import check_shadowing
    c=execution_pg
    check_shadowing(c,role,'sales_tasks','buyeros_purge_sales_task',uuid.UUID(c.task['id']),'task')


def test_purge_erases_versions_sections_and_intake_without_erasing_hold(outputs_pg):
    import psycopg
    from tests.test_buyer_review_db import OPERATOR
    from buyeros_api.sales.contracts import Scope
    from buyeros_api.db.session import tenant_session
    c = outputs_pg
    pg_dispatch(c, 0)
    pg_dispatch(c, 1)
    output = save(c)
    save(c, key='retention-version-2')
    assert importlib.util.find_spec('buyeros_api.services.sales_retention'), 'missing physical purge'
    from buyeros_api.services.sales_retention import purge_sales_content
    scope = Scope(workspace_id=c.ws, project_id=c.project, actor_id=uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR))
    async def purge(engine):
        async with tenant_session(engine, c.ws) as session:
            return await purge_sales_content(session, scope, uuid.UUID(c.task['id']))
    receipt = pg_call(c, purge, worker=False)
    assert uuid.UUID(c.task['id']) in receipt.affected_ids
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT user_message,arguments,intake_history FROM sales_tasks WHERE id=%s', (c.task['id'],)).fetchone() == ('Content purged', {}, [])
        assert db.execute('SELECT count(*) FROM sales_output_sections').fetchone()[0] == 0
        versions = db.execute('SELECT candidate FROM sales_output_versions WHERE output_id=%s', (output.id,)).fetchall()
        assert len(versions) == 2 and all(v[0] == {'kind': 'research_report', 'purged': True} for v in versions)
        assert db.execute('SELECT remaining_hold=upper_bound FROM budget_reservations WHERE operation_id IN (SELECT id FROM sales_executions WHERE task_id=%s)', (c.task['id'],)).fetchone()[0]
    from tests.test_conversation_threads_api import headers
    root = c.path.split('/sales-tasks')[0]+'/sales-outputs/'+str(output.id)
    response = c.client.get(root, headers=headers())
    assert response.status_code == 200, response.text
    assert response.json()['data']['availability'] == 'unavailable'
    assert response.json()['data']['content'] is None
    assert c.client.get(root+'/permissions',headers=headers()).json()['data']=={'can_edit':False}


def test_purge_owner_has_content_free_receipt():
    assert importlib.util.find_spec('buyeros_api.services.sales_retention'), 'missing bounded physical purge owner'
    from buyeros_api.sales.contracts import PurgeReceipt
    assert set(PurgeReceipt.model_fields) == {'affected_ids', 'completed_at'}


def test_deleted_source_is_unreadable_from_all_outputs(outputs_pg):
    import psycopg
    from tests.test_sales_core_journey_db import new_task
    from tests.test_sales_tasks_api import SALES_ROOT
    from tests.test_conversation_threads_api import headers
    from tests.test_conversation_reply_db import DOCUMENT
    c=outputs_pg
    pg_dispatch(c,0);pg_dispatch(c,1)
    original=save(c)
    child=new_task(c.client,'first-project',{'offer_description':'Synthetic derived offer'},[
        {'id':str(original.id),'kind':'output','version':1,'locator':'output:'+str(original.id),'retention_class':'durable'}])
    response=c.client.post(SALES_ROOT+'/'+child['id']+'/core-preparation',headers=headers(version=1))
    assert response.status_code==200,response.text
    derived=response.json()['data']
    base=SALES_ROOT.replace('sales-tasks','sales-outputs')
    exported=c.client.post(base+'/'+str(original.id)+'/exports',headers=headers(version=1),
        json={'revision':1,'format':'markdown','approved':True})
    assert exported.status_code==200,exported.text
    export_id=exported.json()['data']['id']
    deleted=c.client.request('DELETE',f'/v1/workspaces/{c.ws}/offer-documents/{DOCUMENT}',
        headers=headers(version=1),json={'reason':'obsolete'})
    assert deleted.status_code==202,deleted.text
    for output_id in (str(original.id),derived['id']):
        read=c.client.get(base+'/'+output_id,headers=headers())
        assert read.status_code==200,read.text
        assert read.json()['data']['content'] is None
        assert c.client.post(base+'/'+output_id+'/exports',headers=headers(version=1),
            json={'revision':1,'format':'markdown','approved':True}).status_code!=200
    assert c.client.get(f'/v1/workspaces/{c.ws}/exports/{export_id}/content',headers=headers()).status_code!=200
    with psycopg.connect(c.dsn) as db:
        assert db.execute("SELECT count(*) FROM sales_output_versions WHERE candidate ? 'content'").fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM sales_output_sections').fetchone()[0]==0
        assert db.execute('SELECT selection_manifest FROM export_jobs WHERE id=%s',(export_id,)).fetchone()[0] is None


@pytest.mark.parametrize('revocation',['membership','purge'])
def test_revoked_during_native_claim_keeps_only_financial_receipt(outputs_pg,revocation):
    import psycopg
    from decimal import Decimal
    from buyeros_api.db.session import tenant_session
    from buyeros_api.execution import sales_tasks as execution
    from buyeros_api.services.sales_retention import purge_sales_content
    from buyeros_api.sales.contracts import Scope
    from tests.test_sales_execution_db import synthetic_result
    from tests.test_buyer_review_db import OPERATOR
    c=outputs_pg;actor=uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR)
    async def claim(engine):
        async with tenant_session(engine,c.ws) as s:
            return await execution.claim(s,c.steps[0][0],workspace_id=c.ws)
    _,prepared=pg_call(c,claim)
    basis,item,claim_id=prepared
    if revocation=='membership':
        with psycopg.connect(c.dsn) as db:db.execute('UPDATE memberships SET active=false WHERE workspace_id=%s AND user_id=%s',(c.ws,actor))
    else:
        async def purge(engine):
            async with tenant_session(engine,c.ws) as s:
                await purge_sales_content(s,Scope(workspace_id=c.ws,project_id=c.project,actor_id=actor),uuid.UUID(c.task['id']))
        pg_call(c,purge,worker=False)
    async def arrive(engine):
        async with tenant_session(engine,c.ws) as s:
            await execution.persist_result(s,c.steps[0][0],claim_id,basis,synthetic_result(basis))
    pg_call(c,arrive)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT count(*) FROM sales_output_sections').fetchone()[0]==0
        assert db.execute('SELECT state,usage IS NOT NULL FROM sales_steps WHERE id=%s',(c.steps[0][0],)).fetchone()==('received',True)
        assert db.execute('SELECT remaining_hold FROM budget_reservations WHERE operation_id IN(SELECT id FROM sales_executions WHERE task_id=%s)',(c.task['id'],)).fetchone()[0]==Decimal('.2')
    assert c.calls==0


def test_worker_continues_bounded_purge_after_fifty_tasks(execution_pg):
    import psycopg
    from buyeros_api.db.session import tenant_session
    from buyeros_api.services.sales_retention import invalidate_retained_subject,drain_pending
    from tests.test_conversation_reply_db import DOCUMENT
    c=execution_pg
    with psycopg.connect(c.dsn) as db:
        for n in range(51):
            task=uuid.uuid4()
            db.execute('''INSERT INTO sales_tasks(id,workspace_id,project_id,thread_id,owner_user_id,actor_id,
              client_message_id,intent_fingerprint,message_sequence,skill_id,skill_version,user_message,
              arguments,source_refs,intake_history,state,revision,event_sequence,output_ids)
              SELECT %s,workspace_id,project_id,thread_id,owner_user_id,actor_id,%s,intent_fingerprint,%s,
              skill_id,skill_version,'Private bounded purge text',arguments,source_refs,intake_history,
              state,revision,event_sequence,output_ids FROM sales_tasks WHERE id=%s''',(task,uuid.uuid4(),100+n,c.task['id']))
            db.execute('''INSERT INTO sales_task_dependencies(id,workspace_id,project_id,thread_id,task_id,source_id,source_version,kind,retention_class)
              SELECT %s,workspace_id,project_id,thread_id,%s,%s,1,'document','durable' FROM sales_tasks WHERE id=%s''',
              (uuid.uuid4(),task,DOCUMENT,task))
    async def first(engine):
        async with tenant_session(engine,c.ws) as s:
            return await invalidate_retained_subject(s,c.ws,c.project,uuid.UUID(DOCUMENT))
    assert pg_call(c,first)==50
    async def next_page(engine):
        async with tenant_session(engine,c.ws) as s:return await drain_pending(s,c.ws)
    assert pg_call(c,next_page)==2
    assert pg_call(c,next_page)==0
    with psycopg.connect(c.dsn) as db:
        assert db.execute("SELECT count(*) FROM sales_tasks WHERE user_message!='Content purged'").fetchone()[0]==0


def test_current_membership_gates_task13_discovery_and_output_capabilities(outputs_pg):
    import psycopg
    from tests.test_buyer_review_db import OPERATOR
    from tests.test_conversation_threads_api import headers
    c=outputs_pg;pg_dispatch(c,0);pg_dispatch(c,1);out=save(c)
    root=c.path.split('/sales-tasks')[0]
    urls=[root+'/sales-tasks/native-sources',root+'/sales-tasks/capability',
          root+'/sales-outputs/'+str(out.id)+'/permissions',root+'/sales/skills',
          root+'/sales-tasks?thread_id='+c.task['thread_id']]
    for url in urls:assert c.client.get(url,headers=headers()).status_code==200,url
    with psycopg.connect(c.dsn) as db:
        db.execute('UPDATE memberships SET active=false WHERE workspace_id=%s AND user_id=%s',
            (c.ws,uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR)))
    for url in urls:assert c.client.get(url,headers=headers()).status_code in {403,404},url


def test_explicit_project_retention_rejects_then_physically_purges_authored_content(outputs_pg):
    import psycopg
    from tests.test_conversation_threads_api import headers
    from buyeros_api.db.session import tenant_session
    from buyeros_api.services.sales_retention import drain_pending
    c=outputs_pg;pg_dispatch(c,0);pg_dispatch(c,1);out=save(c)
    with psycopg.connect(c.dsn) as db:
        assert db.execute("UPDATE policy_decisions SET retention_days=1 WHERE workspace_id=%s AND subject_type='project' AND subject_id=%s RETURNING id",(c.ws,c.project)).fetchall()
        db.execute("UPDATE sales_tasks SET created_at=now()-interval '2 days' WHERE id=%s",(c.task['id'],))
    url=c.path.split('/sales-tasks')[0]+'/sales-outputs/'+str(out.id)
    assert c.client.get(url,headers=headers()).json()['data']['content'] is None
    async def drain(engine):
        async with tenant_session(engine,c.ws) as s:return await drain_pending(s,c.ws)
    assert pg_call(c,drain)==1
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT user_message FROM sales_tasks WHERE id=%s',(c.task['id'],)).fetchone()[0]=='Content purged'
        assert db.execute('SELECT count(*) FROM sales_output_sections').fetchone()[0]==0
