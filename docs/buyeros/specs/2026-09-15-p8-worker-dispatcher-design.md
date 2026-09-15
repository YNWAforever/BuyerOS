# P8 design — outbox dispatcher and durable worker

**Status: PROPOSED / PLAN ONLY.** Plan revision v1. Recorded 2026-09-15 (Hong Kong). Design covers the worker/dispatch phase. Approved in the Plan review session; this is a design input, not Build approval.

No application code, lockfile, install, migration, cloud resource, deployment, Site access change, paid provider call, mailbox connection, message, or send is authorized by this document. Execution happens only under the explicit dependency waiver recorded for the BO-005 spike.

Related records: [P2 foundation](2026-09-15-p2-persistence-foundation-design.md), [P3 discovery/fit](2026-09-15-p3-discovery-fit-design.md), [P4 contact](2026-09-15-p4-contact-guardrails-design.md), [BO-005 spike record](../decisions/BUILD_APPROVAL_RECORD.BO-005.md), [02 architecture](../02_ARCHITECTURE_AND_REUSE.md).

Base content commit: `b804ba8d1514a1049b7202c861278dd72c473a75`, tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`. Canonical repository: `YNWAforever/BuyerOS`.

## Scope

Deliver the durable execution layer that turns committed outbox intents into worker work: a dispatcher, a Celery/Valkey worker, database leases with fencing, a recovery sweeper, run/event emission, and a handler registry with one genuinely implementable handler (`fetch.evidence`). No HTTP API, auth, or real provider is in scope.

## A. Architecture and boundaries

- New `services/worker/` with package `buyeros_worker`, depending on `buyeros_api` by **local path** (uv path dependency). One domain package: models, transaction-local tenant context, budget/policy rules and migrations stay in `buyeros_api`.
- **Celery worker + one Valkey broker** (ADR-06). Result backend disabled — Postgres holds job identity and business truth.
- Two roles share one built image: **dispatcher** and **worker**.

## B. Dispatch and lease protocol

1. Dispatcher selects `outbox_events` rows in `state='ready'` (bounded batch), claims each with a **DB lease**, and publishes the already-deterministic intent id (`outbox_service.build_intent`) to the broker.
2. Claim is an atomic conditional update: set `lease_owner`, `lease_expires_at`, and increment `fencing_generation` only when the row is `ready` or its lease has expired.
3. Worker resolves the intent from the database by id, re-derives the tenant context, and runs the handler. **Ack only after commit.**
4. **Fencing:** every state write asserts the worker's `fencing_generation`; a superseded worker's commit is rejected (0 rows) and the task exits without side effects.
5. **Sweeper:** periodic task re-enqueues intents whose lease expired without a terminal state; this recovers from broker loss and worker death. Recovery before dispatch also reconciles reservations/held work, but never releases unknown paid holds.
6. Schema: new `worker_leases` table and outbox columns (`dispatched_at`, `lease_owner`, `lease_expires_at`, `fencing_generation`) via one Alembic migration `0006_worker_leases` owned by `buyeros_api`.

## C. Handler registry and lifecycle

- A registry maps `event_type` → handler. Handlers receive `(session, tenant_context, intent_payload)` and may only write through the tenant-scoped session.
- **Implemented now:** `fetch.evidence` — validates and normalizes the URL with `safe_fetch.normalize_url`, blocks private/loopback/link-local/metadata hosts via `is_blocked_host`, enforces a decoded-size cap and content-type allowlist, follows at most three re-validated redirects, stores `source_documents` (with digest/language) and permitted `evidence` rows. Fetched content is untrusted data.
- **Registered but fail-closed:** `run.discover`, `contact.submit`, `draft.generate`. With no verified provider/model they transition the run/job to a capability-blocked terminal state, emit one `run_events` row, and make **no external call**.
- **Run lifecycle:** `draft → queued → running → completed/partial/paused_budget/failed`; active → `cancel_requested → cancelled`; eligible terminal → `queued` on explicit retry. Every transition commits **atomically with its `run_events` row** (monotonic sequence; duplicates/out-of-order ignored via `run_events.apply_event`).
- **Contact safety:** no contact handler executes, so an unknown paid submission cannot occur; if one is later added it must retain its hold and never blind-retry.

## D. Error and concurrency semantics

- Exceptions are classified **retryable** (transient DB/network in fetch) vs **terminal** (capability-blocked, validation, fencing rejection). Terminal errors never retry.
- Retries are bounded with backoff; exhaustion produces a terminal `failed` with exactly one terminal event and partial results preserved.
- Duplicate broker delivery is idempotent: the worker checks terminal state and the fencing generation before writing.
- Checkpoints and queue acknowledgements are **not** business truth; business state lives in the domain tables.

## E. Testing and local runtime

| Check | Approach |
|---|---|
| Dispatch → execute → commit | Celery eager mode + disposable Postgres fixture |
| Duplicate delivery | same intent delivered twice → one semantic effect |
| Expired lease / worker death | sweeper re-enqueues; fencing rejects the stale worker's commit |
| Kill between commit and enqueue | accepted job survives; recovered exactly once semantically |
| `fetch.evidence` safety | blocked hosts, oversized body, disallowed content-type, redirect re-validation |
| Capability-blocked handlers | terminal blocked state, no outbound call |
| Broker integration | one test with a **disposable Valkey container**, skipped when Docker is unavailable |

Local runtime: `uv run celery -A buyeros_worker.app worker` plus a dispatcher/sweeper command, against disposable Postgres and Valkey containers. No deployment.

## F. Scope, limits and non-goals

- **In:** dispatcher, Celery app, DB leases + fencing, sweeper/recovery, `worker_leases` migration, `fetch.evidence`, capability-blocked handlers, run/event lifecycle, tests.
- **Out:** HTTP API, auth (BO-004, blocked by B-IDENTITY), real search/LLM/contact providers (BO-002), canonicalization/fit graph, drafting, delivery, cloud provisioning.
- Operates under the existing **dependency waiver** (BO-003/BO-004/BO-011 not complete). No task is marked DONE by this design.

## Completion criteria

The worker phase is complete only when its acceptance evidence is recorded and reviewed; this document does not complete any task. A capability-blocked handler is an explicit, expected state — not a passing provider integration.

## Rollback / roll-forward

Supersede this design with a dated successor for design changes. On failure, stop new dispatch, retain reservations and held work, reconcile committed outbox/leases before resuming, and prefer forward-compatible changes over destructive resets.
