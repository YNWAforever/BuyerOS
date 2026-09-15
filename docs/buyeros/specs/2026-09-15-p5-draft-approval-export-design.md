# P5 design — grounded drafts, exact-context approval, authorized export, manual outcomes, UI parity

**Status: PROPOSED / PLAN ONLY.** Plan revision v1. Recorded 2026-09-15 (Hong Kong). Design covers tasks **BO-021, BO-022, BO-023, BO-024, BO-025** (phase P5). Approved in the Plan review session (approval acknowledged with "ok"); this is a design input, not Build approval.

No application code, lockfile, dependency install, database migration, cloud resource, deployment, Site access change, paid provider call, mailbox connection, message, commit or push is authorized or performed by this document. No delivery capability is enabled.

Related records: [P1](2026-09-15-p1-boundary-design.md), [P2](2026-09-15-p2-persistence-foundation-design.md), [P3](2026-09-15-p3-discovery-fit-design.md), [P4](2026-09-15-p4-contact-guardrails-design.md), [02 architecture](../02_ARCHITECTURE_AND_REUSE.md), [03 data/API contracts](../03_DATA_API_AND_STATE_CONTRACTS.md), [contracts/openapi.proposed.yaml](../contracts/openapi.proposed.yaml).

Base content commit: `b804ba8d1514a1049b7202c861278dd72c473a75`, tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`. Canonical repository: `YNWAforever/BuyerOS` (planning pack committed at `1512d4c17d4f792e14598d524fdac3c9c37d27e7`; a source import is still expected to produce tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`).

## Scope

Deliver reviewed draft preparation: grounded draft revisions, an approval that binds an exact revision/recipient/evidence/policy context, authorized export/copy/download, manual outcomes with ledger-consistent usage, and bilingual/responsive/deep-link parity. Real delivery remains out of scope (BO-030).

In scope: BO-021, BO-022, BO-023, BO-024, BO-025. Out of scope: sending/mailboxes (never in MVP-A), P7 delivery, provider selection, provisioning.

## R. Grounded draft revisions (BO-021)

- Generation reads **approved offer facts + accessible buyer evidence** and produces an immutable `draft_revision` carrying objective, tone, language, value proposition and optional follow-up.
- Every factual claim references an **approved offer-fact ID or evidence ID**. Uncited/unsupported claims are removed or flagged as needs review. No invented certifications, relationships, purchasing intent, or promised savings.
- One approved model route per task; versioned prompt; model generation is budget-reserved with token accounting. Template-based drafts may be free; model generation is paid. The worker has **no mailbox tools**.
- A draft may exist without send permission. Delivery stays `not_connected`; no `sent` state is ever created in this phase.
- Operations: `generateDraft`, `listDrafts`, `getDraft`, `editDraft`.

## S. Exact-context approval (BO-022)

- Approval binds: draft id + **revision number + content hash**; project buyer + reviewed assessment + approved ICP version; recipient contact id + **normalized recipient value hash** + contact version; **sender identity version**; objective/tone/language + offer-fact IDs; ordered **evidence id/version set hash**; policy decision IDs/versions/context hash; current **suppression epoch**; approver identity + timestamp.
- **Fingerprint:** versioned **canonical JSON** (UTF-8, sorted keys, LF-normalized, presentation-only fields excluded). The **serializer version is stored alongside the hash**. Python and TypeScript share a **golden-vector** fixture set so both compute identical digests. (Default recorded because the question was left unanswered in session; raw-text hashing is the alternative if the owner prefers it.)
- **Approval transaction:** lock draft / current-buyer-gate / recipient-policy rows in a stable order, compare `If-Match`, recompute hashes and eligibility, then insert the immutable approval and update draft state/version **in one transaction**. Concurrent edit vs approve → exactly one wins; the loser receives `412 STALE_REVISION`.
- **Material change invalidates approval:** recipient, subject/body/follow-up, approved value proposition, sender identity, ICP or assessed evidence versions, evidence-access expiry, policy/suppression, buyer acceptance, or relevant contact identity/validity. A note or non-material owner label does not change the content revision (authorization is still checked).
- **Sender binding is authoritative:** `projects.active_sender_identity_version` points to an immutable `sender_identity_versions` record; the server records the reviewer/time, generates a `version_key`, retires the previous version, and invalidates affected approvals. A fabricated client string never satisfies the guard.
- Approval **never** implies delivery or mailbox ownership.
- Operations: `requestDraftReview`, `approveDraft`, `rejectDraft`.

## T. Authorized export, copy and download (BO-023)

