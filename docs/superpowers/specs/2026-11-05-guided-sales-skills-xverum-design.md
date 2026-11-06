# BuyerOS guided sales skills and buyer enrichment

Date: 2026-11-05 (Asia/Singapore)
Status: Approved by the user on 2026-11-05; implementation planning requested. Live activation, deployment, shared-data migrations and consequential Git actions remain separately scoped.

## Intent and decisions

Users complete sales work through project-scoped chat: choose a guided template or describe a task, supply missing information, run a preset skill, review changes, and reopen saved results in the existing BuyerOS workflows. Separate discussions retain their own context and link to shared project records. Ads Copilot is the interaction reference, not an execution dependency.

The user selected adapting https://github.com/zubair-trabzada/ai-sales-team-claude into BuyerOS and requested Xverum MCP for buyer-profile enrichment. These are accepted direction decisions. Defaults explicitly labelled below are design proposals, not prior user decisions.

This is a project-sized change. This design extends the 2026-10-26 conversation-home proposal and takes precedence for skill integration, provider scope, execution, and delivery criteria. Its preservation map and bilingual/accessibility requirements remain applicable.

## Evidence and implementation baseline

The current primary checkout is main at 3f10f419; it contains untracked work that must be preserved. Worktree inventory also contains T21 at 84bf9d58, a login checkout at 3c79793b, and BuyerOS-live at ee085b76. These are different revisions, not interchangeable release evidence. No live deployment revision has been established in this design session.

Graph discovery and focused source inspection in BuyerOS_T21 found:

- `services/live/operations.ts:createOperationClient` checks current workspace/project context, attaches authentication, and carries idempotency and version headers.
- `services/api/buyeros_api/services/confirm_service.py:confirm_lookup` revalidates an exact quote, reserves USD liability, and creates provider operations and an outbox event in one transaction. It does not call a provider itself.
- The October design identifies existing document ingestion, buyer review, runs, draft preparation, and policy boundaries to reuse. Their acceptance on a selected implementation revision must be checked again.

Planning begins with a read-only reconciliation of retained revisions and current remote metadata, followed by selecting a non-destructive isolated implementation checkout. Do not start implementation against the old primary checkout by assumption. The plan must record the chosen SHA and missing/reusable service capabilities; no push, merge, deploy, migration against shared data, or provider activation is implied.

## Goals, exclusions, and failure conditions

Deliver guided templates, durable discussions, saved and versioned outputs, native workflow links, and a bounded Xverum enrichment path. A complete task has a persisted output with canonical readback, provenance, and an accurate execution state.

Exclude automatic sending, scheduled outreach, mailbox integration, arbitrary user-supplied code or MCP servers, autonomous approval, and replacement of existing full screens. Existing unavailable features remain visibly unavailable. UI-only chat, invented evidence, silently lost work, cross-project leakage, duplicate spend, or a completion message before saving are release failures.

## Approaches

1. **Native skill adaptation — selected.** Translate upstream playbooks into versioned BuyerOS task definitions and use existing authenticated services. This provides one record/permission model but requires structured input/output mapping.
2. **Hosted original Claude Code agent — considered.** Preserves its runtime assumptions but introduces a second execution environment and file-to-record synchronisation. Not selected.

Keep React/TypeScript and the current Python/domain boundaries. The builder may choose module names and internal composition; changing the application runtime or adding a second general-purpose agent host needs a design amendment.

## User experience and guided completion

Retain the earlier conversation-home layout: project identity, new discussion, recent discussions, task library, and direct links to existing work screens. Discussion content contains questions, progress, actionable review cards, and result links. Results/Sources/Decisions may appear alongside chat on desktop and as separate views on mobile. This is a proposed layout pending visual review; the exact newly supplied Ads Copilot discussion could not be loaded by the web reader.

Every template has an outcome label and an availability state. Natural-language requests and template cards enter the same task engine. The assistant asks only for missing required fields and previews the selected skill and intended result. A user can correct the skill or scope before execution. Broad requests can become multiple explicit steps inside one discussion; independently useful tasks can start a linked discussion.

Example: “Research this buyer and prepare a follow-up.” Resolve the buyer, confirm missing offer context, propose bounded research/enrichment, present the cost review when needed, save a cited research result, and prepare an outreach result. Formal draft creation requires the existing recipient, evidence, policy, and review conditions. The user can complete each permitted review inside chat; full screens remain reachable.

Draft text and attachment selection survive route changes. Server-acknowledged messages survive reload. A failed submission remains visibly unsent; retry uses the same client message key. Model outage preserves saved work and provides a link to the corresponding existing screen.

## Skill catalogue and output mapping

