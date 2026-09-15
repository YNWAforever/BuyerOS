# P4 Contact Guardrails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Build is NOT authorized by this document.**

**Goal:** Deliver the optional business-contact path as guarded states — quote (no dispatch) → confirm (atomic reservation + durable job) → submit (uncertainty-safe) → reconcile (callbacks/status) and cancellation.

**Architecture:** Quotes are immutable snapshots that hold no money. Confirmation is one database transaction that revalidates eligibility/policy/budget, reserves a bounded upper amount, and commits a unique job plus outbox intent atomically. The worker commits `submitting` before the network call, treats timeouts as `unknown` with the hold retained, and settles only on authoritative provider evidence. Callbacks verify raw bytes, dedupe by provider event id, and apply only monotonic transitions.

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic + Celery/Valkey, PostgreSQL 16; provider is **unverified and disabled**.

## Global Constraints

- Canonical repository: `YNWAforever/BuyerOS` (planning pack committed at `1512d4c17d4f792e14598d524fdac3c9c37d27e7`; a source import is still expected to produce tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`).
- Plan-only artifact. No commits, pushes, installs, migrations, provisioning, paid calls, or contact purchase are authorized. **No provider is active; the contact path is disabled.**
- Depends on P2 (`BudgetAccount`, `BudgetReservation`, `CostEvent`, `OutboxEvent`, `build_intent`, `effective_decision`) and P3 (`RunEvent`, `apply_event`).
- Money is `NUMERIC(20,6)`; use `lock_order` from P2 for every multi-account lock.
- Defaults: single capability-gated contact provider; signed webhook primary + polling fallback.
- Every unexecuted check is marked **NOT RUN**.

---

### Task 1: Immutable quote snapshot and eligibility

**Files:**
- Create: `services/api/buyeros_api/db/quotes.py`
- Create: `services/api/buyeros_api/services/quote_service.py`
- Create: `services/api/tests/test_quote.py`

**Interfaces:**
- Produces: `EnrichmentQuote` (immutable; `status` in `quoted/consumed/expired/cancelled`, `reservation_id`/`consumed_job_id` null until consumed); `quote_hash(payload: dict) -> str`; `eligible(gates: dict) -> tuple[bool, list[str]]`.
- Consumes: `Base`, `TenantMixin`, `canonical_hash` (P2).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_quote.py
from buyeros_api.services.quote_service import eligible, quote_hash


def test_quote_hash_is_stable():
    p = {"selection": ["b1", "b2"], "purpose": "contact_lookup"}
    assert quote_hash(p) == quote_hash({"purpose": "contact_lookup", "selection": ["b1", "b2"]})


def test_eligibility_lists_block_reasons():
    ok, reasons = eligible({"accepted": True, "policy": "unknown", "suppressed": False})
    assert not ok and "policy" in " ".join(reasons).lower()


def test_eligible_when_all_gates_pass():
    ok, reasons = eligible({"accepted": True, "policy": "permitted", "suppressed": False, "role_supported": True})
    assert ok and reasons == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_quote.py -v` (cwd `services/api`)
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/quote_service.py
import json
import hashlib


def quote_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def eligible(gates: dict) -> tuple[bool, list[str]]:
    reasons = []
    if not gates.get("accepted"):
        reasons.append("buyer not accepted")
    if gates.get("policy") != "permitted":
        reasons.append(f"policy is {gates.get('policy')}")
    if gates.get("suppressed"):
        reasons.append("suppressed")
    if not gates.get("role_supported", True):
        reasons.append("unsupported role/contact type")
    return (not reasons), reasons
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_quote.py -v`
Expected: PASS (3 passed). A quote **never** creates a reservation or job at creation time.

---

### Task 2: Idempotent confirm with atomic reservation and durable job

**Files:**
- Create: `services/api/buyeros_api/services/confirm_service.py`
- Create: `services/api/tests/test_confirm.py`

**Interfaces:**
- Produces: `@dataclass ConfirmResult(job_id, reservation_id, idempotent_replay: bool)`; `request_fingerprint(body: dict) -> str`; `confirm_quote(session, *, actor_id, quote, body, request_key) -> ConfirmResult` raising `IdempotencyConflict` on same-key/different-body, `QuoteChanged`, `QuoteExpired`.
- Consumes: `quote_hash` (Task 1), `lock_order`/`would_exceed` (P2), `build_intent` (P2).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_confirm.py
import pytest

from buyeros_api.services.confirm_service import IdempotencyConflict, request_fingerprint, same_request


def test_fingerprint_is_order_independent():
    assert request_fingerprint({"a": 1, "b": 2}) == request_fingerprint({"b": 2, "a": 1})


def test_same_key_different_body_conflicts():
    assert same_request("k1", "h1", "k1", "h2") is False
    assert same_request("k1", "h1", "k1", "h1") is True
    with pytest.raises(IdempotencyConflict):
        same_request("k1", "h1", "k1", "h2", raise_on_conflict=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_confirm.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/confirm_service.py
import hashlib
import json
from dataclasses import dataclass


class IdempotencyConflict(Exception):
    pass


class QuoteChanged(Exception):
    pass


class QuoteExpired(Exception):
    pass


@dataclass
class ConfirmResult:
    job_id: str
    reservation_id: str
    idempotent_replay: bool = False


def request_fingerprint(body: dict) -> str:
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def same_request(key_a, hash_a, key_b, hash_b, raise_on_conflict: bool = False) -> bool:
    if key_a != key_b:
        return False
    if hash_a == hash_b:
        return True
    if raise_on_conflict:
        raise IdempotencyConflict("same key with a different body")
    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_confirm.py -v`
Expected: PASS (2 passed). The full transaction (lock quote → revalidate gates → lock budget accounts in `lock_order` → reserve → insert job/outbox/audit → commit) is implemented against real models in BO-018 and is **NOT RUN**.

---

### Task 3: Uncertainty-safe provider submission state machine

**Files:**
- Create: `services/api/buyeros_api/services/provider_op.py`
- Create: `services/api/tests/test_provider_op.py`

**Interfaces:**
- Produces: `STATES` and `transition(current: str, event: str) -> str` that never regresses; `submit_outcome(kind: str) -> str` mapping `accepted/pending/timeout/error`; `should_hold(state: str) -> bool`.
- Consumes: nothing external.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_provider_op.py
from buyeros_api.services.provider_op import should_hold, submit_outcome, transition


def test_timeout_is_unknown_not_failed():
    assert submit_outcome("timeout") == "unknown"


def test_unknown_holds_cost():
    assert should_hold("unknown") is True
    assert should_hold("succeeded") is False


def test_no_regression_after_success():
    assert transition("succeeded", "pending") == "succeeded"
    assert transition("submitting", "accepted") == "accepted"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_provider_op.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/provider_op.py
_ORDER = ["intent", "reserved", "submitting", "accepted", "pending", "unknown", "succeeded", "not_found", "failed"]
TERMINAL = {"succeeded", "not_found", "failed"}


def submit_outcome(kind: str) -> str:
    return {"accepted": "accepted", "pending": "pending", "timeout": "unknown", "error": "unknown"}.get(kind, "unknown")


def transition(current: str, event: str) -> str:
    if current in TERMINAL or current == "unknown":
        return current
    if _ORDER.index(event) <= _ORDER.index(current):
        return current
    return event


def should_hold(state: str) -> bool:
    return state in {"reserved", "submitting", "accepted", "pending", "unknown"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_provider_op.py -v`
Expected: PASS (3 passed). The worker commits `submitting` plus a stable provider idempotency identity **before** the network call (BO-019) — **NOT RUN**.

---

### Task 4: Callback verification, dedupe and monotonic apply

**Files:**
- Create: `services/api/buyeros_api/services/callback.py`
- Create: `services/api/tests/test_callback.py`

**Interfaces:**
- Produces: `event_key(provider, account, event_id) -> str`; `is_replay(seen: set[str], key: str, digest: str) -> bool`; `digest_conflict(seen: dict, key: str, digest: str) -> bool`.
- Consumes: `transition` (Task 3).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_callback.py
from buyeros_api.services.callback import digest_conflict, event_key, is_replay


def test_event_key_scopes_provider_account_event():
    assert event_key("p", "acct", "e1") == "p:acct:e1"


def test_replay_detected():
    seen = {"p:acct:e1": "sha256:x"}
    assert is_replay(set(seen), "p:acct:e1", "sha256:x") is True
    assert is_replay(set(), "p:acct:e1", "sha256:x") is False


def test_same_key_different_digest_conflicts():
    assert digest_conflict({"p:acct:e1": "sha256:x"}, "p:acct:e1", "sha256:y") is True
    assert digest_conflict({"p:acct:e1": "sha256:x"}, "p:acct:e1", "sha256:x") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_callback.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/callback.py
def event_key(provider: str, account: str, event_id: str) -> str:
    return f"{provider}:{account}:{event_id}"


def is_replay(seen_keys: set[str], key: str, digest: str) -> bool:
    return key in seen_keys


def digest_conflict(seen: dict[str, str], key: str, digest: str) -> bool:
    return key in seen and seen[key] != digest
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_callback.py -v`
Expected: PASS (3 passed). Raw-body signature verification, size/replay window, and quarantine are added with the provider adapter in BO-020 — **NOT RUN**.

---

### Task 5: Ledger settlement and cancellation rules

**Files:**
- Create: `services/api/buyeros_api/services/settlement.py`
- Create: `services/api/tests/test_settlement.py`

**Interfaces:**
- Produces: `settle_effect(state: str, charge: str) -> dict` returning `{"release": Decimal, "commit": Decimal}`; `cancel_effect(state: str) -> str` in `{"release","reconcile"}`.
- Consumes: `Decimal` (P2).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_settlement.py
from decimal import Decimal

from buyeros_api.services.settlement import cancel_effect, settle_effect


def test_success_commits_charge_and_releases_rest():
    eff = settle_effect("succeeded", "0.300000")
    assert eff == {"commit": Decimal("0.300000"), "release": Decimal("0.000000")}


def test_unknown_releases_nothing():
    eff = settle_effect("unknown", "0.300000")
    assert eff == {"commit": Decimal("0.000000"), "release": Decimal("0.000000")}


def test_cancel_before_dispatch_releases_but_after_submit_reconciles():
    assert cancel_effect("reserved") == "release"
    assert cancel_effect("submitting") == "reconcile"
    assert cancel_effect("unknown") == "reconcile"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_settlement.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/settlement.py
from decimal import Decimal

ZERO = Decimal("0.000000")


def settle_effect(state: str, charge: str) -> dict:
    if state == "succeeded":
        return {"commit": Decimal(charge), "release": ZERO}
    if state == "not_found":
        return {"commit": ZERO, "release": ZERO}
    return {"commit": ZERO, "release": ZERO}


def cancel_effect(state: str) -> str:
    return "release" if state in {"reserved", "intent"} else "reconcile"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_settlement.py -v`
Expected: PASS (3 passed).

---

## Self-Review

- **Spec coverage:** P4 spec sections N (Task 1), O (Task 2), P (Task 3), Q (Task 4) are mapped; Task 5 covers ledger release/reconcile. Remaining P4 items needing their own tasks before Build: quote/confirm HTTP routes, real budget reservation transaction, the queue/dispatch wiring, the signed webhook route + polling reconciliation job, admin exception review, and cancellation endpoint.
- **Placeholder scan:** no `TBD`/`TODO`; each code step shows real code. Provider activation and migrations are **NOT RUN**.
- **Type consistency:** `quote_hash`/`eligible`, `request_fingerprint`/`same_request`/`ConfirmResult`, `transition`/`submit_outcome`/`should_hold`, `event_key`/`is_replay`/`digest_conflict`, `settle_effect`/`cancel_effect` are consistent across tasks and reuse P2 names.

## Global Notes

- No commits, pushes, installs, migrations, provisioning, provider calls, or contact purchase are performed by this plan.
- Every command is **NOT RUN**; capture exact output in the progress record when executed under an approved task.
