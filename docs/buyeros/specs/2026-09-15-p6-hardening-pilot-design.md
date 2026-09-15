# P6 design — hardening, recovery proof, pilot readiness, bounded activation

**Status: PROPOSED / PLAN ONLY.** Plan revision v1. Recorded 2026-09-15 (Hong Kong). Design covers tasks **BO-026, BO-027, BO-028, BO-029** (phase P6). Approval acknowledged with "ok"; this is a design input, not Build, provisioning, or activation approval.

No application code, lockfile, dependency install, database migration, cloud resource, deployment, Site access change, paid provider call, contact purchase, mailbox connection, message, commit or push is authorized or performed by this document. BO-029 in particular requires its own separate, explicit owner approval.

Related records: [P1](2026-09-15-p1-boundary-design.md), [P2](2026-09-15-p2-persistence-foundation-design.md), [P3](2026-09-15-p3-discovery-fit-design.md), [P4](2026-09-15-p4-contact-guardrails-design.md), [P5](2026-09-15-p5-draft-approval-export-design.md), [02 architecture](../02_ARCHITECTURE_AND_REUSE.md), [03 data/API contracts](../03_DATA_API_AND_STATE_CONTRACTS.md), [05 test/security/release](../05_TEST_SECURITY_AND_RELEASE.md).

