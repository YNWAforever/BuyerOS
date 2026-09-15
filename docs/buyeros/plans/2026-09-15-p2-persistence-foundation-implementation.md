# P2 Persistence Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Build is NOT authorized by this document.**

**Goal:** Persist the project → approved-profile → reviewed-buyer vertical slice and add the foundations every billable operation must pass: purpose policy, atomic budgets, a durable outbox, and safe intake.

**Architecture:** Extends the P1 FastAPI/SQLAlchemy/RLS boundary with immutable ICP versions, evidence-bound assessments, append-only reviews, snapshot selections, an immutable policy-decision engine, a `NUMERIC(20,6)` ledger with deterministic multi-account locking, a transactional outbox drained to Celery/Valkey, and an SSRF-safe fetcher. All tenant tables reuse the P1 tenant mixin, RLS, and single Alembic owner.

**Tech Stack:** Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic, PostgreSQL 16, Celery + Valkey, `uv`; existing Vinext/React/TS frontend.

## Global Constraints

- Canonical repository: `YNWAforever/BuyerOS` (the audited source is imported at commit `b804ba8d1514a1049b7202c861278dd72c473a75`, tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`, merged into `main` via `72fef7da785624a35bb6701f1451ebcf0184a089`).
- Plan-only artifact. No commits, pushes, installs, migrations, provisioning, paid calls, mailbox connections, or Site changes are authorized by this plan.
- Depends on the P1 boundary plan (`plans/2026-09-15-p1-boundary-implementation.md`): `Base`, `TenantMixin`, `tenant_session`, `Principal`, `is_allowed`, `Settings`.
- Money is `NUMERIC(20,6)`/`Decimal`; wire amounts are 6-place decimal strings. USD only.
- No provider is active; no paid step is reachable. Demo and live never mix.
- Every unexecuted check is marked **NOT RUN**.

---

### Task 1: Project, offer and immutable ICP version models

**Files:**
- Create: `services/api/buyeros_api/db/icp.py`
- Create: `services/api/alembic/versions/0003_icp.py`
- Create: `services/api/tests/test_icp_immutability.py`

**Interfaces:**
- Produces: `Project`, `IcpVersion` (fields: `workspace_id`, `project_id`, `number`, `content: dict`, `content_hash: str`, `parent_id`, `approved_at`, `approved_by`), `canonical_hash(content: dict) -> str` (UTF-8, sorted keys, LF-normalized).
- Consumes: `Base`, `TenantMixin` (P1).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_icp_immutability.py
from buyeros_api.db.icp import canonical_hash


def test_canonical_hash_is_order_independent():
    a = canonical_hash({"b": 1, "a": [1, 2]})
    b = canonical_hash({"a": [1, 2], "b": 1})
    assert a == b
    assert a.startswith("sha256:")


def test_canonical_hash_changes_with_content():
    assert canonical_hash({"a": 1}) != canonical_hash({"a": 2})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_icp_immutability.py -v` (cwd `services/api`)
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/db/icp.py
import hashlib
import json

from sqlalchemy import BigInteger, DateTime, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin, UUIDPk


def canonical_hash(content: dict) -> str:
    payload = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Project(Base, TenantMixin):
    __tablename__ = "projects"
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32), default="active")
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
    )


class IcpVersion(Base, TenantMixin):
    __tablename__ = "icp_versions"
    project_id: Mapped[str] = mapped_column()
    number: Mapped[int] = mapped_column(BigInteger)
    content: Mapped[dict] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(80))
    parent_id: Mapped[str | None] = mapped_column(nullable=True)
    approved_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(nullable=True)
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "project_id", "number"),
        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        ForeignKeyConstraint(["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"]),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_icp_immutability.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Generate the migration**

Run: `uv run alembic revision --autogenerate -m "projects and icp versions"`
Expected: new revision; **review generated SQL**. Applying is **NOT RUN**.

---

### Task 2: Hash-bound ICP approval

**Files:**
- Create: `services/api/buyeros_api/services/icp_service.py`
- Create: `services/api/tests/test_icp_approval.py`

**Interfaces:**
- Produces: `approve_icp(session, *, workspace_id, project_id, number, expected_hash, actor_id) -> IcpVersion` raising `StaleRevision` when `expected_hash` mismatches and `AlreadyApproved` on re-approval.
- Consumes: `IcpVersion`, `canonical_hash` (Task 1), `tenant_session` (P1).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_icp_approval.py
import pytest

from buyeros_api.services.icp_service import StaleRevision, verify_approval_hash


class Row:
    def __init__(self, h):
        self.content_hash = h


def test_stale_hash_rejected():
    with pytest.raises(StaleRevision):
        verify_approval_hash(Row("sha256:aaa"), "sha256:bbb")


def test_matching_hash_ok():
    verify_approval_hash(Row("sha256:aaa"), "sha256:aaa")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_icp_approval.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/icp_service.py
class StaleRevision(Exception):
    pass


class AlreadyApproved(Exception):
    pass


