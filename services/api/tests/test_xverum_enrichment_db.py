"""Reviewed enrichment: synthetic provider fixtures on owned PostgreSQL only."""
import importlib.util
import pytest
import psycopg
from tests.xverum_fixtures import credit_case, connection_case, provisional_pg, execution_api, pg
from tests.test_xverum_dispatch_db import dispatch_case, thread_entry, native_dispatch, linked_task


def test_trusted_enrichment_owner_exists():
    assert importlib.util.find_spec('buyeros_api.services.xverum_enrichment'), 'reviewed native enrichment owner missing'


@pytest.mark.parametrize('projection,expected', [
    ({'company_name':'Synthetic','website':'https://other.example'}, 'conflicting'),
    ({'company_name':'Synthetic','website':None}, 'unresolved'),
    ({'company_name':'Synthetic','website':'https://synthetic.example'}, 'resolved'),
    ({'full_name':'Person','company_name':None,'experience':[{'company_name':'Synthetic','end_time':None}]}, 'unresolved'),
])
def test_identity_never_infers_domain_or_current_employment(projection, expected):
    from buyeros_api.services.xverum_enrichment import identity_match
    assert identity_match('Synthetic','synthetic.example',projection)==expected


def test_enrichment_storage_relation_exists(isolated_seeded):
    with psycopg.connect(isolated_seeded) as db:
        assert db.execute("SELECT to_regclass('public.xverum_enrichments')").fetchone()[0], 'durable reviewed proof missing'


@pytest.fixture
def journey(dispatch_case,monkeypatch,request):
    from buyeros_api.sales.contracts import XverumCompanyCard, XverumCompanyDetail
    from buyeros_api.services.xverum_quotes import quote_details,confirm_quote
    from tests.test_xverum_dispatch_db import select_receipt
    c=dispatch_case
    card={**{k:None for k in XverumCompanyCard.model_fields},'id':'1','company_name':'Synthetic','website':'https://synthetic.example'}
    detail={**{k:None for k in XverumCompanyDetail.model_fields},'company_name':'SYNTHETIC','website':'https://synthetic.example',
        'specialties':[],'locations':[],'industry':'Synthetic procurement'}
    c.projections={'search_company_xverum':{'result_type':'company','results':[card],'total_count':1,'page':1,'page_size':5},
        'enrich_company_xverum':detail}
    assert native_dispatch(c).state=='done'
    c.language=getattr(request,'param','en')
    if c.language=='buyer':
        selected_buyer_context(c);c.language='en'
    c.task=linked_task(c,monkeypatch,c.language)
    async def details(factory):
        async with factory() as s:q=await quote_details(s,c.scope,c.admitted.id,['1'],False)
        async with factory() as s:return await confirm_quote(s,c.scope,q.id,q.fingerprint,'enrichment-detail',task_id=c.task,expected_task_version=1)
    c.search=c.admitted
    c.detail=pg(c,details);select_receipt(c,c.detail)
    assert native_dispatch(c).state=='done'
    return c


def propose(c):
    from buyeros_api.services.xverum_enrichment import propose_enrichment
    async def run(factory):
        async with factory() as s:return await propose_enrichment(s,c.scope,c.buyer,[c.detail.id])
    return pg(c,run)


@pytest.mark.parametrize('journey',['en','zh-HK'],indirect=True)
def test_native_save_canonical_output_and_exact_retry(journey):
    from buyeros_api.services.xverum_enrichment import apply_enrichment
    from buyeros_api.services.sales_outputs import get_output
    from buyeros_api.db.sales_tasks import SalesTask
    import uuid
    c=journey;p=propose(c)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT arguments FROM sales_tasks WHERE id=%s',(c.task,)).fetchone()[0]['language']==c.language
    assert p.identity_match=='resolved'
    assert next(f for f in p.fields if f.field=='company_name').status=='conflict'
    with psycopg.connect(c.dsn) as db:
        before_reviews=db.execute('SELECT count(*) FROM human_reviews').fetchone()[0]
    async def run(factory):
        async with factory() as s:
            task=await s.get(SalesTask,c.task)
            output=await get_output(s,c.scope,uuid.UUID(task.output_ids[0]))
            assert output.availability=='available' and not output.native_refs
        for _ in range(2):
            async with factory() as s:result=await apply_enrichment(s,c.scope,p.id,['company_name'],1,'native-enrichment-save')
            assert result.revision==2
        async with factory() as s:
            task=await s.get(SalesTask,c.task)
            saved=await get_output(s,c.scope,uuid.UUID(task.output_ids[0]))
            assert saved.availability=='available' and saved.native_refs[0]==result
            assert saved.revision==2 and task.state=='completed'
    pg(c,run)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT version FROM project_buyers WHERE id=%s',(c.buyer,)).fetchone()[0]==2
        assert db.execute('SELECT count(*) FROM human_reviews').fetchone()[0]==before_reviews
        assert db.execute('SELECT count(*) FROM sales_output_versions').fetchone()[0]==2
        assert db.execute('SELECT count(*) FROM people').fetchone()[0]==0


