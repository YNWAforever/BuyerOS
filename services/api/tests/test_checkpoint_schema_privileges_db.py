"""Restricted native workers read schema versions and write only checkpoint data."""
import asyncio
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.cloudflare_fixtures import cloudflare_database as migrated
from tests.conftest import ALEMBIC_INI, SERVICE_ROOT, _require_disposable_test_dsn
from tests.test_cloudflare_runtime_probe import probe_module


@pytest.fixture(scope="module")
def schema_worker(migrated):
    _require_disposable_test_dsn(migrated)
    parts = urlsplit(migrated)
    host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    with psycopg.connect(migrated) as owner:
        owner.execute("CREATE ROLE buyeros_schema_fixture LOGIN INHERIT PASSWORD 'test-only' "
                      "NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS")
        owner.execute("GRANT buyeros_worker TO buyeros_schema_fixture")
    return urlunsplit(parts._replace(netloc=f"buyeros_schema_fixture:test-only@{host}:{parts.port}"))


@pytest.mark.parametrize("statement", [
    "INSERT INTO buyeros_graph.checkpoint_migrations(v) VALUES(99)",
    "UPDATE buyeros_graph.checkpoint_migrations SET v=99 WHERE v=9",
    "DELETE FROM buyeros_graph.checkpoint_migrations WHERE v=9",
    "TRUNCATE buyeros_graph.checkpoint_migrations",
])
def test_worker_cannot_mutate_checkpoint_schema_versions(schema_worker, statement):
    with psycopg.connect(schema_worker) as worker:
        assert worker.execute("SELECT max(v),count(*) FROM buyeros_graph.checkpoint_migrations").fetchone() == (9, 10)
        try:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                worker.execute(statement)
        finally:
            worker.rollback()  # retain the original version rows even during RED


def test_runtime_catalog_rejects_reintroduced_checkpoint_version_write(migrated, schema_worker):
    from buyeros_api.services.worker_execution import WORKER_ROLE_CATALOG_SQL
    with psycopg.connect(migrated, autocommit=True) as owner:
        previous = owner.execute("SELECT has_table_privilege('buyeros_schema_fixture', "
                                 "'buyeros_graph.checkpoint_migrations','INSERT')").fetchone()[0]
        owner.execute("GRANT INSERT ON buyeros_graph.checkpoint_migrations TO buyeros_schema_fixture")
        try:
            with psycopg.connect(schema_worker) as worker:
                assert worker.execute(WORKER_ROLE_CATALOG_SQL).fetchone() == (False,)
        finally:
            if not previous:
                owner.execute("REVOKE INSERT ON buyeros_graph.checkpoint_migrations FROM buyeros_schema_fixture")


def test_schema_read_only_worker_resumes_actual_checkpoint_without_replaying(schema_worker):
    records = []
    asyncio.run(probe_module()._checkpoint_probe(schema_worker, records))
    checkpoint = next(row for row in records if row['check'] == 'postgres_checkpoint')
    assert checkpoint['state'] == 'verified'
    assert checkpoint['details'] == {
        'committed_node_replayed': False, 'interrupted_node_resumed': True,
        'cross_tenant_read_closed': True, 'schema_created_at_runtime': False,
    }
    with psycopg.connect(schema_worker) as worker:
        assert worker.execute("SELECT max(v),count(*) FROM buyeros_graph.checkpoint_migrations").fetchone() == (9, 10)


def test_0036_round_trip_keeps_schema_version_grants_read_only(migrated, schema_worker):
    config = Config(str(ALEMBIC_INI))
    config.set_main_option('script_location', str(SERVICE_ROOT / 'alembic'))
    with psycopg.connect(migrated) as owner:
        assert owner.execute('SELECT version_num FROM alembic_version').fetchone()[0] == '0037_bulk_manifests'
    # A compatibility downgrade retains security hardening and all checkpoint data.
    command.downgrade(config, '0035_worker_recovery_probe')
    with psycopg.connect(schema_worker) as worker:
        assert worker.execute("SELECT has_table_privilege(current_user,'buyeros_graph.checkpoint_migrations',"
                              "'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')").fetchone() == (False,)
        assert worker.execute("SELECT max(v),count(*) FROM buyeros_graph.checkpoint_migrations").fetchone() == (9, 10)
    command.upgrade(config, 'head')
    with psycopg.connect(migrated) as owner:
        assert owner.execute('SELECT version_num FROM alembic_version').fetchone()[0] == '0037_bulk_manifests'
        assert owner.execute('SELECT count(*) FROM buyeros_graph.checkpoints').fetchone()[0] > 0


def test_operator_previews_current_head_without_mutating_selector(migrated):
    from buyeros_api.services.worker_recovery import set_execution_runtime
    with psycopg.connect(migrated) as owner:
        before = owner.execute('SELECT backend,enabled,epoch FROM worker_runtime_control').fetchone()
    result = set_execution_runtime(migrated, expected_epoch=before[2], backend='cloudflare',
                                   enabled=False, reason='Owned permission regression dry run')
    assert result['applied'] is False and result['epoch'] == before[2]
    with psycopg.connect(migrated) as owner:
        assert owner.execute('SELECT backend,enabled,epoch FROM worker_runtime_control').fetchone() == before

def test_runtime_selector_still_rejects_unknown_schema_head(migrated):
    from buyeros_api.services.worker_recovery import set_execution_runtime
    with psycopg.connect(migrated,autocommit=True) as db:
        before=db.execute('SELECT backend,enabled,epoch FROM worker_runtime_control').fetchone()
        db.execute("UPDATE alembic_version SET version_num='fixture_unknown_schema'")
        try:
            with pytest.raises(ValueError,match='compatible 0035/0036/0037'):
                set_execution_runtime(migrated,expected_epoch=before[2],backend='cloudflare',enabled=False,reason='Owned unknown schema dry run')
            assert db.execute('SELECT backend,enabled,epoch FROM worker_runtime_control').fetchone()==before
        finally:db.execute("UPDATE alembic_version SET version_num='0037_bulk_manifests'")