The upstream library is a Claude Code orchestrator with specialised sales playbooks and file outputs. Its prospect workflow coordinates five analysis roles. Source: [orchestrator](https://github.com/zubair-trabzada/ai-sales-team-claude/blob/main/sales/SKILL.md) and [prospect skill](https://github.com/zubair-trabzada/ai-sales-team-claude/blob/main/skills/sales-prospect/SKILL.md).

Proposed release scope covers the complete catalogue, grouped as follows. Core workflows are delivered first, but the phase is not declared complete while the remaining catalogue is only placeholder text.

| BuyerOS task | Adapted upstream skills | Persisted destination |
|---|---|---|
| Define ideal buyers | sales-icp | Offer/profile proposal; explicit profile approval |
| Research a buyer | sales-research, sales-prospect, quick routing | Research run/report linked to buyer and evidence |
| Assess fit and buying readiness | sales-qualify | Versioned assessment; human buyer review stays separate |
| Enrich buyer and purchasing roles | sales-contacts plus BuyerOS enrichment adapter | Company/person evidence proposals and reviewed field changes |
| Understand competitors | sales-competitors | Cited research document linked to buyer/project |
| Prepare outreach and follow-up | sales-outreach, sales-followup | Preparation outputs; eligible native draft revisions |
| Prepare a meeting | sales-prep | Versioned meeting brief |
| Prepare proposal and responses | sales-proposal, sales-objections | Versioned proposal/playbook; verified commercial inputs |
| Summarise pipeline | sales-report, sales-report-pdf | Timestamped report and export of that same revision |

Document understanding and project setup remain BuyerOS-native templates that supply context to these skills. Existing shortlist/list actions are native capabilities that qualification may propose.

Each adapted definition has an immutable version, upstream revision/hash, attribution, supported languages, required inputs, allowed capabilities, output schema, evidence requirements, budget class, and completion validator. Pin the upstream commit and preserve its licence notice before importing content. Do not execute its installer. Do not expose terminal commands as product requirements.

Replace upstream WebFetch/WebSearch/file/Task assumptions with approved BuyerOS adapters. No arbitrary shell execution or dynamic skill installation. Administrator-reviewed skill releases cannot expand permissions without a separate capability change. In-flight tasks retain their original skill version. Model/tool outputs are untrusted data and pass server-side validation.

Parallel analysis is an implementation option under one bounded parent task, not permission to multiply cost. All branches share an immutable context snapshot, individually tracked budgets and receipts, and a final completion check. Conflicting evidence is retained. Numerical qualification is labelled advisory with its rubric and unknown inputs; a score cannot establish confirmed budget, purchasing authority, intent, or buyer acceptance. Unknowns never become zeros or invented facts.

## Discussions, records, and persistence

Proposed defaults: discussions are private to their creator; explicit sharing grants access only to authorised project members. Existing project record access rules remain unchanged. Saving a shared output from a private discussion shows its destination and audience. Backlinks must not reveal private titles or content.

Add durable thread, message, task-invocation, task-event, output-version/link, connection-binding, and provider-receipt records where equivalent records do not exist. Every record is tenant scoped; relevant entities include project, owner, visibility, revision, timestamps and retention state. Messages have stable client IDs and sequence numbers. Invocations pin skill/model configuration, context versions, action fingerprint and initiating actor. Receipts reference native jobs and approvals rather than cloning their state machines.

Canonical buyers, lists, profiles, runs and drafts remain authoritative. Outputs contain authored revisions and references to those records. Regeneration creates a new revision; it never replaces the old one invisibly. A saved output can be opened outside chat. Reports include their data time and scope, and unavailable inputs remain unavailable rather than reporting zero.

New conversations read only selected, authorised project facts, documents and outputs, not sibling transcripts automatically. Project switching never changes an existing thread's identity. Read, search, sharing, export, and worker execution all recheck access. Permission revocation removes retrieval eligibility, including cached excerpts and summaries. Source removal invalidates derived content for retrieval/export; retain only permitted audit metadata under existing retention policy, not hidden copies of deleted text.

## Xverum provider facts

The [official MCP documentation](https://ask.xverum.com/docs/mcp-server), reviewed 2026-11-05, describes an OAuth-protected hosted endpoint at `https://mcp.xverum.com/mcp` and a synthetic demo endpoint. Company and people searches use `search_company_xverum` and `search_people_xverum`; detail tools are `enrich_company_xverum(company_id)` and `enrich_person_xverum(id)`. Search costs one credit per returned result; detail fetches cost four. Email lookup costs two credits when found. Responses expose usage and request identifiers; nullable fields and freshness labels require careful handling. These are documented capabilities, not tested BuyerOS integration evidence.

## Proposed enrichment behaviour

First release allows company and professional-role discovery/detail plus separately selected business-email lookup. Phone lookup, reverse lookup, and job-change prediction stay disabled by default as outside the requested profile-enrichment journey. This scope is a design proposal.

Use a server-side connection owned by an authorised workspace administrator and explicitly assigned to projects. Do not reuse a developer's Codex session or expose credentials to the browser/model. Live enablement requires validating that the provider's OAuth registration, token lifecycle, account terms, and permitted data use support this SaaS connection model. If they do not, leave live enrichment unavailable and revise the connection design; do not quietly substitute a personal credential.

Company matching uses existing canonical identity, normalised website domain and corroborating name/location. A name-only match, duplicate subsidiary, conflicting domain, or several plausible candidates requires user selection before detail fetching or merging. Store provider identity separately from native buyer identity. People must be linked to the resolved employer with source evidence; title alone does not establish decision authority.

Present enrichment as a field-level proposal: existing value, proposed value, source, retrieval time, provider freshness description, and conflict/unknown state. Applying selected fields uses native version checks and a durable audit event. Never overwrite reviewed facts silently. Provider-supplied verification is attributed to the provider, not represented as BuyerOS independently verifying the claim. Unknown employment dates do not prove current employment. Enrichment does not accept a buyer, approve an ICP, or unsuppress a contact.

Request only needed company/role fields; exclude education, personal background and other unnecessary fields from persisted projections and model context. Raw responses are not retained by default. Provider terms and the workspace retention policy constrain any necessary encrypted short-lived recovery payload. Suppression and permitted-purpose checks apply before dispatch and before exposing contact data.

## Execution, spend, and recovery

Request flow: authenticated message → scoped context → validated skill plan → permissions and cost review → durable task/native job → validated output → save/readback → linked chat result.

Model-generated arguments never supply trusted tenant identity, grant access, approve a spend quote, or bypass a native validator. Existing canonical writes use existing services. Skill-specific operations missing from that surface need explicit typed endpoints and the same controls; no direct model-to-database writes.

The reviewed contact admission code currently reserves USD. Add a provider-credit reservation/settlement ledger linked to native operation receipts; do not store credits in a USD amount. Enforce both the workspace credit cap and any applicable monetary budget. A monetary estimate uses an administrator-configured, versioned account tariff; if a required monetary cap cannot be calculated, dispatch is blocked. Never invent a credit-to-currency conversion.

A cost review binds actor, project, connection/account, selected buyers/people, tool allowlist, result/page limits, context/price versions, expiry, and maximum total credits. Proposed initial limits: one company candidate page of at most five results, one selected company detail, one people page of at most five results, at most three selected person details, and business email only for explicitly selected people. Expanding those limits requires a revised quote. Every billable step, including disambiguation search, falls within reviewed scope. Model usage has a separate bounded cost reservation.

Reserve before dispatch and revalidate access, suppression, connection status and quote versions in the worker. Persist dispatch intent before calling the provider. Settle actual reported usage once against the receipt and release only known unused liability. No automatic pagination or unbounded retries. Cached outputs may be reused only with current permissions, retention eligibility and visible age; refresh is a newly budgeted operation.

Builder-review clarification (proposed default): discovery and detail retrieval use separate approvals. A search quote binds the existing buyer/project, exact query, tool, page/result ceiling and maximum credits; it cannot bind unknown returned identities. After search results arrive, pause for candidate selection. A second quote binds the selected provider IDs and exact detail/email actions before any such call. People discovery similarly follows resolution of the company. No initial search approval authorises unspecified downstream enrichment. Unchanged, already approved steps need no repeated approval; each changed scope gets a new quote.

A lost response creates Outcome unknown and retains the reservation. Do not automatically repeat a possibly billed call or assume provider deduplication. Reconciliation uses available provider/account evidence; if unavailable, an operator resolves the receipt before any new paid attempt. Stream reconnection replays durable events, not jobs. Cancellation stops undispatched steps and reports already dispatched liability accurately.

States: Needs input, Ready for review, Queued, Running, Partially completed, Completed, Failed, Cancel requested, Cancelled, Outcome unknown. Completion requires all required outputs to pass schema/evidence checks and canonical readback. Partial subtask success saves usable outputs with explicit missing steps. Schema drift, expired authentication, exhausted balance and disallowed capabilities stop execution with actionable status.

## Model and provider configuration

Default proposal: reuse the selected revision's configured server-side model adapter behind a capability interface; do not select or purchase a new vendor during design. Planning must identify the actual supported model configuration and missing streaming/structured-output capabilities. A deterministic test adapter is for fixture validation only. Without an authorised live model and Xverum account, the UI shows configuration requirements and live acceptance stays BLOCKED.

Do not forward whole private discussions to Xverum. Construct minimal company/role queries. Select only necessary authorised context for the model; make destination/provider scope inspectable. Logs redact secrets and personal payloads. Endpoint destinations and tool schemas are allowlisted and validated at the transport boundary.

## Delivery and acceptance

1. Reconcile source baseline and preservation matrix; pin and audit upstream skills. Establish task schemas, tenant rules, permissions, budgets and test fixtures.
2. Deliver durable discussions and guided core journey: profile context → research → enrichment proposal → reviewed save → draft preparation/native draft.
3. Complete meeting/proposal/objection/report skills, output history, source lifecycle, recovery, exports and bilingual responsive UI.
4. Validate an isolated authenticated integration, then separately authorised bounded live model/provider acceptance. Enable by workspace feature flag only after release review. Disabling the entry point preserves recovery access to saved records.

Required checks, each recorded as PASS, FAIL, BLOCKED or NOT_RUN with revision/environment:

- Natural-language and template starts select the same skill, gather missing fields, and save the same output type.
- Every catalogue task produces a schema-valid persisted result or an honest missing-input/capability state; core end-to-end live completion is mandatory for phase acceptance.
- Saved outputs reopen from native Buyers, Research, Drafts or Documents after reload and across permitted discussions.
- Cross-tenant/project/user reads, search, job dispatch and writes fail safely; sharing never broadens source permissions.
- Concurrent edits reject stale proposals; material changes invalidate approvals.
- Multiple tabs, duplicate submissions, stream loss and worker restart do not duplicate internal writes or paid dispatches.
- Company ambiguity, employer mismatch, null fields, outdated evidence and conflicting facts preserve uncertainty.
- Cost bounds, concurrent credit reservations, USD/credit separation, expired quotes and uncertain charges reconcile correctly.
- Expired/revoked connections, tool-schema changes, outages, no results and partial jobs remain distinguishable.
- Retention/deletion removes restricted derived context and prevents stale export/retrieval.
- Generated outreach uses actual source facts and verified project claims; no fabricated introductions, proof points or approvals.
- Keyboard, mobile, zoom, English/Traditional Chinese, navigation history and existing screen regression checks pass.
- Synthetic provider/model fixtures and any provider demo are clearly labelled; neither counts as live enrichment acceptance.

Measure task-to-saved-output completion, correction rate, unresolved failure rate, time to first usable output, and actual cost per completed task. Establish a baseline before claiming improvement.

## Builder discretion and review

Builder may settle internal module layout, component composition, schema/index names, accessible visual details and bounded concurrency. Builder must not change task scope, connection ownership, paid-action approval, canonical record authority, or retention boundaries without revising the design.

User review should focus on the proposed full-catalogue scope, private-by-default discussions, project-assigned administrator connection, initial enrichment limits and disabled extra lookup categories. Operational account/model configuration and implementation SHA are explicit prerequisites in the plan, not inferred approvals.

The user granted design approval on 2026-11-05 and requested implementation planning. No product code, provider account, shared database or deployment has been changed by this document. The document is left uncommitted to preserve the user's task-specific Git approval boundary.

An independent builder review identified ambiguity between paid discovery and exact-identity quotes. The staged-approval clarification above resolves it as a proposed default for user review. This review assesses planning completeness, not runtime or release acceptance.

## Visual concept evidence

The user accepted a browser mockup. A local, fictional-data concept is saved at `.superpowers/brainstorm/20261105-sales-skills/content/sales-workspace-v1.html`. It illustrates the template library, discussion, separate paid-stage reviews, selected-field application, buyer record and linked outputs. Browser checks passed for opening the enrichment template, advancing through search/candidate/detail stages, applying sample fields, opening the sample buyer record and returning to the discussion. The preview remains open for review.

This concept uses scripted in-memory state. It does not implement independent durable threads, reload persistence, real AI, live enrichment, or native backend writes. Other template screens illustrate their entry points only. No mobile, language, production, or full-catalogue acceptance is claimed.

## Planning baseline correction — 2026-11-05

Read-only remote verification during planning identified main at `da49de0f70077db14c15219338133b59fcecd822`, 28 commits ahead of retained `3c79793b`. Unlike the older local/graph baseline described above, it already includes conversation-home templates, server threads/shares (0058), grounded conversation model/admission code, and Google Drive connection metadata (0059). These are foundations to extend, not missing modules to recreate. Source presence does not establish live acceptance: the conversation registration remains unselected, replies are restricted, and Drive content is explicitly excluded from paid persistent receipts.

The implementation plan targets this verified remote SHA, preserves the Drive zero-content-retention boundary, and adds versioned skill/task/output contracts alongside existing thread identity and ACLs. Its new capabilities do not retroactively widen legacy note imports, Drive data use, or provider activation. Current root AGENTS.md requires: “Avoid unnecessary secondary labels and descriptions. Let the layout do the explaining.” Apply that rule to implementation; the mockup's explanatory labels are design-review aids.