@pytest.mark.parametrize('change',['buyer','expiry','generation'])
def test_stale_enrichment_apply_preserves_native_buyer(journey,change):
    from buyeros_api.services.xverum_enrichment import apply_enrichment
    from buyeros_api.api.errors import ApiError
    c=journey;p=propose(c)
    with psycopg.connect(c.dsn) as db:
        if change=='buyer':db.execute('UPDATE project_buyers SET version=version+1 WHERE id=%s',(c.buyer,))
        if change=='expiry':db.execute("UPDATE xverum_tool_receipts SET expires_at=now()-interval '1 second' WHERE stage_id=%s",(c.search.id,))
        if change=='generation':db.execute('UPDATE xverum_connections SET generation=generation+1 WHERE id=%s',(c.id,))
        before=db.execute('SELECT c.display_name,b.version FROM companies c JOIN project_buyers b ON b.company_id=c.id WHERE b.id=%s',(c.buyer,)).fetchone()
    async def run(factory):
        with pytest.raises((ApiError,ValueError)):
            async with factory() as s:await apply_enrichment(s,c.scope,p.id,['company_name'],1,'native-stale-save')
    pg(c,run)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT c.display_name,b.version FROM companies c JOIN project_buyers b ON b.company_id=c.id WHERE b.id=%s',(c.buyer,)).fetchone()==before


@pytest.fixture
def person_journey(dispatch_case,monkeypatch,request):
    from buyeros_api.sales.contracts import XverumPersonDetail
    from buyeros_api.services.xverum_quotes import quote_search,quote_details,confirm_quote
    from tests.test_xverum_dispatch_db import select_receipt
    c=dispatch_case
    c.projections={'enrich_person_xverum':{**{k:None for k in XverumPersonDetail.model_fields},
        'full_name':'Synthetic Buyer','company_name':'Synthetic','position':'Buyer','evidence_summary':'Synthetic',
        'experience':[{'company_name':'Uncertain old company','position':'Unknown','start_time':None,'end_time':None}]},
        'get_email_xverum':{'has_email':True,'emails':[{'email':'buyer@synthetic.example','confidence':'provider-valid','last_checked':None}]}}
    async def search(factory):
        async with factory() as s:q=await quote_search(s,c.scope,c.id,'Synthetic buyer','people',c.buyer)
        async with factory() as s:return await confirm_quote(s,c.scope,q.id,q.fingerprint,'enrichment-people')
    c.search=pg(c,search);select_receipt(c,c.search)
    assert native_dispatch(c).state=='done'
    if getattr(request,'param',None)=='buyer':selected_buyer_context(c)
    c.task=None if getattr(request,'param',None)=='standalone' else linked_task(c,monkeypatch)
    async def detail(factory):
        async with factory() as s:q=await quote_details(s,c.scope,c.search.id,['1'],True)
        async with factory() as s:return await confirm_quote(s,c.scope,q.id,q.fingerprint,'enrichment-person',task_id=c.task,expected_task_version=1)
    c.detail=pg(c,detail);select_receipt(c,c.detail)
    assert native_dispatch(c).state=='done'
    return c