def verify_approval_hash(row, expected_hash: str) -> None:
    if row.content_hash != expected_hash:
        raise StaleRevision("content hash changed; reload the profile")


async def approve_icp(session, *, workspace_id, project_id, number, expected_hash, actor_id):
    from sqlalchemy import select

    from ..db.icp import IcpVersion

    result = await session.execute(
        select(IcpVersion).where(
            IcpVersion.workspace_id == workspace_id,
            IcpVersion.project_id == project_id,
            IcpVersion.number == number,
        ).with_for_update()
    )
    row = result.scalar_one()
    verify_approval_hash(row, expected_hash)
    if row.approved_at is not None:
        raise AlreadyApproved("profile already approved")
    from datetime import datetime, timezone

    row.approved_at = datetime.now(timezone.utc)
    row.approved_by = actor_id
    return row
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_icp_approval.py -v`
Expected: PASS (2 passed).

---

### Task 3: Buyer snapshots, reviews and lists

**Files:**
- Create: `services/api/buyeros_api/db/buyers.py`
- Create: `services/api/buyeros_api/services/snapshot_service.py`
- Create: `services/api/tests/test_snapshot.py`

**Interfaces:**
- Produces: `BuyerSnapshot`, `BuyerSnapshotItem`, `HumanReview` (append-only), `BuyerList`, `ListMembership`; `materialize_snapshot(ids_and_versions, ttl_seconds=900, max_ids=1000) -> list[tuple[int,str,int]]` (pure function) raising `TooManyIds` over the cap.
- Consumes: `Base`, `TenantMixin`.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_snapshot.py
import pytest

from buyeros_api.services.snapshot_service import TooManyIds, materialize_snapshot


def test_snapshot_assigns_stable_ordinals():
    out = materialize_snapshot([("b", 2), ("a", 1)])
    assert out == [(0, "b", 2), (1, "a", 1)]


def test_snapshot_rejects_over_cap():
    with pytest.raises(TooManyIds):
        materialize_snapshot([(f"b{i}", 1) for i in range(1001)])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_snapshot.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/snapshot_service.py
class TooManyIds(Exception):
    pass


def materialize_snapshot(ids_and_versions, ttl_seconds: int = 900, max_ids: int = 1000):
    if len(ids_and_versions) > max_ids:
        raise TooManyIds(f"selection exceeds {max_ids}")
    return [(i, bid, version) for i, (bid, version) in enumerate(ids_and_versions)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_snapshot.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Define the models** (`HumanReview` append-only: no UPDATE/DELETE grants; `ListMembership` unique `(workspace_id,list_id,buyer_id)`) and generate the migration. Applying is **NOT RUN**.

---

### Task 4: Fail-closed purpose policy engine

**Files:**
- Create: `services/api/buyeros_api/db/policy.py`
- Create: `services/api/buyeros_api/services/policy_service.py`
- Create: `services/api/tests/test_policy.py`

**Interfaces:**
- Produces: `PolicyDecision` (immutable); `effective_decision(decisions: list[dict], purpose: str) -> str` returning `permitted`/`blocked`/`requires_review`/`unknown` with a **most-restrictive-wins** rule. `PURPOSES = ("research","contact_lookup","export","outreach")`.
- Consumes: `Base`, `TenantMixin`.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_policy.py
from buyeros_api.services.policy_service import effective_decision


def test_unknown_when_no_decision():
    assert effective_decision([], "contact_lookup") == "unknown"


def test_most_restrictive_wins():
    ds = [{"purpose": "contact_lookup", "status": "permitted"}, {"purpose": "contact_lookup", "status": "blocked"}]
    assert effective_decision(ds, "contact_lookup") == "blocked"


def test_purposes_are_separate():
    ds = [{"purpose": "research", "status": "permitted"}]
    assert effective_decision(ds, "outreach") == "unknown"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_policy.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/policy_service.py
PURPOSES = ("research", "contact_lookup", "export", "outreach")
_RANK = {"permitted": 0, "requires_review": 1, "blocked": 2}


def effective_decision(decisions, purpose: str) -> str:
    relevant = [d["status"] for d in decisions if d.get("purpose") == purpose and d.get("status") in _RANK]
    if not relevant:
        return "unknown"
    return max(relevant, key=lambda s: _RANK[s])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_policy.py -v`
Expected: PASS (3 passed).

---

### Task 5: Atomic budget ledger with deterministic locking

**Files:**
- Create: `services/api/buyeros_api/db/budget.py`
- Create: `services/api/buyeros_api/services/budget_service.py`
- Create: `services/api/tests/test_budget.py`

**Interfaces:**
- Produces: `BudgetAccount`, `BudgetReservation`, `CostEvent`; `would_exceed(limit, settled, reserved, proposed) -> bool`; `lock_order(account_ids) -> list` (sorted, deterministic).
- Consumes: `Decimal`, `NUMERIC(20,6)`.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_budget.py
from decimal import Decimal

