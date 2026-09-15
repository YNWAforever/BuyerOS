# P4 design — guarded contact quote, atomic confirmation, uncertainty-safe submit, reconciliation

**Status: PROPOSED / PLAN ONLY.** Plan revision v1. Recorded 2026-09-15 (Hong Kong). Design covers tasks **BO-017, BO-018, BO-019, BO-020** (phase P4). Approved in the Plan review session; this is a design input, not Build approval.

No application code, lockfile, dependency install, database migration, cloud resource, deployment, Site access change, paid provider call, contact purchase, mailbox connection, message, commit or push is authorized or performed by this document. No provider is activated and no paid step is enabled.

Related records: [P1 boundary design](2026-09-15-p1-boundary-design.md), [P2 foundation design](2026-09-15-p2-persistence-foundation-design.md), [P3 discovery/fit design](2026-09-15-p3-discovery-fit-design.md), [02 architecture](../02_ARCHITECTURE_AND_REUSE.md), [03 data/API contracts](../03_DATA_API_AND_STATE_CONTRACTS.md), [contracts/openapi.proposed.yaml](../contracts/openapi.proposed.yaml).

Base content commit: `b804ba8d1514a1049b7202c861278dd72c473a75`, tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`. Canonical repository: `YNWAforever/BuyerOS` (the audited source is imported at commit `b804ba8d1514a1049b7202c861278dd72c473a75`, tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`, merged into `main` via `72fef7da785624a35bb6701f1451ebcf0184a089`).

## Scope

Deliver the optional business-contact path as a sequence of independently guarded states: quote (no dispatch) → confirm (atomic reservation + durable job) → submit (uncertainty-safe) → reconcile (callbacks/status) and cancellation. Real contact purchase stays **disabled** until the provider capability gate is satisfied.

In scope: BO-017, BO-018, BO-019, BO-020. Out of scope: drafting/approval (BO-021+), delivery, provider selection (BO-002), provisioning. Depends on the P1–P3 designs and BO-002/009/010/011/016.

## Decision defaults

- **Contact provider:** one provider behind a verified capability manifest; activation requires bounded max charge + status retrieval + **(idempotency OR a safe unknown-submission + manual-reconciliation path)**. Until verified, the contact path is disabled. No fallback waterfall. (This question was left unanswered in session; recorded as the default, open to owner confirmation.)
- **Reconciliation:** signed **webhook primary**, authenticated **polling fallback**.

## N. Quote without dispatch (BO-017)

- Eligibility is computed server-side only: an accepted review on the current Match ICP/evidence, contact-research purpose permitted, not suppressed, a supported requested role/contact type, and no already-covered active lookup.
- A quote is an **immutable snapshot**: frozen selection (ids + expected versions), purpose, roles, request hash, profile/review/policy versions, provider adapter + pricing version, decimal `max_cost`, and server expiry. A quote **holds no money** and creates **no provider job** (`reservation_id = null`, `consumed_job_id = null`).
- Response returns the eligible set and explicit skipped/blocked reasons. UI copy is "Quote expires…" and "Maximum cost"; it must not claim money is reserved on dialog open.
- Quote is actor-bound: an administrator cannot confirm another operator's quote and must request a fresh one.
- Operations: `quoteLookup`, `getLookupQuote`.

## O. Confirm once with atomic reservation and durable job (BO-018)

- **One transaction**, in order: authenticate and derive actor/workspace → acquire idempotency scope → lock quote → reject consumed/expired/cancelled or request/quote-hash/price-version mismatch → resolve the frozen selection → lock buyer/gate rows in sorted UUID order → recheck acceptance, fit, policy, suppression, capability and price upper bound → lock every applicable budget account in deterministic ID order → verify and increment reserved balances → insert reservation + allocations, the unique enrichment job, provider intent records, the consumed-quote pointer, outbox messages, audit and idempotency result → **commit together**. Any failure queues/reserves nothing.
- Returns `202` with a durable job ID, never an address.
- Idempotency: same key/same body returns the original result; same key/different body is `409`; two keys on one quote yield exactly one consumption.
- If eligibility changes during confirm, the quote is invalidated; **only** an explicit `confirm_eligible_only` permits charging a changed eligible subset.
- Operations: `confirmLookup`.

## P. Uncertainty-safe submission (BO-019)

