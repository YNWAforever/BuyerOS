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

### Task 9: Celery task entrypoint (ack after commit)

**Files:**
- Create: `services/worker/buyeros_worker/tasks.py`
- Create: `services/worker/tests/test_tasks.py`

**Interfaces:**
- Produces: `execute_intent(intent_key: str, event_type: str, payload: dict, generation: int) -> str` Celery task returning the terminal state; `run_intent(handler, payload, session_factory, context) -> str` pure orchestration helper.
- Consumes: `get_handler` (Task 4), `fence_ok` (Task 3), `HandlerResult` (Task 4).

- [ ] **Step 1: Write the failing test**

```python
# services/worker/tests/test_tasks.py
import pytest

from buyeros_worker.registry import HandlerResult, UnknownHandler
from buyeros_worker.tasks import run_intent


class FakeSession:
    def __init__(self):
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def commit(self):
        self.committed = True


def test_run_intent_returns_handler_state():
    session = FakeSession()

    async def handler(s, context, payload):
        return HandlerResult(state="done", detail="ok")

    state = __import__("asyncio").run(run_intent(handler, {}, session, context={"workspace_id": "w"}))
    assert state == "done"
    assert session.committed is True


def test_run_intent_reports_blocked_without_raising():
    session = FakeSession()

    async def handler(s, context, payload):
        return HandlerResult(state="blocked", detail="no provider")

    state = __import__("asyncio").run(run_intent(handler, {}, session, context={"workspace_id": "w"}))
    assert state == "blocked"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tasks.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/worker/buyeros_worker/tasks.py
import asyncio

from .app import celery_app
from .registry import get_handler


async def run_intent(handler, payload, session, context) -> str:
    """Execute one handler inside the tenant session and commit before ack.

    The caller passes a session already scoped with the transaction-local
    tenant context; nothing is committed if the handler raises.
    """
    result = handler(session, context, payload)
    if asyncio.iscoroutine(result):
        result = await result
    await session.commit()
    return result.state


@celery_app.task(name="buyeros.execute_intent", acks_late=True)
def execute_intent(intent_key: str, event_type: str, payload: dict, generation: int) -> str:
    handler = get_handler(event_type)

    async def _run() -> str:
        from buyeros_api.db.session import tenant_session

        engine = _engine()
        async with tenant_session(engine, payload["workspace_id"]) as session:
            return await run_intent(handler, payload, session, context={"workspace_id": payload["workspace_id"]})

    return asyncio.run(_run())


def _engine():
    from sqlalchemy.ext.asyncio import create_async_engine

    from buyeros_api.settings import get_settings

    return create_async_engine(get_settings().database_url)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tasks.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add services/worker/buyeros_worker/tasks.py services/worker/tests/test_tasks.py
git commit -m "feat(worker): celery task entrypoint with commit-before-ack"
```

---
