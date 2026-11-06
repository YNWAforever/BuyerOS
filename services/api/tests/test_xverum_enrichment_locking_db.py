"""Bounded two-transaction tests for policy/USD-before-thread composition."""
import asyncio,time,uuid
from concurrent.futures import ThreadPoolExecutor
import psycopg
import pytest
from sqlalchemy import text
from tests.xverum_fixtures import credit_case,connection_case,provisional_pg,execution_api,pg
from tests.test_xverum_dispatch_db import dispatch_case,thread_entry
from tests.test_xverum_enrichment_db import journey,propose


@pytest.mark.parametrize('entry',['output','planning','apply'])
def test_enrichment_composition_takes_gates_before_thread(journey,entry):
    from buyeros_api.services.xverum_dispatch import gates
    from buyeros_api.services.sales_outputs import get_output
    from buyeros_api.services.sales_tasks import task_row
    from buyeros_api.services.xverum_enrichment import apply_enrichment
    from buyeros_api.execution.sales_tasks import preview_step
    from buyeros_api.sales.contracts import ActionProposal
    from buyeros_api.db.sales_tasks import SalesTask
    c=journey;proposal=propose(c)
    async def entrypoint(factory):
        async with factory() as s:
            await s.execute(text("SET LOCAL lock_timeout='5s'"))
            if entry=='output':
                task=await s.get(SalesTask,c.task)
                assert (await get_output(s,c.scope,uuid.UUID(task.output_ids[0]))).availability=='available'
            elif entry=='planning':
                # A typed provider action must still hit the model native-identity
                # guard, but only after the canonical gates and task authority.
                action=ActionProposal(id=uuid.uuid4(),capability='search_company_xverum',
                    arguments={'query':'Synthetic'},source_versions=[])
                with pytest.raises(ValueError,match='native source/adapter'):
                    await preview_step(s,c.scope,c.task,action)
            else:assert (await apply_enrichment(s,c.scope,proposal.id,['company_name'],1,'concurrent-apply')).revision==2
    with ThreadPoolExecutor(max_workers=1) as pool:
        async def holder(factory):
            async with factory() as s:
                await s.execute(text("SET LOCAL lock_timeout='1500ms'"))
                await gates(s,c.ws)
                pid=await s.scalar(text('SELECT pg_backend_pid()'))
                future=pool.submit(pg,c,entrypoint)
                deadline=time.monotonic()+5
                blocked=False
                while time.monotonic()<deadline:
                    with psycopg.connect(c.dsn) as db:
                        blocked=db.execute('SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE %s=ANY(pg_blocking_pids(pid)))',(pid,)).fetchone()[0]
                    if blocked:break
                    await asyncio.sleep(.02)
                assert blocked,'entry point never reached the held workspace gate'
                # If the other transaction took the thread first, this deadlocks.
                await task_row(s,c.scope,c.task,edit=True)
            await asyncio.to_thread(future.result,5)
        pg(c,holder)
