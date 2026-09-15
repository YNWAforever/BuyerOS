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