def test_person_native_save_replay_and_quarantine_closes_all_copies(person_journey):
    from buyeros_api.services.xverum_enrichment import apply_enrichment,read_proposal
    from buyeros_api.services.xverum_dispatch import read_evidence
    from buyeros_api.services.sales_outputs import get_output
    from buyeros_api.db.sales_tasks import SalesTask
    from buyeros_api.api.errors import ApiError
    import uuid
    c=person_journey;p=propose(c)
    assert p.identity_match=='resolved'
    async def save(factory):
        for _ in range(2):
            async with factory() as s:
                ref=await apply_enrichment(s,c.scope,p.id,['person_name','job_title','business_email'],1,'person-save-key')
                assert ref.revision==2
        async with factory() as s:
            task=await s.get(SalesTask,c.task)
            saved=await get_output(s,c.scope,uuid.UUID(task.output_ids[0]))
            assert saved.availability=='available'
            assert next(f for f in saved.content.fields if f.field=='business_email').proposed_value is None
            return saved.id
    oid=pg(c,save)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT count(*) FROM people').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM contact_points').fetchone()[0]==1
        assert db.execute('SELECT validity,checked_at FROM contact_points').fetchone()==('unverified_public',None)
        db.execute('UPDATE contact_points SET quarantined=true')
    async def denied(factory):
        for fn in (lambda s:read_proposal(s,c.scope,p.id),lambda s:read_evidence(s,c.scope,c.detail.id),
                   lambda s:apply_enrichment(s,c.scope,p.id,['person_name','job_title','business_email'],1,'person-save-key')):
            with pytest.raises((ValueError,ApiError)):
                async with factory() as s:await fn(s)
        async with factory() as s:
            saved=await get_output(s,c.scope,oid)
            assert saved.availability=='unavailable' and saved.content is None
    pg(c,denied)


@pytest.mark.parametrize('change',['buyer','source_expiry','membership','task_share'])
def test_applied_result_does_not_relax_later_authority(journey,change):
    import uuid
    from buyeros_api.services.xverum_enrichment import apply_enrichment
    from buyeros_api.services.sales_outputs import get_output
    from buyeros_api.db.sales_tasks import SalesTask
    from buyeros_api.api.errors import ApiError
    c=journey;p=propose(c)
    async def save(factory):
        async with factory() as s:
            await apply_enrichment(s,c.scope,p.id,['company_name'],1,'revoke-after-save')
            task=await s.get(SalesTask,c.task)
            return uuid.UUID(task.output_ids[0])
    oid=pg(c,save)
    with psycopg.connect(c.dsn) as db:
        if change=='buyer':db.execute('UPDATE project_buyers SET version=version+1 WHERE id=%s',(c.buyer,))
        if change=='source_expiry':db.execute("UPDATE xverum_tool_receipts SET expires_at=now()-interval '1 second' WHERE stage_id=%s",(c.search.id,))
        if change=='membership':db.execute('UPDATE memberships SET active=false WHERE user_id=%s',(c.scope.actor_id,))
        if change=='task_share':
            # Removing the owning task is forbidden by native FK; use a current intake change.
            db.execute("UPDATE sales_tasks SET arguments=arguments || '{\"purpose\":\"changed\"}'::jsonb WHERE id=%s",(c.task,))
    async def denied(factory):
        with pytest.raises((ValueError,ApiError)):
            async with factory() as s:await apply_enrichment(s,c.scope,p.id,['company_name'],1,'revoke-after-save')
        if change!='membership':
            async with factory() as s:assert (await get_output(s,c.scope,oid)).availability=='unavailable'
    pg(c,denied)


