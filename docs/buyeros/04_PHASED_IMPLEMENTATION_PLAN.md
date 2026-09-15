# Phased implementation plan and dependency-ordered OpenCode work pack

Plan revision **v1**. Application implementation **NOT STARTED**. This document plans against the owner-confirmed canonical repository `YNWAforever/BuyerOS` (planning pack committed at `1512d4c17d4f792e14598d524fdac3c9c37d27e7`; a source import of the audited content baseline `YNWAforever/buyerosgpt` commit `b804ba8d1514a1049b7202c861278dd72c473a75` is still expected), with matching Sites source tree at `76892126c86031bfe8e7ab517adba7f306040313`. It does not claim the current Site has a backend. The package is delivered under `docs/buyeros/` in the confirmed Sites checkout, with a standalone planning archive. Implementation paths are relative to that confirmed application checkout; no application file is changed by this package.

The recommended first release is **MVP-A: live research, optional gated contact lookup and grounded reviewed drafts**. Real delivery is a separate decision. Preserve Offer → approved buyer profile → Discovery → Evidence → human acceptance → optional business-contact lookup → grounded draft → human approval → manual outcomes.

## How to select work

[tasks/index.json](tasks/index.json) is our handoff convention, **not** a native OpenCode execution engine. Its dependency graph is authoritative for this plan revision; the task documents supply code scope, algorithms, failure cases, tests and prompts. A dependency edge means prerequisite completion evidence is required. It does not grant task approval.

Only [BO-000](tasks/BO-000-reconcile-the-exact-source-missing-inputs-and-opencode-baseline.md) is **READY_FOR_REVIEW**. This means OpenCode **Plan** may inspect and propose its work. Every other task is **BLOCKED**, and none is APPROVED_READY, IN_PROGRESS or DONE. An owner must explicitly approve the selected task before Build. Paid calls, deployment, new infrastructure and delivery need the additional explicit approvals listed in the task.

First BO-000 resolves missing pack references/current instructions/source drift and the absent local OpenCode executable. Missing original research/projection/source register must be recovered or expressly dispositioned; their contents/hashes cannot be reconstructed. This input gap does not invalidate inspected source. Source-dependent tasks are not marked source-unavailable because the exact code was obtained; they remain blocked by prerequisites, unresolved configuration/policy/provider decisions and lack of implementation approval.

## Phase exits and useful demonstrations

| Phase | Tasks | Hours | Observable demonstration and exit evidence |
|---|---|---:|---|
| P0 — decisions and readiness | BO-000–002 | 22–40 | Exact source/input/OpenCode record; one architecture/OIDC/hosting choice; verified provider interface/price/capability matrix and license disposition. Optional GPL integration may be expressly deferred so independent public-web discovery can proceed. No providers activated. |
| P1 — contracts and isolated persistence boundary | BO-003–006 | 76–126 | Typed contract/client boundary, verified bearer/tenant checks, local PostgreSQL constraints and explicit demo/live adapters. Break the live API: the UI shows a real error and no fictional fallback. No cloud deployment. |
| P2 — first persisted vertical slice and paid-operation foundation | BO-007–012 | 140–230 | Create/select/save project and immutable approved profile; review/list/note a controlled integration-test buyer through the existing UI; verify persistence and audit. Policy/suppression, atomic budgets, outbox and safe file/fetch pipeline are ready before enabling billable discovery. Test fixtures here demonstrate persistence, **not real research**. |
| P3 — bounded live-discovery implementation | BO-013–016 | 92–154 | Against deterministic provider fixtures, start approved run, normalize candidate identities, surface supported/contrary/unknown evidence and fit, reconnect, cancel and retry without duplicate cost. Code is ready for later authorized real-provider validation; no paid test implied by the phase name. |
| P4 — guarded contact implementation | BO-017–020 | 88–146 | Open quote without purchase, confirm once under budget race, persist pending/unknown state, reconcile callback/status once and gate late results. Valid/catch-all/unavailable remain distinct from research/outreach permission. |
| P5 — reviewed preparation and existing UI parity | BO-021–025 | 98–164 | Generate grounded draft, edit/review/approve exact revision, invalidate on context changes, export only permitted data and record an explicitly manual outcome. Overview/Usage reconcile; en/zh-HK, mobile, keyboard and deep links pass. Delivery stays disabled in UI/API. |
| P6 — hardening and separate bounded activation | BO-026–029 | 84–144 | Security/lifecycle and crash/restore evidence; human evaluation/release candidate prepared in BO-028. BO-029 runs only after separate environment, spend and data-scope approval; produces measured go/no-go rather than assumed success. |
| P7 — separately approved delivery **design only** | BO-030 | 12–20 | A new proposed delivery task pack with one sender, verified terms/interfaces, jurisdiction/policy gates, suppression/reply/bounce loops and independent activation approval. No sending implementation or activation included in this estimate. |

