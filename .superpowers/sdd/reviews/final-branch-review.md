# final-branch review package
## commits
```
c715715 test(worker): restore broker url and poll valkey readiness
600e755 test(worker): disposable valkey broker integration check
ac4abb6 fix(worker): reuse engine, retry on retry state, ack unknown handlers
24c615b feat(worker): celery task entrypoint with commit-before-ack
32e4af0 fix(worker): dispatch using the persisted outbox intent key
d0ad91e feat(worker): outbox dispatcher with lease claims and sweeper
77df73c fix(worker): make failed/partial/paused_budget runs retryable
bfd2c81 feat(worker): run lifecycle transition table
5b5d384 fix(worker): block IPv6-literal and empty-host fetch URLs
5d2d0be fix(worker): fail closed on non-string fetch payload fields
ca3a23d fix(worker): make fetch.evidence payload handling fail closed
ba2d48d fix(worker): fail closed on malformed fetch URLs
cf1f57b feat(worker): SSRF-safe fetch.evidence validation handler
c1c6821 feat(worker): fail-closed handlers for unverified provider job types
6c70b28 feat(worker): handler registry
ce5f850 feat(worker): lease expiry and fencing primitives
c01ef8e feat(db): worker_leases table and outbox dispatch columns
6b92180 fix(build): make buyeros-api installable so the worker path dependency resolves
4264b03 feat(worker): bootstrap buyeros_worker package and celery app
1d0df22 chore: P8 build approval record and progress ledger
```
## stat (lockfiles excluded)
```
 .superpowers/sdd/progress.md                       |  7 ++
 docs/buyeros/SHA256SUMS.txt                        |  1 +
 .../decisions/BUILD_APPROVAL_RECORD.P8-worker.md   | 29 +++++++
 .../api/alembic/versions/0006_worker_leases.py     | 56 +++++++++++++
 services/api/buyeros_api/db/outbox.py              |  8 +-
 services/api/buyeros_api/db/worker.py              | 29 +++++++
 services/api/pyproject.toml                        |  7 ++
 services/api/tests/test_worker_leases_model.py     | 32 ++++++++
 services/worker/buyeros_worker/__init__.py         |  2 +
 services/worker/buyeros_worker/app.py              | 25 ++++++
 services/worker/buyeros_worker/config.py           | 17 ++++
 services/worker/buyeros_worker/dispatcher.py       | 67 +++++++++++++++
 .../worker/buyeros_worker/handlers/__init__.py     |  2 +
 .../buyeros_worker/handlers/capability_blocked.py  | 13 +++
 .../buyeros_worker/handlers/fetch_evidence.py      | 66 +++++++++++++++
 services/worker/buyeros_worker/leases.py           | 15 ++++
 services/worker/buyeros_worker/registry.py         | 30 +++++++
 services/worker/buyeros_worker/run_lifecycle.py    | 27 ++++++
 services/worker/buyeros_worker/tasks.py            | 70 ++++++++++++++++
 services/worker/pyproject.toml                     | 26 ++++++
 services/worker/tests/__init__.py                  |  0
 services/worker/tests/test_app.py                  | 21 +++++
 services/worker/tests/test_capability_blocked.py   | 14 ++++
 services/worker/tests/test_dispatcher.py           | 54 ++++++++++++
 services/worker/tests/test_fetch_evidence.py       | 95 ++++++++++++++++++++++
 services/worker/tests/test_leases.py               | 26 ++++++
 services/worker/tests/test_registry.py             | 17 ++++
 services/worker/tests/test_run_lifecycle.py        | 50 ++++++++++++
 services/worker/tests/test_tasks.py                | 43 ++++++++++
 services/worker/tests/test_valkey_integration.py   | 56 +++++++++++++
 30 files changed, 904 insertions(+), 1 deletion(-)
```
## diff (lockfiles excluded)
```diff
diff --git a/.superpowers/sdd/progress.md b/.superpowers/sdd/progress.md
new file mode 100644
index 0000000..c322aa0
--- /dev/null
+++ b/.superpowers/sdd/progress.md
@@ -0,0 +1,7 @@
+# P8 worker/dispatcher - progress ledger
+
+Plan: docs/buyeros/plans/2026-09-15-p8-worker-dispatcher-implementation.md
+Branch: p8-worker-dispatcher
+Base commit: 36e67d5
+
+
diff --git a/docs/buyeros/SHA256SUMS.txt b/docs/buyeros/SHA256SUMS.txt
index d8180f7..436d0ff 100644
--- a/docs/buyeros/SHA256SUMS.txt
+++ b/docs/buyeros/SHA256SUMS.txt
@@ -62,10 +62,11 @@ fff7d7c34a37f35e7dfa7b9156592acc4ddcec857e3cd5ab266050c35d21753f  plans/2026-09-
 3371b162214eb358f521b86556b38eed24731a681ef6d3ec20cf5f3b4a6bb5fd  plans/2026-09-15-p5-draft-approval-export-implementation.md
 4937b367fadc1b327f0c35412dd685532d62543aeb08e51c1b44f55677a91de9  plans/2026-09-15-p6-hardening-pilot-implementation.md
 66c47ab3a60ccb7aecc9d269073e57c1027e665af654b4fdd8d412bcadee16f5  plans/2026-09-15-p7-delivery-design-implementation.md
 9fe83b53f163af200b07f45a390f86d9cfe755dba215a6c4e74bfc62bb212524  HANDOFF_INDEX.md
 3aa5d1f31bdf8e6bdb13facf5c48e3076e84dab2e355372917207e16c88322ce  PROGRESS.md
 44295f9fe1bbe047d5c37a267093b72065206f89efd8c69a44dbff1865482441  decisions/BUILD_APPROVAL_RECORD.template.md
 15f0824dff410942a097aee8b125112bc1a8c4a76360e301b038eab6e899c00d  verification/SOURCE_IMPORT_CHECKLIST.md
 b8d23868093d42452b222e9f3420cee7a331e37f316b86db49924486da6b9256  decisions/BUILD_APPROVAL_RECORD.BO-005.md
 de3c29a0259d4e6fc51fe9d158a49da9ffacd0608b503283bb38e0ce7eedf9e6  specs/2026-09-15-p8-worker-dispatcher-design.md
 972e2b28cf3a95cc0a4a32c42c8976f4fedb49b4cfe3b6f7c2417f4c015be1ba  plans/2026-09-15-p8-worker-dispatcher-implementation.md
+8c060ab8973e0a9da62f807edf29d03684a1d2df736243a715b867dad776311a  decisions/BUILD_APPROVAL_RECORD.P8-worker.md
diff --git a/docs/buyeros/decisions/BUILD_APPROVAL_RECORD.P8-worker.md b/docs/buyeros/decisions/BUILD_APPROVAL_RECORD.P8-worker.md
new file mode 100644
index 0000000..752eceb
--- /dev/null
+++ b/docs/buyeros/decisions/BUILD_APPROVAL_RECORD.P8-worker.md
@@ -0,0 +1,29 @@
+# Build approval record — P8 worker/dispatcher (dependency waiver)
+
+**Status: APPROVED (owner-authorized this session).** Plan revision v1. Recorded 2026-09-15 (Hong Kong).
+
+## Approval fields
+
+| Field | Value |
+|---|---|
+| Phase/task | **P8 worker + dispatcher** (covers the pending BO-011 execution layer) |
+| Scope | Outbox dispatcher, Celery/Valkey worker, DB leases + fencing, sweeper/recovery, `worker_leases` migration, handler registry, `fetch.evidence` (validation), fail-closed handlers for `run.discover`/`contact.submit`/`draft.generate`, run/event lifecycle, tests |
+| Spec | `docs/buyeros/specs/2026-09-15-p8-worker-dispatcher-design.md` |
+| Plan | `docs/buyeros/plans/2026-09-15-p8-worker-dispatcher-implementation.md` |
+| Source baseline | `YNWAforever/BuyerOS` `main`; audited source `b804ba8d1514a1049b7202c861278dd72c473a75` (tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`) |
+| Current HEAD at approval | recorded in `docs/buyeros/PROGRESS.md` at execution time |
+| Allowed files | create `services/worker/**`; modify `services/api/buyeros_api/db/{outbox,worker}.py`; create `services/api/alembic/versions/0006_worker_leases.py`; add `services/api/tests/**` and `services/worker/tests/**` |
+| Dependencies with evidence | **BO-003/BO-004/BO-011 NOT complete** — see waiver |
+| Approver | Owner (session authorization, execution mode = subagent-driven) |
+| Environment/spend | none. Local disposable PostgreSQL and (optionally) a local `valkey/valkey:8` container only |
+| Explicitly excluded | remote commits/pushes, deployment, cloud resources, real-data migrations, paid provider calls, contact purchase, mailbox connections, sends, AGENTS.md/OpenCode config changes |
+
+## Dependency waiver (explicit)
+
+The owner authorized P8 Build with an explicit waiver of `depends_on` prerequisites (BO-003 contract freeze, BO-004 bearer identity, BO-011 outbox/task completion). Rationale: the dispatch/execution layer is independent of auth and the HTTP contract, and it builds directly on the P2–P5 tables already implemented and tested. Consequences accepted: later auth/contract changes may require rework; no provider is verified, so discover/contact/draft handlers remain fail-closed.
+
+This waiver does **not** mark BO-003, BO-004, or BO-011 complete, and does not authorize any other phase.
+
+## Sign-off (owner)
+
+> I approve implementation of the P8 worker/dispatcher phase against the imported source baseline, under the dependency waiver and exclusions above, executed subagent-by-task with review between tasks, and with no remote commits/pushes, deployment, real-data migration, provider, or delivery authorization.
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
diff --git a/services/api/pyproject.toml b/services/api/pyproject.toml
index 6503bce..9598246 100644
--- a/services/api/pyproject.toml
+++ b/services/api/pyproject.toml
@@ -17,10 +17,17 @@ dev = [
   "pytest-asyncio>=0.24,<1",
 ]
 
 [tool.pytest.ini_options]
 testpaths = ["tests"]
 pythonpath = ["."]
 
 # NOTE (BO-005 spike): fastapi, asyncpg and pyjwt[crypto] are intentionally
 # omitted here; they are added when BO-004 (bearer identity) and the HTTP
 # layer (BO-003/BO-007+) are implemented. No auth or API route exists yet.
