"""C17 existing shared-core stale-basis acceptance; owned fixture, no model accuracy claim."""
import asyncio,uuid
import psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.execution.fit_runner import FitDomainRunner
from tests.test_discovery_runner_db import (ACTOR_ID,PROJECT_A,RUN_ID,WS_A,SearchFixture,_execute,discovery_case)

@pytest.fixture(autouse=True)
def cleanup_owned_model_receipts(discovery_case):
    # Runs before the preexisting parent cleanup. Populated receipt FKs should
    # block accidental deletion; fixture owner clears only this owned scope.
    owner_dsn,_=discovery_case
    yield
    with psycopg.connect(owner_dsn) as db:
        # Epochs remain monotonic, including within the owned fixture.
        if db.execute("SELECT to_regclass('public.model_receipts')").fetchone()[0]:db.execute('DELETE FROM model_receipts WHERE workspace_id=%s',(WS_A,))
        db.execute("DELETE FROM outbox_events WHERE workspace_id=%s AND intent_key LIKE 'c17-model:%%'",(WS_A,))
        db.execute("DELETE FROM provider_operations WHERE workspace_id=%s AND intent_key LIKE 'c17-model:%%'",(WS_A,))
        db.execute('ALTER ROLE buyeros_api NOLOGIN')
        db.execute('ALTER ROLE buyeros_worker NOLOGIN')

@pytest.mark.parametrize('change',['offer','icp','evidence','actor'])
def test_stale_basis_cannot_persist_match(discovery_case,change):
    owner_dsn,runtime_dsn=discovery_case
    assert _execute(runtime_dsn,SearchFixture(owner_dsn))=='done'
    with psycopg.connect(owner_dsn) as db:
        buyer=db.execute('SELECT id FROM project_buyers WHERE project_id=%s',(PROJECT_A,)).fetchone()[0]
        canonical=db.execute('SELECT id FROM users ORDER BY id').fetchall()
    async def exercise():
        engine=create_async_engine(runtime_dsn.replace('postgresql://','postgresql+psycopg://',1))
        try:
            runner=FitDomainRunner(engine,uuid.UUID(WS_A),uuid.UUID(RUN_ID),buyer)
            state={'workspace_id':WS_A,'run_id':RUN_ID,'buyer_id':str(buyer),'workflow_version':'fit-v1','attempt':1}
            state.update(await runner.load_basis(state));state.update(await runner.hard_exclusions(state));state.update(await runner.fit(state));state.update(await runner.verify(state))
            assert state['verified'] is True # the result was verified under the old basis
            with psycopg.connect(owner_dsn) as db:
                if change=='offer':db.execute('UPDATE projects SET offer_revision=offer_revision+1 WHERE id=%s',(PROJECT_A,))
                elif change=='icp':db.execute('UPDATE projects SET active_icp_version_id=NULL WHERE id=%s',(PROJECT_A,))
                elif change=='evidence':db.execute('UPDATE evidence SET version=version+1 WHERE run_id=%s',(RUN_ID,))
                else:db.execute('UPDATE memberships SET active=false,version=version+1 WHERE workspace_id=%s AND user_id=%s',(WS_A,ACTOR_ID))
            with pytest.raises(ValueError,match='stale|basis changed|revoked'):await runner.persist(state)
        finally:await engine.dispose()
    asyncio.run(exercise())
    with psycopg.connect(owner_dsn) as db:
        assert db.execute('SELECT count(*) FROM fit_assessments WHERE run_id=%s',(RUN_ID,)).fetchone()==(0,)
        assert db.execute('SELECT id FROM users ORDER BY id').fetchall()==canonical
        assert db.execute('SELECT count(*) FROM evidence WHERE run_id=%s',(RUN_ID,)).fetchone()[0]>0