**MVP-A total including its gated pilot: 600–1,004 engineering hours.** Readiness through BO-028 is **580–968 hours**; BO-029 authorized activation/evaluation adds **20–36 hours**. Optional P7 delivery planning adds **12–20 hours**, for an all-listed-task total of **612–1,024 hours**. These are bottom-up proposed effort ranges, not the research report's 8–12-week promise. They include relevant implementation tests and the current monolithic frontend integration work; they exclude owner approval waits, provisioning/procurement, legal advice, provider spend, unexpected source drift and actual P7 delivery implementation.

At 40 productive engineering hours/week this is about **15–25 engineering weeks** for MVP-A. A team with one backend/platform engineer, one frontend/AI-capable engineer and part-time QA/reviewer support could provisionally target **10–16 calendar weeks**, subject to shared-file/schema serialization and external approval waits. This staffing/calendar estimate is an assumption, not a delivery commitment or an invitation to make all tasks concurrent.

## Dependency and ownership table

| Task | Observable scope | Owner | Dependencies | Hours | Current status |
|---|---|---|---|---:|---|
| [BO-000](tasks/BO-000-reconcile-the-exact-source-missing-inputs-and-opencode-baseline.md) | Reconcile the exact source, missing inputs, and OpenCode baseline | platform | — | 4–8 | READY_FOR_REVIEW |
| [BO-001](tasks/BO-001-approve-the-runtime-identity-deployment-and-migration-decision-record.md) | Approve the runtime, identity, deployment and migration decision record | platform | BO-000 | 6–12 | BLOCKED |
| [BO-002](tasks/BO-002-pin-reusable-upstream-components-and-verify-bounded-provider-capabilities.md) | Pin reusable upstream components and verify bounded provider capabilities | ai | BO-000 | 12–20 | BLOCKED |
| [BO-003](tasks/BO-003-freeze-domain-api-shapes-and-generate-a-typed-browser-boundary.md) | Freeze domain API shapes and generate a typed browser boundary | backend | BO-001, BO-002 | 14–24 | BLOCKED |
| [BO-004](tasks/BO-004-verify-api-bearer-identity-and-enforce-tenant-membership.md) | Verify API bearer identity and enforce tenant membership | backend | BO-003 | 18–30 | BLOCKED |
| [BO-005](tasks/BO-005-create-tenant-safe-domain-persistence-and-one-migration-owner.md) | Create tenant-safe domain persistence and one migration owner | backend | BO-003, BO-004 | 24–40 | BLOCKED |
| [BO-006](tasks/BO-006-separate-demo-state-from-authenticated-live-adapters.md) | Separate demo state from authenticated live adapters | frontend | BO-004, BO-005 | 20–32 | BLOCKED |
| [BO-007](tasks/BO-007-persist-projects-editable-offers-and-immutable-approved-buyer-profiles.md) | Persist projects, editable offers and immutable approved buyer profiles | backend | BO-005, BO-006 | 24–40 | BLOCKED |
| [BO-008](tasks/BO-008-persist-buyer-evidence-views-reviews-stable-selections-and-lists.md) | Persist buyer evidence views, reviews, stable selections and lists | backend | BO-007 | 28–44 | BLOCKED |
| [BO-009](tasks/BO-009-enforce-purpose-specific-policy-and-scoped-suppression.md) | Enforce purpose-specific policy and scoped suppression | backend | BO-008 | 18–30 | BLOCKED |
| [BO-010](tasks/BO-010-reserve-and-settle-bounded-spend-atomically.md) | Reserve and settle bounded spend atomically | backend | BO-005, BO-009 | 24–40 | BLOCKED |
| [BO-011](tasks/BO-011-enqueue-durable-work-through-one-transactional-outbox-and-queue.md) | Enqueue durable work through one transactional outbox and queue | platform | BO-005, BO-010 | 22–36 | BLOCKED |
| [BO-012](tasks/BO-012-safely-ingest-offer-files-and-fetch-permitted-web-evidence.md) | Safely ingest offer files and fetch permitted web evidence | platform | BO-007, BO-009, BO-011 | 24–40 | BLOCKED |
| [BO-013](tasks/BO-013-run-bounded-multilingual-discovery-with-verified-search-and-model-adapters.md) | Run bounded multilingual discovery with verified search and model adapters | ai | BO-002, BO-010, BO-011, BO-012 | 24–40 | BLOCKED |
| [BO-014](tasks/BO-014-canonicalize-company-candidates-and-persist-linked-evidence.md) | Canonicalize company candidates and persist linked evidence | ai | BO-008, BO-012, BO-013 | 20–34 | BLOCKED |
| [BO-015](tasks/BO-015-assess-fit-through-a-checkpointed-evidence-first-langgraph.md) | Assess fit through a checkpointed evidence-first LangGraph | ai | BO-014 | 26–44 | BLOCKED |
| [BO-016](tasks/BO-016-expose-durable-run-progress-cancellation-and-retry-in-the-existing-ui.md) | Expose durable run progress, cancellation and retry in the existing UI | frontend | BO-006, BO-007, BO-011, BO-015 | 22–36 | BLOCKED |
| [BO-017](tasks/BO-017-quote-eligible-business-contact-lookup-without-dispatching-it.md) | Quote eligible business-contact lookup without dispatching it | backend | BO-002, BO-008, BO-009, BO-010, BO-016 | 18–30 | BLOCKED |
| [BO-018](tasks/BO-018-confirm-a-contact-quote-once-with-atomic-reservation-and-durable-job-creation.md) | Confirm a contact quote once with atomic reservation and durable job creation | backend | BO-011, BO-017 | 22–36 | BLOCKED |
| [BO-019](tasks/BO-019-submit-contact-operations-with-uncertainty-safe-provider-semantics.md) | Submit contact operations with uncertainty-safe provider semantics | backend | BO-018 | 24–40 | BLOCKED |
| [BO-020](tasks/BO-020-reconcile-provider-results-callback-replay-and-in-flight-cancellation.md) | Reconcile provider results, callback replay and in-flight cancellation | backend | BO-019 | 24–40 | BLOCKED |
| [BO-021](tasks/BO-021-generate-grounded-draft-revisions-from-approved-facts-and-evidence.md) | Generate grounded draft revisions from approved facts and evidence | ai | BO-009, BO-011, BO-015, BO-020 | 22–36 | BLOCKED |
| [BO-022](tasks/BO-022-bind-human-approval-to-exact-draft-recipient-evidence-and-policy-revisions.md) | Bind human approval to exact draft, recipient, evidence and policy revisions | backend | BO-021 | 22–36 | BLOCKED |
| [BO-023](tasks/BO-023-authorize-and-audit-csv-draft-copy-and-download-without-bypassing-policy.md) | Authorize and audit CSV, draft copy and download without bypassing policy | backend | BO-008, BO-009, BO-022 | 16–28 | BLOCKED |
| [BO-024](tasks/BO-024-persist-manual-outcomes-and-reconcile-every-displayed-usage-metric.md) | Persist manual outcomes and reconcile every displayed usage metric | backend | BO-016, BO-020, BO-022, BO-023 | 18–30 | BLOCKED |
| [BO-025](tasks/BO-025-preserve-bilingual-responsive-interactions-and-deep-link-behavior.md) | Preserve bilingual responsive interactions and deep-link behavior | frontend | BO-006, BO-007, BO-008, BO-016, BO-020, BO-022, BO-023, BO-024 | 20–34 | BLOCKED |
| [BO-026](tasks/BO-026-harden-tenant-data-retention-secrets-and-dependency-boundaries.md) | Harden tenant data, retention, secrets and dependency boundaries | platform | BO-012, BO-020, BO-022, BO-023, BO-024, BO-025 | 24–40 | BLOCKED |
| [BO-027](tasks/BO-027-prove-crash-recovery-budget-races-and-reversible-release-operations.md) | Prove crash recovery, budget races and reversible release operations | qa | BO-010, BO-011, BO-016, BO-018, BO-019, BO-020, BO-022, BO-026 | 24–40 | BLOCKED |
| [BO-028](tasks/BO-028-prepare-a-reviewable-pilot-release-and-human-evaluation-protocol.md) | Prepare a reviewable pilot release and human evaluation protocol | qa | BO-024, BO-025, BO-026, BO-027 | 16–28 | BLOCKED |
| [BO-029](tasks/BO-029-execute-only-the-separately-approved-bounded-live-mvp-a-pilot.md) | Execute only the separately approved bounded live MVP-A pilot | platform | BO-028 | 20–36 | BLOCKED |
| [BO-030](tasks/BO-030-design-a-separately-approved-controlled-delivery-phase-without-activating-it.md) | Design a separately approved controlled delivery phase without activating it | platform | BO-028 | 12–20 | BLOCKED |

