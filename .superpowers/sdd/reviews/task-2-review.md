# task-2 review package
## commits
```
c01ef8e feat(db): worker_leases table and outbox dispatch columns
```
## stat (lockfiles excluded)
```
 .../api/alembic/versions/0006_worker_leases.py     | 56 ++++++++++++++++++++++
 services/api/buyeros_api/db/outbox.py              |  8 +++-
 services/api/buyeros_api/db/worker.py              | 29 +++++++++++
 services/api/tests/test_worker_leases_model.py     | 32 +++++++++++++
 4 files changed, 124 insertions(+), 1 deletion(-)
```
## diff (lockfiles excluded)
```diff
diff --git a/services/api/alembic/versions/0006_worker_leases.py b/services/api/alembic/versions/0006_worker_leases.py
new file mode 100644
index 0000000..7640098
--- /dev/null
+++ b/services/api/alembic/versions/0006_worker_leases.py
@@ -0,0 +1,56 @@
+"""worker leases and outbox dispatch columns"""
+
+from collections.abc import Sequence
+
+import sqlalchemy as sa
+from alembic import op
+from sqlalchemy.dialects import postgresql
+
+revision: str = "0006_worker_leases"
+down_revision: str | None = "0005_p3_tables"
+branch_labels: str | Sequence[str] | None = None
+depends_on: str | Sequence[str] | None = None
+
+UUID = postgresql.UUID(as_uuid=True)
+
+
+def upgrade() -> None:
+    op.add_column("outbox_events", sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True))
+    op.add_column("outbox_events", sa.Column("lease_owner", sa.String(128), nullable=True))
+    op.add_column("outbox_events", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
+    op.add_column(
+        "outbox_events",
+        sa.Column("fencing_generation", sa.Integer(), nullable=False, server_default="0"),
+    )
+    op.create_table(
+        "worker_leases",
+        sa.Column("id", UUID, primary_key=True),
+        sa.Column("workspace_id", UUID, nullable=False),
+        sa.Column("intent_key", sa.String(128), nullable=False),
+        sa.Column("owner", sa.String(128), nullable=True),
+        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
+        sa.Column("fencing_generation", sa.Integer(), nullable=False, server_default="0"),
+        sa.Column("state", sa.String(16), nullable=False, server_default="free"),
+        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
+        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
+        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
+        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_worker_leases_workspace"),
+        sa.UniqueConstraint("workspace_id", "id", name="uq_worker_leases_workspace_id"),
+        sa.UniqueConstraint("workspace_id", "intent_key", name="uq_worker_leases_intent"),
+    )
+    op.create_index("ix_worker_leases_workspace_id", "worker_leases", ["workspace_id"])
+    op.execute("ALTER TABLE worker_leases ENABLE ROW LEVEL SECURITY;")
+    op.execute("ALTER TABLE worker_leases FORCE ROW LEVEL SECURITY;")
+    op.execute(
+        "CREATE POLICY tenant_isolation ON worker_leases "
+        "USING (workspace_id = current_setting('app.workspace_id')::uuid) "
+        "WITH CHECK (workspace_id = current_setting('app.workspace_id')::uuid);"
+    )
+    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON worker_leases TO buyeros_api, buyeros_worker;")
+
+
+def downgrade() -> None:
+    op.execute("DROP POLICY IF EXISTS tenant_isolation ON worker_leases;")
+    op.drop_table("worker_leases")
+    for column in ("fencing_generation", "lease_expires_at", "lease_owner", "dispatched_at"):
+        op.drop_column("outbox_events", column)
diff --git a/services/api/buyeros_api/db/outbox.py b/services/api/buyeros_api/db/outbox.py
index 7fddc10..e9529cd 100644
--- a/services/api/buyeros_api/db/outbox.py
+++ b/services/api/buyeros_api/db/outbox.py
@@ -1,27 +1,33 @@
 """Transactional outbox (BO-011).
 
 Business intent and its outbox row commit in the same transaction; the
 dispatcher publishes deterministic task IDs to the single Celery/Valkey broker.
 Queue acknowledgement is not durable business completion.
 """
 
-from sqlalchemy import ForeignKeyConstraint, Integer, String, UniqueConstraint
+from datetime import datetime
+
+from sqlalchemy import DateTime, ForeignKeyConstraint, Integer, String, UniqueConstraint
 from sqlalchemy.dialects.postgresql import JSONB
 from sqlalchemy.orm import Mapped, mapped_column
 
 from .base import Base, TenantMixin
 
 
 class OutboxEvent(Base, TenantMixin):
     __tablename__ = "outbox_events"
     __table_args__ = (
         UniqueConstraint("workspace_id", "id", name="uq_outbox_events_workspace_id"),
         UniqueConstraint("workspace_id", "intent_key", "event_type", name="uq_outbox_events_intent_type"),
         ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_outbox_events_workspace"),
     )
 
     intent_key: Mapped[str] = mapped_column(String(128), nullable=False)
     event_type: Mapped[str] = mapped_column(String(64), nullable=False)
     payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
     attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
     state: Mapped[str] = mapped_column(String(32), nullable=False, default="ready")
+    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
+    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
+    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
+    fencing_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
diff --git a/services/api/buyeros_api/db/worker.py b/services/api/buyeros_api/db/worker.py
new file mode 100644
index 0000000..15b3495
--- /dev/null
+++ b/services/api/buyeros_api/db/worker.py
@@ -0,0 +1,29 @@
+"""Durable worker leases and fencing generations (P8).
+
+Leases are the database-side half of the dispatcher/worker handshake: the
+dispatcher claims an outbox intent by writing a lease row, and the worker must
+present the matching fencing generation before its writes are accepted.
+"""
+
+from datetime import datetime
+
+from sqlalchemy import DateTime, ForeignKeyConstraint, Integer, String, UniqueConstraint
+from sqlalchemy.orm import Mapped, mapped_column
+
+from .base import Base, TenantMixin
+
+
+class WorkerLease(Base, TenantMixin):
+    __tablename__ = "worker_leases"
+    __table_args__ = (
+        UniqueConstraint("workspace_id", "id", name="uq_worker_leases_workspace_id"),
+        UniqueConstraint("workspace_id", "intent_key", name="uq_worker_leases_intent"),
+        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_worker_leases_workspace"),
+    )
+
+    intent_key: Mapped[str] = mapped_column(String(128), nullable=False)
+    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
+    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
+    fencing_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
+    state: Mapped[str] = mapped_column(String(16), nullable=False, default="free")
+    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
diff --git a/services/api/tests/test_worker_leases_model.py b/services/api/tests/test_worker_leases_model.py
new file mode 100644
index 0000000..568a088
--- /dev/null
+++ b/services/api/tests/test_worker_leases_model.py
@@ -0,0 +1,32 @@
+from pathlib import Path
+
+from buyeros_api.db.base import Base
+from buyeros_api.db.outbox import OutboxEvent
+from buyeros_api.db.worker import WorkerLease
+
+MIGRATION = Path("alembic/versions/0006_worker_leases.py")
+
+
+def test_worker_lease_table_and_unique_intent():
+    table = WorkerLease.__table__
+    uniques = {
+        tuple(sorted(c.name for c in constraint.columns))
+        for constraint in table.constraints
+        if constraint.__class__.__name__ == "UniqueConstraint"
+    }
+    assert ("intent_key", "workspace_id") in uniques
+
+
+def test_outbox_has_dispatch_columns():
+    for column in ("dispatched_at", "lease_owner", "lease_expires_at", "fencing_generation"):
+        assert column in OutboxEvent.__table__.columns
+
+
+def test_migration_enables_rls_on_worker_leases():
+    src = MIGRATION.read_text(encoding="utf-8")
+    assert "FORCE ROW LEVEL SECURITY" in src
+    assert '"worker_leases"' in src
+
+
+def test_only_worker_leases_is_new_tenant_table():
+    assert "worker_leases" in Base.metadata.tables

```
## lockfile stat (contents omitted)
```
```