@pytest.mark.parametrize('change',['none','offer','evidence','actor'])
def test_live_model_receipt_persists_only_current_grounded_assessment(discovery_case,change):
    import importlib,hashlib
    from datetime import datetime,timezone
    from buyeros_api.providers.model import ModelRoute
    owner_dsn,runtime_dsn=discovery_case
    assert _execute(runtime_dsn,SearchFixture(owner_dsn))=='done'
    with psycopg.connect(owner_dsn) as db:buyer=db.execute('SELECT id FROM project_buyers WHERE project_id=%s',(PROJECT_A,)).fetchone()[0]
    cls=getattr(importlib.import_module('buyeros_api.execution.live_fit_runner'),'LiveFitDomainRunner')
    async def exercise():
        from buyeros_api.providers.live_model import ModelRequest,canonical_json,validate_live_proposal
        engine=create_async_engine(runtime_dsn.replace('postgresql://','postgresql+psycopg://',1))
        class Receipts:
            async def get(self,ref):return saved
        try:
            runner=cls(engine,uuid.UUID(WS_A),uuid.UUID(RUN_ID),buyer,receipts=Receipts())
            state={'workspace_id':WS_A,'run_id':RUN_ID,'buyer_id':str(buyer),'workflow_version':'fit-v1','attempt':1}
            state.update(await runner.load_basis(state));basis=await runner.model_basis(state)
            assert basis['company_id'] and basis['actor_id']==ACTOR_ID and basis['offer_revision']==1
            assert basis['evidence'] and all(x['current'] and x['source_excerpt'] for x in basis['evidence'])
            selected=ModelRoute('c61-offline-prompt-v1',frozenset(),20000,1000,30,0,'offline-model-route-v1')
            request=ModelRequest('offline-model:'+buyer.hex,basis,selected,'offline-owned-model-v1','US','en','company')
            item=basis['evidence'][0]
            proposal={'company_id':basis['company_id'],'verdict':'match','rationale':'Offline proposal, human review required','citations':[{'evidence_id':item['id'],'version':item['version'],'source_id':item['source_id'],'source_hash':item['source_hash'],'quote':item['excerpt']}]}
            response={'provider_ref':'resp_offline_owned_1','proposal':proposal,'assessment':validate_live_proposal(proposal,basis),'usage':{'input_tokens':100,'output_tokens':60,'total_tokens':160},'model_id':request.model_id,'prompt_version':selected.prompt_version}
            saved={'ref':str(uuid.uuid4()),'request':request,'state':'received','response':response,'digest':hashlib.sha256(canonical_json(response)).hexdigest()}
            state['proposal_id']=saved['ref'];state.update(await runner.verify(state));assert state['verified'] is True
            forged={**state,'hard_excluded':True}
            with pytest.raises(ValueError,match='unproven'):await runner.persist(forged)
            with psycopg.connect(owner_dsn) as db:
                if change=='offer':db.execute('UPDATE projects SET offer_revision=offer_revision+1 WHERE id=%s',(PROJECT_A,))
                elif change=='evidence':db.execute('UPDATE evidence SET version=version+1 WHERE run_id=%s',(RUN_ID,))
                elif change=='actor':db.execute('UPDATE memberships SET active=false,version=version+1 WHERE workspace_id=%s AND user_id=%s',(WS_A,ACTOR_ID))
            if change=='none':
                first=await runner.persist(state);second=await runner.persist(state);assert first==second
            else:
                with pytest.raises(ValueError,match='stale|basis changed|revoked'):await runner.persist(state)
        finally:await engine.dispose()
    asyncio.run(exercise())
    with psycopg.connect(owner_dsn) as db:
        rows=db.execute('SELECT verdict,assessment_details,fit_algorithm_version FROM fit_assessments WHERE run_id=%s',(RUN_ID,)).fetchall()
        assert len(rows)==(1 if change=='none' else 0)
        if rows:
            assert rows[0][0]=='match' and rows[0][2]=='live-model-v1'
            trace=rows[0][1]['model_provenance'];assert trace['model_id']=='offline-owned-model-v1' and trace['prompt_version']=='c61-offline-prompt-v1' and trace['response_hash']
            assert trace['offer_revision']==1 and trace['icp_version_id'] and trace['evidence_revisions']
            assert rows[0][1]['next_action']=='human_review' and 'source_excerpt' not in repr(rows[0][1])