The main dependency chain is source/decisions → contract/identity/schema → persisted profile/review/policy → budget/outbox/safe intake → discovery/evidence/fit/run progress → quote/confirm/dispatch/reconcile → draft/approval/export/usage → UI/security/recovery → release review. BO-030 depends on release-readiness material for context, **and** an independent delivery-design approval; it is never automatically selected when BO-028 or BO-029 ends.

## Ownership and safe parallelism

- **Backend owner:** Python domain API, SQLAlchemy models, Alembic migration order, state/authorization rules and typed contract coordination. A single owner serializes migrations; Drizzle's empty SQLite starter does not become a second domain migration system.
- **Platform owner:** identity/runtime decisions, private storage/safe fetch, queue/outbox runtime, secret/data lifecycle and recovery. API and worker use least-privilege DB roles; migrations use a separate owner role.
- **AI owner:** approved reusable MIT component adaptation, query/search/fit/draft prompts, structured output validation and deterministic provider fixtures. AI fit never accepts a buyer or triggers contact/send.
- **Frontend owner:** existing `features/workspace.tsx`, `features/discovery/wizard.tsx`, `features/buyers/detail.tsx`, adapters and locale integration. Workspace contains many inline views and handlers; do not let parallel branches independently refactor it.
- **QA/reviewer:** domain/concurrency/provider-contract/browser tests, human-labelled evaluation and independent evidence review. Fixture tests do not constitute live provider validation.