- **Before the network call:** lock intent/gates, recheck permission/suppression/cancellation and the reserved bound, commit `submitting` plus a stable provider idempotency identity. **Never hold a database transaction across the external HTTP call.**
- **Capability gate:** activation requires a verified bounded maximum charge, status retrieval, and either idempotency or a safe unknown-submission + manual-reconciliation path. If any is unverified, contact submission stays disabled.
- **After the call:** settle the exact observed result/charge **once**, store permitted result + operation identifiers, update events/ledger, and release only a proven-unused bound. A timeout leaves the operation `unknown` with the reservation **held**. No blind retry of an unknown submission.
- Composite result counts retain per-operation states. `failed` does not by itself prove no charge.

## Q. Reconcile, callback replay and cancellation (BO-020)

- **Webhook (primary):** the normalized callback schema and `X-Provider-Signature` are **PROPOSED adapter contracts, not a verified vendor API**. The handler verifies raw vendor bytes first, enforces body size and a replay window, dedupes `(provider, account, event_id)` with digest-conflict quarantine, maps a server-owned operation identity (caller-supplied workspace IDs are forbidden), and applies only allowed **monotonic** transitions under lock. A duplicate callback returns success without repeating cost or contact insertion; completed-before-pending must not regress.
- **Polling (fallback):** authenticated status query for stuck/unknown operations, plus an administrative exception review. A late result arriving after suppression/policy revocation is quarantined/deleted per policy while the legitimate charge is retained.
- **Cancellation:** `cancel_requested` is independent of pending/unknown provider states. Cancel before dispatch may release a proven-unsent bound; cancel during submit or after a result reconciles and retains possible charges. Closing the UI never proves the provider cancelled.
- **Ledger:** append-only `reserve` / `commit` / `release` / `reconcile` / `reversal`. Unknown holds persist across budget periods (`carried_reserved`); provider credit/invoice reconciliation records variance explicitly. Never "age out" uncertainty into free budget.
- Operations: `getEnrichmentJob`, `cancelEnrichmentJob`, provider callback, `getLookupQuote`, `cancelLookupQuote`.

## Cross-cutting

RLS + composite tenant FKs and the single Alembic migration owner apply to all new tables. Mutations carry an `Idempotency-Key` and version preconditions where relevant; provider callbacks are exempt from the client key but verified by signature. Live responses use `{data, request_id, data_mode:"live"}`. Provider failure never returns demo fixtures.

## Data flow

Eligible buyer → quote (immutable, no hold) → confirm (single transaction: revalidate + reserve + job + outbox) → outbox dispatch → worker submit (`submitting` committed before call; provider idempotency identity) → accepted/pending/unknown → webhook and/or polling reconcile exactly once → settlement or reconciliation, hold released only when proven unused; cancellation handled independently.

## Interfaces

Provider-neutral public API per the proposed OpenAPI. No new endpoint may be invented; any disagreement is a reviewed contract revision. Error codes/envelopes follow 03 §4 (including `PROVIDER_SUBMISSION_UNKNOWN`, `QUOTE_CHANGED`, `QUOTE_EXPIRED`, `BUDGET_LIMIT`).

## Testing (all PROPOSED_AFTER_TASK / NOT RUN)

| Test | Expectation |
|---|---|
| TEST-BO-017-01 | quote binds normalized request/purpose/price/actor; expired/consumed/altered quote rejected; opening/closing the dialog dispatches nothing |
| TEST-BO-018-01 | same key/same body returns prior result; changed body conflicts; two keys/one quote → one job+reservation; budget lock atomic |
| TEST-BO-019-01 | crash before call may release proven-unsent; crash after acceptance/timeout → unknown with held bound; no blind retry without verified guarantees |
| TEST-BO-020-01 | duplicate/out-of-order callbacks settle once; late charge reconciled; revoked-policy result quarantined; invoice variance visible |

Supporting: deterministic provider fixtures, `node tests/domain-checks.mjs`, `pnpm exec tsc --noEmit` — NOT RUN. No live provider call is authorized.

## Assumptions, blockers and non-goals

- **Blocked by:** B-PROVIDERS (provider guarantee proof), B-POLICY (contact-research permission), B-HOST. Dependencies: BO-017 needs BO-002/008/009/010/016; BO-018 needs BO-011/017; BO-019 needs BO-018; BO-020 needs BO-019.
- **Non-goals:** real contact purchase, provider selection, drafting, delivery, migrations executed, provisioning, and any Build action.

## Completion criteria

No task is completed by this document. BO-017…BO-020 may be marked DONE only when their own acceptance tests and approval obligations have recorded evidence.

## Rollback / roll-forward

Supersede this design with a dated successor for design changes. Prefer forward-compatible migrations and additive repair; never discard committed charges or release unknown holds to satisfy a limit.
