"""Populated rollback never revives private unknown payload or releases its hold."""
import asyncio
from datetime import datetime,timezone
import psycopg,pytest
from alembic import command
from alembic.config import Config
from buyeros_api.db.session import tenant_session
from buyeros_api.providers.base import ProviderIntent
from buyeros_api.settings import get_settings
from buyeros_api.services.receipt_retention import expire_provider_receipts
from tests.test_live_contact_db import contact_case,held
from tests.test_provider_receipt_retention_db import expiring_engines
from tests.test_lookup_quotes_db import quote_case
from tests.test_buyer_review_db import api
from tests.conftest import ALEMBIC_INI,SERVICE_ROOT,runtime_role_dsn

def test_unknown_redacted_payload_and_hash_survive_downgrade_and_reupgrade(contact_case,monkeypatch):
    case=contact_case
    async def exercise(m,engine,first,store,ref,cipher):
        with psycopg.connect(case['dsn']) as db:db.execute("UPDATE provider_operations SET status='submitting' WHERE id=%s",(case['operation'],))
        intent=ProviderIntent(case['request'].key,'contact','US','en','Procurement manager')
        assert (await store.claim(intent))[1];await store.finish(ref,state='unknown')
        with psycopg.connect(case['dsn']) as db:expiry=db.execute('SELECT retention_until FROM contact_receipts WHERE id=%s',(ref,)).fetchone()[0]
        await asyncio.sleep(max(0,(expiry-datetime.now(timezone.utc)).total_seconds())+0.05)
        async with tenant_session(first.engine,case['workspace']) as session:assert await expire_provider_receipts(session,now=datetime.now(timezone.utc),policy_version='owned-c19-v1',limit=1)
        saved=await store.get(ref);assert saved['state']=='redacted'
        config=Config(str(ALEMBIC_INI));config.set_main_option('script_location',str(SERVICE_ROOT/'alembic'))
        monkeypatch.setenv('BUYEROS_DATABASE_URL',case['dsn']);get_settings.cache_clear()
        from tests.migration_guards import invoke_revision
        try:
            with pytest.raises(RuntimeError,match='preserve controller policy history'):
                command.downgrade(config,'0042_c61_contact_receipts')
            invoke_revision(case['dsn'],config,'0043_c61_receipt_retention')
            assert await store.get(ref)==saved
            from buyeros_api.services.worker_recovery import set_execution_runtime
            with psycopg.connect(case['dsn']) as db:epoch=db.execute('SELECT epoch FROM worker_runtime_control WHERE singleton=1').fetchone()[0]
            paused=set_execution_runtime(case['dsn'],expected_epoch=epoch,backend='celery',enabled=False,reason='owned rollback dry run')
            assert paused['epoch']==epoch and paused['enabled'] is False and paused['applied'] is False
            with pytest.raises(ValueError,match='0042'):await store.claim(intent)
        finally:
            invoke_revision(case['dsn'],config,'0056_policy_activation','_fences',('0056_policy_activation',))
            monkeypatch.setenv('BUYEROS_DATABASE_URL',runtime_role_dsn(case['dsn']));get_settings.cache_clear()
        assert await store.get(ref)==saved and not (await store.claim(intent))[1] and held(case)[1]==0
    asyncio.run(expiring_engines(case,exercise))
