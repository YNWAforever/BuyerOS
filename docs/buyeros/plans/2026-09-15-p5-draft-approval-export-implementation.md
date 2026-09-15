# P5 Draft, Approval and Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Build is NOT authorized by this document.**

**Goal:** Deliver reviewed draft preparation — grounded draft revisions, an approval bound to an exact revision/recipient/evidence/policy context, authorized export/copy/download, manual outcomes with ledger-consistent usage, and bilingual/responsive/deep-link parity.

**Architecture:** Drafts are immutable revisions whose factual claims must cite approved offer-fact or evidence IDs. Approval stores a versioned canonical-JSON fingerprint (shared Python/TS golden vectors) over the exact context and is invalidated transactionally by any material change. Exports recheck current policy/approval at download and neutralize CSV formula vectors. Outcomes are append-only manual events; usage projections derive from the ledger with distinct-company denominators.

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic, PostgreSQL 16; existing Vinext/React/TS frontend; no delivery/mailbox.

## Global Constraints

- Canonical repository: `YNWAforever/BuyerOS` (planning pack committed at `1512d4c17d4f792e14598d524fdac3c9c37d27e7`; a source import is still expected to produce tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`).
- Plan-only artifact. No commits, pushes, installs, migrations, provisioning, paid calls, mailbox connections, or sends are authorized. Delivery stays disabled.
- Depends on P2 (`Evidence`, `effective_decision`, `CostEvent`) and P4 (`settle_effect`).
- Default approval fingerprint = versioned canonical JSON (UTF-8, sorted keys, LF-normalized) with shared golden vectors; **serializer version stored** with the hash.
- Every unexecuted check is marked **NOT RUN**.

---

### Task 1: Grounded draft revision and claim validation

**Files:**
- Create: `services/api/buyeros_api/db/drafts.py`
- Create: `services/api/buyeros_api/services/draft_service.py`
- Create: `services/api/tests/test_draft.py`

**Interfaces:**
- Produces: `DraftRevision` (immutable; `revision_number`, `content`, `content_hash`, `evidence_ids`, `offer_fact_ids`); `validate_grounding(revision: dict, allowed_evidence: set[str], allowed_facts: set[str]) -> dict` raising `UncitedClaim`.
- Consumes: `Base`, `TenantMixin`, `canonical_hash` (P2).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_draft.py
import pytest

from buyeros_api.services.draft_service import UncitedClaim, validate_grounding


def test_uncited_claim_rejected():
    rev = {"body": "We cut costs 40%", "evidence_ids": [], "offer_fact_ids": []}
    with pytest.raises(UncitedClaim):
        validate_grounding(rev, allowed_evidence=set(), allowed_facts=set())


def test_grounded_revision_ok():
    rev = {"body": "We supply industrial sensors", "evidence_ids": ["ev1"], "offer_fact_ids": ["f1"]}
    assert validate_grounding(rev, allowed_evidence={"ev1"}, allowed_facts={"f1"})["evidence_ids"] == ["ev1"]


def test_foreign_ids_rejected():
    rev = {"body": "x", "evidence_ids": ["ghost"], "offer_fact_ids": []}
    with pytest.raises(UncitedClaim):
        validate_grounding(rev, allowed_evidence={"ev1"}, allowed_facts=set())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_draft.py -v` (cwd `services/api`)
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/draft_service.py
class UncitedClaim(Exception):
    pass


def validate_grounding(revision: dict, allowed_evidence: set[str], allowed_facts: set[str]) -> dict:
    ev = revision.get("evidence_ids", [])
    facts = revision.get("offer_fact_ids", [])
    if not ev and not facts:
        raise UncitedClaim("revision has no cited evidence or offer facts")
    if any(e not in allowed_evidence for e in ev):
        raise UncitedClaim("unknown evidence id")
    if any(f not in allowed_facts for f in facts):
        raise UncitedClaim("unknown offer fact id")
    return revision
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_draft.py -v`
Expected: PASS (3 passed). The model-route call and token accounting are wired in BO-021 with budget reservation — **NOT RUN**.

---

### Task 2: Canonical approval fingerprint with shared golden vectors

**Files:**
- Create: `services/api/buyeros_api/services/approval_fingerprint.py`
- Create: `services/generated/approval-golden-vectors.json`
- Create: `services/api/tests/test_approval_fingerprint.py`

**Interfaces:**
- Produces: `SERIALIZER_VERSION = "approval-cjson-v1"`; `fingerprint(context: dict) -> str` (canonical JSON + SHA-256, LF-normalized, presentation fields excluded); `MATERIAL_FIELDS` set.
- Consumes: `canonical_hash` (P2).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_approval_fingerprint.py
import json
from pathlib import Path

from buyeros_api.services.approval_fingerprint import SERIALIZER_VERSION, fingerprint

GOLDEN = Path(__file__).parents[2] / "generated" / "approval-golden-vectors.json"


def test_fingerprint_matches_golden_vector():
    vectors = json.loads(GOLDEN.read_text())
    for v in vectors:
        assert fingerprint(v["context"]) == v["digest"], v["name"]


def test_fingerprint_ignores_presentation_fields():
    ctx = {"subject": "Hi", "body": "Body\n", "evidence_ids": ["ev1"], "display_locale": "zh-HK"}
    assert fingerprint(ctx) == fingerprint({**ctx, "display_locale": "en"})
    assert SERIALIZER_VERSION == "approval-cjson-v1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_approval_fingerprint.py -v`
Expected: FAIL — `ModuleNotFoundError` / missing golden file.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/approval_fingerprint.py
import hashlib
import json

SERIALIZER_VERSION = "approval-cjson-v1"
PRESENTATION_FIELDS = {"display_locale", "ui_theme", "sidebar_state"}
MATERIAL_FIELDS = {
    "draft_id", "revision_number", "subject", "body", "follow_up",
    "recipient_hash", "sender_version_key", "icp_version", "evidence_ids",
    "policy_decision_ids", "suppression_epoch",
}


def fingerprint(context: dict) -> str:
    material = {k: v for k, v in context.items() if k not in PRESENTATION_FIELDS}
    if "body" in material and isinstance(material["body"], str):
        material["body"] = material["body"].replace("\r\n", "\n")
    raw = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_approval_fingerprint.py -v`
Expected: PASS. The TypeScript mirror `services/live/approval-fingerprint.ts` must reproduce the same golden vectors; that check is **NOT RUN** until the JS test runner is pinned.

---

### Task 3: Approval transaction with material-change invalidation

**Files:**
- Create: `services/api/buyeros_api/services/approval_service.py`
- Create: `services/api/tests/test_approval.py`

**Interfaces:**
- Produces: `material_change(old: dict, new: dict) -> bool` (true if any `MATERIAL_FIELDS` differ); `approve(session, *, draft, context, expected_revision, expected_hash, actor_id)` raising `StaleApproval`.
- Consumes: `fingerprint`, `MATERIAL_FIELDS` (Task 2).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_approval.py
from buyeros_api.services.approval_service import material_change, stale


def test_material_field_change_detected():
    assert material_change({"body": "a"}, {"body": "b"}) is True
    assert material_change({"body": "a"}, {"body": "a"}) is False


def test_presentation_change_is_not_material():
    assert material_change({"body": "a", "display_locale": "en"}, {"body": "a", "display_locale": "zh-HK"}) is False


def test_stale_hash_or_revision():
    assert stale(expected_hash="h1", actual_hash="h2", expected_revision=4, actual_revision=4) is True
    assert stale(expected_hash="h1", actual_hash="h1", expected_revision=4, actual_revision=5) is True
    assert stale(expected_hash="h1", actual_hash="h1", expected_revision=4, actual_revision=4) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_approval.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/approval_service.py
from .approval_fingerprint import MATERIAL_FIELDS, PRESENTATION_FIELDS


class StaleApproval(Exception):
    pass


def material_change(old: dict, new: dict) -> bool:
    for field in MATERIAL_FIELDS:
        if field in PRESENTATION_FIELDS:
            continue
        if old.get(field) != new.get(field):
            return True
    return False


def stale(*, expected_hash: str, actual_hash: str, expected_revision: int, actual_revision: int) -> bool:
    return expected_hash != actual_hash or expected_revision != actual_revision
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_approval.py -v`
Expected: PASS (3 passed). The transactional insert/lock order and `412 STALE_REVISION` response are wired in BO-022 — **NOT RUN**.

---

### Task 4: CSV export safety and scope labeling

**Files:**
- Create: `services/api/buyeros_api/services/csv_export.py`
- Create: `services/api/tests/test_csv_export.py`

**Interfaces:**
- Produces: `neutralize(value: str) -> str`; `to_csv(rows: list[dict], columns: list[str], data_mode: str) -> str`.
- Consumes: nothing external.

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_csv_export.py
from buyeros_api.services.csv_export import neutralize, to_csv


def test_formula_prefixes_are_neutralized():
    for v in ("=1+1", "+x", "-x", "@x", "\t=x", "\r=x"):
        assert neutralize(v).startswith("'")


def test_quotes_and_newlines_are_escaped():
    out = to_csv([{"name": 'A, "B"', "city": "X\nY"}], ["name", "city"], "live")
    assert '"A, ""B"""' in out
    assert "data_mode" not in out.splitlines()[0]  # header is the column list


def test_export_carries_mode_column():
    out = to_csv([{"name": "A"}], ["name"], "live")
    assert "A" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_csv_export.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/csv_export.py
import csv
import io

FORMULA_PREFIX = ("=", "+", "-", "@", "\t", "\r")


def neutralize(value: str) -> str:
    if value and value[0] in FORMULA_PREFIX:
        return "'" + value
    return value


def to_csv(rows: list[dict], columns: list[str], data_mode: str) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow([*columns, "data_mode"])
    for row in rows:
        writer.writerow([neutralize(str(row.get(c, ""))) for c in columns] + [data_mode])
    return buf.getvalue()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_csv_export.py -v`
Expected: PASS (3 passed). Download rechecks current policy/approval via a short-lived token in BO-023 — **NOT RUN**.

---

### Task 5: Manual outcomes and usage projections

**Files:**
- Create: `services/api/buyeros_api/db/outcomes.py`
- Create: `services/api/buyeros_api/services/usage.py`
- Create: `services/api/tests/test_usage.py`

**Interfaces:**
- Produces: `OutcomeEvent` (append-only, `source='manual'`); `safe_ratio(numerator, denominator) -> str | None` returning `None` on zero denominator; `outcome_chain(events: list[dict]) -> dict`.
- Consumes: `Decimal` (P2).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_usage.py
from buyeros_api.services.usage import outcome_chain, safe_ratio


def test_zero_denominator_is_none():
    assert safe_ratio("2.400000", 0) is None
    assert safe_ratio("2.400000", 2) == "1.200000"


def test_outcome_chain_keeps_latest_superseding():
    events = [
        {"buyer_id": "b1", "stage": "meeting", "superseded": False},
        {"buyer_id": "b1", "stage": "replied", "superseded": True},
    ]
    assert outcome_chain(events)["b1"] == "meeting"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_usage.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/services/usage.py
from decimal import Decimal, ROUND_HALF_UP


def safe_ratio(numerator: str, denominator: int) -> str | None:
    if denominator == 0:
        return None
    value = (Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return f"{value:.6f}"


def outcome_chain(events: list[dict]) -> dict:
    latest: dict[str, str] = {}
    for e in events:
        if not e.get("superseded", False):
            latest[e["buyer_id"]] = e["stage"]
    return latest
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_usage.py -v`
Expected: PASS (2 passed). Distinct-company denominators and reserved/total separation are assembled from ledger projections in BO-024 — **NOT RUN**.

---

### Task 6: Deep-link route parsing and zh-HK copy coverage (frontend, interface-level)

**Files:**
- Create: `services/live/routes.ts`
- Create: `tests/contracts/routes.test.ts`
- Modify: `locales/index.ts` (inspect current dictionary keys first; snapshot-dependent)

**Interfaces:**
- Produces: `parseRoute(path: string): {name: string; id?: string} | {name: "not_found"}` covering `/app/discover/:runId`, `/app/buyers/:buyerId`, `/app/lists/:listId`, `/app/outreach/:draftId`, `/app/results`, `/app/settings`.
- **Verification required:** read `locales/index.ts` and `features/workspace.tsx` at the imported commit to capture exact keys/paths before editing.

- [ ] **Step 1: Write the failing test**

```ts
// tests/contracts/routes.test.ts
import { describe, expect, it } from "vitest";
import { parseRoute } from "../../services/live/routes";

describe("route parsing", () => {
  it("parses a known buyer deep link", () => {
    expect(parseRoute("/app/buyers/abc")).toEqual({ name: "buyer", id: "abc" });
  });
  it("rejects unknown routes without falling back to the sample run", () => {
    expect(parseRoute("/app/unknown").name).toBe("not_found");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm exec vitest run tests/contracts/routes.test.ts`
Expected: FAIL — module not found (a JS runner must be pinned; the repo has no `test` script today).

- [ ] **Step 3: Write minimal implementation**

```ts
// services/live/routes.ts
type Route = { name: string; id?: string } | { name: "not_found" };

export function parseRoute(path: string): Route {
  const parts = path.replace(/\/+$/, "").split("/").filter(Boolean);
  const [app, section, id] = parts;
  if (app !== "app") return { name: "not_found" };
  const known: Record<string, string> = {
    discover: "run",
    buyers: "buyer",
    lists: "list",
    outreach: "draft",
  };
  if (section === "results" || section === "settings") return { name: section };
  if (section in known && id) return { name: known[section], id };
  if (section in known) return { name: known[section] };
  return { name: "not_found" };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm exec vitest run tests/contracts/routes.test.ts`
Expected: PASS, or **NOT RUN** if no runner is approved.

---

## Self-Review

- **Spec coverage:** P5 spec sections R (Task 1), S (Tasks 2–3), T (Task 4), U (Task 5), V (Task 6) are mapped. Remaining P5 items needing their own tasks before Build: draft-generation route with model budget, review/approve HTTP routes, export job + download route, outcomes HTTP routes, usage/overview endpoints, full zh-HK string coverage, and Playwright responsive/keyboard suites.
- **Placeholder scan:** no `TBD`/`TODO`; each code step shows real code. Frontend files are flagged for source verification rather than assumed.
- **Type consistency:** `validate_grounding`, `fingerprint`/`SERIALIZER_VERSION`/`MATERIAL_FIELDS`, `material_change`/`stale`, `neutralize`/`to_csv`, `safe_ratio`/`outcome_chain`, `parseRoute` are consistent across tasks and reuse P2 names.

## Global Notes

- No commits, pushes, installs, migrations, provisioning, provider, or mailbox actions are performed by this plan. Delivery remains disabled.
- Every command is **NOT RUN**; capture exact output in the progress record when executed under an approved task.
