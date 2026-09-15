# FIMMICK BuyerOS — Codex Astra 6 Planning Master Instruction

Version: 1.0 · Prepared 2026-09-15
Purpose: instruct Codex to audit the existing BuyerOS frontend and produce an implementation-ready plan for OpenCode. This file is an instruction to the planner, not the implementation plan itself.
Mode: **PLAN ONLY / DOCUMENTATION WRITES ONLY**.

## 0. Your assignment and boundaries

Act as the technical architect and implementation planner for FIMMICK BuyerOS. The owner intends to use Codex Astra 6 for planning and OpenCode for subsequent implementation. Use the model actually available in the owner's environment; the label “Astra 6” is not an API model identifier and must not be invented in configuration.

Create a repository-grounded execution plan that turns the existing ChatGPT Sites frontend into a working, cost-controlled, evidence-first overseas B2B buyer-discovery MVP. Preserve the existing product experience. Do not replace it with either upstream project's UI, a generic CRM, a marketing homepage, or a chatbot.

**Do not implement the application in this task.** You may inspect authorized source, inspect the Site, read documentation, and create/update the planning documents specified below. Do not modify application source, lockfiles, active agent configuration, database state, infrastructure, or production settings. Do not create a replacement repository or database. Do not deploy, publish, push, send messages, buy contacts, or make billable provider calls. Do not bypass permissions or access controls.

First read applicable existing repository instructions, including AGENTS.md and any more specific applicable guidance. Preserve unrelated work and record the starting working-tree state. Do not execute install hooks, package scripts, tests, or downloaded code without checking their side effects and ensuring they cannot access production or paid services. Safe baseline checks may run in an isolated environment; label everything else NOT RUN.

Write English engineering documentation while preserving the English/Traditional Chinese product requirements. Keep recommendations, verified observations, assumptions, and blockers visibly distinct.

## 1. Inputs and evidence hierarchy

### 1.1 Exact target

- Owner-specified Site: `https://fimmick-buyeros.laichiwillyjp.chatgpt.site`
- Matching saved Site title: `FIMMICK BuyerOS — Review Workspace`
- Matching saved project ID: `appgprj_6aa82285e5108191aac9c44c840c5efe`
- Saved slug: `fimmick-buyeros`
- Saved metadata: source version 1; projection revision 2; status active; access mode custom.

These metadata identify a saved Site record, not a verified current Git commit, source export, hosting topology, authentication configuration, or production backend. Confirm current identity and version before making repository-specific conclusions. Never change Site access settings to inspect it.

No BuyerOS source repository has been confirmed in the preparation of this instruction. An installed-repository search for `buyeros` returned no matches; that is not proof that no repository exists. Do not invent `YNWAforever/buyeros`, another repo name, or source paths.

### 1.2 Supplied reference files

Read the following completely, not just their summaries:

1. `references/BUYEROS_FRONTEND_MASTER_INSTRUCTION_v1.md`: the earlier frontend specification.
2. `references/BUYEROS_RESEARCH_SOURCE.md`: the owner's attached research.
3. `references/SITE_PROJECTION.txt`: labelled excerpts and metadata from a saved one-line text projection of the matching Site, not a fresh interactive audit or source export.
4. `references/SOURCE_REGISTER.md`: provenance, limitations, hashes, and documentation links.

The owner's `deep-research-report (1).md` and `deep-research-report (2).md` are byte-identical. They are one research source, not two independent reports or corroborating implementations. Their SHA-256 is recorded in the source register. The research contains embedded citation tokens from an earlier session; these tokens alone are not independently retrievable verification. Follow actual primary sources where a technical or licensing decision depends on them.

Also inspect the actual frontend export or repository when available, plus authorized backend work already in that same project. Read manifests, lockfiles, route definitions, types, state, adapters, tests, deployment configuration, environment examples, and migration history. Never print secret values.

Upstream capability references:

- `https://github.com/xiongQvQ/AI_Find_Customer`
- `https://openoutreach.app/`

Find the currently linked OpenOutreach/OpenOutFind repositories from authoritative upstream references. Do not guess their owners, branches, packages, CLI flags, or import paths. Inspect the relevant files and LICENSE at pinned commits before proposing code reuse.

### 1.3 How to resolve conflicts

Use an explicit conflict/decision table rather than silently replacing any source:

`Topic | Source A position | Source B/current-source position | Proposed resolution | Rationale | Approval/blocker | Evidence`

For implementation reality, actual inspected source is stronger than a screenshot or generated report. For the desired product, preserve the owner's existing BuyerOS direction and document deviations. A bug in current code is not a requirement to preserve the bug. A frontend specification is not proof a feature was implemented.

Critical conflicts to address:

