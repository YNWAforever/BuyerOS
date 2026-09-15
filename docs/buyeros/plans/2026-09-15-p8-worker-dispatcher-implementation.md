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

### Task 1: Worker package and Celery app

**Files:**
- Create: `services/worker/pyproject.toml`
- Create: `services/worker/buyeros_worker/__init__.py`
- Create: `services/worker/buyeros_worker/config.py`
- Create: `services/worker/buyeros_worker/app.py`
- Create: `services/worker/tests/__init__.py`
- Create: `services/worker/tests/test_app.py`

**Interfaces:**
- Produces: `WorkerSettings` (`broker_url: str`, `eager: bool`, `lease_seconds: int`, `batch_size: int`), `get_settings() -> WorkerSettings`, `celery_app` (a `Celery` instance), `configure_eager(app, enabled)`.
- Consumes: `buyeros_api` (path dependency).

- [ ] **Step 1: Write the failing test**

```python
# services/worker/tests/test_app.py
from buyeros_worker.app import celery_app, configure_eager
from buyeros_worker.config import WorkerSettings


def test_settings_defaults_are_safe():
    s = WorkerSettings()
    assert s.lease_seconds == 120
    assert s.batch_size == 10
    assert s.eager is False


def test_celery_app_is_named_and_has_no_result_backend():
    assert celery_app.main == "buyeros_worker"
    assert celery_app.conf.task_ignore_result is True


def test_eager_mode_can_be_enabled():
    configure_eager(celery_app, True)
    assert celery_app.conf.task_always_eager is True
    configure_eager(celery_app, False)
    assert celery_app.conf.task_always_eager is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_app.py -v` (cwd `services/worker`)
Expected: FAIL — `ModuleNotFoundError: buyeros_worker`.

- [ ] **Step 3: Write minimal implementation**

```toml
# services/worker/pyproject.toml
[project]
name = "buyeros-worker"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "buyeros-api",
  "celery>=5.4,<6",
  "redis>=5,<6",
  "psycopg[binary]>=3.2,<4",
]

[tool.uv.sources]
buyeros-api = { path = "../api" }

[dependency-groups]
dev = ["pytest>=8.3,<9", "pytest-asyncio>=0.24,<1"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

```python
# services/worker/buyeros_worker/__init__.py
__all__ = ["__version__"]
__version__ = "0.1.0"
```

```python
# services/worker/buyeros_worker/config.py
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BUYEROS_", extra="ignore")

    broker_url: str = "redis://localhost:6379/0"
    eager: bool = False
    lease_seconds: int = 120
    batch_size: int = 10


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()
```

```python
# services/worker/buyeros_worker/app.py
from celery import Celery

from .config import get_settings


def build_app() -> Celery:
    settings = get_settings()
    app = Celery("buyeros_worker", broker=settings.broker_url)
    app.conf.update(
        task_ignore_result=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        broker_connection_retry_on_startup=True,
    )
    return app


celery_app = build_app()


def configure_eager(app: Celery, enabled: bool) -> None:
    app.conf.task_always_eager = bool(enabled)


