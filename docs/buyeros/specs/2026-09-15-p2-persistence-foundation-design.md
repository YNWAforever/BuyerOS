# P2 design — persistence vertical slice and paid-operation foundation

**Status: PROPOSED / PLAN ONLY.** Plan revision v1. Recorded 2026-09-15 (Hong Kong). Design covers tasks **BO-007, BO-008, BO-009, BO-010, BO-011, BO-012** (phase P2). Approved in the Plan review session; this is a design input, not Build approval.

No application code, lockfile, dependency install, database migration, cloud resource, deployment, Site access change, paid provider call, mailbox connection, message, commit or push is authorized or performed by this document. No provider is activated and no paid step is enabled.

Related records: [P1 boundary design](2026-09-15-p1-boundary-design.md), [BO-001 decision](../decisions/BO-001-runtime-identity.md), [02 architecture](../02_ARCHITECTURE_AND_REUSE.md), [03 data/API contracts](../03_DATA_API_AND_STATE_CONTRACTS.md), [contracts/openapi.proposed.yaml](../contracts/openapi.proposed.yaml).

Base content commit: `b804ba8d1514a1049b7202c861278dd72c473a75`, tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`. Canonical repository: `YNWAforever/BuyerOS` (the audited source is imported at commit `b804ba8d1514a1049b7202c861278dd72c473a75`, tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`, merged into `main` via `72fef7da785624a35bb6701f1451ebcf0184a089`).

## Scope

Deliver the first persisted vertical slice (project → approved profile → reviewed buyer/list) plus the foundations a billable operation must pass through: purpose policy, atomic budgets, a durable outbox/queue, and safe file/web intake.

In scope: BO-007, BO-008, BO-009, BO-010, BO-011, BO-012. Out of scope: real discovery/model/contact calls (BO-013+), provider adapters (BO-002 outputs), delivery, cloud provisioning. The P1 boundary (BO-004/005/006) is a prerequisite.

## D. Projects, offers and approved profiles (BO-007)

- `projects` are workspace-scoped. An **offer** is an editable draft belonging to a project.
- Each save creates a new **pending `icp_version`**; saved versions are **immutable**. Versions carry stable requirement/offer-fact IDs, monotonic number, parent pointer, and a server-computed **content hash**.
- **Approval** binds the exact version number + content hash + approver identity/time. The client cannot set approval fields; approval is a server operation.
- Editing an approved profile creates a **successor version**. Old review/fit bases become stale for future guarded actions; historical evidence and reviews are never rewritten.
- `offer_documents`: private object key, SHA-256, MIME, parser status, retention expiry, uploader. Objects are **quarantined first** and only become usable inputs after validation.
- Operations map to `createProject`, `updateProject`, `listICPVersions`, `saveICPVersion`, `approveICPVersion`, `uploadOfferDocument`, `getOfferDocument` in the OpenAPI.

## E. Buyer evidence, reviews, selections and lists (BO-008)

- Immutable **`fit_assessments`** (bound to ICP version + evidence-set hash) are **separate** from append-only **`human_reviews`**. Accepting a buyer never changes AI fit or contact validity; rejecting invalidates relevant approvals.
- **Selection snapshots:** the server materializes ordered `(ordinal, buyer_id, buyer_version)` for a normalized filter/sort, proposed 15-minute TTL, maximum 1,000 IDs, tied to actor/workspace/project/filter hash.
  - "Select this page" = explicit versioned IDs.
  - "Select all filtered" = snapshot ID + explicit excluded IDs.
  - Filter, sort or locale change creates a new snapshot and clears selection. A snapshot cannot outlive authorization or be reused across actors/projects.
- **Lists** are membership-only: removal keeps the company and evidence; duplicate add is a no-op; rename/versioning is audited.
- **Notes/owner** use optimistic concurrency (`If-Match` on the buyer version) and write an audit event; assignment targets an active project member.

## F. Purpose policy and scoped suppression (BO-009) — configurable, fail-closed

- `policy_decisions` are immutable records keyed by subject/controller context + purpose, with basis/version/author/review expiry and `supersedes`. Current lookup is `(workspace, subject, purpose)`; the **most restrictive applicable rule wins**.
- Purposes are evaluated **separately**: `research`, `contact_lookup`, `export`, `outreach`. A contact-research decision never grants outreach or export permission. Independent dimensions remain: AI fit, human review, contact validity, suppression, research permission, outreach permission, draft approval, delivery.
- **Effective states:** `unknown` / `requires_review` / `permitted` / `blocked`. `unknown` and expiry **fail closed** for the relevant operation.
- `suppressions` are an independent overlay with controller/workspace/project + purpose scope. Adding a suppression invalidates affected approvals and stops unsubmitted operations; removing it does **not** restore prior approvals or change contact validity. Removal is audited.
- **The engine is designed now; the actual market/entity/purpose/basis values remain unset** (owner-supplied policy). With no supplied decision, live personal-data operations stay blocked. No legal-compliance claim is implied.

## G. Atomic budget and bounded spend (BO-010)