P0 identity/hosting and upstream/provider research can be reviewed in parallel after BO-000. After contract freeze, backend modules and frontend fixture-driven adapter work may be prepared in parallel only when task dependencies and file ownership permit; do not mark unfinished prerequisites DONE to obtain parallelism. Security test design and visual baselines can be drafted ahead without modifying unapproved product scope. Serialize contract changes, shared migrations, budget/provider-operation transactions, Workspace wiring and final integration.

Proposed application path ownership is `services/api/buyeros_api/` for FastAPI domain code, `services/api/alembic/` for the sole domain migration history, and `services/worker/buyeros_worker/` for Celery/LangGraph/provider workers. All are **PROPOSED**, absent at the audited source commit. Existing `services/contracts.ts`, `services/http-client.ts` and feature files remain the browser boundary. These paths do not introduce a second web application or replace the Sites frontend.

## Integration checkpoints

1. **After BO-006:** preserve demo fixtures and all primary routes while a live API failure produces only an error. Authentication/provenance determine data access; a Demo banner is never the integration switch.
2. **After BO-008:** immutable profile approval and durable review/list actions traverse the actual existing UI. Controlled test data is clearly a test fixture; no live discovery claim yet.
3. **After BO-012:** no paid search/model/contact step is reachable without server budget reservation, tenant/purpose gates and durable job intent.
4. **After BO-016:** true run events come from committed worker work, resume with monotonic IDs and retain partial results. Discovery ends at human review.
5. **After BO-020:** unknown provider submissions keep reservations; quote confirmation, dispatch and reconciliation remain distinct. Contact validity never grants outreach permission.
6. **After BO-024/025:** exact revision approval, authorized export/copy, manual outcomes and ledger metrics form a complete preparation workflow in both locales and supported widths.
7. **After BO-027/028:** observable security/failure/restore gates and concrete pilot scope are reviewable; only then request the explicit BO-029 external activation/spend approval.
8. **After BO-029:** actual pilot results support go/no-go. The next action is evidence-led repair/tuning or separately approved P7 planning, never automatic delivery.