celery_app.autodiscover_tasks(["buyeros_worker"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_app.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit (local only; no push without explicit approval)**

```bash
git add services/worker/pyproject.toml services/worker/buyeros_worker services/worker/tests
git commit -m "feat(worker): bootstrap buyeros_worker package and celery app"
```

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

### Task 3: Lease and fencing primitives

**Files:**
- Create: `services/worker/buyeros_worker/leases.py`
- Create: `services/worker/tests/test_leases.py`

**Interfaces:**
- Produces: `lease_expiry(now, seconds) -> datetime`; `can_claim(state, expires_at, now) -> bool`; `fence_ok(worker_generation, row_generation) -> bool`.
- Consumes: `WorkerLease` (Task 2).

- [ ] **Step 1: Write the failing test**

```python
# services/worker/tests/test_leases.py
from datetime import datetime, timedelta, timezone

from buyeros_worker.leases import can_claim, fence_ok, lease_expiry

NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)


def test_free_lease_can_be_claimed():
    assert can_claim("free", None, NOW) is True


def test_unexpired_lease_cannot_be_claimed():
    assert can_claim("held", NOW + timedelta(seconds=30), NOW) is False


def test_expired_lease_can_be_claimed():
    assert can_claim("held", NOW - timedelta(seconds=1), NOW) is True


def test_lease_expiry_adds_seconds():
    assert lease_expiry(NOW, 120) == NOW + timedelta(seconds=120)


def test_fence_rejects_stale_worker():
    assert fence_ok(3, 3) is True
    assert fence_ok(2, 3) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_leases.py -v` (cwd `services/worker`)
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/worker/buyeros_worker/leases.py
from datetime import datetime, timedelta


def lease_expiry(now: datetime, seconds: int) -> datetime:
    return now + timedelta(seconds=seconds)


def can_claim(state: str, expires_at: datetime | None, now: datetime) -> bool:
    if state == "free" or expires_at is None:
        return True
    return expires_at <= now


def fence_ok(worker_generation: int, row_generation: int) -> bool:
    return worker_generation == row_generation
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_leases.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add services/worker/buyeros_worker/leases.py services/worker/tests/test_leases.py
git commit -m "feat(worker): lease expiry and fencing primitives"
```

---

### Task 4: Handler registry and result types

**Files:**
- Create: `services/worker/buyeros_worker/registry.py`
- Create: `services/worker/tests/test_registry.py`

**Interfaces:**
- Produces: `HandlerResult(state: str, detail: str)`; `register(event_type: str)` decorator; `get_handler(event_type: str)` raising `UnknownHandler`; `HANDLERS: dict`.
- Consumes: nothing external.

- [ ] **Step 1: Write the failing test**

```python
# services/worker/tests/test_registry.py
import pytest

from buyeros_worker.registry import HANDLERS, HandlerResult, UnknownHandler, get_handler, register


def test_unknown_handler_raises():
    with pytest.raises(UnknownHandler):
        get_handler("does.not.exist")


def test_registration_makes_handler_available():
    @register("test.event")
    def handler(session, context, payload):
        return HandlerResult(state="done", detail="ok")

    assert get_handler("test.event") is handler
    assert "test.event" in HANDLERS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_registry.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/worker/buyeros_worker/registry.py
from collections.abc import Callable
from dataclasses import dataclass


class UnknownHandler(Exception):
    pass


@dataclass(frozen=True)
class HandlerResult:
    state: str          # "done" | "blocked" | "retry"
    detail: str = ""


HANDLERS: dict[str, Callable] = {}


def register(event_type: str):
    def decorator(func: Callable) -> Callable:
        HANDLERS[event_type] = func
        return func

    return decorator


def get_handler(event_type: str) -> Callable:
    try:
        return HANDLERS[event_type]
    except KeyError as exc:  # pragma: no cover - exercised via test
        raise UnknownHandler(event_type) from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_registry.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add services/worker/buyeros_worker/registry.py services/worker/tests/test_registry.py
git commit -m "feat(worker): handler registry"
```

---

### Task 5: Capability-blocked handlers

**Files:**
- Create: `services/worker/buyeros_worker/handlers/__init__.py`
- Create: `services/worker/buyeros_worker/handlers/capability_blocked.py`
- Create: `services/worker/tests/test_capability_blocked.py`

**Interfaces:**
- Produces: `BLOCKED_EVENTS = {"run.discover", "contact.submit", "draft.generate"}`; `blocked(session, context, payload) -> HandlerResult(state="blocked", detail=...)`; handlers registered for each blocked event.
- Consumes: `register`, `HandlerResult` (Task 4).

- [ ] **Step 1: Write the failing test**

```python
# services/worker/tests/test_capability_blocked.py
from buyeros_worker.handlers.capability_blocked import BLOCKED_EVENTS, blocked
from buyeros_worker.registry import get_handler


def test_blocked_handlers_are_registered():
    for event in BLOCKED_EVENTS:
        assert get_handler(event) is blocked


def test_blocked_result_makes_no_external_call():
    result = blocked(session=None, context=None, payload={})
    assert result.state == "blocked"
    assert "no verified provider" in result.detail.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_capability_blocked.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/worker/buyeros_worker/handlers/__init__.py
"""Worker handlers."""
```

```python
# services/worker/buyeros_worker/handlers/capability_blocked.py
from ..registry import HandlerResult, register

BLOCKED_EVENTS = frozenset({"run.discover", "contact.submit", "draft.generate"})


def blocked(session, context, payload) -> HandlerResult:
    """Fail closed: no verified provider/model, so make no external call."""
    event_type = (payload or {}).get("event_type", "unknown")
    return HandlerResult(state="blocked", detail=f"{event_type}: no verified provider or model is configured")


for _event in BLOCKED_EVENTS:
    register(_event)(blocked)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_capability_blocked.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add services/worker/buyeros_worker/handlers services/worker/tests/test_capability_blocked.py
git commit -m "feat(worker): fail-closed handlers for unverified provider job types"
```

---

### Task 6: SSRF-safe `fetch.evidence` handler

**Files:**
- Create: `services/worker/buyeros_worker/handlers/fetch_evidence.py`
- Create: `services/worker/tests/test_fetch_evidence.py`

**Interfaces:**
- Produces: `MAX_DECODED_BYTES = 2 * 1024 * 1024`; `ALLOWED_CONTENT_TYPES`; `validate_fetch(url, content_type, size) -> None` raising `FetchRejected`; `handle(session, context, payload) -> HandlerResult` registered for `fetch.evidence`.
- Consumes: `buyeros_api.services.safe_fetch.normalize_url`/`is_blocked_host`; `register`, `HandlerResult` (Task 4).

- [ ] **Step 1: Write the failing test**

```python
# services/worker/tests/test_fetch_evidence.py
import pytest

from buyeros_worker.handlers.fetch_evidence import (
    MAX_DECODED_BYTES,
    FetchRejected,
    validate_fetch,
)
from buyeros_worker.registry import get_handler


def test_blocked_host_is_rejected():
    with pytest.raises(FetchRejected):
        validate_fetch("http://127.0.0.1/x", "text/html", 10)


def test_private_host_is_rejected():
    with pytest.raises(FetchRejected):
        validate_fetch("http://10.0.0.1/x", "text/html", 10)


def test_oversized_body_is_rejected():
    with pytest.raises(FetchRejected):
        validate_fetch("https://example.com/x", "text/html", MAX_DECODED_BYTES + 1)


def test_disallowed_content_type_is_rejected():
    with pytest.raises(FetchRejected):
        validate_fetch("https://example.com/x", "application/octet-stream", 10)


def test_valid_public_html_passes():
    validate_fetch("https://example.com/x", "text/html; charset=utf-8", 100)


def test_handler_is_registered():
    assert get_handler("fetch.evidence") is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_fetch_evidence.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/worker/buyeros_worker/handlers/fetch_evidence.py
from ipaddress import ip_address
from urllib.parse import urlsplit

from buyeros_api.services.safe_fetch import normalize_url

from ..registry import HandlerResult, register

MAX_DECODED_BYTES = 2 * 1024 * 1024
ALLOWED_CONTENT_TYPES = frozenset({"text/html", "text/plain", "text/markdown", "application/xhtml+xml"})


class FetchRejected(Exception):
    pass


def _reject_if_blocked_host(host: str) -> None:
    try:
        addr = ip_address(host)
    except ValueError:
        return  # hostname; DNS/IP pinning happens at connection time
    if not addr.is_global or addr.is_multicast or addr.is_unspecified or addr.is_loopback or addr.is_link_local or addr.is_private:
        raise FetchRejected(f"blocked host {host}")


def validate_fetch(url: str, content_type: str, size: int) -> None:
    normalized = normalize_url(url)
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"}:
        raise FetchRejected(f"unsupported scheme {parsed.scheme}")
    _reject_if_blocked_host(parsed.hostname or "")
    if size > MAX_DECODED_BYTES:
        raise FetchRejected("decoded body exceeds 2 MiB")
    media_type = (content_type or "").split(";")[0].strip().lower()
    if media_type not in ALLOWED_CONTENT_TYPES:
        raise FetchRejected(f"content type {media_type} not allowed")


@register("fetch.evidence")
def handle(session, context, payload) -> HandlerResult:
    """Validate and (in the fetch client) retrieve permitted evidence.

    The live HTTP client is intentionally not wired here: it must run with
    DNS/IP pinning against the deployed egress policy. Validation is enforced
    now so an unsafe URL can never be dispatched.
    """
    try:
        validate_fetch(payload.get("url", ""), payload.get("content_type", ""), int(payload.get("size", 0)))
    except FetchRejected as exc:
        return HandlerResult(state="blocked", detail=str(exc))
    return HandlerResult(state="done", detail="validated; retrieval client is not enabled in this phase")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_fetch_evidence.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add services/worker/buyeros_worker/handlers/fetch_evidence.py services/worker/tests/test_fetch_evidence.py
git commit -m "feat(worker): SSRF-safe fetch.evidence validation handler"
```

---

### Task 7: Run lifecycle transitions and event emission

**Files:**
- Create: `services/worker/buyeros_worker/run_lifecycle.py`
- Create: `services/worker/buyeros_worker/run_emitter.py`
- Create: `services/worker/tests/test_run_lifecycle.py`
- Create: `services/worker/tests/test_run_emitter.py`

**Interfaces:**
- Produces: `RUN_STATES`; `TERMINAL = {"completed", "cancelled"}` (owner decision — `failed`, `partial` and `paused_budget` stay retryable); `BLOCKED = {"blocked"}`; `transition_run(current, event) -> str` (no regression from a terminal or blocked state); `terminal(state) -> bool`; `halted(state) -> bool`; `async emit_run_event(session, run_id, event_type, *, transition=None, payload=None) -> int` (status update + one `run_events` row in the caller's transaction).
- Consumes: `buyeros_api.services.run_events.next_sequence`/`apply_event` (P3); `buyeros_api.db.runs.SearchRun`/`RunEvent`.

- [ ] **Step 1: Write the failing test**

```python
# services/worker/tests/test_run_lifecycle.py
from buyeros_worker.run_lifecycle import halted, terminal, transition_run


def test_valid_progressions():
    assert transition_run("queued", "start") == "running"
    assert transition_run("running", "complete") == "completed"
    assert transition_run("running", "cancel") == "cancel_requested"


def test_terminal_states_do_not_regress():
    assert transition_run("completed", "start") == "completed"
    assert transition_run("cancelled", "start") == "cancelled"


def test_failed_and_paused_budget_are_retryable():
    assert transition_run("failed", "retry") == "queued"
    assert transition_run("partial", "retry") == "queued"
    assert transition_run("paused_budget", "retry") == "queued"


def test_capability_blocked_runs_halt():
    assert transition_run("running", "capability_block") == "blocked"
    assert transition_run("blocked", "retry") == "blocked"
    assert halted("blocked") is True
    assert terminal("blocked") is False


def test_cancel_requested_is_not_terminal():
    assert terminal("cancel_requested") is False
    assert terminal("cancelled") is True
    assert terminal("completed") is True


def test_unknown_event_is_ignored():
    assert transition_run("running", "bogus") == "running"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_run_lifecycle.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/worker/buyeros_worker/run_lifecycle.py
RUN_STATES = ("draft", "queued", "running", "partial", "paused_budget", "completed", "failed", "cancel_requested", "cancelled", "blocked")
# Owner decision: only completed/cancelled are terminal. failed, partial and
# paused_budget are retryable and can return to queued.
TERMINAL = {"completed", "cancelled"}
# A capability-blocked run is halting (nothing retries it) but not a
# business-terminal outcome, so it is tracked separately from TERMINAL.
BLOCKED = {"blocked"}

_TRANSITIONS = {
    ("draft", "enqueue"): "queued",
    ("queued", "start"): "running",
    ("running", "complete"): "completed",
    ("running", "partial"): "partial",
    ("running", "pause_budget"): "paused_budget",
    ("running", "fail"): "failed",
    ("running", "cancel"): "cancel_requested",
    ("partial", "retry"): "queued",
    ("failed", "retry"): "queued",
    ("paused_budget", "retry"): "queued",
    ("paused_budget", "resume"): "running",
    ("cancel_requested", "cancel"): "cancelled",
    ("draft", "capability_block"): "blocked",
    ("queued", "capability_block"): "blocked",
    ("running", "capability_block"): "blocked",
    ("partial", "capability_block"): "blocked",
    ("paused_budget", "capability_block"): "blocked",
    ("cancel_requested", "capability_block"): "blocked",
}


def terminal(state: str) -> bool:
    return state in TERMINAL


def halted(state: str) -> bool:
    """Terminal or capability-blocked: no further transition is applied."""
    return state in TERMINAL or state in BLOCKED


def transition_run(current: str, event: str) -> str:
    if halted(current):
        return current
    return _TRANSITIONS.get((current, event), current)
```

```python
# services/worker/buyeros_worker/run_emitter.py
import uuid

from sqlalchemy import func, select

from buyeros_api.db.runs import RunEvent, SearchRun
from buyeros_api.services.run_events import apply_event, next_sequence

from .run_lifecycle import transition_run


async def emit_run_event(session, run_id, event_type: str, *, transition: str | None = None, payload: dict | None = None) -> int:
    """Advance the run (if ``transition``) and append exactly one event.

    Runs on the caller's tenant transaction, so the status update and the
    ``run_events`` insert commit with the work or roll back with it. Returns the
    sequence, or 0 when there is nothing to do. Never makes an external call.
    """
    if session is None or run_id is None:
        return 0
    run_key = run_id if isinstance(run_id, uuid.UUID) else uuid.UUID(str(run_id))
    result = await session.execute(select(SearchRun).where(SearchRun.id == run_key).with_for_update())
    run = result.scalar_one_or_none()
    if run is None:
        return 0
    last = (await session.execute(select(func.coalesce(func.max(RunEvent.sequence), 0)).where(RunEvent.run_id == run_key))).scalar_one()
    sequence = next_sequence(int(last))
    if not apply_event(int(last), sequence):
        return 0
    if transition is not None:
        new_status = transition_run(run.status, transition)
        if new_status != run.status:
            run.status = new_status
    session.add(RunEvent(workspace_id=run.workspace_id, run_id=run_key, sequence=sequence, event_type=event_type, payload=payload or {}))
    return sequence
```


- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_run_lifecycle.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add services/worker/buyeros_worker/run_lifecycle.py services/worker/tests/test_run_lifecycle.py
git commit -m "feat(worker): run lifecycle transition table"
```

---

### Task 8: DB dispatcher and sweeper

**Files:**
- Create: `services/worker/buyeros_worker/dispatcher.py`
- Create: `services/worker/tests/test_dispatcher.py`

**Interfaces:**
- Produces: `claimable(state, lease_expires_at, now) -> bool`; `select_ready(rows, now, limit) -> list[dict]`; `async def list_workspace_ids(session) -> list`; `async def claim_outbox_rows(session, owner, limit, now, lease_seconds, *, expired_only=False) -> list[dict]` (atomic conditional update, increments `fencing_generation`, never re-claims terminal rows); `async def release_claim(session, intent_key)`; `async def dispatch_once(engine, publish, owner, now, limit, lease_seconds) -> list[str]`; `async def sweep_once(engine, publish, owner, now, limit, lease_seconds) -> list[str]` (re-enqueues expired in-progress intents).
- Consumes: `lease_expiry` (Task 3); `OutboxEvent`/`TERMINAL_STATES` (Task 2); `buyeros_api.db.session.tenant_session`, `Workspace`.
- **RLS decision:** the dispatcher cannot read all tenants' `outbox_events`, so it enumerates tenants from `workspaces` (non-RLS tenant root, read grant added by migration `0007`) and sets the transaction-local tenant context per workspace via `tenant_session` before claiming.
- **Ordering:** the claim (lease + `fencing_generation` bump + `state='dispatched'`) commits before the publish, so a crash between them is recovered by the sweeper's lease expiry; a publish failure calls `release_claim` to put the row straight back to `ready`. The published message carries only opaque ids.

- [ ] **Step 1: Write the failing test** (pure selection logic, no DB)

```python
# services/worker/tests/test_dispatcher.py
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from buyeros_worker.dispatcher import claimable, dispatch_once, select_ready

NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)


def test_only_ready_and_expired_rows_are_selected():
    rows = [
        {"id": 1, "state": "ready", "lease_expires_at": None},
        {"id": 2, "state": "dispatched", "lease_expires_at": NOW + timedelta(seconds=60)},
        {"id": 3, "state": "dispatched", "lease_expires_at": NOW - timedelta(seconds=1)},
        {"id": 4, "state": "done", "lease_expires_at": None},
        {"id": 5, "state": "failed", "lease_expires_at": NOW - timedelta(days=1)},
    ]
    assert [r["id"] for r in select_ready(rows, NOW)] == [1, 3]


def test_batch_is_bounded():
    rows = [{"id": i, "state": "ready", "lease_expires_at": None} for i in range(20)]
    assert len(select_ready(rows, NOW, limit=5)) == 5


def test_terminal_rows_are_never_claimable():
    assert claimable("done", NOW - timedelta(days=1), NOW) is False
    assert claimable("failed", None, NOW) is False


def test_dispatch_once_publishes_only_opaque_ids(monkeypatch):
    """The broker message never carries the instruction (event type/payload)."""

    async def fake_workspace_ids(engine):
        return ["ws-1"]

    @asynccontextmanager
    async def fake_tenant_session(engine, workspace_id):
        yield object()

    async def fake_claim(session, owner, limit, now, lease_seconds, *, expired_only=False):
        return [{"id": 1, "workspace_id": "ws-1", "intent_key": "job:aaa",
                 "event_type": "fetch.evidence", "payload": {"url": "https://e.com"}, "fencing_generation": 7}]

    monkeypatch.setattr("buyeros_worker.dispatcher._workspace_ids", fake_workspace_ids)
    monkeypatch.setattr("buyeros_worker.dispatcher.tenant_session", fake_tenant_session)
    monkeypatch.setattr("buyeros_worker.dispatcher.claim_outbox_rows", fake_claim)
    messages = []
    out = asyncio.run(dispatch_once(object(), messages.append, "owner", NOW, 10, 120))
    assert out == ["job:aaa"]
    assert messages == [{"intent_key": "job:aaa", "workspace_id": "ws-1", "generation": 7}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dispatcher.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/worker/buyeros_worker/dispatcher.py
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from buyeros_api.db.models import Workspace
from buyeros_api.db.outbox import DISPATCHED_STATE, READY_STATE
from buyeros_api.db.session import tenant_session

from .leases import lease_expiry

_CLAIM_COLUMNS = "id, workspace_id, intent_key, event_type, payload, fencing_generation"

# Terminal rows (done/failed) are deliberately absent: the predicate is an
# allow-list, so a terminal row can never be re-claimed or re-run.
_CLAIMABLE_PREDICATE = "state = 'ready' OR (state = 'dispatched' AND lease_expires_at <= :now)"
_EXPIRED_PREDICATE = "state = 'dispatched' AND lease_expires_at <= :now"


def claimable(state: str, lease_expires_at: datetime | None, now: datetime) -> bool:
    if state == READY_STATE:
        return True
    return state == DISPATCHED_STATE and lease_expires_at is not None and lease_expires_at <= now


def select_ready(rows: list[dict], now: datetime, limit: int = 10) -> list[dict]:
    selected = [r for r in rows if claimable(r.get("state", READY_STATE), r.get("lease_expires_at"), now)]
    return selected[:limit]


async def list_workspace_ids(session) -> list:
    from sqlalchemy import select

    return list((await session.execute(select(Workspace.id).order_by(Workspace.id))).scalars().all())


async def claim_outbox_rows(
    session, owner: str, limit: int, now: datetime, lease_seconds: int, *, expired_only: bool = False
) -> list[dict]:
    """Claim ready (or expired in-progress) rows, bumping the fencing generation."""
    predicate = _EXPIRED_PREDICATE if expired_only else _CLAIMABLE_PREDICATE
    result = await session.execute(
        text(
            f"""
            UPDATE outbox_events
               SET lease_owner = :owner,
                   lease_expires_at = :expires,
                   dispatched_at = :now,
                   attempts = attempts + 1,
                   fencing_generation = fencing_generation + 1,
                   state = 'dispatched'
             WHERE id IN (
                   SELECT id FROM outbox_events
                    WHERE {predicate}
                    ORDER BY created_at
                    LIMIT :limit
                    FOR UPDATE SKIP LOCKED
             )
         RETURNING {_CLAIM_COLUMNS}
            """
        ),
        {"owner": owner, "expires": lease_expiry(now, lease_seconds), "now": now, "limit": limit},
    )
    return [dict(r._mapping) for r in result]


async def release_claim(session, intent_key: str) -> None:
    """Return a claimed row to the claimable pool (publish failure recovery)."""
    await session.execute(
        text(
            "UPDATE outbox_events SET state = 'ready', lease_owner = NULL, lease_expires_at = NULL"
            " WHERE intent_key = :key AND state = 'dispatched'"
        ),
        {"key": intent_key},
    )


async def _workspace_ids(engine) -> list:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        return await list_workspace_ids(session)


async def _dispatch_workspace(
    engine, workspace_id, publish: Callable, owner: str, now: datetime, limit: int, lease_seconds: int, *, expired_only: bool
) -> list[str]:
    async with tenant_session(engine, workspace_id) as session:
        claimed = await claim_outbox_rows(session, owner, limit, now, lease_seconds, expired_only=expired_only)
    # The claim above committed, so dispatch state is durable before the publish.
    published: list[str] = []
    for row in claimed:
        message = {
            "intent_key": row["intent_key"],
            "workspace_id": str(row["workspace_id"]),
            "generation": row["fencing_generation"],
        }
        try:
            publish(message)
        except Exception:
            async with tenant_session(engine, workspace_id) as session:
                await release_claim(session, row["intent_key"])
            raise
        published.append(row["intent_key"])
    return published


async def _fan_out(
    engine, publish: Callable, owner: str, now: datetime, limit: int, lease_seconds: int, *, expired_only: bool
) -> list[str]:
    published: list[str] = []
    for workspace_id in await _workspace_ids(engine):
        published.extend(
            await _dispatch_workspace(
                engine, workspace_id, publish, owner, now, limit, lease_seconds, expired_only=expired_only
            )
        )
    return published


async def dispatch_once(
    engine, publish: Callable, owner: str, now: datetime, limit: int = 10, lease_seconds: int = 120
) -> list[str]:
    """Claim and publish ready intents across all workspaces."""
    return await _fan_out(engine, publish, owner, now, limit, lease_seconds, expired_only=False)


async def sweep_once(
    engine, publish: Callable, owner: str, now: datetime, limit: int = 10, lease_seconds: int = 120
) -> list[str]:
    """Re-enqueue intents whose lease expired without a terminal state."""
    return await _fan_out(engine, publish, owner, now, limit, lease_seconds, expired_only=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_dispatcher.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add services/worker/buyeros_worker/dispatcher.py services/worker/tests/test_dispatcher.py
git commit -m "feat(worker): RLS-aware dispatcher, re-enqueueing sweeper and CLI entrypoints"
```

---

### Task 9: Celery task entrypoint (ack after commit)

**Files:**
- Create: `services/worker/buyeros_worker/engine.py`
- Create: `services/worker/buyeros_worker/tasks.py`
- Create: `services/worker/buyeros_worker/cli.py`
- Create: `services/worker/tests/test_tasks.py`

**Interfaces:**
- Produces: `engine.async_database_url(url)`/`create_engine()`/`set_active_engine(engine)`/`dispose_engine(**kwargs)`; `execute_intent_sync(intent_key, workspace_id, generation) -> str`; `async run_intent(session, context, intent_key, generation) -> str`; `async load_intent(session, intent_key)`; `async mark_outbox_terminal(session, intent_key, generation, state) -> int`; `execute_intent(intent_key, workspace_id, generation)` Celery task (acks late, retries on `RetryRequested`); `sweep` Celery task.
- Consumes: `get_handler`/`UnknownHandler` (Task 4), `fence_ok` (Task 3), `TERMINAL_STATES`/`OutboxEvent` (Task 2), `create_engine`/`dispose_engine` (this task).
- **Message contract:** the task signature is `(intent_key, workspace_id, generation)` only. The broker is never the instruction source: `run_intent` loads the row from the database, and the event type and payload come from that row.
- **Fencing:** `load_intent` takes a `FOR UPDATE` lock and `fence_ok` compares the presented generation with the row's before any handler runs; a stale call returns `"stale"` with no handler execution and no writes.
- **Engine lifecycle:** one engine is created and disposed per invocation on the same event loop (no singleton reused across `asyncio.run` loops). `dispose_engine` is connected to Celery's `worker_shutdown` signal as a mid-run safety net.


- [ ] **Step 1: Write the failing test**

```python
# services/worker/tests/test_tasks.py
import asyncio
from contextlib import asynccontextmanager

import pytest

import buyeros_worker.engine as engine_mod
import buyeros_worker.tasks as tasks
from buyeros_worker.registry import HandlerResult, UnknownHandler


class FakeEngine:
    def __init__(self):
        self.disposed = False

    async def dispose(self):
        self.disposed = True


def test_each_invocation_creates_and_disposes_its_own_engine(monkeypatch):
    created = []

    def fake_create_engine():
        engine = FakeEngine()
        created.append(engine)
        return engine

    @asynccontextmanager
    async def fake_tenant_session(engine, workspace_id):
        yield object()

    async def fake_run_intent(session, context, intent_key, generation):
        return "done"

    monkeypatch.setattr(tasks, "create_engine", fake_create_engine)
    monkeypatch.setattr(tasks, "tenant_session", fake_tenant_session)
    monkeypatch.setattr(tasks, "run_intent", fake_run_intent)
    assert tasks.execute_intent_sync("job:1", "ws", 1) == "done"
    assert tasks.execute_intent_sync("job:2", "ws", 1) == "done"
    assert len(created) == 2
    assert all(engine.disposed for engine in created)


def _row(state="dispatched", generation=1, event_type="fetch.evidence", payload=None):
    return {"state": state, "event_type": event_type, "payload": payload or {}, "fencing_generation": generation}


def test_run_intent_rejects_a_stale_generation_without_running_the_handler(monkeypatch):
    async def fake_load(session, intent_key):
        return _row(generation=9)

    called = []
    monkeypatch.setattr(tasks, "load_intent", fake_load)
    monkeypatch.setattr(tasks, "get_handler", lambda event_type: lambda *args: called.append(event_type))
    assert asyncio.run(tasks.run_intent(object(), {}, "job:1", 1)) == "stale"
    assert called == []


def test_run_intent_marks_the_row_done(monkeypatch):
    async def fake_load(session, intent_key):
        return _row()

    terminal = []

    async def fake_mark(session, intent_key, generation, state):
        terminal.append((intent_key, generation, state))
        return 1

    monkeypatch.setattr(tasks, "load_intent", fake_load)
    monkeypatch.setattr(tasks, "mark_outbox_terminal", fake_mark)
    monkeypatch.setattr(tasks, "get_handler", lambda event_type: lambda s, c, p: HandlerResult(state="done"))
    assert asyncio.run(tasks.run_intent(object(), {}, "job:1", 1)) == "done"
    assert terminal == [("job:1", 1, "done")]


def test_worker_shutdown_disposes_the_in_flight_engine():
    from celery import signals

    engine = FakeEngine()
    engine_mod.set_active_engine(engine)
    signals.worker_shutdown.send(sender=None)
    assert engine.disposed is True
    assert engine_mod._active_engine is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tasks.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/worker/buyeros_worker/engine.py  (async engine lifecycle)
def async_database_url(url: str) -> str:
    """Force the psycopg (v3) async driver for SQLAlchemy async engines."""
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def create_engine():
    from buyeros_api.settings import get_settings
    return create_async_engine(async_database_url(get_settings().database_url))


def dispose_engine(**_) -> None:
    """Dispose the in-flight engine. Wired to Celery's ``worker_shutdown``."""
    global _active_engine
    with _active_lock:
        engine, _active_engine = _active_engine, None
    if engine is not None:
        asyncio.run(engine.dispose())
```

```python
# services/worker/buyeros_worker/tasks.py
import asyncio
from collections.abc import Callable
from datetime import datetime, timezone

from celery import signals
from sqlalchemy import select, update

from buyeros_api.db.outbox import DISPATCHED_STATE, TERMINAL_STATES, OutboxEvent
from buyeros_api.db.session import tenant_session

from . import handlers  # noqa: F401  (import registers handlers)
from .app import celery_app
from .engine import create_engine, dispose_engine, set_active_engine
from .leases import fence_ok
from .registry import UnknownHandler, get_handler

# Handler result state -> terminal outbox state. ``retry`` is absent: it leaves
# the row non-terminal and asks Celery for a bounded retry.
TERMINAL_FOR_RESULT = {"done": "done", "blocked": "failed"}


class RetryRequested(Exception):
    """The handler asked for a bounded Celery retry; the transaction rolls back."""


class StaleFenced(Exception):
    """A superseded worker lost the fencing race; nothing may be committed."""


async def load_intent(session, intent_key: str) -> dict | None:
    """Lock and read the intent from the database (never from the message)."""
    row = (await session.execute(select(OutboxEvent).where(OutboxEvent.intent_key == intent_key).with_for_update())).scalar_one_or_none()
    if row is None:
        return None
    return {"state": row.state, "event_type": row.event_type, "payload": row.payload, "fencing_generation": row.fencing_generation}


async def mark_outbox_terminal(session, intent_key: str, generation: int, state: str) -> int:
    """Terminal write guarded by the fencing generation; returns rows updated."""
    result = await session.execute(
        update(OutboxEvent)
        .where(OutboxEvent.intent_key == intent_key, OutboxEvent.fencing_generation == generation, OutboxEvent.state == DISPATCHED_STATE)
        .values(state=state, lease_owner=None, lease_expires_at=None)
    )
    return result.rowcount or 0


async def run_intent(session, context, intent_key: str, generation: int) -> str:
    row = await load_intent(session, intent_key)
    if row is None:
        return "unknown_intent"
    if row["state"] in TERMINAL_STATES:
        return "duplicate"
    if not fence_ok(generation, row["fencing_generation"]):
        return "stale"
    try:
        handler = get_handler(row["event_type"])
    except UnknownHandler:
        await mark_outbox_terminal(session, intent_key, generation, "failed")
        return "unknown_handler"
    handler_context = dict(context or {})
    handler_context["event_type"] = row["event_type"]
    result = handler(session, handler_context, row["payload"])
    if asyncio.iscoroutine(result):
        result = await result
    if result.state == "retry":
        raise RetryRequested()
    terminal = TERMINAL_FOR_RESULT.get(result.state)
    if terminal is not None and await mark_outbox_terminal(session, intent_key, generation, terminal) == 0:
        raise StaleFenced()
    return result.state


async def _with_engine(body: Callable):
    """Create an engine, run ``body`` on a fresh loop, always dispose it."""
    engine = create_engine()
    set_active_engine(engine)
    try:
        return await body(engine)
    finally:
        try:
            await engine.dispose()
        finally:
            set_active_engine(None)


def execute_intent_sync(intent_key: str, workspace_id: str, generation: int) -> str:
    async def body(engine):
        async with tenant_session(engine, workspace_id) as session:
            return await run_intent(session, {"workspace_id": workspace_id}, intent_key, generation)

    try:
        return asyncio.run(_with_engine(body))
    except StaleFenced:
        return "stale"


def publish_message(message: dict) -> None:
    celery_app.send_task("buyeros.execute_intent", args=[message["intent_key"], message["workspace_id"], message["generation"]])


def sweep_sync() -> list[str]:
    from .config import get_settings
    from .dispatcher import sweep_once

    settings = get_settings()
    now = datetime.now(timezone.utc)

    async def body(engine):
        return await sweep_once(engine, publish_message, "buyeros-sweeper", now, settings.batch_size, settings.lease_seconds)

    return asyncio.run(_with_engine(body))


@celery_app.task(name="buyeros.execute_intent", acks_late=True, bind=True)
def execute_intent(self, intent_key: str, workspace_id: str, generation: int) -> str:
    try:
        return execute_intent_sync(intent_key, workspace_id, generation)
    except RetryRequested:
        raise self.retry(countdown=30, max_retries=3)


@celery_app.task(name="buyeros.sweep")
def sweep() -> int:
    """Periodic recovery task (see ``beat_schedule`` in ``app.build_app``)."""
    return len(sweep_sync())


signals.worker_shutdown.connect(dispose_engine, weak=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tasks.py -v`
Expected: PASS (12 passed).

- [ ] **Step 5: Commit**

```bash
git add services/worker/buyeros_worker/engine.py services/worker/buyeros_worker/tasks.py services/worker/tests/test_tasks.py
git commit -m "feat(worker): enforce fencing and resolve intents from the database"
```

---

### Task 10: Disposable Valkey integration test

**Files:**
- Create: `services/worker/tests/test_valkey_integration.py`

**Interfaces:**
- Consumes: `celery_app` (Task 1), `dispatch_once` (Task 8).

- [ ] **Step 1: Write the failing test**

```python
# services/worker/tests/test_valkey_integration.py
import shutil
import subprocess
import time
import uuid

import pytest

from buyeros_worker.app import celery_app
from buyeros_worker.dispatcher import select_ready


def _valkey_container():
    if shutil.which("docker") is None:
        pytest.skip("docker unavailable")
    name = f"buyeros-valkey-{uuid.uuid4().hex[:8]}"
    run = subprocess.run(
        ["docker", "run", "-d", "--name", name, "-p", "127.0.0.1::6379", "valkey/valkey:8"],
        capture_output=True, text=True,
    )
    if run.returncode != 0:
        pytest.skip(f"could not start valkey: {run.stderr.strip()}")
    return name


def test_broker_is_reachable_and_dispatcher_selection_is_pure():
    name = _valkey_container()
    try:
        time.sleep(3)
        port = subprocess.run(["docker", "port", name, "6379"], capture_output=True, text=True).stdout.strip().splitlines()[0].rsplit(":", 1)[1]
        celery_app.conf.broker_url = f"redis://127.0.0.1:{port}/0"
        with celery_app.connection() as conn:
            conn.ensure_connection(max_retries=3)
        assert celery_app.conf.broker_url.endswith("/0")
        assert select_ready([{"id": 1, "state": "ready", "lease_expires_at": None}], __import__("datetime").datetime.now(__import__("datetime").timezone.utc))[0]["id"] == 1
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True)
```

- [ ] **Step 2: Run test to verify it fails / skips**

Run: `uv run pytest tests/test_valkey_integration.py -v` (cwd `services/worker`)
Expected: FAIL or SKIP depending on environment; on failure, confirm the module import is the only issue.

- [ ] **Step 3: Ensure the test passes (or skips) cleanly**

Run: `uv run pytest tests/test_valkey_integration.py -v`
Expected: PASS when Docker and the `valkey/valkey:8` image are available; SKIP otherwise. Container is removed in `finally`.

- [ ] **Step 4: Run the full worker suite**

Run: `uv run pytest -q` (cwd `services/worker`)
Expected: all tests PASS (integration SKIP if Docker is unavailable).

- [ ] **Step 5: Commit**

```bash
git add services/worker/tests/test_valkey_integration.py
git commit -m "test(worker): disposable valkey broker integration check"
```

---

## Self-Review

- **Spec coverage:** A (Tasks 1, 2), B (Tasks 2, 3, 8, 9), C (Tasks 4, 5, 6, 7), D (Tasks 7, 9), E (Tasks 2 Step 5, 10) are mapped. The sweeper's periodic schedule (Celery `beat_schedule` + `buyeros.sweep`) and the `buyeros-worker dispatch`/`sweep` CLI are delivered in Task 9 and registered as a console script; the only intentional gap is the **live HTTP fetch client with DNS/IP pinning** (Task 6 stays validation-only).
- **Placeholder scan:** no `TBD`/`TODO`; every code step shows complete code. `store.py` was removed from the plan and the tree: the dispatcher reads and writes `outbox_events` directly.
- **Type consistency:** `HandlerResult(state, detail)`, `register`/`get_handler`, `lease_expiry`/`fence_ok`, `claimable`/`select_ready`/`claim_outbox_rows`/`release_claim`/`dispatch_once`/`sweep_once`, `transition_run`/`terminal`/`halted`/`emit_run_event`, `load_intent`/`mark_outbox_terminal`/`run_intent`/`execute_intent` are consistent across tasks and reuse `buyeros_api` names (`next_sequence`, `apply_event`, `TERMINAL_STATES`, `normalize_url`, `is_blocked_host`, `tenant_session`). There is no engine singleton: `_with_engine` creates and disposes one engine per invocation.

## Global Notes

- No remote commits, pushes, deploys, cloud resources, real-data migrations, provider calls, or sends are performed by this plan.
- Every command is **NOT RUN** until executed under explicit approval; record exact output in `PROGRESS.md`.
- Execution requires the recorded dependency waiver (BO-003/BO-004/BO-011 incomplete) and may use `superpowers:subagent-driven-development` or `superpowers:executing-plans`.