- The research recommends using AI_Find_Customer as a Web foundation. An existing BuyerOS frontend now exists: preserve its UI and selectively reuse backend capabilities instead of discarding it.
- The research expands “FIMMICK” into a technology acronym containing Keycloak/Kubernetes/Terraform/Helm. This is a proposed stack inside the report, **not evidence of FIMMICK's actual company stack**.
- The frontend intentionally prohibits real delivery. The research includes sending and reply sync. Recommend a live research/contact/draft MVP first, with delivery as a separately approved phase; label this staging choice as a new recommendation.
- The research's timing, API prices, capacity limits, retention examples, and cloud budgets are planning assumptions or historical snapshots, not current commitments.
- The research's source retention suggestion must not become a blanket promise of permanent personal-data retention. Specify configurable retention and deletion propagation after appropriate policy review.

Do not infer that separate processes automatically resolve GPL obligations. Do not convert fit confidence into purchase probability. Do not treat a provider-marked-valid address as permission to contact.

## 2. Mandatory Phase 0: verify the Site and code

### 2.1 Audit the current frontend

Use an authorized browser and source export where available. Record inspection time, final URL, viewport, access condition, and current source/commit identity. Capture desktop and mobile evidence without changing sharing or triggering external operations.

The saved projection supports these observations only:

- Navigation labels: Overview, Find Buyers, Buyer Lists, Outreach, Results, Settings.
- HarbourSense / HarbourSense Instruments sample project, European sensor partners.
- Germany, Netherlands, Belgium; distributors and system integrators.
- A completed sample run: 24 unique companies, 14 Match, 6 Review, USD 6.60 illustrative discovery spend.
- Sample rows including Rheinwerk Controls GmbH, DeltaGrid Automation BV, Ardenne Systems SRL, Nordline Industrial GmbH, and Westhaven Technik GmbH.
- Why-fit text, evidence counts, human-review states, and contact labels such as Provider-marked valid, Not researched, Catch-all, and Suppressed.
- Search, filters, export, selection, and pagination controls; eight rows on the first page.
- Explicit demo/no-live-services and fictional-data disclosures.

None of the above establishes that clicks work, data persists, providers are connected, or a backend exists. Repeated text in the projection may represent responsive/hidden DOM variants; do not classify it as a visible duplicate-content defect without browser evidence.

Inspect all actual routes. The earlier specification proposes `/app`, `/app/discover`, `/app/discover/new`, `/app/discover/:runId`, `/app/buyers/:buyerId`, `/app/lists`, `/app/lists/:listId`, `/app/outreach`, `/app/results`, and `/app/settings`. These are candidate routes to verify, not an asserted source inventory.

Exercise the search wizard, buyer drawer/tabs, evidence links, fit filters, acceptance/rejection, list operations, lookup confirmation, draft revision/approval, CSV download, results/usage, locale switch, refresh, deep links, and mobile navigation. Only exercise state-changing controls where they are confirmed local/synthetic and safe. Never assume an ambiguous “Find contacts” or “Send” action is harmless.

Classify each capability as:

`OBSERVED_UI | LOCAL_DEMO_VERIFIED | SOURCE_VERIFIED | LIVE_BACKEND_VERIFIED | SPEC_ONLY | INFERRED | BLOCKED`

A screenshots-only review cannot be labelled SOURCE_VERIFIED. An HTTP success cannot establish a durable job or working permission gate.

### 2.2 Required UI-to-backend matrix

For every major screen and every state-changing control, produce:

`Requirement ID | URL/route | Existing file:symbol | Current behaviour | Evidence/status | Preserve/change | API operation | Entity/state transition | Permission/policy | Cost implication | Failure states | Test ID | Work package`

Use exact inspected paths and symbols where available. Mark every not-yet-existing path `PROPOSED`. Avoid generic rows such as “implement dashboard backend.” Trace the existing buttons to concrete backend work.

Include presentation regression baselines: navigation, density, drawer/tab structure, visual hierarchy, mobile behaviour, and English/zh-HK. Preserve approved assets and newer changes. Do not rebuild the visual system simply to adopt a preferred framework.

### 2.3 Source-access gate

If the Site cannot be reached, record the exact failure and continue with the saved projection/specification as provisional evidence. Do not declare the Site broken based only on your environment's access failure.

If the actual repository/export cannot be obtained, deliver a useful provisional architecture, source-import checklist, and blocked implementation tasks. Do not fabricate existing file paths, baseline tests, git hashes, API availability, or screenshots. Require source access before tasks that would modify the frontend can become READY.

If no repository is mounted, create the planning pack in the permitted output directory rather than initializing a new app or placing it in an unrelated repo. Identify the smallest missing inputs: frontend export/confirmed repo, deployment/identity decisions, and approval for future live services. Continue all independent planning work.

## 3. Product invariants and MVP boundary

The product is an account-first buyer intelligence workspace:

`Offer → Markets → Approved buyer profile → Discovery → Evidence → Human acceptance → Optional business-contact lookup → Draft → Human approval → Outcome`

