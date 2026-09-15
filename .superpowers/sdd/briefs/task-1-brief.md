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
