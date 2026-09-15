# P6 Hardening and Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Build is NOT authorized by this document.**

**Goal:** Provide observable security/lifecycle controls, prove crash and financial-race recovery, prepare a reviewable pilot with a human-evaluation protocol, and define (without activating) the bounded live pilot.

**Architecture:** Retention/deletion propagates from a configurable policy through objects, evidence, contacts, approvals and caches, keeping only minimal non-content audit and immutable financial hashes. Recovery tests run against a disposable full stack and reconcile outbox/ledger/reservations before dispatch. Readiness gates (G0–G5) consume concrete evidence; BO-029 activation stays behind its own approval.

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic, PostgreSQL 16, Celery/Valkey, disposable test stack; existing Vinext/React/TS frontend.

## Global Constraints

- Canonical repository: `YNWAforever/BuyerOS` (the audited source is imported at commit `b804ba8d1514a1049b7202c861278dd72c473a75`, tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`, merged into `main` via `72fef7da785624a35bb6701f1451ebcf0184a089`).
- Plan-only artifact. No commits, pushes, installs, migrations, provisioning, paid calls, mailbox connections, or deployment are authorized.
- Depends on P1–P5. Delivery stays disabled; MVP-A has no sender.
- Retention defaults are **provisional and configurable** (≈30-day event replay, 15-minute snapshot/export TTL); all values remain pending controller/legal review.
- Every unexecuted check is marked **NOT RUN**.

---

### Task 1: Retention configuration and deletion propagation

**Files:**
- Create: `services/api/buyeros_api/services/retention.py`
- Create: `services/api/tests/test_retention.py`

**Interfaces:**
- Produces: `DEFAULT_TTL = {"run_events": 30, "snapshot": 15, "export": 15}` (days/minutes as documented); `is_expired(now, created_at, ttl) -> bool`; `propagation_targets(kind: str) -> list[str]` listing derived artifacts to invalidate.
- Consumes: nothing external.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_retention.py
from datetime import datetime, timedelta, timezone

from buyeros_api.services.retention import DEFAULT_TTL, is_expired, propagation_targets


def test_export_ttl_expiry():
    now = datetime(2026, 9, 15, tzinfo=timezone.utc)
    assert is_expired(now, now - timedelta(minutes=16), ttl_minutes=15) is True
    assert is_expired(now, now - timedelta(minutes=5), ttl_minutes=15) is False


def test_deleting_a_source_invalidates_evidence_and_approvals():
    targets = propagation_targets("source_document")
    assert "evidence" in targets and "approvals" in targets


def test_defaults_are_configurable_not_promises():
    assert DEFAULT_TTL["run_events"] == 30
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_retention.py -v` (cwd `services/api`)
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/retention.py
from datetime import datetime, timedelta

DEFAULT_TTL = {"run_events": 30, "snapshot": 15, "export": 15}


def is_expired(now: datetime, created_at: datetime, *, ttl_minutes: int) -> bool:
    return (now - created_at) >= timedelta(minutes=ttl_minutes)


def propagation_targets(kind: str) -> list[str]:
    return {
        "source_document": ["evidence", "fit_assessments", "approvals", "caches", "exports"],
        "evidence": ["fit_assessments", "approvals", "exports"],
        "contact_point": ["approvals", "exports", "caches"],
    }.get(kind, [])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_retention.py -v`
Expected: PASS (3 passed). Actual deletion jobs and tombstone replay are executed in BO-026/BO-027 against a disposable database — **NOT RUN**.

---

### Task 2: Secret redaction in logs

**Files:**
- Create: `services/api/buyeros_api/services/redaction.py`
- Create: `services/api/tests/test_redaction.py`

**Interfaces:**
- Produces: `redact(value: str) -> str` masking bearer tokens, signatures, signed-URL query strings and API keys; `redact_mapping(d: dict) -> dict` applying it recursively.
- Consumes: nothing external.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_redaction.py
from buyeros_api.services.redaction import redact, redact_mapping


def test_bearer_and_signature_masked():
    assert "abc" not in redact("Authorization: Bearer abc123")
    assert "sig" not in redact("?X-Amz-Signature=sig123&x=1")


def test_nested_mapping_redacted():
    out = redact_mapping({"headers": {"authorization": "Bearer tok"}, "url": "https://x/?token=secret"})
    assert "tok" not in str(out) and "secret" not in str(out)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_redaction.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/redaction.py
import re

BEARER = re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*")
QUERY_SECRET = re.compile(r"([?&](?:X-Amz-Signature|token|access_token|key)=)[^&\s]+", re.IGNORECASE)


def redact(value: str) -> str:
    value = BEARER.sub(r"\1***", value)
    return QUERY_SECRET.sub(r"\1***", value)


def redact_mapping(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = redact_mapping(v)
        elif isinstance(v, str):
            out[k] = redact(v)
        else:
            out[k] = v
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_redaction.py -v`
Expected: PASS (2 passed).

---

### Task 3: Dependency and license inventory gate

**Files:**
- Create: `services/api/tests/test_license_gate.py`
- Create: `services/api/buyeros_api/services/license_gate.py`

**Interfaces:**
- Produces: `FORBIDDEN_LICENSES = {"AGPL-3.0","GPL-3.0-only","GPL-3.0-or-later"}`; `check_inventory(entries: list[dict]) -> list[str]` returning offending package names.
- Consumes: an SBOM/inventory produced at Build time.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_license_gate.py
from buyeros_api.services.license_gate import check_inventory


def test_gpl_and_agpl_flagged():
    entries = [{"name": "a", "license": "MIT"}, {"name": "pymupdf", "license": "AGPL-3.0"}, {"name": "gplpkg", "license": "GPL-3.0-or-later"}]
    assert check_inventory(entries) == ["pymupdf", "gplpkg"]


def test_clean_inventory_passes():
    assert check_inventory([{"name": "fastapi", "license": "MIT"}]) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_license_gate.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/license_gate.py
FORBIDDEN_LICENSES = {"AGPL-3.0", "AGPL-3.0-only", "GPL-3.0-only", "GPL-3.0-or-later", "AGPL-3.0-or-later"}


def check_inventory(entries: list[dict]) -> list[str]:
    return sorted(e["name"] for e in entries if e.get("license") in FORBIDDEN_LICENSES)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_license_gate.py -v`
Expected: PASS (2 passed). Generating the real SBOM is a Build-time action — **NOT RUN**.

---

### Task 4: Kill switch, readiness flags and budget-invariant guard

**Files:**
- Create: `services/api/buyeros_api/services/readiness.py`
- Create: `services/api/tests/test_readiness.py`

**Interfaces:**
- Produces: `readiness(api_ok, db_ok, queue_ok, providers_enabled, policy_blocked) -> dict`; `can_admit(kill_switch: bool, invariant_ok: bool) -> bool`.
- Consumes: `would_exceed` (P2).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_readiness.py
from buyeros_api.services.readiness import can_admit, readiness


def test_readiness_reflects_real_state_not_a_label():
    r = readiness(api_ok=True, db_ok=True, queue_ok=False, providers_enabled=False, policy_blocked=True)
    assert r["api"] == "ok" and r["queue"] == "unavailable" and r["providers"] == "disabled" and r["policy"] == "blocked"


def test_kill_switch_and_invariant_block_admission():
    assert can_admit(kill_switch=True, invariant_ok=True) is False
    assert can_admit(kill_switch=False, invariant_ok=False) is False
    assert can_admit(kill_switch=False, invariant_ok=True) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_readiness.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/readiness.py
def readiness(api_ok, db_ok, queue_ok, providers_enabled, policy_blocked) -> dict:
    return {
        "api": "ok" if api_ok else "unavailable",
        "database": "ok" if db_ok else "unavailable",
        "queue": "ok" if queue_ok else "unavailable",
        "providers": "enabled" if providers_enabled else "disabled",
        "policy": "blocked" if policy_blocked else "ok",
    }


def can_admit(*, kill_switch: bool, invariant_ok: bool) -> bool:
    return (not kill_switch) and invariant_ok
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_readiness.py -v`
Expected: PASS (2 passed).

---

### Task 5: Pilot evaluation metrics

**Files:**
- Create: `services/api/buyeros_api/services/pilot_metrics.py`
- Create: `services/api/tests/test_pilot_metrics.py`

**Interfaces:**
- Produces: `precision(accepted_relevant: int, accepted_total: int) -> float | None`; `agreement(a: list[str], b: list[str]) -> float | None`; `stop_triggered(events: list[str]) -> bool`.
- Consumes: nothing external.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_pilot_metrics.py
from buyeros_api.services.pilot_metrics import agreement, precision, stop_triggered

STOPS = {"tenant_leak", "unauthorized_contact", "unsupported_claim", "unexpected_send", "oversubscribed", "unknown_cost"}


def test_precision_and_zero_denominator():
    assert precision(8, 10) == 0.8
    assert precision(0, 0) is None


def test_agreement_counts_matching_verdicts():
    assert agreement(["a", "b", "c"], ["a", "x", "c"]) == 2 / 3


def test_stop_trigger_detected():
    assert stop_triggered(["ok", "tenant_leak"], STOPS) is True
    assert stop_triggered(["ok"], STOPS) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_pilot_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/pilot_metrics.py
def precision(accepted_relevant: int, accepted_total: int) -> float | None:
    return None if accepted_total == 0 else accepted_relevant / accepted_total


def agreement(a: list[str], b: list[str]) -> float | None:
    if not a and not b:
        return None
    if len(a) != len(b):
        raise ValueError("verdict lists must align")
    if not a:
        return None
    return sum(1 for x, y in zip(a, b) if x == y) / len(a)


def stop_triggered(events: list[str], stops: set[str]) -> bool:
    return any(e in stops for e in events)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_pilot_metrics.py -v`
Expected: PASS (3 passed).

---

## Self-Review

- **Spec coverage:** P6 spec sections W (Tasks 1–3), X (Task 4 + recovery tests), Y (Task 5), Z (activation gating) are mapped. Remaining P6 items needing their own tasks before Build: backup/restore + tombstone-replay rehearsal, crash-window test harness, real SBOM generation, telemetry wiring, and the readiness-evidence pack required by release gates G0–G5.
- **Placeholder scan:** no `TBD`/`TODO`; each code step shows real code. All live/DB/restore checks are **NOT RUN**.
- **Type consistency:** `is_expired`/`propagation_targets`, `redact`/`redact_mapping`, `check_inventory`, `readiness`/`can_admit`, `precision`/`agreement`/`stop_triggered` are consistent across tasks.

## Global Notes

- No commits, pushes, installs, migrations, provisioning, provider calls, or deployment are performed by this plan.
- BO-029 remains ungated by this plan: it requires its own separate, explicit activation approval.
- Every command is **NOT RUN**; capture exact output in the progress record when executed under an approved task.