Keep a canonical company separate from its people, contact points, project-specific buyer relationship, fit assessments, and reviews. Three people at one company do not equal three buyer companies. A company may fit one project's profile and fail another; never store the only fit verdict on a global Company object.

The core differentiator is a useful, inspectable explanation of why a company fits, including contradictions and unknowns. Do not build an autonomous mass-mailing system or claim a proven competitive advantage from agent count.

Recommend this release boundary, subject to the explicit decision table:

- **MVP-A — Live buyer discovery and reviewed outreach preparation:** tenant-aware persistence, approved ICP versions, real bounded research, evidence-based fit, human review, lists/export, one optional cost-gated business-email provider, grounded drafts, revision-bound approval, real usage ledger, manually recorded outcomes with provenance.
- **MVP-B — Controlled email delivery:** optional later release requiring mailbox/provider selection, verified capabilities, jurisdiction/policy approval, suppression, deliverability, sender identity, audit, and explicit owner authorization.
- **Later:** multiple enrichment waterfalls, additional licensed discovery engines, CRM sync, advanced active learning, phone lookup, social automation, self-hosted GPUs, cross-customer learning, multi-region deployment, and high-scale event platforms.

Do not remove MVP-A features merely because the frontend is currently mocked. The objective is a working pilot, not a second simulation. Equally, do not enable sending merely because upstream code already has a scheduler.

## 4. Choose a FIMMICK-aligned, low-overhead architecture

First inventory what the project actually uses. Classify every stack choice as EXISTING_VERIFIED, OWNER_DIRECTION, REPORT_RECOMMENDATION, NEW_RECOMMENDATION, or UNRESOLVED.

Use the following as a **proposed low-friction default**, not a claim about deployed infrastructure:

| Layer | Planning preference | Required decision |
|---|---|---|
| Frontend | Preserve actual React/TypeScript starter, styling, components, router, and lockfile | Do not force Next.js, TanStack Start, or Vite migration without source-based justification |
| Web hosting | Vercel-compatible frontend deployment when appropriate to the actual export | Keep the existing Sites URL unchanged; identify a separate staging target only after authorization |
| Domain API | Python FastAPI, Pydantic, typed OpenAPI boundary | Reuse existing verified API work; avoid duplicating domain logic in a Node BFF |
| AI workflow | LangGraph in a separate worker runtime; small bounded nodes | Persist checkpoints and distinguish business state from graph state |
| System of record | PostgreSQL, with Neon as a proposed managed option | Confirm workspace/region, credentials, pooling, migration path, backups, and supported extensions |
| Schema ownership | One migration owner; with a new Python domain API, prefer SQLAlchemy/Alembic | Do not let Alembic and Drizzle/Prisma independently migrate the same domain tables |
| Async execution | One durable queue and Python workers; Celery plus compatible Redis/Valkey is the report's default | Preserve an existing proven queue when suitable; choose one, not several competing systems |
| Identity | Reuse a verified company/project identity pattern; otherwise select one supported managed OIDC approach | Decide login, token/session verification, expiry/revocation, tenant membership; do not leave auth as “add later” |
| Storage | One private object-store adapter for uploaded documents and permitted source artifacts | Document retention, file access, signed URLs, and deletion |
| Providers | Typed search, extraction, LLM, contact, and later delivery adapters | One primary provider per required capability first, with fixtures for tests |
| Monitoring | Structured redacted logs, request/run IDs, cost ledger; selectively reuse Langfuse | Avoid a large self-hosted monitoring cluster for a small pilot |
| CI | Existing GitHub workflow conventions, tests, contract checks, manual deployment gate | Do not publish or create cloud resources during planning |

Choose a single primary architecture and justify rejected alternatives briefly. Do not provide an unresolved shopping list. Where source information blocks a decision, specify a provisional choice and the exact validation that can overturn it.

Explicitly address:

1. Browser → API authentication, CSRF/CORS or bearer-token approach, and server-side tenant authorization. Never expose provider or database secrets to the client.
2. Whether a Node proxy/BFF already exists; preserve it only if it has a clear role. Do not add a second domain backend merely to fit a hosting brand.
3. Long-running Python research workers outside the browser and ordinary web-request lifecycle. Verify chosen hosting limits, timeouts, concurrency, and restart semantics in current official documentation.
4. Queue delivery versus LangGraph checkpointing versus Postgres business entities: each has a different responsibility. A checkpoint is not a queue or a financial ledger.
5. API/worker database roles, transaction scope, pooled connections, migrations, and checkpoint compatibility. Test tenant context reset; do not assume RLS protects a role that bypasses it.
6. A small deployment footprint: frontend, API, worker, managed data services as necessary. Keycloak, Kubernetes, Kafka, Helm/Terraform, a dedicated vector service, and GPU hosting are not mandatory just because the report names them.
7. Reuse existing package managers and migration tooling rather than introducing parallel standards. Add pgvector only for a concrete MVP retrieval use case, not as a substitute for deterministic company identity.