@pytest.mark.parametrize('person_journey',['standalone'],indirect=True)
@pytest.mark.parametrize('invalidation',['expiry','disconnect'])
def test_final_standalone_enrichment_physical_paged_erasure(person_journey,invalidation):
    from buyeros_api.services.xverum_enrichment import apply_enrichment,read_proposal
    from buyeros_api.services.sales_retention import drain_pending
    from buyeros_api.services.xverum_connections import disconnect_xverum
    from buyeros_api.api.errors import ApiError
    c=person_journey
    proposals=[propose(c) for _ in range(52)]
    async def apply(factory):
        async with factory() as s:
            await apply_enrichment(s,c.scope,proposals[0].id,['person_name','business_email'],1,'final-retention-apply')
    pg(c,apply)
    with psycopg.connect(c.dsn) as db:
        before=[db.execute('SELECT * FROM '+t+' ORDER BY id').fetchall() for t in
            ('xverum_credit_settlements','xverum_credit_reservations','cost_events')]
        requests=db.execute('SELECT id,request_id,credits_used FROM xverum_tool_receipts ORDER BY id').fetchall()
        if invalidation=='expiry':
            db.execute("UPDATE xverum_tool_receipts SET expires_at=now()-interval '1 second' WHERE stage_id=%s",(c.detail.id,))
        version=db.execute('SELECT version FROM xverum_connections WHERE id=%s',(c.id,)).fetchone()[0]
    async def sweep(factory):
        if invalidation=='disconnect':
            async with factory() as s:await disconnect_xverum(s,c.scope,version,'final-retention-disconnect')
        else:
            async with factory() as s:return await drain_pending(s,c.ws)
    progress=pg(c,sweep)
    if invalidation=='expiry':
        assert progress==50, 'standalone erasure must report progress to the caller'
    with psycopg.connect(c.dsn) as db:
        count=db.execute("SELECT count(*) FROM xverum_enrichments WHERE proposal='{}'").fetchone()[0]
        assert count==50, 'standalone enrichment must participate in bounded purge pages'
        assert db.execute("SELECT count(*) FROM sales_content_tombstones WHERE kind='source' AND completed_at IS NULL").fetchone()[0]>0
    async def finish(factory):
        pages=[]
        for _ in range(5):
            async with factory() as s:pages.append(await drain_pending(s,c.ws))
        assert pages[0]==2, 'remaining standalone bodies must report nonzero progress'
        assert sum(pages)==2
        for proposal in proposals:
            with pytest.raises((ApiError,ValueError)):
                async with factory() as s:await read_proposal(s,c.scope,proposal.id)
    pg(c,finish)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT proposal,proof,applied FROM xverum_enrichments').fetchall()==[({}, {}, None)]*52
        assert db.execute("SELECT count(*) FROM sales_content_tombstones WHERE kind='source' AND completed_at IS NULL").fetchone()[0]==0
        assert [db.execute('SELECT * FROM '+t+' ORDER BY id').fetchall() for t in
            ('xverum_credit_settlements','xverum_credit_reservations','cost_events')]==before
        assert db.execute('SELECT id,request_id,credits_used FROM xverum_tool_receipts ORDER BY id').fetchall()==requests


@pytest.mark.parametrize('person_journey',['standalone'],indirect=True)
@pytest.mark.parametrize('role',['buyeros_api','buyeros_worker'])
def test_final_enrichment_purge_runtime_temp_guard(person_journey,role):
    from tests.sales_purge_security import check_shadowing
    c=person_journey;p=propose(c)
    check_shadowing(c,role,'xverum_enrichments','buyeros_purge_xverum_enrichment',p.id,'enrichment')
    with psycopg.connect(c.dsn) as db:
        assert not db.execute("SELECT has_column_privilege(%s,'xverum_enrichments','proposal','UPDATE')",(role,)).fetchone()[0]
        assert not db.execute("SELECT has_table_privilege(%s,'xverum_enrichment_dependencies','UPDATE')",(role,)).fetchone()[0]


def selected_buyer_context(c):
    import uuid
    from tests.policy_activation_fixtures import approve_research_fixture,approve_provider_fixture
    from buyeros_api.services.xverum_dispatch import CONTRACT_HASH
    c.native_source=uuid.uuid4()
    with psycopg.connect(c.dsn) as db:
        db.execute("INSERT INTO source_documents(id,workspace_id,project_id,canonical_url,digest,storage_mode,excerpt,retention_until,permission_purpose) VALUES(%s,%s,%s,'https://synthetic.example/about',%s,'excerpt_only','Synthetic purchasing evidence',now()+interval '1 day','account_research')",(c.native_source,c.ws,c.project,'a'*64))
        db.execute("INSERT INTO evidence(id,workspace_id,project_id,company_id,source_document_id,excerpt,stance,is_inference) SELECT %s,%s,%s,company_id,%s,'Synthetic purchasing evidence','qualifies',false FROM project_buyers WHERE id=%s",(uuid.uuid4(),c.ws,c.project,c.native_source,c.buyer))
    from tests.test_run_admission_integration_db import FIXTURE_SEARCH_BINDING
    approve_research_fixture(c.dsn,c.ws,c.project,domains=('synthetic.example',),search=FIXTURE_SEARCH_BINDING)
    approve_provider_fixture(c.dsn,c.ws,c.project,c.scope.actor_id,purpose='contact_research',
        scope={'provider_name':'xverum','account_reference':'synthetic-account','contract_sha256':CONTRACT_HASH},
        domains=['synthetic.example'],actions=['contact.enrich'])
    c.selected_refs=[{'id':str(c.buyer),'version':1,'kind':'buyer','locator':'buyer:'+str(c.buyer),'retention_class':'durable'}]
    c.other_source=uuid.uuid4();c.other_buyer=uuid.uuid4();company=uuid.uuid4()
    with psycopg.connect(c.dsn) as db:
        db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES(%s,%s,'Other','Other')",(company,c.ws))
        db.execute('INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES(%s,%s,%s,%s)',(c.other_buyer,c.ws,c.project,company))
        db.execute("INSERT INTO source_documents(id,workspace_id,project_id,canonical_url,digest,storage_mode,excerpt,retention_until,permission_purpose) VALUES(%s,%s,%s,'https://synthetic.example/other',%s,'excerpt_only','Other selected evidence',now()+interval '1 day','account_research')",(c.other_source,c.ws,c.project,'b'*64))
        db.execute("INSERT INTO evidence(id,workspace_id,project_id,company_id,source_document_id,excerpt,stance,is_inference) VALUES(%s,%s,%s,%s,%s,'Other selected evidence','qualifies',false)",(uuid.uuid4(),c.ws,c.project,company,c.other_source))
    c.selected_refs.append({'id':str(c.other_buyer),'version':1,'kind':'buyer','locator':'buyer:'+str(c.other_buyer),'retention_class':'durable'})



