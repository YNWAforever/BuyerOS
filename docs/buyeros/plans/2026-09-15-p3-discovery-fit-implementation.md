# P3 Discovery and Fit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Build is NOT authorized by this document.**

**Goal:** Deliver bounded multilingual company discovery, canonicalization with linked evidence, an evidence-first fit assessment that stops for human review, and durable run progress/cancel/retry.

**Architecture:** A budgeted run binds an approved ICP version, generates a bounded query plan, calls one provider-agnostic search adapter (capability manifest + fixtures), canonicalizes candidates, fetches permitted evidence through the P2 SSRF guard, and produces an immutable evidence-bound fit assessment in a checkpointed LangGraph. `run_events` carry a monotonic per-run sequence and are streamed to the UI over authenticated SSE with a polling fallback.

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic + LangGraph (pinned saver) + Celery/Valkey, PostgreSQL 16; existing Vinext/React/TS frontend.

## Global Constraints

- Canonical repository: `YNWAforever/BuyerOS` (planning pack committed at `1512d4c17d4f792e14598d524fdac3c9c37d27e7`; a source import is still expected to produce tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`).
- Plan-only artifact. No commits, pushes, installs, migrations, provisioning, paid calls, mailbox connections, or Site changes are authorized. No provider is active.
- Depends on P1 (`tenant_session`, `Principal`, `is_allowed`, `Settings`) and P2 (`IcpVersion`, `BudgetAccount`/reservations, `OutboxEvent`, `is_blocked_host`).
- Authoritative limits (03 §8.1): ≤3 rounds, ≤12 query dispatches total per logical run, ≤300 raw results, ≤200 page fetches, 2 MiB/page, 1800 s wall clock, ≤100k model tokens, provider concurrency 4.
- **No invented model IDs, provider endpoints, or prices.** Live discovery stays disabled until BO-002 verifies a provider.
- Every unexecuted check is marked **NOT RUN**.

---

### Task 1: Search adapter interface and capability manifest

**Files:**
- Create: `services/api/buyeros_api/providers/search.py`
- Create: `services/api/tests/test_search_adapter.py`

**Interfaces:**
- Produces: `@dataclass SearchResult(url,title,snippet,provider_ref)`; `@dataclass SearchCapability(verified: bool, supports_filters: set[str], max_results: int, bounded_price: bool)`; `class SearchAdapter(Protocol)` with `async def search(query, market, language, limit) -> list[SearchResult]`; `FixtureSearchAdapter` for tests.
- Consumes: nothing external (provider pinned later in BO-002).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_search_adapter.py
import pytest

from buyeros_api.providers.search import FixtureSearchAdapter, SearchCapability, is_activation_allowed


def test_unverified_provider_cannot_activate():
    assert not is_activation_allowed(SearchCapability(verified=False, supports_filters=set(), max_results=10, bounded_price=False))
    assert is_activation_allowed(SearchCapability(verified=True, supports_filters=set(), max_results=10, bounded_price=True))


@pytest.mark.asyncio
async def test_fixture_adapter_is_deterministic():
    a = FixtureSearchAdapter([{"url": "https://ex.com", "title": "t", "snippet": "s"}])
    r1 = await a.search("q", "DE", "de", 5)
    r2 = await a.search("q", "DE", "de", 5)
    assert r1 == r2 and r1[0].url == "https://ex.com"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_search_adapter.py -v` (cwd `services/api`)
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/providers/search.py
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class SearchResult:
    url: str
    title: str
    snippet: str
    provider_ref: str = ""


@dataclass(frozen=True)
class SearchCapability:
    verified: bool
    supports_filters: set[str] = field(default_factory=set)
    max_results: int = 0
    bounded_price: bool = False


def is_activation_allowed(cap: SearchCapability) -> bool:
    return cap.verified and cap.bounded_price and cap.max_results > 0


class SearchAdapter(Protocol):
    async def search(self, query: str, market: str, language: str, limit: int) -> list[SearchResult]: ...


class FixtureSearchAdapter:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    async def search(self, query: str, market: str, language: str, limit: int) -> list[SearchResult]:
        return [SearchResult(r["url"], r["title"], r.get("snippet", ""), r.get("ref", "")) for r in self._rows[:limit]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_search_adapter.py -v`
Expected: PASS (2 passed).

---

### Task 2: Bounded query planner

**Files:**
- Create: `services/api/buyeros_api/services/query_plan.py`
- Create: `services/api/tests/test_query_plan.py`

**Interfaces:**
- Produces: `@dataclass QueryPlan(queries: list[dict], rationale_summary: str)`; `validate_plan(plan, *, max_queries=12, dialects=("de","nl","fr","en")) -> QueryPlan` raising `UnsupportedDialect`/`TooManyQueries`.
- Consumes: approved ICP content (P2 Task 1).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_query_plan.py
import pytest

from buyeros_api.services.query_plan import TooManyQueries, UnsupportedDialect, validate_plan


def test_rejects_unsupported_dialect():
    with pytest.raises(UnsupportedDialect):
        validate_plan({"queries": [{"query": "x", "language": "zz"}], "rationale_summary": ""})


def test_enforces_query_cap():
    q = {"queries": [{"query": f"q{i}", "language": "de"} for i in range(13)], "rationale_summary": ""}
    with pytest.raises(TooManyQueries):
        validate_plan(q)


def test_accepts_valid_plan():
    plan = validate_plan({"queries": [{"query": "sensor distributor", "language": "de"}], "rationale_summary": "r"})
    assert plan.queries[0]["language"] == "de"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_query_plan.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/query_plan.py
from dataclasses import dataclass


class UnsupportedDialect(Exception):
    pass


class TooManyQueries(Exception):
    pass


@dataclass
class QueryPlan:
    queries: list[dict]
    rationale_summary: str


def validate_plan(plan: dict, *, max_queries: int = 12, dialects=("de", "nl", "fr", "en")) -> QueryPlan:
    queries = plan.get("queries") or []
    if len(queries) > max_queries:
        raise TooManyQueries(f"plan exceeds {max_queries} queries")
    for q in queries:
        if q.get("language") not in dialects:
            raise UnsupportedDialect(q.get("language"))
    return QueryPlan(queries=queries, rationale_summary=plan.get("rationale_summary", ""))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_query_plan.py -v`
Expected: PASS (3 passed).

---

### Task 3: Canonicalization with reversible lineage

**Files:**
- Create: `services/api/buyeros_api/services/canonicalize.py`
- Create: `services/api/tests/test_canonicalize.py`

**Interfaces:**
- Produces: `registrable_hint(url: str) -> str` (host minus leading `www`; **hint only**); `canonical_key(url: str) -> str`; `is_auto_merge_allowed(a: dict, b: dict) -> bool` (true only when registry IDs match exactly).
- Consumes: `normalize_url` (P2 safe_fetch).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_canonicalize.py
from buyeros_api.services.canonicalize import canonical_key, is_auto_merge_allowed


def test_canonical_key_normalizes_host_and_path():
    assert canonical_key("HTTPS://WWW.Example.com/#x") == "example.com"


def test_shared_domain_is_not_auto_merged():
    assert not is_auto_merge_allowed({"registry_id": "DE1", "domain": "brand.com"}, {"registry_id": "DE2", "domain": "brand.com"})


def test_matching_registry_id_may_merge():
    assert is_auto_merge_allowed({"registry_id": "DE1"}, {"registry_id": "DE1"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_canonicalize.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/canonicalize.py
def registrable_hint(url_or_host: str) -> str:
    host = url_or_host.split("://")[-1].split("/")[0].lower()
    return host[4:] if host.startswith("www.") else host


def canonical_key(url: str) -> str:
    return registrable_hint(url)


def is_auto_merge_allowed(a: dict, b: dict) -> bool:
    ra, rb = a.get("registry_id"), b.get("registry_id")
    return bool(ra) and ra == rb
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_canonicalize.py -v`
Expected: PASS (3 passed). Fuzzy/shared-domain matches go to a review queue (persisted in BO-014), never auto-merged.

---

### Task 4: Evidence validation and fit output schema

**Files:**
- Create: `services/api/buyeros_api/services/fit.py`
- Create: `services/api/tests/test_fit.py`

**Interfaces:**
- Produces: `VERDICTS = ("match","needs_review","not_a_match")`; `validate_assessment(assessment: dict, allowed_evidence_ids: set[str]) -> dict` raising `InventedEvidence` when an ID is outside the tenant/run scope; `needs_review_if_uncited(assessment) -> bool`.
- Consumes: evidence IDs (P2/BO-014).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_fit.py
import pytest

from buyeros_api.services.fit import InventedEvidence, validate_assessment


def test_rejects_invented_evidence_id():
    a = {"verdict": "match", "evidence_ids": ["ev1", "ghost"]}
    with pytest.raises(InventedEvidence):
        validate_assessment(a, {"ev1"})


def test_rejects_unknown_verdict():
    with pytest.raises(ValueError):
        validate_assessment({"verdict": "probably", "evidence_ids": []}, set())


def test_accepts_scoped_ids():
    a = validate_assessment({"verdict": "needs_review", "evidence_ids": ["ev1"]}, {"ev1"})
    assert a["verdict"] == "needs_review"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_fit.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/fit.py
VERDICTS = ("match", "needs_review", "not_a_match")


class InventedEvidence(Exception):
    pass


def validate_assessment(assessment: dict, allowed_evidence_ids: set[str]) -> dict:
    if assessment.get("verdict") not in VERDICTS:
        raise ValueError("unknown verdict")
    for eid in assessment.get("evidence_ids", []):
        if eid not in allowed_evidence_ids:
            raise InventedEvidence(eid)
    return assessment


def needs_review_if_uncited(assessment: dict) -> bool:
    return assessment.get("verdict") == "match" and not assessment.get("evidence_ids")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_fit.py -v`
Expected: PASS (3 passed).

---

### Task 5: Monotonic run events and durable progress

**Files:**
- Create: `services/api/buyeros_api/db/runs.py`
- Create: `services/api/buyeros_api/services/run_events.py`
- Create: `services/api/tests/test_run_events.py`

**Interfaces:**
- Produces: `RunEvent` (unique `(workspace_id, run_id, sequence)`); `next_sequence(last_sequence: int) -> int`; `apply_event(applied: int, incoming: int) -> bool` (ignore duplicates/out-of-order).
- Consumes: `Base`, `TenantMixin`.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_run_events.py
from buyeros_api.services.run_events import apply_event, next_sequence


def test_sequence_is_monotonic():
    assert next_sequence(0) == 1
    assert next_sequence(41) == 42


def test_duplicate_and_out_of_order_events_ignored():
    assert apply_event(applied=5, incoming=5) is False
    assert apply_event(applied=5, incoming=4) is False
    assert apply_event(applied=5, incoming=6) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_run_events.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/run_events.py
def next_sequence(last_sequence: int) -> int:
    return last_sequence + 1


def apply_event(applied: int, incoming: int) -> bool:
    return incoming > applied
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_run_events.py -v`
Expected: PASS (2 passed). The SSE endpoint (`GET /runs/{id}/events` with `after_sequence`) and cancel/retry transitions are wired in BO-016 — **NOT RUN**.

---

## Self-Review

- **Spec coverage:** P3 spec sections J (Tasks 1–2), K (Task 3), L (Task 4), M (Task 5) are mapped. Remaining P3 items needing their own tasks before Build: run admission against real budget/reservation, search dispatch + evidence fetch pipeline, LangGraph graph assembly with the pinned saver, candidate/evidence persistence, SSE route + polling fallback, and cancel/retry state machine.
- **Placeholder scan:** no `TBD`/`TODO`; each code step shows real code. Provider activation, migrations, and graph execution are **NOT RUN**.
- **Type consistency:** `SearchResult`/`SearchCapability`/`is_activation_allowed`, `validate_plan`, `canonical_key`/`is_auto_merge_allowed`, `validate_assessment`, `next_sequence`/`apply_event` are consistent across tasks and reuse P1/P2 names.

## Global Notes

- No commits, pushes, installs, migrations, provisioning, provider, or model calls are performed by this plan.
- Every command is **NOT RUN**; capture exact output in the progress record when executed under an approved task.