## Blocker dispositions that allow the independent pilot path

Use [00's blocker register](00_README_AND_DECISIONS.md) as the owner record. B-INPUTS and B-OPENCODE are investigated by BO-000; missing source references need recovery or explicit documented disposition. B-HOST/B-IDENTITY need a selected supported runtime/issuer/tenant/region plan. B-PROVIDERS must be resolved per selected provider before the relevant capability activates; contact can remain disabled if its capabilities cannot guarantee bounded safe operation. B-POLICY applies by purpose, not as a single global compliance checkbox.

B-LICENSE may be resolved for this MVP by approving specifically verified MIT adaptation and **deferring** GPL OpenOutreach/OpenOutFind integration. Deferral is a real decision, not an exemption inferred from process separation. It must not block the independent public-web discovery path once its own provider and license requirements are satisfied. No task requires copying an upstream UI.

B-APPROVAL is present on every task after BO-000 because planning has granted no implementation approval. BO-000 itself still requires explicit approval before any Build-phase documentation updates. B-PILOT keeps live spend/deploy/data activation separate. B-DELIVERY requires separate delivery design approval and later an independently approved implementation/activation pack. B-MOBILE is satisfied with actual authorized browser evidence or remains NOT RUN and a release blocker where required.

## Requirement registry

These stable IDs link the master instruction, source/UI action matrix, task YAML and security/test matrix. They are planning labels, not assertions that the underlying capability exists.

| ID | Requirement |
|---|---|
| REQ-IDENTITY | Verify the exact GitHub/Sites project, pinned tree and current working state. |
| REQ-INPUTS | Read/reconcile the original master/reference provenance; disclose unavailable inputs. |
| REQ-OPENCODE | Verify actual OpenCode version and use Plan before explicitly approved Build. |
| REQ-STACK | Preserve the verified Vinext/React/TypeScript/pnpm frontend; one API/queue/migration owner. |
| REQ-REUSE | Pin exact upstream component/interfaces/licenses and record approved reuse boundaries. |
| REQ-CONTRACT | Typed, versioned OpenAPI requests/responses with tenant/error/idempotency semantics. |
| REQ-TENANT | Verified identity and server-side membership/RBAC on every request, event, job and file. |
| REQ-DATA | Tenant-local canonical company/person/project-buyer model with constraints and history. |
| REQ-DEMO | Isolate synthetic fixtures/storage/providers; live failure never falls back to demo. |
| REQ-PROFILE | Persist offer/markets and immutable explicitly approved buyer-profile versions. |
| REQ-BUYERS | Preserve buyer table/drawer, separate human review, bounded selection and durable lists. |
| REQ-POLICY | Purpose-specific research/outreach/export decisions and scoped suppression with provenance. |
| REQ-BUDGET | Atomic bounded reservations, fixed money/currency and immutable reconciled cost events. |
| REQ-QUEUE | One durable queue plus transactionally committed outbox; checkpoint distinct from business truth. |
| REQ-FETCH | Safe SSRF-resistant fetch, private uploads, isolated parsing and bounded storage. |
| REQ-DISCOVERY | Real bounded multilingual company discovery from approved profiles; no automatic enrichment. |
| REQ-EVIDENCE | Source-linked, versioned facts, contradictions, unknowns, translation and retention. |
| REQ-FIT | Structured evidence-grounded profile-specific fit separate from acceptance or purchase probability. |
| REQ-EVENTS | Committed monotonic progress, reconnect/poll, idempotent apply and durable cancel/retry. |
| REQ-QUOTE | Immutable purpose/selection/price/expiry-bound quote with eligibility and no implicit purchase. |
| REQ-CONFIRM | Idempotent quote confirmation with atomic eligibility/budget/job/outbox transaction. |
| REQ-PROVIDER | Verified provider interface/cost bound and safe submission/capability semantics. |
| REQ-RECONCILE | Unknown outcomes, callbacks/status, cost settlement and late policy gates. |
| REQ-DRAFT | Grounded persisted revisions; no invented facts, automatic approval or delivery. |
| REQ-APPROVAL | Exact content/recipient/evidence/policy revision binding with material-change invalidation. |
| REQ-EXPORT | Scoped audited CSV/draft copy/download, formula safety and no policy bypass. |
| REQ-OUTCOME | Manual outcomes with actor/time/provenance; no fabricated inbox conversions. |
| REQ-USAGE | Distinct-company denominators and consistent scope/currency/ledger-derived figures. |
| REQ-UI | Preserve existing routes/layouts/controls, en/zh-HK and desktop/mobile accessibility. |
| REQ-SECURITY | Tenant/secrets/dependency/data lifecycle controls with observable negative tests. |
| REQ-RECOVERY | Crash/race/replay/cancellation/restore verification without duplicate financial effects. |
| REQ-PILOT | Explicitly approved bounded live research/contact/draft release and human evaluation. |
| REQ-DELIVERY | Separate later delivery design/activation gate; never enabled by MVP-A completion. |

Each task's acceptance cases are stable `TEST-BO-###-01`, `-02`, `-03` IDs. [05](05_TEST_SECURITY_AND_RELEASE.md) expands the release/security coverage. Task commands distinguish CURRENT_VERIFIED definitions from PROPOSED_AFTER_TASK and all unexecuted implementation checks are NOT RUN. Manifest/YAML/OpenAPI documentation validation is separate from application test execution.

## OpenCode review and completion rules

Read [06](06_OPENCODE_EXECUTION_GUIDE.md) and [the starter prompt](handoff/OPENCODE_START_PROMPT.md). The first task to review is **BO-000**. Confirm current source against the pinned baseline, read applicable instructions, and check progress before choosing one task. In Plan, return exact file scope, blockers, proposed steps, tests and updated estimate. Use Build only after explicit approval of that selected task and only within that scope.

Completion evidence must include exact changed files, current commit/diff, test commands/output, migrations/environment targets, contract revisions, source/provider/license deviations, remaining NOT RUN items and rollback status. No task is complete because an endpoint stub, screenshot, generated code file or passing UI fixture exists. Stop and replan when requirements/capabilities differ; never fabricate providers or weaken safety invariants to obtain a green test.

**Planner boundary:** only this documentation/contract/task package was written. Application code/lockfiles, active AGENTS/OpenCode configuration, databases, infrastructure, Sites access/deployment, paid operations, mailboxes, messages and git pushes were not changed by these tasks.

