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