@pytest.mark.parametrize('journey',['buyer'],indirect=True)
def test_final_selected_buyer_company_transition(journey):
    test_native_save_canonical_output_and_exact_retry(journey)


@pytest.mark.parametrize('person_journey',['buyer'],indirect=True)
def test_final_selected_buyer_person_transition(person_journey):
    test_person_native_save_replay_and_quarantine_closes_all_copies(person_journey)


def paid_people_batch(dispatch_case,monkeypatch,count):
    from buyeros_api.sales.contracts import XverumPersonDetail
    from buyeros_api.services.xverum_quotes import quote_search,quote_details,confirm_quote
    from buyeros_api.services.xverum_enrichment import propose_enrichment,apply_enrichment
    from tests.test_xverum_dispatch_db import select_receipt
    from buyeros_api.api.errors import ApiError
    c=dispatch_case;selected_buyer_context(c);c.task=linked_task(c,monkeypatch)
    c.projections={'enrich_person_xverum':lambda args:{**{k:None for k in XverumPersonDetail.model_fields},
        'full_name':'Person '+args['id'],'company_name':'Synthetic','position':'Buyer','evidence_summary':'Synthetic','experience':[]},
        'get_email_xverum':lambda args:{'has_email':True,'emails':[{'email':'person'+args['id']+'@synthetic.example','confidence':'provider-valid','last_checked':None}]}}
    async def search(factory):
        async with factory() as s:q=await quote_search(s,c.scope,c.id,'Synthetic people','people',c.buyer)
        async with factory() as s:return await confirm_quote(s,c.scope,q.id,q.fingerprint,'final-batch-search')
    search=pg(c,search);select_receipt(c,search);assert native_dispatch(c).state=='done'
    async def details(factory):
        async with factory() as s:q=await quote_details(s,c.scope,search.id,[str(i) for i in range(1,count+1)],True)
        async with factory() as s:return await confirm_quote(s,c.scope,q.id,q.fingerprint,'final-batch-details',task_id=c.task,expected_task_version=1)
    detail=pg(c,details);select_receipt(c,detail);assert native_dispatch(c).state=='done'
    calls=c.calls
    return c,detail,calls