Architecture diagrams must show both the deployable units and the trust/data boundaries. Proposed services must never be described as already connected.

## 5. Upstream code reuse and licensing plan

Inspect actual upstream code at pinned commits and produce a component-level map:

`Capability | Repo/commit | Exact path:symbol | License/dependencies | Current contract | Reuse/adapt/reimplement/defer | BuyerOS target | Tests | Risk/blocker`

For AI_Find_Customer, investigate company/product insight, keyword generation, search adapters, content extraction, lead extraction, evaluation, email drafting, job/SSE behaviour, model routing, and tests. Do not infer symbol names solely from the report. Record which single-user assumptions, local storage, token authentication, or scheduler behaviours require replacement. Preserve applicable copyright and license notices for reused code.

For OpenOutreach/OpenOutFind, verify where orchestration, discovery, fit reasons, optional contact resolution, and sending actually live. Check whether candidate import exists: **do not invent an inbound interface for accounts discovered by another engine**. If it only supports independent discovery/export, plan parallel candidate generation followed by normalization, or defer that adapter.

The research describes AI_Find_Customer as MIT and OpenOutreach/OpenOutFind as GPLv3. Verify each repository, component, and relevant dependency. Treat process/container/JSONL isolation as an architectural boundary requiring license review, not an automatic proprietary-use exemption. Do not copy GPL code into BuyerOS while calling it a clean-room reimplementation.

Prefer selectively adapting verified reusable capabilities behind BuyerOS-owned contracts. A proprietary deployment path and a source-distribution path may have different obligations; flag them for appropriate review. Unresolved optional GPL integration must not prevent the independent public-web discovery pilot from being planned.

Do not assume discovery is free merely because email enrichment is disabled. Budget any billable search, licensed discovery, extraction, or model operation.

## 6. Domain model, API contracts, and state transitions

### 6.1 Data model requirements

Design an ERD and a schema proposal with keys, relationships, constraints, tenant scope, indexes, retention, and migration ownership. At minimum address:

`workspaces, users/memberships, projects, offer_documents, icp_versions, search_runs, run_events, raw_candidates, companies, project_buyers, people, contact_points, source_documents, evidence, fit_assessments, human_reviews, buyer_lists, list_memberships, enrichment_quotes, enrichment_jobs, provider_operations, budget_accounts, budget_reservations, cost_events, outreach_drafts, draft_revisions, approvals, suppressions, policy_decisions, outcome_events, audit_events`.

These are required concepts, not a demand for a separate microservice or table per noun. Consolidate where justified. Explain terminology mapping from the report's `campaign/lead` to the frontend's `project/buyer`, and keep email campaigns distinct.

Include composite tenant-safe relationships, uniqueness, idempotency scope, optimistic concurrency, and server-controlled timestamps. Decide whether company records are tenant-local; default to tenant-local for this pilot rather than sharing private research, contacts, or outcomes across customers.

Canonicalization must handle normalized domains and known aliases without merging separate legal entities merely because they share a brand/domain. Fuzzy matches should produce reviewable candidates, not irreversible automatic merges. Lists reference existing buyers; removing membership does not remove the underlying company/evidence.

Evidence records must preserve source URL/provider ID, excerpt, content hash where available, retrieval time, original language, labelled translation, permitted retention, source type, supporting/contradictory requirement, and observation/inference distinction. Source deletion/expiry must update dependent assessments and approval validity as appropriate.

### 6.2 API contracts

Map actual frontend adapters to concrete API methods. Produce a proposed OpenAPI contract with request/response examples for:

- Project CRUD; offer ingestion; saving and approving an immutable ICP version.
- Start/get/list/cancel/retry search runs; subscribe to durable run events.
- Buyer listing/detail/evidence; filtering, stable sorting, pagination, and bulk review.
- Lists/membership/notes/owners and audited scoped CSV export.
- Contact-lookup quote and confirmation, job status, provider callback or polling reconciliation.
- Draft generation/edit/review/approval and approval invalidation.
- Suppression/policy decisions, usage/budgets, and manually recorded outcomes.
- Readiness/health and capability status without credential disclosure.

Give every operation its tenant/role checks, validation, version preconditions, idempotency semantics, cost implications, errors, and asynchronous states. `202 Accepted` means a durable job was accepted, not that research finished. Explain the atomic job/outbox enqueue boundary so the database cannot say “queued” while work is silently lost.

Use structured errors and stable reason codes. Include permission denial, stale revision, stale quote, budget limit, provider unavailable, uncertain provider submission, and partial success. Return request IDs without leaking personal data.

