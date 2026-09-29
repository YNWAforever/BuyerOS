"""T12 heartbeat is persisted by the worker role after broker-delivered sweep."""
import psycopg

from buyeros_worker.tasks import record_worker_heartbeat_sync


def test_worker_role_can_record_heartbeat_without_schema_ownership(migrated, monkeypatch):
    with psycopg.connect(migrated, autocommit=True) as owner:
        owner.execute("DELETE FROM worker_heartbeats")
        owner.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
        owner.execute("GRANT USAGE ON SCHEMA public TO buyeros_worker")
    worker_dsn = migrated.replace('buyeros:buyeros', 'buyeros_worker:test-only', 1)
    monkeypatch.setenv('BUYEROS_DATABASE_URL', worker_dsn)
    try:
        record_worker_heartbeat_sync()
        with psycopg.connect(migrated) as owner:
            row = owner.execute("SELECT broker_state, observed_at IS NOT NULL FROM worker_heartbeats WHERE worker_id='celery-sweeper'").fetchone()
            assert row == ('ready', True)
            role = owner.execute("SELECT rolbypassrls FROM pg_roles WHERE rolname='buyeros_worker'").fetchone()
            assert role == (False,)
    finally:
        with psycopg.connect(migrated, autocommit=True) as owner:
            owner.execute("DELETE FROM worker_heartbeats")