Base content commit: `b804ba8d1514a1049b7202c861278dd72c473a75`, tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`. Canonical repository: `YNWAforever/BuyerOS` (empty; exact import expected).

## Scope

Provide observable security/lifecycle controls, prove crash and financial-race recovery, prepare a reviewable pilot with a human-evaluation protocol, and define (without activating) the bounded live pilot.

In scope: BO-026, BO-027, BO-028, BO-029. Out of scope: delivery (BO-030), provider selection, and any live call, provisioning, or deployment.

## W. Tenant data, retention, secrets and dependency boundaries (BO-026)

- **End-to-end negative tests:** cross-tenant access, export/privacy bypass, SSRF, and approval bypass, plus dependency/secret/license scanning.
- **Retention (provisional, configurable):** ~30-day run-event replay window, 15-minute buyer-snapshot and export TTLs, source-specific and contact TTLs. Deletion/expiry propagates to private objects, extracted fields, caches, checkpoints, contacts, and derived evidence/fit/approval visibility. A minimal non-content audit event is retained; immutable financial/audit hashes are preserved while personal payload is deleted. A deleted source's hash alone does not substantiate its old claim.
- **Secrets** exist only in server-side secret configuration, never in browser code, fixtures, logs, prompts, analytics, or checkpoints. Signed URLs are short-lived and tenant-authorized; their query strings are redacted from logs.
- **Database roles** remain least-privilege: API and worker are non-owner with no `BYPASSRLS`; migrations use a separate owner role.
- **Dependencies:** an SBOM/license inventory is recorded; GPL reuse stays deferred; PDF-parser adoption stays deferred (text/Markdown only).
- **Stop conditions:** tenant leakage, send capability appearing in MVP-A, repeated unexplained charges, or a missing authoritative budget lock.

## X. Crash recovery, budget races and reversible release (BO-027)

- **Crash windows tested on a disposable stack:** kill between DB commit and enqueue; duplicate delivery; expired lease; worker crash after vendor acceptance but before local ack; concurrent reservations at the cap and at a UTC rollover; kill switch; and backup restore.
- **Reconciliation:** the ledger settles exactly once; unknown holds are retained; deleted content is not re-exposed (deletion tombstones are replayed before serving restored data); outbox, external operation IDs, ledger, reservations, and checkpoints are reconciled **before** dispatch resumes.
- **Migrations:** expand/contract rehearsal against fresh and previous supported schemas; no production migration during a test; destructive removal requires a later approved task plus backup evidence.
- **Objectives (pending host approval):** RPO ≤24h, RTO ≤4h. Roll back application versions only when schema-compatible; otherwise roll forward with an additive repair; never discard charged operations.

## Y. Reviewable pilot release and human evaluation protocol (BO-028)

- **Readiness evidence pack:** current commit/diff, acceptance-test results, security-findings disposition, named operator, retention/deletion evidence, telemetry, restore evidence, and a signed scope/budget/policy approval.
- **Evaluation scope:** one tenant, one approved offer/ICP, DE/NL/BE distributor/systems-integrator markets, **30–50 real companies**, each reviewed by **two designated humans**. Contact lookup is optional and limited to a separately approved subset.
- **Metrics (pending approval):** accepted-candidate precision ≥80% (report numerator/denominator and sampling); evidence structural linkage 100% with empirically supported claims ≥95% of sampled claims; reviewer agreement ≥80%; contact yield measured with no promised yield (catch-all reported separately); cost per accepted and per contactable company reported with scope and active holds; human review-time baseline.
- **Stop triggers:** tenant leakage, unauthorized contact access, unsupported material claims passing review, unexpected send behavior, oversubscribed reservation invariant, or unknown provider costs without reconciliation support.
- All readiness gates (G0–G5 in 05 §7) remain **NOT SATISFIED / NOT RUN** until evidence exists.

## Z. Bounded live activation (BO-029) — design only

- Requires a **separate, explicit owner approval** naming environment, users, market/purpose, providers, maximum spend, currency, time window, and retention.
- Executes the bounded slice (discovery → evidence → acceptance → optional quote/contact → grounded draft → approval → manual outcome) with measured costs, stop triggers, and a documented go/no-go. **No sending in any case.**
- BO-028 completion never auto-unlocks BO-029. Activated spend, data scope, and provider use are independently authorized and capped.
- On any stop trigger: stop new work, retain reservations, reconcile submitted operations, and review evidence before any resumption.

## Cross-cutting

All P1–P5 controls (identity, RLS/FKs, policy, budgets, outbox/queue, intake, drafts/approval, export, outcomes) apply. No provisioning, no live provider call, no deployment, and no Site access change is part of this design.

## Data flow

Security/lifecycle controls wrap existing flows; recovery tests operate on a disposable full stack; the pilot protocol consumes readiness evidence; activation is gated by a separate approval and bounded by caps, stop triggers, and reconciliation.

## Interfaces

Provider-neutral public API per the proposed OpenAPI; health/readiness distinguishes API reachable, database usable, queue unavailable, provider disabled, and capability policy-blocked. No decorative "Connected" label may substitute for readiness.

## Testing (all PROPOSED_AFTER_TASK / NOT RUN)

| Test | Expectation |
|---|---|
| TEST-BO-026-01 | tenant/export/privacy/SSRF/approval bypasses do not succeed; dependency/secret scan has no unresolved high-risk item; audit redacted |
| TEST-BO-027-01 | restore reconciles ledger/holds/outbox; deleted content not re-exposed; no migration runs in production during the test; kill switch works |
| TEST-BO-028-01 | readiness evidence review passes; protocol has named scope/budget/policy approval and stop criteria |
| TEST-BO-029-01 | only a separately approved bounded live evaluation runs; measured costs and go/no-go recorded; no sending |

Supporting: `node tests/domain-checks.mjs`, `pnpm exec tsc --noEmit`, disposable PostgreSQL/Valkey, fake providers with denied external egress — NOT RUN. No live provider, mailbox, or deployment action is authorized.

## Assumptions, blockers and non-goals

- **Blocked by:** B-POLICY, B-PROVIDERS, B-HOST, B-LICENSE (residual), B-PILOT, B-APPROVAL. Dependencies: BO-026 needs BO-012/020/022/023/024/025; BO-027 needs BO-010/011/016/018/019/020/022/026; BO-028 needs BO-024/025/026/027; BO-029 needs BO-028.
- **Non-goals:** delivery implementation, provider selection, provisioning, migrations executed, and any Build action.

## Completion criteria

No task is completed by this document. BO-026…BO-029 may be marked DONE only when their own acceptance tests and approval obligations have recorded evidence. Release gates remain unsatisfied until then.

## Rollback / roll-forward

Supersede this design with a dated successor for design changes. Prefer forward-compatible migrations and additive repair; never discard charged operations or release unknown holds to satisfy a limit. Restored backups replay deletion tombstones before serving data.