For “select all filtered,” define a server-owned selection/snapshot or equivalent bounded mechanism; never silently act on different records after filters or data change. Recheck each record's eligibility at mutation time. Separate company counts from contacts at every aggregation endpoint.

### 6.3 Independent states

Specify legal transitions, actors, side effects, guards, and invalidation rules for each independent dimension:

- AI fit: Match / Needs review / Not a match, tied to ICP and evidence versions.
- Human review: awaiting review / accepted / rejected / needs information.
- Contact: not researched / unverified public / provider-marked valid / catch-all / unavailable.
- Suppression: active/inactive with explicit purpose and scope; it is not merely a contact-validation value.
- Policy: unknown / requires review / permitted / blocked, by purpose and policy version.
- Run: draft/queued/running/partial/paused_budget/cancel_requested/cancelled/failed/completed.
- Enrichment: quoted/reserved/submitting/pending/found/not_found/failed/unknown/reconciled.
- Draft: draft/review_requested/approved/stale; no delivery states in MVP-A.

The exact internal enum names may differ, but do not overload an upstream `ACCEPT` verdict to mean a human approved contact or sending.

## 7. Research workflow and quality controls

Define LangGraph state, nodes, transition conditions, checkpoint keys, task identities, retries, cancellation points, and node-level output validation:

`Validate request/limits → Load approved ICP version → Generate bounded multilingual queries → Discover candidates → Normalize/deduplicate → Fetch permitted evidence → Apply hard exclusions → Structured fit assessment → Verify evidence linkage → Persist buyer assessment → Await human review`.

A separate explicitly approved workflow handles contact lookup. A separate drafting workflow handles grounded copy. No accidental graph edge may move directly from discovery to paid enrichment or sending.

Include search-language and market strategy for the sample DE/NL/BE distributor/integrator use case without limiting the real product to fixtures. Define maximum query rounds, results, fetched pages/bytes, execution time, token budgets, provider concurrency, and total spend. New countries or unsupported filters must not silently return the sample dataset.

Use deterministic parsing/rules before expensive LLM calls, cached normalized queries where permitted, and bounded re-research of uncertain cases. Select one model route per task plus limited escalation; do not build a model marketplace or use the largest model for every page.

For each model operation specify a versioned prompt, structured output schema, permitted tools, timeout, retry limit, and evaluation fixture. An assessment must return supported requirements, contradictory evidence, unknowns, source/evidence IDs, concise fit rationale, and next action. Do not request or store private model chain-of-thought.

Treat webpages and uploads as untrusted data. Enforce tool permissions, safe fetching, and schema validation outside the prompt. A sentence telling the LLM to ignore injected instructions is not the entire security design.

Persist progress as durable events with monotonic per-run IDs. Support reconnect/resume, polling fallback, stable event ordering, and idempotent application in the UI. Progress must come from committed work; it is not a percentage animation disguised as a live run.

Explicitly test worker crash after a provider accepted a request but before local acknowledgement. Checkpoints and task retries alone do not guarantee exactly-once external side effects.

## 8. Cost, contact permission, and financial correctness

This is a core work package, not a dashboard added at the end. Design the budget governor before enabling any paid discovery or lookup.

Store money in a fixed-precision representation and explicit currency; do not use binary floating-point totals. Separate provider credits, metered operation cost, subscription allocation, and infrastructure overhead. Snapshot the pricing assumptions used by quotes; verify current prices separately and never hard-code the report's sample price as truth.

At authorization time enforce an invariant such as:

`settled_spend + active_reserved_upper_bounds + proposed_reservation <= approved_budget`.

Use an atomic transaction/conditional update or lock with a concurrency test. A UI-side comparison or check-then-write race is not a budget gate. Specify workspace/project/run/category limits and which has precedence.

A quote must bind selected buyer IDs, normalized request hash, purpose, provider/price version, maximum cost, currency, actor/tenant, and expiry. Revalidate acceptance, fit/profile freshness, suppression, policy, and budget at confirmation and before dispatch. Revalidate applicable gates when a late result arrives; quarantine or discard prohibited personal data according to policy rather than blindly exposing it.

Define reservation, commitment, release, reconciliation, and reversal events. Never release a reservation merely because a request timed out: the provider may have accepted and charged it. Keep unknown outcomes pending reconciliation; avoid blindly retrying paid requests without provider-supported idempotency or status lookup.

Cancellation stops new work where possible; already dispatched calls may still cost money. Document this honestly. Do not promise an absolute vendor invoice cap when a provider cannot bound charges. Block unbounded operations or require a separately approved policy and disclose the limitation.

Test concurrent confirmations, duplicate clicks, identical keys with different payloads, webhook replay/out-of-order arrival, quote expiry, job restart, cancellation during dispatch, price changes, missing results, and provider-credit reconciliation.