@pytest.mark.parametrize('outcome',['received','lost-response','epoch','revoke','offer'])
def test_live_model_pg_receipt_survives_restart_without_new_submission(discovery_case,monkeypatch,outcome):
    import importlib,hashlib,json
    from datetime import datetime,timezone
    from decimal import Decimal
    from dataclasses import replace
    from buyeros_api.providers.model import ModelRoute
    from buyeros_api.providers.base import Money,ProviderCapability,ProviderIntent
    from buyeros_api.execution.external_runner import execute_external,input_digest
    from buyeros_api.db.session import tenant_session
    from buyeros_api.services.budget_service import ensure_period_accounts,reserve_operation
    from buyeros_api.providers import base
    owner_dsn,runtime_dsn=discovery_case;assert _execute(runtime_dsn,SearchFixture(owner_dsn))=='done'
    monkeypatch.setattr(base,'SELECTED_LIVE_PROVIDERS',frozenset({'openai-responses'})) # owned synthetic protocol only
    m=importlib.import_module('buyeros_api.providers.live_model');cls=getattr(m,'PostgresModelReceipts')
    from buyeros_api.execution.live_fit_runner import LiveFitDomainRunner
    route=ModelRoute('c61-offline-prompt-v1',frozenset(),20000,1000,30,0,'offline-model-route-v1')
    cap=ProviderCapability(provider='openai-responses',adapter_version='c61-model-v1',service='model',markets=frozenset({'US'}),languages=frozenset({'en'}),roles=frozenset({'company'}),auth_model='server-key',pricing_version='offline-model-price-v1',max_liability=Money(Decimal('0.100000'),'USD'),idempotency='verified',status='verified',callback='unsupported',cancel='unsupported',retention='offline-only',verified_at=datetime.now(timezone.utc),source_urls=('https://developers.openai.com/api/reference/responses/overview',))
    operation=uuid.uuid4();outbox=uuid.uuid4();intent=ProviderIntent('c17-model:'+operation.hex,'model','US','en','company');calls=[]
    with psycopg.connect(owner_dsn) as db:
        buyer=db.execute('SELECT id FROM project_buyers WHERE project_id=%s',(PROJECT_A,)).fetchone()[0]
        db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
        db.execute("ALTER ROLE buyeros_api LOGIN PASSWORD 'test-only'")
        db.execute('UPDATE budget_accounts SET approved_limit=20 WHERE workspace_id=%s',(WS_A,))
    async def exercise():
        from urllib.parse import urlsplit,urlunsplit
        parsed=urlsplit(owner_dsn)
        api_dsn=urlunsplit(parsed._replace(netloc='buyeros_api:test-only@'+parsed.netloc.split('@')[1]))
        engine=create_async_engine(api_dsn.replace('postgresql://','postgresql+psycopg://',1))
        worker_dsn=urlunsplit(parsed._replace(netloc='buyeros_worker:test-only@'+parsed.netloc.split('@')[1]))
        worker_engine=create_async_engine(worker_dsn.replace('postgresql://','postgresql+psycopg://',1))
        try:
            async with tenant_session(engine,uuid.UUID(WS_A)) as session:
                await ensure_period_accounts(session,uuid.UUID(WS_A),uuid.UUID(PROJECT_A),None,'discovery')
                await reserve_operation(session,operation,{'workspace_id':uuid.UUID(WS_A),'project_id':uuid.UUID(PROJECT_A),'category':'discovery'},cap.max_liability.amount,'USD',cap.pricing_version)
            with psycopg.connect(owner_dsn) as db:
                db.execute("INSERT INTO provider_operations(id,workspace_id,intent_key,capability,input_hash,status) VALUES(%s,%s,%s,'model',%s,'reserved')",(operation,WS_A,intent.key,input_digest(intent)))
                backend,epoch=db.execute('SELECT backend,epoch FROM worker_runtime_control').fetchone()
                db.execute("INSERT INTO outbox_events(id,workspace_id,intent_key,event_type,payload,state,fencing_generation,runtime_backend,runtime_epoch) VALUES(%s,%s,%s,'provider.external',%s::jsonb,'dispatched',1,%s,%s)",(outbox,WS_A,intent.key,json.dumps({'operation_id':str(operation),'service':'model','market':'US','language':'en','role':'company'}),backend,epoch))
            runner=LiveFitDomainRunner(engine,uuid.UUID(WS_A),uuid.UUID(RUN_ID),buyer,receipts=None)
            state={'workspace_id':WS_A,'run_id':RUN_ID,'buyer_id':str(buyer),'workflow_version':'fit-v1','attempt':1}
            state.update(await runner.load_basis(state));basis=await runner.model_basis(state)
            request=m.ModelRequest(intent.key,basis,route,'offline-owned-model-v1','US','en','company')
            api_store=cls(engine,uuid.UUID(WS_A),cap,model_id=request.model_id,route=route)
            ref=await api_store.prepare(request,operation_id=operation,outbox_id=outbox)
            store=cls(worker_engine,uuid.UUID(WS_A),cap,model_id=request.model_id,route=route)
            if outcome in {'revoke','offer'}:
                with psycopg.connect(owner_dsn) as db:
                    if outcome=='revoke':db.execute('UPDATE memberships SET active=false,version=version+1 WHERE workspace_id=%s AND user_id=%s',(WS_A,ACTOR_ID))
                    else:db.execute('UPDATE projects SET offer_revision=offer_revision+1 WHERE id=%s',(PROJECT_A,))
            class Client:
                model_id=request.model_id
                async def complete(self,value,selected):
                    calls.append(1)
                    with psycopg.connect(owner_dsn) as db:
                        db.execute('SELECT id FROM model_receipts WHERE id=%s FOR UPDATE NOWAIT',(uuid.UUID(ref),))
                        db.execute('SELECT id FROM provider_operations WHERE id=%s FOR UPDATE NOWAIT',(operation,))
                        if outcome=='epoch':db.execute('UPDATE worker_runtime_control SET epoch=epoch+1 WHERE singleton=1')
                    if outcome=='lost-response':raise m.ModelResponseUnknown('offline accepted response lost')
                    item=value['evidence'][0];proposal={'company_id':value['company_id'],'verdict':'match','rationale':'Offline data requires human review','citations':[{'evidence_id':item['id'],'version':item['version'],'source_id':item['source_id'],'source_hash':item['source_hash'],'quote':item['excerpt']}]}
                    return {'provider_ref':'resp_offline_owned_1','proposal':proposal,'assessment':m.validate_live_proposal(proposal,value),'usage':{'input_tokens':100,'output_tokens':60,'total_tokens':160},'model_id':self.model_id,'prompt_version':selected.prompt_version}
            adapter=m.LiveModelAdapter(capability=cap,client=Client(),receipts=store)
            result=await execute_external(worker_engine,uuid.UUID(WS_A),operation,1,adapter,intent,environment='test')
            assert result==('accepted' if outcome=='received' else 'unknown')
            saved=await cls(worker_engine,uuid.UUID(WS_A),cap,model_id=request.model_id,route=route).get(ref)
            assert saved['state']==('received' if outcome=='received' else ('prepared' if outcome in {'revoke','offer'} else ('submitting' if outcome=='epoch' else 'unknown')))
            if outcome=='received':
                assert (await adapter.submit(intent)).state=='accepted' and saved['response']['model_id']==request.model_id
                runner.receipts=api_store;state['proposal_id']=ref;state.update(await runner.verify(state));assert (await runner.persist(state))['assessment_id']
                from sqlalchemy import text
                from sqlalchemy.exc import IntegrityError
                async with tenant_session(worker_engine,uuid.UUID(WS_A)) as session:
                    assert (await session.execute(text("SELECT current_user,(SELECT rolbypassrls FROM pg_roles WHERE rolname=current_user),has_table_privilege(current_user,'model_receipts','INSERT')"))).one()==('buyeros_worker',False,False)
                    assert (await session.execute(text("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname='model_receipts'"))).one()==(True,True)
                async with tenant_session(engine,uuid.UUID(WS_A)) as session:
                    assert (await session.execute(text("SELECT current_user,(SELECT rolbypassrls FROM pg_roles WHERE rolname=current_user),has_table_privilege(current_user,'model_receipts','UPDATE')"))).one()==('buyeros_api',False,False)
                assert await cls(worker_engine,uuid.uuid4(),cap,model_id=request.model_id,route=route).get(ref) is None
                for statement in ["UPDATE model_receipts SET state='prepared'","UPDATE model_receipts SET response='{}'","UPDATE model_receipts SET request='{}'"]:
                    with pytest.raises(IntegrityError):
                        async with tenant_session(worker_engine,uuid.UUID(WS_A)) as session:await session.execute(text(statement))
                from alembic import command
                from alembic.config import Config
                from buyeros_api.settings import get_settings
                from pathlib import Path
                service=Path(__file__).resolve().parents[2]/'api';config=Config(str(service/'alembic.ini'));config.set_main_option('script_location',str(service/'alembic'))
                monkeypatch.setenv('BUYEROS_DATABASE_URL',owner_dsn);get_settings.cache_clear()
                try:
                    command.downgrade(config,'0040_c61_search_receipts')
                    assert await store.get(ref)==saved
                    with pytest.raises(ValueError,match='0041'):await api_store.prepare(request,operation_id=operation,outbox_id=outbox)
                finally:
                    command.upgrade(config,'head')
                    monkeypatch.setenv('BUYEROS_DATABASE_URL',runtime_dsn);get_settings.cache_clear()
                assert await store.get(ref)==saved

            elif outcome=='lost-response':assert (await adapter.submit(intent)).state=='unknown'
            with psycopg.connect(owner_dsn) as db:
                assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(operation,)).fetchone()==('active',Decimal('0.100000'))
                assert db.execute('SELECT count(*) FROM cost_events WHERE operation_id=%s',(operation,)).fetchone()==(0,)
        finally:await engine.dispose();await worker_engine.dispose()
    asyncio.run(exercise());assert len(calls)==(0 if outcome in {'revoke','offer'} else 1)