- Money uses PostgreSQL `NUMERIC(20,6)` and Python `Decimal`; HTTP amounts are decimal **strings** (e.g. `"2.400000"`). The pilot accounting currency is USD; provider credits/subscriptions/infrastructure are stored as separate units and never silently summed.
- Accounts exist per `(workspace, project, run, category)`. Invariant for every applicable account: `settled_spend + active_reserved_upper_bounds + proposed_upper_bound <= approved_limit`. The tightest applicable limit controls execution.
- A confirmation/reservation **locks every applicable account in deterministic ID order** in one transaction; never check budget in the browser or across separate transactions. Project creation provisions zero-limit project/category accounts; only a budget admin raises limits.
- Append-only ledger events: `reserve`, `commit/settle`, `release`, `reconcile`, `reversal`. Reservation groups with per-account allocations; a batch may reserve a bounded total then allocate to operations without a second economic hold.
- **Unknown holds:** a submission uncertainty keeps the reservation at its upper bound across period boundaries (`carried_reserved` is a subset of `reserved`, not new spend). Period rollover never resets or releases unknown/in-flight holds; a zero-limit new period is `frozen_pending_budget` until an admin explicitly approves a covering limit. No "age out" of uncertainty into free budget.
- Limit reduction below `settled + effective_reserved` returns `409 BUDGET_LIMIT`; an emergency freeze stops new admission without changing holds.

## H. Durable outbox and queue (BO-011)

- Business intent and its `outbox_events` row are committed in the **same transaction**. There is one task transport: **Celery with one Valkey broker**.
- The dispatcher publishes **deterministic task IDs**; workers handle duplicate delivery idempotently against DB operation state. Acknowledgement follows committed work, not receipt.
- **Leases use DB time with a fencing generation** so a superseded worker cannot commit a step. A sweeper re-enqueues committed jobs whose lease expired without terminal business state, reconstructing intent after broker loss.
- Queue messages carry opaque IDs + workspace ID, never bearer tokens or contact payloads. LangGraph checkpoints and queue acknowledgements are **not** business truth. Unknown paid submissions are never blindly retried.
- Chosen broker policy is a persistent, non-evicting plan; visibility timeout is set longer than the largest bounded task and tested under worker/broker loss.

## I. Safe file and web intake (BO-012)

- **Upload path:** quarantine first → MIME/content sniff + size cap → parse **text/Markdown only**. **PDF parsing is deferred** to a separate task that selects a reviewed, permissively licensed parser; PDF uploads are accepted to quarantine but explicitly labelled unsupported, never silently "analyzed". No AGPL parser (PyMuPDF/PDF4LLM) is adopted.
- **Fetch path:** BuyerOS-owned SSRF-safe fetcher:
  - parse + normalize URL; resolve DNS and **pin the IP per hop**;
  - block private/loopback/link-local/IPv6-local/metadata targets;
  - follow ≤3 redirects, re-validating the destination each hop;
  - 2 MiB decoded cap; content-type allowlist; no JS execution;
  - sanitize to text; store `source_documents` (canonical URL, digest, retrieval time, language, storage mode) and `evidence` (supports/contradicts/qualifies, observation/inference labelling).
  - Fetched content is **untrusted data**; it can never add tools, change policy, authorize spend, or issue instructions.
- **Gate:** after BO-012 no paid search/model/contact step is reachable without tenant + purpose gates, an atomic budget reservation, and durable job intent.

## Cross-cutting

RLS + composite tenant FKs and the single Alembic migration owner from the P1 spec apply to every new table. All mutating endpoints require bearer auth, an `Idempotency-Key` (except provider callbacks), and version preconditions where relevant. Live responses carry `{data, request_id, data_mode:"live"}`; demo and live stores never mix.

## Data flow

Wizard offer/profile → project + versioned ICP → approval (hash-bound) → persisted project with zero-limit budget accounts → (later) discovery job → immutable assessment + human review → snapshot-backed selection → optional policy-gated, budget-reserved paid operation via outbox/queue. Upload/fetch intake produces quarantined/permitted sources feeding evidence only.

## Interfaces

Provider-neutral public API per the proposed OpenAPI (`/v1/workspaces/{workspace_id}/projects/{project_id}/…`). No new endpoint may be invented; client/server disagreement is a reviewed contract revision. Error codes/envelopes follow 03 §4.

## Testing (all PROPOSED_AFTER_TASK / NOT RUN)

| Test | Expectation |
|---|---|
| TEST-BO-007-01 | immutable approved profile persists; concurrent edit → 409; old assessment stays tied to its old version |
| TEST-BO-008-01 | exact page/all-filtered selection; per-item conflicts; stable pagination; list removal keeps evidence |
| TEST-BO-009-01 | unknown/expired policy blocks the operation; lookup permission never implies outreach; cross-client suppression scoped |
| TEST-BO-010-01 | many simultaneous reservations near cap cannot overspend; UTC rollover + carried/unknown holds stable; reduction below settled+held rejected |
| TEST-BO-011-01 | kill between commit and enqueue loses no accepted job; duplicate delivery/expired lease/queue outage handled; no duplicate business writes |
| TEST-BO-012-01 | SSRF set (private/loopback/link-local/rebinding/redirect), oversize body, upload parser escape, prompt injection all blocked before harm |

Supporting: OpenAPI parse (70 ops / 139 schemas / 0 unresolved — verified in planning), `node tests/domain-checks.mjs`, `pnpm exec tsc --noEmit` — NOT RUN.

## Assumptions, blockers and non-goals

- **Blocked by:** B-POLICY (actual policy values), B-PROVIDERS (no provider active), B-HOST (R2/Neon/Render provisioning), B-LICENSE (PDF deferral). BO-007 depends on BO-005/006; BO-008 on BO-007; BO-009 on BO-008; BO-010 on BO-005/009; BO-011 on BO-005/010; BO-012 on BO-007/009/011.
- **Non-goals:** running paid discovery/LLM/contact, provider adapters, drafting, delivery, schema migrations executed, provisioning, and any Build action.

## Completion criteria

No task is completed by this document. BO-007…BO-012 may be marked DONE only when their own acceptance tests and approval obligations have recorded evidence.

## Rollback / roll-forward

Supersede this design with a dated successor for design changes. For implementation, prefer forward-compatible expand/contract migrations and additive repair; never discard committed financial records or release unknown holds to satisfy a limit.