Start with one verified business-email provider only when needed. Publicly found addresses remain unverified unless actually validated. Catch-all is not provider-marked valid. Phone lookup and multi-vendor waterfalls are deferred.

Suppression must be enforced server-side at the appropriate workspace/client/controller scope. Do not create an unreviewed cross-customer contact-sharing database in the name of “global suppression.” Record policy basis, source provenance, purpose, country/entity context, decision author/version, review date, and retention. Unknown policy blocks the relevant action. Do not turn an AI checkbox into a legal approval.

## 9. Drafting, approval, export, and future delivery

Connect the existing outreach editor and evidence panel to real persisted drafts. Use approved offer facts and actual cited buyer evidence. Do not fabricate certifications, commercial relationships, buying intent, personal facts, or promised savings. Preserve recipient language and distinguish translation from original evidence.

Approval must bind the exact draft revision/content hash, recipient/contact, relevant ICP/evidence versions, policy context, approver, and timestamp. Material edits or changed suppression/policy/evidence invalidate approval. Use server-side optimistic concurrency so two editors cannot preserve a stale approval accidentally.

Draft copying or downloading does not create a Sent event. In MVP-A keep sending/scheduling disabled in UI and API. A hidden button is not a server-side gate. Manual outcome records must include actor, source=manual, timestamp, and notes; they must not be described as inbox-synchronised conversions.

Real-data exports must be scoped, authorized, audited, protected from spreadsheet-formula injection, and subject to applicable suppression/purpose policy. CSV and draft export must not be used to bypass a blocked contact policy. Demo exports remain explicitly marked with synthetic data mode.

For the optional delivery phase, plan only one sender of record. Identify mailbox authentication, provider terms, sender-domain configuration, accurate sender identity, opt-out mechanism, suppression recheck, rate limits, reply/bounce handling, pause/kill switch, and stale-approval prevention. Recheck current jurisdiction-specific requirements through authoritative sources and suitable legal review. Do not presume all B2B messages are lawful globally or that a transactional email service accepts cold outreach.

No actual delivery activation is authorized by this planning task.

## 10. Frontend integration without losing the layout

Produce a migration checklist for every existing mock adapter, store, fixture loader, timer, browser-storage key, and hard-coded metric. Separate server state from transient UI state and use the actual project's compatible conventions.

Preserve an isolated reproducible demo mode for design/QA. The live mode must never silently fall back to demo data on API failure. Demo fixtures must not be imported into a live tenant or counted in production usage. Do not merely remove the Demo banner while leaving synthetic rows in place.

Define backend capability/connection states from actual configuration and health, not a decorative “Connected” badge. Validate deep links, session expiry, tenant switching, reconnecting runs, empty workspaces, no-results searches, failed providers, offline states, and pagination.

Preserve the existing table/drawer/three-pane editor and English/zh-HK dictionaries where source verifies them. Identify the source of each displayed metric, including scope/date filter, numerator, denominator, and treatment of failed/partial runs. Count distinct accepted companies for cost per accepted buyer, and distinguish those with at least one valid eligible contact.

Use incremental vertical slices. First make persisted project/profile/review/list state work through the existing UI; then add real bounded discovery; then quote/lookup and drafts. Do not build a second frontend alongside the existing one.

## 11. Security, operations, and testing plan

The plan must assign concrete tasks and acceptance tests for:

- Server-side workspace/RBAC checks, cross-tenant reads/writes/exports/events/files, and tenant-safe background jobs. Test non-owner database roles and connection-pool reuse.
- Server-only secrets, redacted traces/logs, private object storage, scoped signed URLs, deletion/retention, and prompt/provider data minimization.
- SSRF: schemes, private/loopback/link-local IPv4/IPv6, DNS rebinding, redirects, metadata endpoints, outbound limits, and blocked destinations.
- Upload size/type/content checks, unsafe archives, document-parser isolation, and sanitized evidence rendering/XSS.
- Prompt injection, unsupported assertions, schema failures, evidence-ID tampering, stale evidence, and missing source access.
- Idempotency, durable enqueue, leases/worker restart, cancel/retry, provider uncertainty, and budget races.
- Draft revision/approval races, suppressed recipients, permission revocation, and disabled delivery endpoints.
- Dependencies, secret scanning, license notices, migration safety, backups/restore, and roll-forward/rollback strategy.

Create unit, provider-contract, API, database/concurrency, worker integration, frontend, and Playwright E2E coverage. Use deterministic provider fixtures by default. CI must not call paid APIs or send email. Any real-provider smoke test is separately authorized, bounded, and clearly identified.

Preserve these named demo regressions from the frontend specification: 26 raw candidates → 24 canonical companies; 14 Match/6 Needs review/4 Not a match; three detailed fictional dossiers; mixed human acceptance; suppressed/catch-all/missing contacts. The saved Site projection verifies only a subset, so check the actual fixtures before claiming parity.

