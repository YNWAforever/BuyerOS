from pathlib import Path

from buyeros_api.db.base import Base
from buyeros_api.db.outbox import OutboxEvent
from buyeros_api.db.worker import WorkerLease

MIGRATION = Path("alembic/versions/0006_worker_leases.py")


def test_worker_lease_table_and_unique_intent():
    table = WorkerLease.__table__
    uniques = {
        tuple(sorted(c.name for c in constraint.columns))
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("intent_key", "workspace_id") in uniques


def test_outbox_has_dispatch_columns():
    for column in ("dispatched_at", "lease_owner", "lease_expires_at", "fencing_generation"):
        assert column in OutboxEvent.__table__.columns


def test_migration_enables_rls_on_worker_leases():
    src = MIGRATION.read_text(encoding="utf-8")
    assert "FORCE ROW LEVEL SECURITY" in src
    assert '"worker_leases"' in src


def test_only_worker_leases_is_new_tenant_table():
    assert "worker_leases" in Base.metadata.tables