@pytest.mark.parametrize('count',[2,3])
def test_final_paid_people_batch_sequential_selected_identity(dispatch_case,monkeypatch,count):
    from buyeros_api.services.xverum_enrichment import propose_enrichment,apply_enrichment
    from buyeros_api.api.errors import ApiError
    c,detail,calls=paid_people_batch(dispatch_case,monkeypatch,count)
    async def save(factory):
        previous=None;results=[]
        from buyeros_api.services.sales_tasks import get_task
        for index in range(1,count+1):
            with pytest.raises((ApiError,ValueError)):
                async with factory() as s:await propose_enrichment(s,c.scope,c.buyer,[detail.id],selected_id='unselected',previous_proposal_id=previous)
            async with factory() as s:
                p=await propose_enrichment(s,c.scope,c.buyer,[detail.id],selected_id=str(index),previous_proposal_id=previous)
                assert p.buyer_version==index
                assert next(f.proposed_value for f in p.fields if f.field=='person_name')=='Person '+str(index)
                assert (await get_task(s,c.scope,c.task)).state==('ready_for_review' if index==1 else 'partially_completed')
            async with factory() as s:
                native=await apply_enrichment(s,c.scope,p.id,['person_name','job_title','business_email'],index,'final-batch-save-'+str(index))
                assert native.revision==index+1
                from buyeros_api.services.sales_tasks import get_task
                assert (await get_task(s,c.scope,c.task)).state==('partially_completed' if index<count else 'completed')
            results.append((p,native));previous=p.id
        from buyeros_api.services.sales_outputs import get_output
        from buyeros_api.db.xverum_enrichment import XverumEnrichment
        from buyeros_api.db.sales_tasks import SalesTask
        import uuid
        for p,native in results:
            async with factory() as s:
                assert await apply_enrichment(s,c.scope,p.id,['person_name','job_title','business_email'],p.buyer_version,'final-batch-save-'+str(p.buyer_version))==native
                producer=await s.get(XverumEnrichment,p.id)
                saved=await get_output(s,c.scope,uuid.UUID(producer.applied['output_id']),producer.output_revision)
                assert saved.availability=='available'
        async with factory() as s:
            task=await s.get(SalesTask,c.task)
            assert (await get_output(s,c.scope,uuid.UUID(task.output_ids[0]))).availability=='available'
        return results
    results=pg(c,save)
    assert c.calls==calls==1+count*2
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT count(*) FROM people').fetchone()[0]==count
        assert db.execute('SELECT count(*) FROM contact_points').fetchone()[0]==count
        db.execute('UPDATE project_buyers SET version=version+1 WHERE id=%s',(c.buyer,))
    async def denied(factory):
        for p,native in results:
            with pytest.raises((ApiError,ValueError)):
                async with factory() as s:await apply_enrichment(s,c.scope,p.id,['person_name','job_title','business_email'],p.buyer_version,'final-batch-save-'+str(p.buyer_version))
    pg(c,denied);assert c.calls==calls


@pytest.mark.parametrize('count',[2,3])
def test_final_browser_paid_people_batch(dispatch_case,monkeypatch,count):
    from tests.sales_final_browser import run_browser
    from tests.test_xverum_connections import headers
    c,detail,calls=paid_people_batch(dispatch_case,monkeypatch,count)
    with psycopg.connect(c.dsn) as db:
        thread=db.execute('SELECT thread_id FROM sales_tasks WHERE id=%s',(c.task,)).fetchone()[0]
    run_browser(c.client,{'phase':'people','count':count,'workspace':str(c.ws),'project':str(c.project),
        'thread':str(thread),'task':str(c.task),'buyer':str(c.buyer)},headers())
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT version FROM project_buyers WHERE id=%s',(c.buyer,)).fetchone()[0]==count+1
        assert db.execute('SELECT count(*) FROM people').fetchone()[0]==count
        assert db.execute('SELECT count(*) FROM contact_points').fetchone()[0]==count
    assert c.calls==calls==1+count*2


@pytest.mark.parametrize('journey',['buyer'],indirect=True)
@pytest.mark.parametrize('loss',['other_buyer','other_source'])
def test_final_selected_contacts_reject_unrelated_context_changes(journey,loss):
    from buyeros_api.services.xverum_enrichment import apply_enrichment
    from buyeros_api.services.sales_tasks import get_task
    from buyeros_api.api.errors import ApiError
    c=journey;p=propose(c);calls=c.calls
    async def save(factory):
        async with factory() as s:await apply_enrichment(s,c.scope,p.id,['company_name'],1,'final-context-save')
        async with factory() as s:assert (await get_task(s,c.scope,c.task)).state=='completed'
    pg(c,save)
    with psycopg.connect(c.dsn) as db:
        if loss=='other_buyer':db.execute('UPDATE project_buyers SET version=version+1 WHERE id=%s',(c.other_buyer,))
        else:db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c.other_source,))
    async def denied(factory):
        with pytest.raises((ApiError,ValueError)):
            async with factory() as s:await apply_enrichment(s,c.scope,p.id,['company_name'],1,'final-context-save')
        with pytest.raises((ApiError,ValueError)):
            async with factory() as s:await get_task(s,c.scope,c.task)
    pg(c,denied);assert c.calls==calls