Add a human-labelled real-company evaluation set for an authorized pilot. Define precision of accepted candidates, evidence support, reviewer agreement, contact yield, spend per accepted company/contactable accepted company, and human review time. Numeric quality targets must be labelled proposed until approved. Every displayed important factual claim must link to its supporting evidence or be marked unknown/inference; this structural requirement is separate from empirical evaluator accuracy.

Record test commands as CURRENT_VERIFIED, PROPOSED_AFTER_TASK, or NOT_RUN. Do not invent package scripts or claim tests passed because a file exists. All release gates need observable evidence, an owner, a failure action, and a rollback path.

## 12. Required planning output package

Create documents under `docs/buyeros/` inside the confirmed target repo, or in a clearly separate planning-output directory if the repo is missing. Only documentation and proposed contracts inside this directory are writable in this task. Do not overwrite existing plans; reconcile/version them.

Required outputs:

```text
docs/buyeros/
  00_README_AND_DECISIONS.md
  01_SOURCE_AND_UI_AUDIT.md
  02_ARCHITECTURE_AND_REUSE.md
  03_DATA_API_AND_STATE_CONTRACTS.md
  04_PHASED_IMPLEMENTATION_PLAN.md
  05_TEST_SECURITY_AND_RELEASE.md
  06_OPENCODE_EXECUTION_GUIDE.md
  contracts/
    openapi.proposed.yaml
  tasks/
    index.json
    BO-000-...md
    BO-001-...md
    ...
  handoff/
    AGENTS.addendum.proposed.md
    OPENCODE_START_PROMPT.md
    PROGRESS.template.md
    # Optional version-verified permission/config proposal; not active config.
```

The filenames above are required proposed deliverables, not assertions they already exist. Keep documents linked and avoid duplicating entire requirements in every task. Include enough local context and invariant references for a new OpenCode session to resume without this chat.

### Required document contents

**00:** Executive build decision; source access/status; assumptions/conflicts; approved versus proposed decisions; blocker register; critical path; input inventory; reading order.

**01:** Site/source identity, access results, actual repo tree/framework/version inventory, baseline checks, route/action parity matrix, visual evidence references, source-derived gaps versus hypotheses.

**02:** One recommended architecture with deployable/trust boundaries, stack provenance, rejected alternatives, ADRs, upstream commit/path/license inventory, migration/reuse boundaries, hosting/identity/queue decisions.

**03:** ERD, schema constraints/ownership, API examples, error taxonomy, pagination/bulk selection, state machines, graph design, event protocol, budget ledger, policy gates, and draft approval rules. The proposed OpenAPI file must be syntactically valid; endpoints not implemented remain explicitly proposed.

**04:** Dependency-ordered vertical slices, task ownership, effort ranges, parallelism constraints, prerequisites, integration points, demonstration steps, and phase exit criteria. Distinguish prototype work from live pilot and delivery release. Estimate after audit; do not convert a source report's 8–12 weeks into a promise.

**05:** Test matrix with requirement IDs, threat model, data/policy checks, observability, backup/restore, migrations, rollout/rollback, pricing assumptions, bounded pilot evaluation, and release gates.

**06:** OpenCode operating procedure, task selection, context loading, plan-to-build approval, scoped permissions, stop/replan rules, progress evidence, resume procedure, and final handoff checklist.

## 13. OpenCode work-package standard

Each task must be narrow enough to verify independently, ideally one reviewable change. Split oversized tasks. Use stable IDs and explicit dependencies; do not deliver only a week-by-week roadmap.

Every task document must contain:

```yaml
task_id: BO-###
title: Descriptive outcome
phase: P#
status: BLOCKED | READY_FOR_REVIEW | APPROVED_READY | IN_PROGRESS | DONE
priority: P0 | P1 | P2
source_requirements: [REQ-...]
depends_on: [BO-...]
blocked_by: []
base_commit: VERIFIED_SHA_OR_UNVERIFIED
plan_revision: v1
owner_role: frontend | backend | ai | platform | qa
files_to_read: []
existing_files_to_modify: []
proposed_files_to_create: []
forbidden_paths_or_actions: []
contract_refs: []
migration_impact: none_or_description
external_capabilities: []
external_spend_authorized: false
acceptance_tests: [TEST-...]
verification_commands: []
rollback_or_rollforward: description
effort_range_hours: [lower, upper]
```

Then add: observable objective; present-state evidence; exact code changes/algorithm; request/state examples; failure/concurrency cases; tests and expected results; a copy-paste OpenCode prompt; and required completion evidence.

This YAML and `tasks/index.json` are **our handoff conventions**, not a claimed native OpenCode workflow engine. Validate syntax, dependency references, and acyclicity. Do not imply OpenCode automatically executes the manifest.