def test_live_hard_exclusion_persists_without_model_or_receipt(discovery_case):
    import json
    from buyeros_api.db.icp import canonical_hash
    from buyeros_api.execution.live_fit_runner import LiveFitDomainRunner
    from buyeros_worker.research_graph import build_research_graph,checkpoint_config
    from langgraph.checkpoint.memory import MemorySaver
    owner_dsn,runtime_dsn=discovery_case
    with psycopg.connect(owner_dsn) as db:
        icp,content=db.execute('SELECT id,content FROM icp_versions WHERE project_id=%s',(PROJECT_A,)).fetchone()
        content['requirements'][0].update(category='exclude',hard_exclusion=True)
        digest=canonical_hash(content)
        db.execute('UPDATE icp_versions SET content=%s::jsonb,content_hash=%s WHERE id=%s',(json.dumps(content),digest,icp))
        db.execute("UPDATE search_runs SET execution_snapshot=jsonb_set(execution_snapshot,'{icp_content_hash}',to_jsonb(%s::text)) WHERE id=%s",(digest,RUN_ID))
    assert _execute(runtime_dsn,SearchFixture(owner_dsn))=='done'
    with psycopg.connect(owner_dsn) as db:buyer=db.execute('SELECT id FROM project_buyers WHERE project_id=%s',(PROJECT_A,)).fetchone()[0]
    calls=[]
    class Receipts:
        async def get(self,ref):calls.append(ref);raise AssertionError('hard exclusion must not consult a model receipt')
    async def exercise():
        engine=create_async_engine(runtime_dsn.replace('postgresql://','postgresql+psycopg://',1))
        try:
            runner=LiveFitDomainRunner(engine,uuid.UUID(WS_A),uuid.UUID(RUN_ID),buyer,receipts=Receipts())
            graph=build_research_graph(MemorySaver(),runner)
            state={'workspace_id':WS_A,'run_id':RUN_ID,'buyer_id':str(buyer),'workflow_version':'fit-v1','attempt':1}
            result=await graph.ainvoke(state,checkpoint_config(WS_A,RUN_ID,'fit-v1',1,buyer))
            assert result['assessment_id'] and result['hard_excluded'] is True and result['verified'] is True
        finally:await engine.dispose()
    asyncio.run(exercise());assert calls==[]
    with psycopg.connect(owner_dsn) as db:
        assert db.execute('SELECT verdict,fit_algorithm_version FROM fit_assessments WHERE run_id=%s',(RUN_ID,)).fetchone()==('not_a_match','fit-v1')
        assert db.execute('SELECT count(*) FROM model_receipts WHERE workspace_id=%s',(WS_A,)).fetchone()==(0,)
