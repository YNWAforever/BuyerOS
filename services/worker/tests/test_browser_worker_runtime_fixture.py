"""The compatibility browser pump must exercise the real restricted worker role."""
import psycopg
import pytest


def test_browser_fixture_uses_worker_catalog_proof_and_cannot_activate_selector(migrated):
    from tests.fixtures.run_browser_research import prepare_browser_runtime
    from buyeros_api.services.worker_execution import WORKER_ROLE_CATALOG_SQL
    runtime = prepare_browser_runtime(migrated)
    with psycopg.connect(runtime) as db:
        assert db.execute(WORKER_ROLE_CATALOG_SQL).fetchone() == (True,)
        assert db.execute('SELECT backend,enabled FROM worker_runtime_control').fetchone() == ('celery',True)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute('UPDATE worker_runtime_control SET enabled=false,epoch=epoch+1')


def test_browser_runtime_fixture_rejects_nonowned_or_remote_database_before_connection():
    from tests.fixtures.run_browser_research import prepare_browser_runtime
    for dsn in ['postgresql://owner:fake@production.example/buyeros_test_fixture',
                'postgresql://owner:fake@127.0.0.1/working_database']:
        with pytest.raises((ValueError,pytest.UsageError)):
            prepare_browser_runtime(dsn)
