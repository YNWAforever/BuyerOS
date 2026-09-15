# P8 Worker and Dispatcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Build is NOT authorized by this document**; execution requires explicit approval under the recorded dependency waiver.

**Goal:** Turn committed outbox intents into durable worker work via a Celery/Valkey dispatcher and worker with DB leases, fencing, a recovery sweeper, run/event emission, and a handler registry containing one real handler (`fetch.evidence`).

**Architecture:** `services/worker/` (`buyeros_worker`) depends on `buyeros_api` by local path so there is one domain package. The dispatcher claims `outbox_events` rows with a DB lease and publishes deterministic intent IDs to Celery/Valkey; the worker resolves the intent, re-derives tenant context, executes a registered handler, and commits state + `run_events` atomically before acking. A sweeper re-enqueues expired leases; fencing generations reject stale writers.

**Tech Stack:** Python 3.12+ + Celery 5 + Valkey/Redis, SQLAlchemy 2 + Alembic (in `buyeros_api`), PostgreSQL 16, uv.

## Global Constraints

- Canonical repository: `YNWAforever/BuyerOS` (planning pack committed at `1512d4c17d4f792e14598d524fdac3c9c37d27e7`; audited source imported at `b804ba8d` tree `b4c6b538…`).
- Plan-only artifact. No commits to remote, pushes, deploys, cloud resources, real migrations on real data, paid calls, mailboxes, or sends.
- One domain package: worker must **not** duplicate models, authorization, budget or policy rules; it imports `buyeros_api`.
- No provider is verified: `run.discover`, `contact.submit`, `draft.generate` are **fail-closed**. Only `fetch.evidence` executes external reads.
- Every unexecuted check is **NOT RUN**.

**File ownership:** `services/worker/**` (new), plus these `buyeros_api` changes: `db/worker.py` (new), `db/outbox.py` (columns), `alembic/versions/0006_worker_leases.py` (new), and `tests/**`. Worker tests live in `services/worker/tests/`.

---

### Task 2: Worker lease model, outbox dispatch columns and migration

**Files:**
- Create: `services/api/buyeros_api/db/worker.py`
- Modify: `services/api/buyeros_api/db/outbox.py`
- Create: `services/api/alembic/versions/0006_worker_leases.py`
- Create: `services/api/tests/test_worker_leases_model.py`

**Interfaces:**
- Produces: `WorkerLease` (`intent_key`, `owner`, `expires_at`, `fencing_generation`, `state`, `attempts`); `OutboxEvent` gains `dispatched_at`, `lease_owner`, `lease_expires_at`, `fencing_generation`.
- Consumes: `Base`, `TenantMixin` (P1).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_worker_leases_model.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_worker_leases_model.py -v` (cwd `services/api`)
Expected: FAIL — `ModuleNotFoundError: buyeros_api.db.worker`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/db/worker.py
from datetime import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin


class WorkerLease(Base, TenantMixin):
    __tablename__ = "worker_leases"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_worker_leases_workspace_id"),
        UniqueConstraint("workspace_id", "intent_key", name="uq_worker_leases_intent"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_worker_leases_workspace"),
    )

    intent_key: Mapped[str] = mapped_column(String(128), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fencing_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="free")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

```python
# services/api/buyeros_api/db/outbox.py  (add columns to OutboxEvent)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fencing_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

```python
# services/api/alembic/versions/0006_worker_leases.py
"""worker leases and outbox dispatch columns"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_worker_leases"
down_revision: str | None = "0005_p3_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("outbox_events", sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("outbox_events", sa.Column("lease_owner", sa.String(128), nullable=True))
    op.add_column("outbox_events", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "outbox_events",
        sa.Column("fencing_generation", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "worker_leases",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("intent_key", sa.String(128), nullable=False),
        sa.Column("owner", sa.String(128), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fencing_generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("state", sa.String(16), nullable=False, server_default="free"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_worker_leases_workspace"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_worker_leases_workspace_id"),
        sa.UniqueConstraint("workspace_id", "intent_key", name="uq_worker_leases_intent"),
    )
    op.create_index("ix_worker_leases_workspace_id", "worker_leases", ["workspace_id"])
    op.execute("ALTER TABLE worker_leases ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE worker_leases FORCE ROW LEVEL SECURITY;")
    op.execute(
        "CREATE POLICY tenant_isolation ON worker_leases "
        "USING (workspace_id = current_setting('app.workspace_id')::uuid) "
        "WITH CHECK (workspace_id = current_setting('app.workspace_id')::uuid);"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON worker_leases TO buyeros_api, buyeros_worker;")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON worker_leases;")
    op.drop_table("worker_leases")
    for column in ("fencing_generation", "lease_expires_at", "lease_owner", "dispatched_at"):
        op.drop_column("outbox_events", column)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_worker_leases_model.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Verify migrations apply to a disposable database**

Run: `uv run pytest tests/test_tenant_isolation_db.py -q`
Expected: PASS — the container fixture applies migrations through `0006_worker_leases`.

- [ ] **Step 6: Commit**

```bash
git add services/api/buyeros_api/db/worker.py services/api/buyeros_api/db/outbox.py services/api/alembic/versions/0006_worker_leases.py services/api/tests/test_worker_leases_model.py
git commit -m "feat(db): worker_leases table and outbox dispatch columns"
```

---