- CSV uses a consistent column whitelist, correct quoting/doubled quotes, and neutralizes leading whitespace/control characters followed by `=` `+` `-` `@` tab/CR. Exports include evidence references and `data_mode=live`; demo exports remain `DEMO_` and `data_mode=demo`.
- Download rechecks **current** policy and approval and is served through an authenticated API with a short-lived signed URL — never a raw storage URL that bypasses revocation.
- Company-only CSV requires export policy; **contact-inclusive CSV and addressed draft copy/export** additionally require reviewed contact/outreach export permission plus a current suppression check. Every denied row is explicit; copy/export creates only audit/export events and **never** a sent state.
- Operations: `exportBuyers`, `getExport`, `downloadExport`, `exportDraft`.

## U. Manual outcomes and usage reconciliation (BO-024)

- `outcome_events` are append-only with **manual provenance** (actor, occurred_at/recorded_at, notes). Corrections append a superseding event; a placeholder is not a valid stage. No inbox-sync or reply inference from copy/export.
- Usage is server-scoped per workspace/project over a UTC half-open `[from,to)` with `as_of`: numerator = metered charges recorded in the interval (including partial/failed/cancelled work); **reserved shown separately**; credits/subscriptions/infrastructure are separate units and never double-counted; zero denominator returns `null` displayed as "—".
- Denominators: distinct accepted companies; the contactable subset has ≥1 current valid + permitted + unsuppressed business email (contacts never multiply companies).
- Labels: "blended" period cost, awaiting-review counts, and manual outcomes. No purchase/causal claim. Unknown holds are shown; **no zero-cost claim after a timeout**.
- Operations: `recordOutcome`, `correctOutcome`, `getUsage`, `listBudgets`.

## V. Bilingual, responsive and deep-link parity (BO-025)

- **Full zh-HK system-copy coverage:** navigation, labels, buttons, errors, toasts, screen-reader names, and date/currency formatting. **Evidence excerpts stay in their original language.** Locale affects labels, not identity; approved message text is never silently translated (a deliberate translation creates a new revision).
- **Responsive:** 390 / 768 / 1280 / 1440 widths, text zoom, keyboard focus trap/return, and reduced motion, verified with Playwright.
- **Deep links:** explicit not-found/unauthorized states for supported routes; no silent fallback to the sample run; tenant/mode switch clears scoped caches; reload recovers from server; draft/filter/tab state uses an approved convention.

## Cross-cutting

RLS + composite tenant FKs and the single Alembic migration owner apply to all new tables. Mutations carry an `Idempotency-Key` and version preconditions. Live responses use `{data, request_id, data_mode:"live"}`; demo and live never mix.

## Data flow

Accepted eligible buyer → grounded draft revision (evidence/fact-bound) → edit/timekeeping → review request → exact-context approval (hash-bound, transactional) → authorized copy/export (policy-rechecked) → manual outcome recorded; usage projections reconcile against the append-only ledger. Delivery is absent.

## Interfaces

Provider-neutral public API per the proposed OpenAPI. No new endpoint may be invented; any disagreement is a reviewed contract revision. Error codes/envelopes follow 03 §4 (including `EVIDENCE_STALE`, `APPROVAL_STALE`, `DELIVERY_DISABLED`).

## Testing (all PROPOSED_AFTER_TASK / NOT RUN)

| Test | Expectation |
|---|---|
| TEST-BO-021-01 | draft cites allowed facts/evidence; unsupported claims rejected/flagged; language labelled; failure leaves a recoverable draft with no false approval |
| TEST-BO-022-01 | two-editor conflict resolves to one winner; each material change stales approval; forged/foreign/stale sender key rejected; golden-vector hashes match across Python/TS |
| TEST-BO-023-01 | foreign selection/file rejected; blocked contact redacted/denied; formula prefixes neutralized; stale signed link refused; copy/export never becomes sent |
| TEST-BO-024-01 | distinct-company denominators; zero denominator "—"; spent vs reserved separated; manual provenance mandatory |
| TEST-BO-025-01 | 390/768/1280/1440, en/zh-HK, deep links, refresh, keyboard, zoom, reduced motion pass |

Supporting: `node tests/domain-checks.mjs`, `pnpm exec tsc --noEmit` — NOT RUN. No live provider or mailbox call is authorized.

## Assumptions, blockers and non-goals

- **Blocked by:** B-PROVIDERS (approved LLM route), B-POLICY (export/outreach/contact permission), B-LICENSE. Dependencies: BO-021 needs BO-009/011/015/020; BO-022 needs BO-021; BO-023 needs BO-008/009/022; BO-024 needs BO-016/020/022/023; BO-025 needs BO-006/007/008/016/020/022/023/024.
- **Non-goals:** real delivery, mailbox connection, provider selection, migrations executed, provisioning, and any Build action.

## Completion criteria

No task is completed by this document. BO-021…BO-025 may be marked DONE only when their own acceptance tests and approval obligations have recorded evidence.

## Rollback / roll-forward

Supersede this design with a dated successor for design changes. Prefer forward-compatible migrations and additive repair; never discard committed approvals or financial records.