+
+[build-system]
+requires = ["hatchling"]
+build-backend = "hatchling.build"
+
+[tool.hatch.build.targets.wheel]
+packages = ["buyeros_api"]
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
diff --git a/services/worker/buyeros_worker/__init__.py b/services/worker/buyeros_worker/__init__.py
new file mode 100644
index 0000000..07c5de9
--- /dev/null
+++ b/services/worker/buyeros_worker/__init__.py
@@ -0,0 +1,2 @@
+__all__ = ["__version__"]
+__version__ = "0.1.0"
diff --git a/services/worker/buyeros_worker/app.py b/services/worker/buyeros_worker/app.py
new file mode 100644
index 0000000..6b5be3c
--- /dev/null
+++ b/services/worker/buyeros_worker/app.py
@@ -0,0 +1,25 @@
+from celery import Celery
+
+from .config import get_settings
+
+
+def build_app() -> Celery:
+    settings = get_settings()
+    app = Celery("buyeros_worker", broker=settings.broker_url)
+    app.conf.update(
+        task_ignore_result=True,
+        task_acks_late=True,
+        worker_prefetch_multiplier=1,
+        broker_connection_retry_on_startup=True,
+    )
+    return app
+
+
+celery_app = build_app()
+
+
+def configure_eager(app: Celery, enabled: bool) -> None:
+    app.conf.task_always_eager = bool(enabled)
+
+
+celery_app.autodiscover_tasks(["buyeros_worker"])
diff --git a/services/worker/buyeros_worker/config.py b/services/worker/buyeros_worker/config.py
new file mode 100644
index 0000000..9bd5ffd
--- /dev/null
+++ b/services/worker/buyeros_worker/config.py
@@ -0,0 +1,17 @@
+from functools import lru_cache
+
+from pydantic_settings import BaseSettings, SettingsConfigDict
+
+
+class WorkerSettings(BaseSettings):
+    model_config = SettingsConfigDict(env_prefix="BUYEROS_", extra="ignore")
+
+    broker_url: str = "redis://localhost:6379/0"
+    eager: bool = False
+    lease_seconds: int = 120
+    batch_size: int = 10
+
+
+@lru_cache
+def get_settings() -> WorkerSettings:
+    return WorkerSettings()
diff --git a/services/worker/buyeros_worker/dispatcher.py b/services/worker/buyeros_worker/dispatcher.py
new file mode 100644
index 0000000..6a89364
--- /dev/null
+++ b/services/worker/buyeros_worker/dispatcher.py
@@ -0,0 +1,67 @@
+from datetime import datetime
+from typing import Callable
+
+from .leases import can_claim, lease_expiry
+
+
+def select_ready(rows: list[dict], now: datetime, limit: int = 10) -> list[dict]:
+    selected = [r for r in rows if can_claim(r.get("state", "free"), r.get("lease_expires_at"), now)]
+    return selected[:limit]
+
+
+async def claim_outbox_rows(session, owner: str, limit: int, now: datetime) -> list[dict]:
+    """Claim ready outbox rows atomically, bumping the fencing generation."""
+    from sqlalchemy import text
+
+    result = await session.execute(
+        text(
+            """
+            UPDATE outbox_events
+               SET lease_owner = :owner,
+                   lease_expires_at = :expires,
+                   fencing_generation = fencing_generation + 1,
+                   state = 'dispatched'
+             WHERE id IN (
+                   SELECT id FROM outbox_events
+                    WHERE state = 'ready'
+                       OR (state = 'dispatched' AND lease_expires_at <= :now)
+                    ORDER BY created_at
+                    LIMIT :limit
+                    FOR UPDATE SKIP LOCKED
+             )
+         RETURNING id, intent_key, event_type, payload, fencing_generation
+            """
+        ),
+        {"owner": owner, "expires": lease_expiry(now, 120), "now": now, "limit": limit},
+    )
+    return [dict(r._mapping) for r in result]
+
+
+async def mark_dispatched(session, ids: list[int], now: datetime) -> None:
+    from sqlalchemy import text
+
+    if not ids:
+        return
+    await session.execute(text("UPDATE outbox_events SET dispatched_at = :now WHERE id = ANY(:ids)"), {"now": now, "ids": ids})
+
+
+async def sweep_expired(session, now: datetime) -> list[int]:
+    """Return ids of dispatched rows whose lease expired (re-claimable)."""
+    from sqlalchemy import text
+
+    result = await session.execute(
+        text("SELECT id FROM outbox_events WHERE state = 'dispatched' AND lease_expires_at <= :now"),
+        {"now": now},
+    )
+    return [r[0] for r in result]
+
+
+async def dispatch_once(session, publish: Callable, owner: str, now: datetime, limit: int) -> list[str]:
+    claimed = await claim_outbox_rows(session, owner, limit, now)
+    published: list[str] = []
+    for row in claimed:
+        intent = row["intent_key"]
+        publish(intent, row)
+        published.append(intent)
+    await mark_dispatched(session, [row["id"] for row in claimed], now)
+    return published
diff --git a/services/worker/buyeros_worker/handlers/__init__.py b/services/worker/buyeros_worker/handlers/__init__.py
new file mode 100644
index 0000000..f7b26e4
--- /dev/null
+++ b/services/worker/buyeros_worker/handlers/__init__.py
@@ -0,0 +1,2 @@
+"""Worker handlers. Importing this package registers its handlers."""
+from . import capability_blocked, fetch_evidence  # noqa: F401
diff --git a/services/worker/buyeros_worker/handlers/capability_blocked.py b/services/worker/buyeros_worker/handlers/capability_blocked.py
new file mode 100644
index 0000000..6433b29
--- /dev/null
+++ b/services/worker/buyeros_worker/handlers/capability_blocked.py
@@ -0,0 +1,13 @@
+from ..registry import HandlerResult, register
+
+BLOCKED_EVENTS = frozenset({"run.discover", "contact.submit", "draft.generate"})
+
+
+def blocked(session, context, payload) -> HandlerResult:
+    """Fail closed: no verified provider/model, so make no external call."""
+    event_type = (payload or {}).get("event_type", "unknown")
+    return HandlerResult(state="blocked", detail=f"{event_type}: no verified provider or model is configured")
+
+
+for _event in BLOCKED_EVENTS:
+    register(_event)(blocked)
diff --git a/services/worker/buyeros_worker/handlers/fetch_evidence.py b/services/worker/buyeros_worker/handlers/fetch_evidence.py
new file mode 100644
index 0000000..82ac135
--- /dev/null
+++ b/services/worker/buyeros_worker/handlers/fetch_evidence.py
@@ -0,0 +1,66 @@
+from urllib.parse import urlsplit
+
+from buyeros_api.services.safe_fetch import is_blocked_host, normalize_url
+
+from ..registry import HandlerResult, register
+
+MAX_DECODED_BYTES = 2 * 1024 * 1024
+ALLOWED_CONTENT_TYPES = frozenset({"text/html", "text/plain", "text/markdown", "application/xhtml+xml"})
+
+
+class FetchRejected(Exception):
+    pass
+
+
+def _reject_if_blocked_host(host: str) -> None:
+    try:
+        blocked = is_blocked_host(host)
+    except ValueError:
+        return  # hostname; DNS/IP pinning happens at connection time
+    if blocked:
+        raise FetchRejected(f"blocked host {host}")
+
+
+def validate_fetch(url: str, content_type: str, size: int) -> None:
+    try:
+        normalize_url(url)
+    except ValueError:
+        raise FetchRejected(f"malformed url: {url}") from None
+    parts = urlsplit(url)
+    if parts.scheme not in {"http", "https"}:
+        raise FetchRejected(f"unsupported scheme {parts.scheme}")
+    host = parts.hostname
+    if not host:
+        raise FetchRejected("missing host")
+    _reject_if_blocked_host(host)
+    if size < 0 or size > MAX_DECODED_BYTES:
+        raise FetchRejected("decoded body size out of range")
+    media_type = (content_type or "").split(";")[0].strip().lower()
+    if media_type not in ALLOWED_CONTENT_TYPES:
+        raise FetchRejected(f"content type {media_type} not allowed")
+
+
+@register("fetch.evidence")
+def handle(session, context, payload) -> HandlerResult:
+    """Validate and (in the fetch client) retrieve permitted evidence.
+
+    The live HTTP client is intentionally not wired here: it must run with
+    DNS/IP pinning against the deployed egress policy. Validation is enforced
+    now so an unsafe URL can never be dispatched.
+    """
+    if not isinstance(payload, dict):
+        return HandlerResult(state="blocked", detail="fetch.evidence: invalid payload")
+    url = payload.get("url")
+    content_type = payload.get("content_type")
+    size = payload.get("size", 0)
+    if not isinstance(url, str) or not isinstance(content_type, str):
+        return HandlerResult(state="blocked", detail="fetch.evidence: invalid payload")
+    try:
+        size_value = int(size)
+    except (TypeError, ValueError):
+        return HandlerResult(state="blocked", detail="fetch.evidence: invalid size")
+    try:
+        validate_fetch(url, content_type, size_value)
+    except FetchRejected as exc:
+        return HandlerResult(state="blocked", detail=str(exc))
+    return HandlerResult(state="done", detail="validated; retrieval client is not enabled in this phase")
diff --git a/services/worker/buyeros_worker/leases.py b/services/worker/buyeros_worker/leases.py
new file mode 100644
index 0000000..256ec9a
--- /dev/null
+++ b/services/worker/buyeros_worker/leases.py
@@ -0,0 +1,15 @@
+from datetime import datetime, timedelta
+
+
+def lease_expiry(now: datetime, seconds: int) -> datetime:
+    return now + timedelta(seconds=seconds)
+
+
+def can_claim(state: str, expires_at: datetime | None, now: datetime) -> bool:
+    if state == "free" or expires_at is None:
+        return True
+    return expires_at <= now
+
+
+def fence_ok(worker_generation: int, row_generation: int) -> bool:
+    return worker_generation == row_generation
diff --git a/services/worker/buyeros_worker/registry.py b/services/worker/buyeros_worker/registry.py
new file mode 100644
index 0000000..baec808
--- /dev/null
+++ b/services/worker/buyeros_worker/registry.py
@@ -0,0 +1,30 @@
+from collections.abc import Callable
+from dataclasses import dataclass
+
+
+class UnknownHandler(Exception):
+    pass
+
+
+@dataclass(frozen=True)
+class HandlerResult:
+    state: str          # "done" | "blocked" | "retry"
+    detail: str = ""
+
+
+HANDLERS: dict[str, Callable] = {}
+
+
+def register(event_type: str):
+    def decorator(func: Callable) -> Callable:
+        HANDLERS[event_type] = func
+        return func
+
+    return decorator
+
+
+def get_handler(event_type: str) -> Callable:
+    try:
+        return HANDLERS[event_type]
+    except KeyError as exc:  # pragma: no cover - exercised via test
+        raise UnknownHandler(event_type) from exc
diff --git a/services/worker/buyeros_worker/run_lifecycle.py b/services/worker/buyeros_worker/run_lifecycle.py
new file mode 100644
index 0000000..642b818
--- /dev/null
+++ b/services/worker/buyeros_worker/run_lifecycle.py
@@ -0,0 +1,27 @@
+RUN_STATES = ("draft", "queued", "running", "partial", "paused_budget", "completed", "failed", "cancel_requested", "cancelled")
+TERMINAL = {"completed", "cancelled"}
+
+_TRANSITIONS = {
+    ("draft", "enqueue"): "queued",
+    ("queued", "start"): "running",
+    ("running", "complete"): "completed",
+    ("running", "partial"): "partial",
+    ("running", "pause_budget"): "paused_budget",
+    ("running", "fail"): "failed",
+    ("running", "cancel"): "cancel_requested",
+    ("partial", "retry"): "queued",
+    ("failed", "retry"): "queued",
+    ("paused_budget", "retry"): "queued",
+    ("paused_budget", "resume"): "running",
+    ("cancel_requested", "cancel"): "cancelled",
+}
+
+
+def terminal(state: str) -> bool:
+    return state in TERMINAL
+
+
+def transition_run(current: str, event: str) -> str:
+    if terminal(current):
+        return current
+    return _TRANSITIONS.get((current, event), current)
diff --git a/services/worker/buyeros_worker/tasks.py b/services/worker/buyeros_worker/tasks.py
new file mode 100644
index 0000000..671d4be
--- /dev/null
+++ b/services/worker/buyeros_worker/tasks.py
@@ -0,0 +1,70 @@
+import asyncio
+from threading import Lock
+
+from . import handlers  # noqa: F401  (import registers handlers)
+from .app import celery_app
+from .registry import get_handler
+
+_engine_lock = Lock()
+_engine = None
+
+
+def get_engine():
+    """One process-wide async engine; disposing happens at worker shutdown."""
+    global _engine
+    if _engine is None:
+        with _engine_lock:
+            if _engine is None:
+                from sqlalchemy.ext.asyncio import create_async_engine
+
+                from buyeros_api.settings import get_settings
+
+                _engine = create_async_engine(get_settings().database_url)
+    return _engine
+
+
+def dispose_engine() -> None:
+    global _engine
+    _engine = None
+
+
+async def run_intent(handler, payload, session, context) -> str:
+    """Execute one handler inside the tenant session and commit before ack.
+
+    The caller passes a session already scoped with the transaction-local
+    tenant context; nothing is committed if the handler raises.
+    """
+    result = handler(session, context, payload)
+    if asyncio.iscoroutine(result):
+        result = await result
+    await session.commit()
+    return result.state
+
+
+def resolve_handler_state(event_type: str) -> str:
+    from .registry import UnknownHandler, get_handler
+
+    try:
+        get_handler(event_type)
+    except UnknownHandler:
+        return "unknown_handler"
+    return "known"
+
+
+@celery_app.task(name="buyeros.execute_intent", acks_late=True, bind=True)
+def execute_intent(self, intent_key: str, event_type: str, payload: dict, generation: int) -> str:
+    if resolve_handler_state(event_type) == "unknown_handler":
+        return "unknown_handler"
+    handler = get_handler(event_type)
+
+    async def _run() -> str:
+        from buyeros_api.db.session import tenant_session
+
+        engine = get_engine()
+        async with tenant_session(engine, payload["workspace_id"]) as session:
+            return await run_intent(handler, payload, session, context={"workspace_id": payload["workspace_id"]})
+
+    result_state = asyncio.run(_run())
+    if result_state == "retry":
+        raise self.retry(countdown=30, max_retries=3)
+    return result_state
diff --git a/services/worker/pyproject.toml b/services/worker/pyproject.toml
new file mode 100644
index 0000000..7121a71
--- /dev/null
+++ b/services/worker/pyproject.toml
@@ -0,0 +1,26 @@
+[project]
+name = "buyeros-worker"
+version = "0.1.0"
+requires-python = ">=3.12"
+dependencies = [
+  "buyeros-api",
+  "celery>=5.4,<6",
+  "redis>=5,<6",
+  "psycopg[binary]>=3.2,<4",
+  "pydantic-settings>=2.5,<3",
+]
+
+[tool.uv.sources]
+buyeros-api = { path = "../api" }
+
+# NOTE (P8 worker): `buyeros_api` is installed from the local path `../api`.
+# `services/api` declares a hatchling build-system that packages only
+# `buyeros_api`, so the path dependency builds and `import buyeros_api` works
+# at runtime (not just under pytest).
+
+[dependency-groups]
+dev = ["pytest>=8.3,<9", "pytest-asyncio>=0.24,<1"]
+
+[tool.pytest.ini_options]
+testpaths = ["tests"]
+pythonpath = ["."]
diff --git a/services/worker/tests/__init__.py b/services/worker/tests/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/services/worker/tests/test_app.py b/services/worker/tests/test_app.py
new file mode 100644
index 0000000..f778507
--- /dev/null
+++ b/services/worker/tests/test_app.py
@@ -0,0 +1,21 @@
+from buyeros_worker.app import celery_app, configure_eager
+from buyeros_worker.config import WorkerSettings
+
+
+def test_settings_defaults_are_safe():
+    s = WorkerSettings()
+    assert s.lease_seconds == 120
+    assert s.batch_size == 10
+    assert s.eager is False
+
+
+def test_celery_app_is_named_and_has_no_result_backend():
+    assert celery_app.main == "buyeros_worker"
+    assert celery_app.conf.task_ignore_result is True
+
+
+def test_eager_mode_can_be_enabled():
+    configure_eager(celery_app, True)
+    assert celery_app.conf.task_always_eager is True
+    configure_eager(celery_app, False)
+    assert celery_app.conf.task_always_eager is False
diff --git a/services/worker/tests/test_capability_blocked.py b/services/worker/tests/test_capability_blocked.py
new file mode 100644
index 0000000..9f6635e
--- /dev/null
+++ b/services/worker/tests/test_capability_blocked.py
@@ -0,0 +1,14 @@
+# services/worker/tests/test_capability_blocked.py
+from buyeros_worker.handlers.capability_blocked import BLOCKED_EVENTS, blocked
+from buyeros_worker.registry import get_handler
+
+
+def test_blocked_handlers_are_registered():
+    for event in BLOCKED_EVENTS:
+        assert get_handler(event) is blocked
+
+
+def test_blocked_result_makes_no_external_call():
+    result = blocked(session=None, context=None, payload={})
+    assert result.state == "blocked"
+    assert "no verified provider" in result.detail.lower()
diff --git a/services/worker/tests/test_dispatcher.py b/services/worker/tests/test_dispatcher.py
new file mode 100644
index 0000000..559493f
--- /dev/null
+++ b/services/worker/tests/test_dispatcher.py
@@ -0,0 +1,54 @@
+from datetime import datetime, timedelta, timezone
+
+from buyeros_worker.dispatcher import dispatch_once, select_ready, sweep_expired
+
+NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)
+
+
+def test_only_ready_rows_are_selected():
+    rows = [
+        {"id": 1, "state": "ready", "lease_expires_at": None},
+        {"id": 2, "state": "dispatched", "lease_expires_at": NOW + timedelta(seconds=60)},
+        {"id": 3, "state": "ready", "lease_expires_at": NOW - timedelta(seconds=1)},
+    ]
+    assert [r["id"] for r in select_ready(rows, NOW)] == [1, 3]
+
+
+def test_batch_is_bounded():
+    rows = [{"id": i, "state": "ready", "lease_expires_at": None} for i in range(20)]
+    assert len(select_ready(rows, NOW, limit=5)) == 5
+
+
+def test_dispatch_once_publishes_persisted_intent_key():
+    import asyncio
+
+    class FakeResult:
+        def __init__(self, rows):
+            self._rows = rows
+
+        def __iter__(self):
+            return iter(self._rows)
+
+    class FakeRow:
+        def __init__(self, mapping):
+            self._mapping = mapping
+
+    class FakeSession:
+        def __init__(self, rows):
+            self._rows = rows
+            self.executed = []
+
+        async def execute(self, statement, params=None):
+            self.executed.append(params)
+            return FakeResult([FakeRow(r) for r in self._rows])
+
+    rows = [{"id": 1, "intent_key": "job:aaa", "event_type": "fetch.evidence", "payload": {"url": "https://e.com"}, "fencing_generation": 1}]
+    published = []
+    session = FakeSession(rows)
+    out = asyncio.run(dispatch_once(session, lambda intent, row: published.append(intent), "worker-1", __import__("datetime").datetime.now(__import__("datetime").timezone.utc), 10))
+    assert published == ["job:aaa"]
+    assert out == ["job:aaa"]
+
+
+def test_sweep_expired_returns_int_ids():
+    assert sweep_expired.__annotations__["return"] == list[int]
diff --git a/services/worker/tests/test_fetch_evidence.py b/services/worker/tests/test_fetch_evidence.py
new file mode 100644
index 0000000..d4b7923
--- /dev/null
+++ b/services/worker/tests/test_fetch_evidence.py
@@ -0,0 +1,95 @@
+import pytest
+
+from buyeros_worker.handlers.fetch_evidence import (
+    MAX_DECODED_BYTES,
+    FetchRejected,
+    handle,
+    validate_fetch,
+)
+from buyeros_worker.registry import get_handler
+
+
+def test_blocked_host_is_rejected():
+    with pytest.raises(FetchRejected):
+        validate_fetch("http://127.0.0.1/x", "text/html", 10)
+
+
+def test_private_host_is_rejected():
+    with pytest.raises(FetchRejected):
+        validate_fetch("http://10.0.0.1/x", "text/html", 10)
+
+
+def test_oversized_body_is_rejected():
+    with pytest.raises(FetchRejected):
+        validate_fetch("https://example.com/x", "text/html", MAX_DECODED_BYTES + 1)
+
+
+def test_disallowed_content_type_is_rejected():
+    with pytest.raises(FetchRejected):
+        validate_fetch("https://example.com/x", "application/octet-stream", 10)
+
+
+def test_valid_public_html_passes():
+    validate_fetch("https://example.com/x", "text/html; charset=utf-8", 100)
+
+
+def test_handler_is_registered():
+    assert get_handler("fetch.evidence") is not None
+
+
+def test_malformed_url_is_rejected_not_raised():
+    with pytest.raises(FetchRejected):
+        validate_fetch("https://example.com:notaport/x", "text/html", 10)
+
+
+def test_handler_blocks_malformed_url():
+    result = handle(None, None, {"url": "https://example.com:notaport/x", "content_type": "text/html", "size": 1})
+    assert result.state == "blocked"
+
+
+def test_non_numeric_size_is_blocked_not_raised():
+    result = handle(None, None, {"url": "https://example.com/x", "content_type": "text/html", "size": "abc"})
+    assert result.state == "blocked"
+
+
+def test_none_payload_is_blocked_not_raised():
+    result = handle(None, None, None)
+    assert result.state == "blocked"
+
+
+def test_negative_size_is_rejected():
+    with pytest.raises(FetchRejected):
+        validate_fetch("https://example.com/x", "text/html", -1)
+
+
+@pytest.mark.parametrize("bad", [None, 123, [1], {"a": 1}, True])
+def test_non_string_url_is_blocked_not_raised(bad):
+    result = handle(None, None, {"url": bad, "content_type": "text/html", "size": 1})
+    assert result.state == "blocked"
+
+
+@pytest.mark.parametrize("bad", [None, 123, ["text/html"], True])
+def test_non_string_content_type_is_blocked_not_raised(bad):
+    result = handle(None, None, {"url": "https://example.com/x", "content_type": bad, "size": 1})
+    assert result.state == "blocked"
+
+
+@pytest.mark.parametrize(
+    "url",
+    [
+        "http://[::1]/x",
+        "https://[fe80::1]/x",
+        "http://[fc00::1]/x",
+        "http://[::ffff:10.0.0.1]/x",
+        "http:///x",
+    ],
+)
+def test_ipv6_and_empty_host_are_rejected(url):
+    with pytest.raises(FetchRejected):
+        validate_fetch(url, "text/html", 10)
+
+
+@pytest.mark.parametrize("url", ["http://[::1]/x", "http:///x"])
+def test_ipv6_and_empty_host_blocked_via_handle(url):
+    result = handle(None, None, {"url": url, "content_type": "text/html", "size": 1})
+    assert result.state == "blocked"
diff --git a/services/worker/tests/test_leases.py b/services/worker/tests/test_leases.py
new file mode 100644
index 0000000..b3741bb
--- /dev/null
+++ b/services/worker/tests/test_leases.py
@@ -0,0 +1,26 @@
+from datetime import datetime, timedelta, timezone
+
+from buyeros_worker.leases import can_claim, fence_ok, lease_expiry
+
+NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)
+
+
+def test_free_lease_can_be_claimed():
+    assert can_claim("free", None, NOW) is True
+
+
+def test_unexpired_lease_cannot_be_claimed():
+    assert can_claim("held", NOW + timedelta(seconds=30), NOW) is False
+
+
+def test_expired_lease_can_be_claimed():
+    assert can_claim("held", NOW - timedelta(seconds=1), NOW) is True
+
+
+def test_lease_expiry_adds_seconds():
+    assert lease_expiry(NOW, 120) == NOW + timedelta(seconds=120)
+
+
+def test_fence_rejects_stale_worker():
+    assert fence_ok(3, 3) is True
+    assert fence_ok(2, 3) is False
diff --git a/services/worker/tests/test_registry.py b/services/worker/tests/test_registry.py
new file mode 100644
index 0000000..391c66e
--- /dev/null
+++ b/services/worker/tests/test_registry.py
@@ -0,0 +1,17 @@
+import pytest
+
+from buyeros_worker.registry import HANDLERS, HandlerResult, UnknownHandler, get_handler, register
+
+
+def test_unknown_handler_raises():
+    with pytest.raises(UnknownHandler):
+        get_handler("does.not.exist")
+
+
+def test_registration_makes_handler_available():
+    @register("test.event")
+    def handler(session, context, payload):
+        return HandlerResult(state="done", detail="ok")
+
+    assert get_handler("test.event") is handler
+    assert "test.event" in HANDLERS
diff --git a/services/worker/tests/test_run_lifecycle.py b/services/worker/tests/test_run_lifecycle.py
new file mode 100644
index 0000000..50b0210
--- /dev/null
+++ b/services/worker/tests/test_run_lifecycle.py
@@ -0,0 +1,50 @@
+from buyeros_worker.run_lifecycle import terminal, transition_run
+
+
+def test_valid_progressions():
+    assert transition_run("queued", "start") == "running"
+    assert transition_run("running", "complete") == "completed"
+    assert transition_run("running", "cancel") == "cancel_requested"
+
+
+def test_terminal_states_do_not_regress():
+    assert transition_run("completed", "start") == "completed"
+    assert transition_run("cancelled", "start") == "cancelled"
+
+
+def test_cancel_requested_is_not_terminal():
+    assert terminal("cancel_requested") is False
+    assert terminal("cancelled") is True
+    assert terminal("completed") is True
+
+
+def test_unknown_event_is_ignored():
+    assert transition_run("running", "bogus") == "running"
+
+
+def test_failed_and_paused_budget_are_retryable():
+    assert transition_run("failed", "retry") == "queued"
+    assert transition_run("partial", "retry") == "queued"
+    assert transition_run("paused_budget", "retry") == "queued"
+    assert transition_run("paused_budget", "resume") == "running"
+
+
+def test_only_completed_and_cancelled_are_terminal():
+    assert terminal("completed") is True
+    assert terminal("cancelled") is True
+    assert terminal("failed") is False
+    assert terminal("partial") is False
+    assert terminal("paused_budget") is False
+
+
+def test_terminal_states_never_regress_even_on_retry():
+    assert transition_run("completed", "retry") == "completed"
+    assert transition_run("cancelled", "retry") == "cancelled"
+
+
+def test_remaining_edges():
+    assert transition_run("draft", "enqueue") == "queued"
+    assert transition_run("running", "fail") == "failed"
+    assert transition_run("running", "partial") == "partial"
+    assert transition_run("running", "pause_budget") == "paused_budget"
+    assert transition_run("cancel_requested", "cancel") == "cancelled"
diff --git a/services/worker/tests/test_tasks.py b/services/worker/tests/test_tasks.py
new file mode 100644
index 0000000..1faff11
--- /dev/null
+++ b/services/worker/tests/test_tasks.py
@@ -0,0 +1,43 @@
+from buyeros_worker.registry import HandlerResult
+from buyeros_worker.tasks import run_intent
+
+
+class FakeSession:
+    def __init__(self):
+        self.committed = False
+
+    async def __aenter__(self):
+        return self
+
+    async def __aexit__(self, *exc):
+        return False
+
+    async def commit(self):
+        self.committed = True
+
+
+def test_run_intent_returns_handler_state():
+    session = FakeSession()
+
+    async def handler(s, context, payload):
+        return HandlerResult(state="done", detail="ok")
+
+    state = __import__("asyncio").run(run_intent(handler, {}, session, context={"workspace_id": "w"}))
+    assert state == "done"
+    assert session.committed is True
+
+
+def test_run_intent_reports_blocked_without_raising():
+    session = FakeSession()
+
+    async def handler(s, context, payload):
+        return HandlerResult(state="blocked", detail="no provider")
+
+    state = __import__("asyncio").run(run_intent(handler, {}, session, context={"workspace_id": "w"}))
+    assert state == "blocked"
+
+
+def test_unknown_handler_state_is_terminal():
+    from buyeros_worker.tasks import resolve_handler_state
+
+    assert resolve_handler_state("does.not.exist") == "unknown_handler"
diff --git a/services/worker/tests/test_valkey_integration.py b/services/worker/tests/test_valkey_integration.py
new file mode 100644
index 0000000..6f1c5b4
--- /dev/null
+++ b/services/worker/tests/test_valkey_integration.py
@@ -0,0 +1,56 @@
+import shutil
+import subprocess
+import time
+import uuid
+from datetime import datetime, timezone
+
+import pytest
+
+from buyeros_worker.app import celery_app
+from buyeros_worker.dispatcher import select_ready
+
+
+def _valkey_container():
+    if shutil.which("docker") is None:
+        pytest.skip("docker unavailable")
+    name = f"buyeros-valkey-{uuid.uuid4().hex[:8]}"
+    run = subprocess.run(
+        ["docker", "run", "-d", "--name", name, "-p", "127.0.0.1::6379", "valkey/valkey:8"],
+        capture_output=True,
+        text=True,
+    )
+    if run.returncode != 0:
+        pytest.skip(f"could not start valkey: {run.stderr.strip()}")
+    return name
+
+
+def test_broker_is_reachable_and_dispatcher_selection_is_pure():
+    original = celery_app.conf.broker_url
+    name = None
+    try:
+        name = _valkey_container()
+        port_output = subprocess.run(["docker", "port", name, "6379"], capture_output=True, text=True).stdout.strip()
+        if not port_output:
+            pytest.skip(f"could not resolve valkey port for {name}")
+        port = port_output.splitlines()[0].rsplit(":", 1)[1]
+        celery_app.conf.broker_url = f"redis://127.0.0.1:{port}/0"
+        for _ in range(15):
+            try:
+                with celery_app.connection() as conn:
+                    conn.ensure_connection(max_retries=1)
+            except Exception:
+                time.sleep(1)
+            else:
+                break
+        else:
+            pytest.skip("valkey broker did not become ready")
+        assert celery_app.conf.broker_url.endswith("/0")
+        selected = select_ready(
+            [{"id": 1, "state": "ready", "lease_expires_at": None}],
+            datetime.now(timezone.utc),
+        )
+        assert selected[0]["id"] == 1
+    finally:
+        celery_app.conf.broker_url = original
+        if name is not None:
+            subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True)

```
## lockfile stat (contents omitted)
```
 services/api/uv.lock    |   2 +-
 services/worker/uv.lock | 711 ++++++++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 712 insertions(+), 1 deletion(-)
```
