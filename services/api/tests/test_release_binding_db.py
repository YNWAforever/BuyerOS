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
