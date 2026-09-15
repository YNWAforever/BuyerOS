# P7 Delivery Design Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Build is NOT authorized by this document.**

**Goal:** Deliver BO-030's only in-scope artifact — a design/task-pack for a future controlled-delivery phase — and prove MVP-A's delivery boundary stays disabled.

**Architecture:** MVP-A exposes a constant-disabled delivery boundary that rejects regardless of approval and creates no dispatch task. The future phase is documented as a separate, independently approved pack (one sender of record, verified terms/domain, suppression/reply/bounce/opt-out loops, kill switch) with no code enabled here.

**Tech Stack:** Python 3.12 + FastAPI (disabled boundary only); documentation artifacts under `docs/buyeros/`.

## Global Constraints

- Canonical repository: `YNWAforever/BuyerOS` (the audited source is imported at commit `b804ba8d1514a1049b7202c861278dd72c473a75`, tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`, merged into `main` via `72fef7da785624a35bb6701f1451ebcf0184a089`).
- Plan-only artifact. **No delivery implementation, mailbox connection, send, credential, or activation** is authorized. Delivery remains disabled in MVP-A.
- Depends on P5 (approval/export) and P6 (readiness). No provider is active.
- Defaults: single transactional ESP API sender of record (later, separately approved); one-click opt-out; idempotent send key per approval.
- Every unexecuted check is marked **NOT RUN**.

---

### Task 1: Disabled delivery boundary

**Files:**
- Create: `services/api/buyeros_api/api/routes/delivery.py`
- Create: `services/api/tests/test_delivery_disabled.py`

**Interfaces:**
- Produces: `disabled_delivery_response() -> tuple[int, dict]` always returning `(403, {"code": "DELIVERY_DISABLED", ...})`; `POST /v1/.../deliver` route that never enqueues.
- Consumes: `Principal`, `is_allowed` (P1).

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_delivery_disabled.py
from buyeros_api.api.routes.delivery import disabled_delivery_response


def test_delivery_always_disabled_even_with_approval():
    status, body = disabled_delivery_response()
    assert status == 403
    assert body["code"] == "DELIVERY_DISABLED"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_delivery_disabled.py -v` (cwd `services/api`)
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/api/buyeros_api/api/routes/delivery.py
from fastapi import APIRouter

router = APIRouter()


def disabled_delivery_response() -> tuple[int, dict]:
    return 403, {"code": "DELIVERY_DISABLED", "message": "MVP-A has no delivery capability"}


@router.post("/v1/workspaces/{workspace_id}/drafts/{draft_id}/deliver")
async def deliver(workspace_id: str, draft_id: str):
    status, body = disabled_delivery_response()
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=status, content=body)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_delivery_disabled.py -v`
Expected: PASS. This route must **never** import a mail/ESP client, hold credentials, or enqueue an outbox intent; a grep test asserting no `smtp`/`mail`/`esp` import in this module is added at Build.

---

### Task 2: Future delivery task-pack design document

**Files:**
- Create: `docs/buyeros/decisions/BO-030-delivery-task-pack-proposal.md`

**Interfaces:**
- Produces: a proposed, clearly-inactive task pack describing the future phase. No runtime interface.

- [ ] **Step 1: Draft the document** covering, at minimum:

```text
1. Scope: one sender of record; no activation.
2. Sender identity: projects.active_sender_identity_version; display name/role/org/business email; reviewer/time.
3. Domain readiness: SPF, DKIM, DMARC alignment and sending-domain reputation verification before any send.
4. Preconditions: valid exact-context approval (draft/recipient/evidence/policy/sender hash) + current suppression + opt-out + rate limits + legal/jurisdiction review.
5. Idempotency: one send key per approval; never re-send the same approval; uncertain acceptance reconciles.
6. Loops: bounce/complaint mapping, reply ingestion (distinct from manual outcomes), one-click opt-out feeding versioned suppression epochs; removal never restores approval.
7. Kill switch: stop new sends, reconcile in-flight, explicit approval to resume.
8. Audit: immutable send events referencing the exact approval; delivery status separate from approval; copy/export never becomes sent.
9. Activation: separate approval naming environment/users/market/provider/spend cap/time window; never auto-unlocked by BO-028/BO-029.
10. Open decisions: exact provider, terms, retention, jurisdiction.
```

- [ ] **Step 2: Verify the document is marked inactive**

Run: `Select-String -Path docs/buyeros/decisions/BO-030-delivery-task-pack-proposal.md -Pattern 'PROPOSED|not activated'`
Expected: at least one match. Manual review only — **NOT RUN** in this planning session.

---

## Self-Review

- **Spec coverage:** P7 spec ("Disabled delivery boundary", "Channel and sender of record", "Preconditions", "Lifecycle loops", "Idempotency/kill switch/audit", "Separation") is mapped to Tasks 1–2. There is intentionally **no** sending implementation task.
- **Placeholder scan:** Task 2 is a design checklist by design (BO-030 is a design-only task), not an implementation placeholder; Task 1 is concrete code.
- **Type consistency:** `disabled_delivery_response()` returns `(int, dict)` consistently; the future pack references existing names (`sender_identity_versions`, suppression epoch, approval fingerprint).

## Global Notes

- No commits, pushes, installs, migrations, provisioning, mailbox connections, or sends are performed by this plan.
- BO-030 completion requires its design-review acceptance evidence **and** a separate activation approval; neither is provided here.