Do not put guessed paths in `existing_files_to_modify`. Use proposed target paths separately. A task that depends on unavailable source or an unresolved safety-critical decision remains BLOCKED. A planner cannot mark an implementation DONE.

### Example task quality bar

A contact task cannot say only “connect BetterContact.” It must identify the verified existing quote dialog and adapter, proposed quote/confirmation API, authentication, request hash, quote expiry, atomic reservation transaction, per-buyer policy checks, provider idempotency/status capabilities, handling of unknown outcomes, ledger settlement, UI error states, and named concurrency/replay tests. If any provider capability is unverified, the task must contain a verification spike or blocker rather than fabricated API calls.

### Proposed phase skeleton

Adapt granularity to inspected source while preserving dependencies:

- **P0:** source/import verification, UI baseline, stack/license/provider spikes, plan decisions.
- **P1:** preserved frontend shell, domain contracts, authentication/tenant isolation, persistence, baseline tests.
- **P2:** persisted offer/project/ICP approval, buyer review/lists, minimum vertical slice, budget governor and durable execution foundation.
- **P3:** bounded real discovery, canonicalization, evidence capture, structured fit, durable progress, recovery.
- **P4:** quote/confirm gated contact lookup, reconciliation, suppression/policy, real usage metrics.
- **P5:** grounded draft generation, revision-aware review/approval, controlled export, manual outcomes.
- **P6:** security and failure-path hardening, human evaluation, cost tuning, documented pilot release.
- **P7 (separate approval):** one controlled sender, opt-out/reply/bounce loops, delivery-specific release gates.

P7 may be defined but must not be automatically started after P6. Optional OpenOutFind integration can be its own bounded spike/phase rather than blocking the primary public-web path.

## 14. OpenCode execution protocol to include in the handoff

Verify the installed OpenCode version and current official documentation before writing actionable configuration. OpenCode documents Plan and Build agents, repository instructions via AGENTS.md, and permission controls; these are not a reason to grant unrestricted access.

Use Plan first to review a selected task and compare it with the current repository. After explicit approval, use Build for that task only. Require narrow file/tool permissions and human approval for external writes, infrastructure, paid operations, and production. Do not use an allow-all permission setting or invent provider/model IDs.

Prepare an AGENTS addendum **as a proposal inside the planning directory**. Do not replace an existing root AGENTS.md or activate a new agent/command/configuration during planning. Optional `.opencode` artifacts must match the verified installed version and remain proposals until approved.

The execution guide must tell OpenCode to:

1. Read applicable repo instructions, the decisions/invariants, selected task, contracts, and latest progress. Check the current commit/diff and preserve unrelated changes.
2. Confirm the task is explicitly approved and its dependencies have evidence of completion. Missing source/permissions are blockers, not permission to build a replacement app.
3. Implement only that task's file scope. Separate personal/customer data from fixtures. Do not silently change architecture, provider, UI, schema ownership, or approval semantics.
4. Add/run the relevant tests and record exact commands/results. Do not weaken tests or fabricate live service responses to obtain a green build.
5. Update progress with changed files, test evidence, migrations, remaining risks, and the next eligible task. Do not commit, push, deploy, or enable sending unless separately authorized.
6. Stop and propose an ADR/task revision when source differs materially, a license/provider limitation appears, a budget cannot be bounded, or an unexpected migration is necessary.

Parallel work is optional and limited to tasks with disjoint file/schema ownership. Serialize shared migrations, contracts, budget logic, and integration. Reuse source audit and provider fixtures to avoid repeated research and token spend. After context compaction/new sessions, resume from the task/progress files rather than reconstructing decisions from memory.

## 15. Planner completion gate

Before returning the plan, perform a documentation-only self-review:

- All source and Site claims have the correct evidence status.
- The source report's invented technology acronym was not treated as verified corporate architecture.
- Every important current UI action maps to an API/entity/guard/test/task or an explicit deferral.
- The exact frontend is preserved; missing source is not hidden behind invented paths.
- Database/migration ownership, queue ownership, identity, and provider choices are resolved or visibly blocked.
- Fit, human acceptance, contact validity, policy, suppression, approval, and delivery are separate.
- Budget reservations survive concurrency, timeouts, retries, and uncertain provider outcomes.
- Demo/live separation, evidence grounding, tenant isolation, and draft invalidation have negative tests.
- Optional GPL integration and real delivery each have their own approval gates.
- Task manifests and proposed contracts validate; dependencies are consistent; no unapproved implementation task is DONE.
- Exact executed checks and NOT RUN items are reported honestly.
- No application code, database, infrastructure, active agent configuration, production URL, access permission, provider account, or mailbox was changed.

Finish with: verified current state; preserved frontend features; recommended architecture and deviations from the report; generated file list; source/approval blockers; proposed phase estimates with assumptions; the first OpenCode task to review; and the exact OpenCode starter prompt.

**Create the planning package now. Stop after planning.**
