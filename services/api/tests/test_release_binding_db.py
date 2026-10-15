"""Real owned PostgreSQL verification of the release probe's runtime pool."""
import pytest
import psycopg
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import create_async_engine

from buyeros_api.services.release_binding import database_target_sha256,read_runtime_binding
from conftest import runtime_role_dsn


@pytest.mark.asyncio
async def test_binding_reads_current_runtime_database_without_elevated_login(seeded):
    dsn=runtime_role_dsn(seeded)
    engine=create_async_engine(dsn.replace('postgresql://','postgresql+psycopg://',1))
    with psycopg.connect(seeded, autocommit=True) as owner:
        owner.execute('GRANT SELECT(version_num) ON public.alembic_version TO buyeros_api')
    try:
        value=await read_runtime_binding(engine,'a'*40,'dpl_ownedtest')
        assert value['schema_head']=='0054_buyer_source_checks'
        assert value['db_target_sha256']==database_target_sha256(dsn)
        assert value['deployment_id']=='dpl_ownedtest'
        assert dsn not in str(value)
    finally:
        await engine.dispose()
        with psycopg.connect(seeded, autocommit=True) as owner:
            owner.execute('REVOKE SELECT(version_num) ON public.alembic_version FROM buyeros_api')


@pytest.mark.asyncio
async def test_binding_refuses_unreadable_schema_metadata(seeded):
    engine=create_async_engine(runtime_role_dsn(seeded).replace('postgresql://','postgresql+psycopg://',1))
    try:
        with pytest.raises(ProgrammingError):
            await read_runtime_binding(engine,'a'*40,'dpl_ownedtest')
    finally:
        await engine.dispose()

@pytest.mark.asyncio
async def test_configuration_reports_actual_disabled_and_enabled_worker_state(isolated_seeded):
    seeded=isolated_seeded
    from buyeros_api.services.release_configuration import read_runtime_configuration
    from buyeros_api.settings import Settings
    settings=Settings(runtime_source_sha='a'*40,runtime_deployment_id='dpl_ownedtest',
                      paid_admission_enabled=False,delivery_admission_enabled=False,cloudflare_execution_enabled=False)
    engine=create_async_engine(runtime_role_dsn(seeded).replace('postgresql://','postgresql+psycopg://',1))
    with psycopg.connect(seeded,autocommit=True) as owner:
        prior=owner.execute('SELECT enabled FROM public.worker_runtime_control WHERE singleton=1').fetchone()[0]
        owner.execute('GRANT SELECT(enabled) ON public.worker_runtime_control TO buyeros_api')
    try:
        for enabled,expected in ((False,'disabled'),(True,'active')):
            with psycopg.connect(seeded,autocommit=True) as owner:
                owner.execute('UPDATE public.worker_runtime_control SET enabled=%s,epoch=epoch+1 WHERE singleton=1',(enabled,))
            value=await read_runtime_configuration(engine,settings)
            assert value['activation']['worker']==expected
            assert value['activation']['providers']=='disabled' and value['activation']['delivery']=='disabled'
    finally:
        await engine.dispose()
        with psycopg.connect(seeded,autocommit=True) as owner:
            owner.execute('UPDATE public.worker_runtime_control SET enabled=%s,epoch=epoch+1 WHERE singleton=1',(prior,))
            owner.execute('REVOKE SELECT(enabled) ON public.worker_runtime_control FROM buyeros_api')
