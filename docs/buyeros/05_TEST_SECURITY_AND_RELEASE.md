# BuyerOS test, security, operations, and release plan

Plan revision v1. Planning date: 2026-09-14 UTC. All new implementation tests, services, deployment controls, and runtime commands below are **PROPOSED / NOT RUN** unless explicitly identified otherwise. Nothing in this document approves a paid operation, deployment, contact purchase, mailbox connection, or delivery.

Read [00 decisions](00_README_AND_DECISIONS.md), [03 contracts](03_DATA_API_AND_STATE_CONTRACTS.md), and the selected [task manifest](tasks/index.json) together. Requirement IDs are this pack's traceability convention. Test IDs identify acceptance obligations; they do not assert test files already exist.

## 1. Current evidence and test boundaries

The inspected frontend is the exact BuyerOS source tree: local Sites commit `76892126c86031bfe8e7ab517adba7f306040313`, audited content baseline GitHub `YNWAforever/buyerosgpt` commit `b804ba8d1514a1049b7202c861278dd72c473a75` (canonical repository now `YNWAforever/BuyerOS`), common tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`. See document 01 for current browser evidence and source limitations; a matching tree does not establish matching deployment configuration.

| Evidence | Current finding | Consequence |
|---|---|---|
| `package.json` | `pnpm@11.25.0`, `lint`, `build`, and `dev` scripts; no `test` script | Do not claim `pnpm test` exists. Preserve supported execution profile. |
| `tests/domain-checks.mjs` | Source contains 11 synchronous/asynchronous local demo checks; it imports TypeScript and transpiles fixture/service modules | Existing check is suitable for a reviewed, isolated baseline once dependencies exist. **NOT RUN this session**; historical handoff results are not current results. |
| `DEVELOPER_HANDOFF.md` | Historical test/build/browser report and known limitations | Historical evidence only; do not copy its PASS labels into a new release report. |
| `services/mock-client.ts` | `quote`, `confirm`, `block`, `usage`, `csv` implement local synthetic logic | Preserve useful demo regression behavior; their floating-point and browser-only gates are not live financial controls. |
| `services/http-client.ts` | Unconfigured live boundary | Live network error must remain explicit; replacing this stub requires server contracts and tests. |
| Current source dependency directory | `node_modules` absent in inspected source snapshot | No install, package scripts, application tests, build, migrations, or provider checks were run in planning. |
| Current browser | Read-only inspection and confirmed synthetic interactions reported in document 01 | No live-backend verification. Mobile/current automated accessibility test coverage remains **NOT RUN** unless document 01 says otherwise. |

Current demo regression inventory must remain distinct from proposed live invariants. Preserve 26 raw candidates → 24 canonical companies; 14 Match / 6 Needs review / 4 Not a match; mixed human review; suppressed/catch-all/missing contacts. The earlier specification asks for three especially detailed fictional dossiers; actual `data/demo/fixtures.ts:seed` generates 24 dossiers with three evidence records each, with some special-case text for the named examples. Preserve those records and review the three named dossiers as regression anchors; do not claim only three dossiers exist or that each has uniquely authored depth. Source confirms fixtures and deterministic checks, but a fresh execution is still required. Demo quote expiry releasing a never-submitted synthetic reservation must not be generalized to uncertain external submissions.

## 2. Threat model and trust boundaries

Protected assets are tenant research and proprietary offers, personal business-contact data, evidence provenance, approvals, provider credentials, budget balances, and audit history. Adversaries include unauthenticated clients, users from another tenant, overprivileged operators, malicious uploaded/web content, compromised provider responses, duplicate/replayed callbacks, and accidental worker retries. A legitimate user can also exceed intended authority through exports, stale tabs, or concurrent confirmation.

The browser is untrusted. FastAPI verifies identity and membership on every request; a client `workspace_id`, visible role, or disabled button is not authorization. Auth0 OIDC with Authorization Code + PKCE and short-lived API access tokens is the provisional managed identity choice; issuer, audience, tenant, token lifecycle, and CORS origins remain explicit blockers. Use memory-held browser tokens, no access tokens in localStorage or URLs. Browser SSE must use a fetch-based streaming client with authorization headers or polling, not query-string bearer tokens. The API and worker use separate non-owner database roles. The queue carries tenant-scoped identifiers, never uncontrolled arbitrary execution instructions. Provider response data is untrusted until normalized and schema validated. Pages/uploads cannot add tools, modify policy, buy contacts, or authorize a draft.

| Boundary | Required defense | Negative proof |
|---|---|---|
| Browser → API | Verified signature/issuer/audience/expiry; server membership and RBAC; exact allowlisted origins; request limits | Wrong tenant, unsigned/wrong-audience/expired token, revoked member, unauthorized origin rejected without revealing record existence. |
| API/worker → Postgres | Application tenant predicates plus RLS where adopted; composite tenant-safe foreign keys; transaction-local tenant context; non-owner roles | Pooled connection switches A→B; missing tenant context fails closed; neither role has `BYPASSRLS`; cross-tenant joins and inserts denied. |
| Worker → queue/checkpoints | Durable outbox, task identity, leases, bounded retry, checkpoint key including workspace/run | Replay/restart cannot create duplicate business writes or paid operations; stale lease owner cannot commit after a replacement. |
| Worker → Internet | Scheme and hostname checks, DNS/IP validation at connection time and every redirect, egress deny rules, byte/time/page caps | Private/loopback/link-local IPv4/IPv6, metadata targets, rebinding, redirected private IPs, encoded addresses, unsupported protocols denied. |
| Upload/source → parser/LLM/UI | MIME/content validation, bounded parser sandbox, safe rendered text, schema/evidence constraints | Zip bombs/path traversal, active HTML, script URLs, hidden prompt instructions, invented evidence IDs rejected or quarantined. |
| Provider → API | Verified callback mechanism if supported, signed replay-resistant events, raw event digest, ordered reconciliation | Duplicate/out-of-order/unmatched callbacks cannot double-settle, leak contacts, or replace a terminal decision. |
| API → export/file | Same tenant/purpose policy as interactive reads, field filtering, audited scope, private objects, short-lived signed access | A blocked contact cannot be obtained through CSV/draft download/copied content or an old file URL. |

## 3. Task-bound acceptance matrix

All tests below are **PROPOSED_AFTER_TASK / NOT RUN**. Unit/provider fixtures are deterministic. Database concurrency tests require a disposable PostgreSQL instance; worker tests use disposable Valkey and a fake provider. CI network egress must deny real paid/search/LLM/contact/mail endpoints. No test may succeed by substituting demo data in live mode.

| Requirements | Task / primary test | Test layer and concrete cases | Required observable result |
|---|---|---|---|
| REQ-IDENTITY, REQ-INPUTS, REQ-OPENCODE | BO-000 / TEST-BO-000-01 | Read-only identity, current dirty diff, instructions, installed OpenCode/version | Correct repository/tree mapped; absent references/version remain blockers; no existing changes lost. |
| REQ-STACK, REQ-REUSE, REQ-PROVIDER | BO-001–002 / TEST-BO-001-01, TEST-BO-002-01 | Commit/license/capability evidence review; no API execution | Written architecture/license/provider decisions; bounded charge and idempotency/status semantics known before paid dispatch. |
| REQ-CONTRACT | BO-003 / TEST-BO-003-01 | OpenAPI validation, generated TypeScript compile, API response contracts | Valid schemas, all required guards/errors represented; generated code contains no secrets or demo defaults. |
| REQ-TENANT | BO-004 / TEST-BO-004-01 | API: invalid tokens, foreign IDs, viewer writes, revoked membership, forged actor | Consistent 401/403 or non-enumerating 404; zero domain writes/provider calls; audit denial excludes personal payloads. |
| REQ-DATA, REQ-TENANT | BO-005 / TEST-BO-005-01 | DB: composite FK violation; RLS under non-owner roles; A→B pooled reuse; missing context; migration on fresh/previous schema | Tenant isolation holds under API and workers; no leaked context; migrations owned only by Alembic. |
| REQ-DEMO | BO-006 / TEST-BO-006-01 | Frontend/API: live 500/offline/session expiry; switch tenants/modes; saved demo restore | Real errors shown; live records never replaced by HarbourSense; fixtures never enter live entities/costs; tenant caches discarded. |
| REQ-PROFILE | BO-007 / TEST-BO-007-01 | API+UI: create offer/project, approve profile, concurrent edit, old run | Immutable approved profile; stale write conflicts; old assessment remains tied to old version. |
| REQ-BUYERS | BO-008 / TEST-BO-008-01 | API+UI: current-page vs all-filtered snapshot, changed eligibility, duplicate list add, membership removal | Exact selected set and per-item conflicts; stable pagination; no company/evidence deletion on list removal. |
| REQ-POLICY | BO-009 / TEST-BO-009-01 | Independent acceptance/fit/contact/policy/suppression; policy unknown; purpose mismatch; expired decision; cross-client suppression | Unknown blocks relevant operation; lookup permission never implies outreach permission; no unreviewed shared contact/suppression data. |
| REQ-BUDGET | BO-010 / TEST-BO-010-01 | DB concurrency: many simultaneous reservations near cap; reversed lock acquisition; duplicate settle; mixed currencies; UTC period rollover with active/unknown holds; prior-period refunds; admin reduction below settled+held concurrent with confirmation | Fixed precision and deterministic lock order; invariant holds at every commit; rollover never resets/releases holds or double-counts carried economics; period attribution remains stable; limit reduction follows the approved rejection/freeze rule; retryable conflict cannot overspend. |
| REQ-QUEUE | BO-011 / TEST-BO-011-01 | Kill between DB commit/enqueue; duplicate delivery; expired lease; checkpoint retry; queue unavailable | Durable outbox eventually enqueues once semantically; committed progress only; missing queue does not lose accepted jobs. |
| REQ-FETCH, REQ-SECURITY | BO-012 / TEST-BO-012-01 | SSRF set above, compressed-body overflow, upload parsing/malware indicators, parser escape, prompt injection | Block before connection/unsafe parsing; limits enforced outside prompts; no policy changes or secret disclosure. |
| REQ-DISCOVERY | BO-013 / TEST-BO-013-01 | DE/NL/BE query fixtures; unsupported country; limited/no results; token/round/spend cap | Bounded work and honest partial/empty results; no sample substitution or accidental enrichment edge. |
| REQ-EVIDENCE, REQ-FIT | BO-014–015 / TEST-BO-014-01, TEST-BO-015-01 | Distinct legal entities sharing domain; evidence-ID tamper; contradictions; missing source; stale/deleted excerpt | Reviewable ambiguous dedup; claims cite accessible permitted evidence or explicitly unknown/inferred; no unsupported hard-positive fit. |
| REQ-EVENTS | BO-016 / TEST-BO-016-01 | Disconnect/reconnect, last event cursor, duplicate/out-of-order/gap, polling fallback, foreign run stream | Monotonic per-run ordering; no duplicate counts; scoped stream; durable terminal event and recoverable gap. |
| REQ-QUOTE | BO-017 / TEST-BO-017-01 | Alter buyers/roles/purpose/price/currency/actor; expiry at boundary; unsupported provider | Quote binds normalized request and upper bound; no dispatch; stale/invalid quote rejected with current eligibility reasons. |
| REQ-CONFIRM | BO-018 / TEST-BO-018-01 | Same idempotency key/same body; same key/different body; different keys/same quote; eligibility change during confirm | Exactly one durable operation/reservation; repeat returns prior result; changed payload conflicts; budget lock and operation created atomically. |
| REQ-PROVIDER | BO-019 / TEST-BO-019-01 | Crash before call/after vendor acceptance/before local ACK; timeout; cancellation before/after dispatch | Known unsent may release; uncertain submission retains hold and enters reconciliation; no blind retry without verified provider guarantees. |
| REQ-RECONCILE | BO-020 / TEST-BO-020-01 | Duplicate/out-of-order webhook; polling race; late charge/no result; revoked policy/suppression before result; provider invoice mismatch | Unique settlement; reserved uncertainty retained until authoritative resolution; prohibited late contact quarantined/deleted by policy; variance visible. |
| REQ-DRAFT | BO-021 / TEST-BO-021-01 | Unsupported claim, missing evidence, wrong recipient language, budget cap/model failure | Draft cites allowed facts; language labelled; no fabricated personal intent; failure leaves editable recoverable draft, no false approval. |
| REQ-APPROVAL | BO-022 / TEST-BO-022-01 | Two editors/approvers; subject/body/follow-up/recipient/evidence/profile/policy/retention change; forged, foreign-project, missing, revoked or stale sender identity version | Optimistic conflict or new revision; server resolves an authorized versioned sender identity and never trusts a client string; approval binds exact revision/context and becomes stale on material change. |
| REQ-EXPORT | BO-023 / TEST-BO-023-01 | Foreign selection/file; blocked contact; formula prefixes incl whitespace/control chars; stale signed link | Authorized exact snapshot only; contact-policy redaction/denial; safe CSV; copy/export never becomes sent. |
| REQ-OUTCOME, REQ-USAGE | BO-024 / TEST-BO-024-01 | Three contacts at one buyer; zero denominator; partial runs; date/scope changes; manual outcome edits | Distinct-company denominators; spent/reserved separated; manual provenance mandatory; no inbox-synced claim. |
| REQ-UI | BO-025 / TEST-BO-025-01 | Playwright: 390/768/1280/1440 widths, English/zh-HK, deep links, refresh, keyboard, zoom, reduced motion | Preserved table/drawer/editor; no page overflow; focus trap/return; localized errors; stable route/tenant recovery. |
| REQ-SECURITY | BO-026 / TEST-BO-026-01 | End-to-end tenant/export/privacy/SSRF/approval bypass; dependency/secret/license scan | No high-risk unresolved escape; redacted audit evidence; source/dependency obligations recorded with reviewer. |
| REQ-RECOVERY | BO-027 / TEST-BO-027-01 | Disposable backup restore, expand/contract rehearsal, API/worker restart, kill switch, deletion restore | Restored state reconciles ledger/holds/outbox; deleted content is not re-exposed; no migration runs in production during test. |
| REQ-PILOT | BO-028–029 / TEST-BO-028-01, TEST-BO-029-01 | Readiness evidence review; only separately approved bounded live company evaluation | Signed scope/budget/policy approval before real requests; measured results and stop triggers; implementation tasks remain unstarted in this plan. |
| REQ-DELIVERY | BO-030 / TEST-BO-030-01 | Design review for later phase; MVP-A direct attempts to send/schedule/import mailbox | No active sender/credentials/endpoint in MVP-A; explicit later authorization and policy/provider review required. |

## 4. Financial failure protocol

The ledger is the authority; provider credits, cash cost, subscription allocations, and infrastructure costs must be reported separately. Pricing snapshots record source/date/currency/unit/bounded maximum and expiry. USD 0.30/contact and USD 6.60 discovery are demo assumptions, not vendor pricing. BO-002 must verify actual provider billing and capabilities without executing paid calls; no unbounded provider is eligible by default.

Enforce `settled + active reserved upper bounds + proposed reservation <= approved limit` atomically at workspace, project, run, and category scopes where configured. The strictest applicable ceiling governs. Do not release funds because a quote expired after dispatch, a browser closed, a worker crashed, or an HTTP timeout occurred. Keep `unknown` operations on hold until authoritative status, billing evidence, or approved manual reconciliation determines settlement/release. Manual reconciliation requires reason, evidence, actor, and immutable correcting events; never edit away financial history.

When vendor costs may exceed a quoted cap, block dispatch pending a supported upper bound or a separately approved exception policy. An internal reservation prevents local oversubscription; it is not an unconditional guarantee about a vendor invoice. Cancellation stops undispatched work and requests remote cancellation only when capability is verified; dispatched requests may remain chargeable. Pause new operations on unexplained provider balance variance. Read/reconcile already submitted work while paused.

## 5. Privacy, evidence lifecycle, and audit

Policy owner must approve purpose, applicable markets/entities, lawful basis or applicable policy rationale, permitted sources, roles, source retention, contact retention, deletion obligations, and review interval. These are unresolved policy decisions, not a blanket legal-compliance claim. Jurisdiction-specific outreach rules require authoritative legal sources and appropriate legal review before P7. No legal opinion or future sending permission is inferred from company acceptance or a provider-marked-valid address.

Apply configurable lifecycle rules to offer files, raw pages, extracted evidence, contacts, prompts/traces, and derived artifacts. A retention/deletion job must remove or restrict underlying content, propagate a tombstone/version change, stale dependent fit assertions/approvals, revoke regenerated export availability, invalidate caches/signed access where supported, and record a minimal non-content audit event. A deleted source's hash alone does not substantiate its old claim. Keep necessary financial/audit records under a separately reviewed retention basis with minimal personal content. Legal holds, if applicable, require an explicit authorized record and access restriction, not automatic permanent retention.

Document unavoidable limitations: downloaded exports cannot be remotely revoked; backup deletion follows documented expiry and restore-time deletion replay; vendor deletion capability and completion must be verified. Export/download UI and audit must expose the applicable retention/purpose constraint. Avoid private offers and full contact details in logs, exception traces, LangGraph checkpoints, analytics, or model prompts unless necessary and approved. Store provider secrets only in server secret configuration; signed URLs must be short-lived and tenant-authorized, and loggers must redact their query strings.

Required audit fields: tenant, server actor or service identity, action, entity IDs, prior/new version, policy decision IDs, request/correlation ID, timestamp, outcome/reason; no raw access token, email body, or full evidence payload. Record reads/exports of sensitive contact data as appropriate to approved policy.

## 6. Observability and recovery

Correlate API request ID → run/job ID → provider operation ID → reservation/cost event IDs without exposing payloads. Track queue age, worker lease expiry, outbox lag, unknown provider operations, reserved amount age, budget denials, settlement variance, evidence validation failures, tenant denial rates, and approval invalidation. Health/readiness must distinguish API reachable, database usable, queue unavailable, provider disabled, and capability policy-blocked. A decorative Connected label cannot substitute for readiness.

Proposed operational thresholds requiring owner approval: alert when the oldest pending outbox event exceeds 5 minutes, unknown paid operation exceeds the verified provider status SLA, or financial reconciliation discrepancy is nonzero. Immediate stop: tenant leakage, send capability appearing in MVP-A, repeated unexplained charges, or missing authoritative budget lock. Keep read-only UI and reconciliation available when new paid work is disabled.

Alembic is sole domain-schema migration owner. Preserve existing Drizzle starter files as non-domain scaffold until an approved task explicitly removes or disables conflicting ownership. Use backward-compatible expand/backfill/read-switch/contract migrations; serialize migration authorship. Test against fresh and prior supported schemas and realistic volumes in a disposable environment. Destructive column/table removal requires a later approved migration and backup evidence. Never run `db:generate` for new BuyerOS domain ownership merely because the script exists.

Proposed pilot recovery objectives: RPO ≤24 hours and RTO ≤4 hours, pending hosting/backup capability approval; financial unknowns may require longer vendor reconciliation and must remain held. Verify backup availability/encryption/access and restore to an isolated database without sending requests. Replay deletion tombstones before exposing restored data. Reconcile outbox, external operation IDs, ledger, reservations, and checkpoints before restarting dispatch. Roll back application versions only when compatible with current schema; otherwise roll forward with an additive repair. Never roll back by discarding charged operations.

## 7. Release gates

All gates are currently **NOT SATISFIED / NOT RUN**. “Owner” is a required role awaiting a named assignee, not evidence of approval. A successful source audit does not approve implementation or live spend.

| Gate | Accountable owner | Required evidence | Failure action and rollback/roll-forward |
|---|---|---|---|
| G0 source + task review | Lead architect / repository owner | Current commit/diff/instructions, source/reference limitations, BO-000 Plan output, explicit selected-task approval | Remain Plan; revise task/ADR; preserve existing source and dirty work. |
| G1 architecture/provider/legal decisions | Technical owner + data-policy owner + license reviewer | BO-001/002 signed decisions; identity/hosting/provider capabilities; license map; missing-reference disposition | Block dependent integration; defer optional GPL path; do not invent an API/provider workaround. |
| G2 tenant/data/contracts | Backend lead + QA | Token/RLS/pool/concurrency/contract tests, single migration owner, restore rehearsal | Disable live mode; repair forward; do not seed demo into live tenant. |
| G3 research cost and recovery | Platform lead + finance owner | Budget race tests, outbox/retry proof, caps/kill switch, provider uncertainty simulation | Stop new dispatch; preserve holds and reconcile submitted operations; revert compatible worker build. |
| G4 contacts/drafts/export | Data-policy owner + QA | Quote/confirm/reconcile; purpose-specific authorization; stale approval and export bypass tests | Disable affected capability; invalidate unsafe approvals; restrict/quarantine results; reconcile costs. |
| G5 pilot release readiness | Product owner + QA + operations | E2E desktop/mobile/locales; security findings disposition; named operator; retention/deletion; telemetry and restore evidence | Keep staging fixture-only; fix task and repeat affected tests; do not widen scope. |
| G6 bounded live pilot | Willy Lai or explicitly delegated budget owner + policy owner | Written environment/users/market/purpose/provider/max-spend/time-window approval; BO-029 selected task approval | No real calls until approved; on trigger stop new work, retain reservations, review evidence. |
| G7 later delivery | Owner + policy/legal reviewer + sender administrator | Separately approved BO-030 design and subsequent implementation tasks; provider terms, sender identity, suppression, rate/opt-out/reply/bounce controls | Keep all delivery disabled; no automatic P6→P7 transition. |

## 8. Proposed bounded pilot evaluation

After BO-029 explicit approval, begin with one tenant, one approved offer/ICP, DE/NL/BE distributor/system-integrator markets, and 30–50 real candidate companies reviewed independently by two designated humans. Contact lookup is optional and limited to a separately approved subset. The exact provider, numerical spend cap, user list, dates, retention, and role assignments must be filled before execution. No default dollars or presumed permission are supplied by this plan.

| Metric | Exact interpretation | Proposed evaluation target, pending approval |
|---|---|---|
| Accepted-candidate precision | Reviewed accepted candidates independently judged relevant / reviewed accepted candidates; report numerator/denominator and sample selection | ≥80%; measure uncertainty, do not market as guaranteed performance. |
| Evidence support | Important factual claims linked to accessible supporting evidence or explicitly unknown/inferred; also human correctness score | Structural linkage 100%; empirical factual support ≥95% of sampled claims. |
| Reviewer agreement | Same independent relevance verdict / doubly reviewed cases; report disagreement themes | ≥80%; adjudicate ambiguity before changing fit rules. |
| Contact yield | Accepted, policy-eligible companies with ≥1 provider-marked-valid eligible contact / accepted eligible companies actually researched | Measure first; no promised provider yield. Catch-all reported separately. |
| Cost per accepted company | Settled attributable research/contact spend / distinct accepted company IDs in the same approved scope and period | Report actual + active holds separately; zero denominator = unavailable. |
| Cost per contactable accepted company | Settled attributable spend / distinct accepted companies with ≥1 valid, unsuppressed, policy-eligible contact | Report scope and freshness; multiple contacts do not inflate denominator. |
| Human review time | Active review minutes per completed company decision; exclude inactive browser time | Establish baseline; proposed ≤3 minutes median subject to evidence complexity. |

Stop immediately for tenant leakage, unauthorized contact access, unsupported material claims slipping past review, unexpected send behavior, oversubscribed reservation invariant, or unknown provider costs without reconciliation support. Stop new calls at the approved cap/time window. Report unresolved holds alongside settled cost. Manual outcomes retain `source=manual`, actor, time, notes; none imply synchronized reply or measured commercial causality.

## 9. Verification command registry

Commands are to be run later from the verified repository root, after inspecting their side effects and after the relevant task/dependency environment is approved. Existing command definitions are source-verified; execution is **NOT RUN** in this planning session. Do not install dependencies or invoke package hooks as an implied part of reviewing these commands.

| Command | Classification | Prerequisite / expected result |
|---|---|---|
| `git status --short` and `git rev-parse HEAD` | CURRENT_VERIFIED read-only baseline method | Capture current source and unrelated changes; compare to audit, never force-reset. |
| `node tests/domain-checks.mjs` | CURRENT_VERIFIED command target; execution NOT RUN | Reviewed local dependency install; expected 11 demo checks pass; does not prove server controls. |
| `pnpm exec tsc --noEmit` | CURRENT_VERIFIED TypeScript dependency; execution NOT RUN | Approved local dependency environment; zero diagnostics on unchanged source or document actual baseline failures. |
| `pnpm lint` | CURRENT_VERIFIED script; execution NOT RUN | Review ESLint/runtime; exit 0 or record actual pre-existing failures. |
| `pnpm build` | CURRENT_VERIFIED script; execution NOT RUN | Review `scripts/run-framework.mjs`, `scripts/build-verified.sh`, environment profile; isolate secrets; build artifact only, no deployment. |
| `python -m pytest tests` from proposed backend directory | PROPOSED_AFTER_TASK; NOT RUN | BO task creates test files/environment; deterministic fixtures, disposable DB/queue, denied external egress; exact narrowed commands in selected task take precedence. |
| `pnpm exec playwright test` | PROPOSED_AFTER_TASK; NOT RUN | Approved BO-025 harness/dependency; isolated frontend/API fake-provider stack; no live tenant credentials. |
| `opencode --version` | NOT RUN; executable unavailable in planning PATH | Owner's implementation environment must first resolve installed binary and version; configuration remains withheld. |

Selected task documents specify narrower tests and expected outcomes. These commands are not a blanket execution authorization. Broaden testing only to resolve a concrete remaining risk or required release gate. Record actual stdout summary/exit status, fixture versions, source commit, and redacted artifacts; mark every skipped check **NOT RUN** with reason.