from buyeros_api.services.budget_service import lock_order, would_exceed


def test_invariant_boundary():
    assert not would_exceed(Decimal("10.000000"), Decimal("5.000000"), Decimal("4.000000"), Decimal("1.000000"))
    assert would_exceed(Decimal("10.000000"), Decimal("5.000000"), Decimal("4.000000"), Decimal("1.000001"))


def test_lock_order_is_deterministic():
    assert lock_order(["c", "a", "b"]) == ["a", "b", "c"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_budget.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/budget_service.py
from decimal import Decimal


def would_exceed(limit: Decimal, settled: Decimal, reserved: Decimal, proposed: Decimal) -> bool:
    return (settled + reserved + proposed) > limit


def lock_order(account_ids):
    return sorted(account_ids)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_budget.py -v`
Expected: PASS (2 passed). Define `NUMERIC(20,6)` columns and append-only `CostEvent` in the models; generate the migration. Applying is **NOT RUN**.

---

### Task 6: Transactional outbox and Celery dispatch

**Files:**
- Create: `services/api/buyeros_api/db/outbox.py`
- Create: `services/api/buyeros_api/services/outbox_service.py`
- Create: `services/api/tests/test_outbox.py`

**Interfaces:**
- Produces: `OutboxEvent` (unique `(workspace_id, intent_key, event_type)`); `build_intent(event_type, payload, logical_index) -> str` deterministic task id.
- Consumes: `Base`, `TenantMixin`.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_outbox.py
from buyeros_api.services.outbox_service import build_intent


def test_intent_is_deterministic_and_unique():
    a = build_intent("run.discover", {"run_id": "r1"}, 0)
    b = build_intent("run.discover", {"run_id": "r1"}, 0)
    c = build_intent("run.discover", {"run_id": "r1"}, 1)
    assert a == b and a != c and a.startswith("job:")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_outbox.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/outbox_service.py
import hashlib
import json


def build_intent(event_type: str, payload: dict, logical_index: int) -> str:
    raw = event_type + "|" + json.dumps(payload, sort_keys=True, separators=(",", ":")) + "|" + str(logical_index)
    return "job:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_outbox.py -v`
Expected: PASS. The worker/dispatcher (`services/worker/buyeros_worker/`) consumes these intents; its tasks are defined in the BO-011 task and are **NOT RUN**.

---

### Task 7: SSRF-safe fetch guard

**Files:**
- Create: `services/api/buyeros_api/services/safe_fetch.py`
- Create: `services/api/tests/test_safe_fetch.py`

**Interfaces:**
- Produces: `is_blocked_host(ip: str) -> bool` (private/loopback/link-local/multicast/unspecified, IPv4 and IPv6); `normalize_url(url: str) -> str`.
- Consumes: `ipaddress`, `urllib.parse`.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_safe_fetch.py
from buyeros_api.services.safe_fetch import is_blocked_host, normalize_url


def test_blocks_private_and_loopback():
    for ip in ("127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254", "::1", "fe80::1"):
        assert is_blocked_host(ip), ip


def test_allows_public():
    assert not is_blocked_host("93.184.216.34")


def test_normalize_strips_fragment_and_default_port():
    assert normalize_url("HTTPS://Example.com:443/a#frag") == "https://example.com/a"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_safe_fetch.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/safe_fetch.py
import ipaddress
from urllib.parse import urlsplit, urlunsplit


def is_blocked_host(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return not addr.is_global or addr.is_multicast or addr.is_unspecified or addr.is_loopback or addr.is_link_local or addr.is_private


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    netloc = host if port in (None, 80 if scheme == "http" else 443) else f"{host}:{port}"
    return urlunsplit((scheme, netloc, parts.path or "/", parts.query, ""))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_safe_fetch.py -v`
Expected: PASS (3 passed). Redirect-hop revalidation, 2 MiB cap, and content-type allowlist are implemented in the fetch client and tested in the BO-012 task — **NOT RUN**.

---

## Self-Review

- **Spec coverage:** P2 spec sections D (Tasks 1–2), E (Task 3), F (Task 4), G (Task 5), H (Task 6), I (Task 7) are mapped. Remaining P2 items needing their own tasks before Build: offer-document quarantine/upload service, evidence/source-document persistence, snapshot API wiring, budget reserve/commit/release transaction against real accounts, outbox dispatcher/worker, and full fetch client.
- **Placeholder scan:** no `TBD`/`TODO`; each code step shows real code. Applying migrations and running the worker are explicitly **NOT RUN**.
- **Type consistency:** `canonical_hash(content)`, `approve_icp(...)`, `materialize_snapshot(...)`, `effective_decision(decisions, purpose)`, `would_exceed(...)`/`lock_order(...)`, `build_intent(...)`, `is_blocked_host(ip)` are consistent across tasks.

## Global Notes

- No commits, pushes, installs, migrations, provisioning, or provider calls are performed by this plan.
- Every command is **NOT RUN**; capture exact output in the progress record when executed under an approved task.
