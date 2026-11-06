# BuyerOS conversation home — design proposal

Date: 26 October 2026 (Asia/Hong_Kong)

Status: **Proposal for review; no product implementation or deployment.** The user selected **Conversation as project home**, with templates and saved results beside it and all existing screens directly accessible. The remaining defaults below are recommendations, not separately approved product decisions.

## 1. Product decision

Make the project home a guided place to ask for an outcome, continue a discussion, or choose a task template. A conversation coordinates the existing BuyerOS workflow. Its outputs become linked, versioned project records that remain usable through tables, document views, review screens and editors.

Success means a first-time user can say what they want, attach relevant material, understand the next question, and reach a reviewable result without learning the navigation first. Experienced users retain direct access to every current screen and bulk operation.

This proposal concerns the authenticated application. Keep the public marketing site and its demo separate. Changing the home must not activate research providers, contact enrichment, sending, or any other currently disabled operation.

## 2. Evidence used and limits

### Browser observations on 26 October 2026

- [Ads Copilot conversation home](https://ads-copilot-alpha.vercel.app/spaces/c5ca6abc-d53c-4fa7-85bf-aef922ca64a7/chat): persistent sidebar, space selector, new conversation, recent discussions, prominent question box, account chips, six initial template cards, and an expandable library of 16 templates grouped under All / Monitor / Create / Optimize / Report.
- A saved Ads Copilot discussion contains the guided-interview prompt and two interrupted-response notices. This supports a design observation, not a successful end-to-end AI execution claim. No new prompt or retry was submitted.
- Its settings show accounts explicitly assigned to a space. The connection screen describes centrally authorised Google Ads and Meta connections through Ryze. This is visible connection-management behaviour; the underlying use of MCP was not verified from the UI.
- In this signed-in browser, opening the reference root URL returned to a recent conversation. Its workspace directory has cards with Start conversation and Settings.
- [BuyerOS public home](https://buyer-os-nu.vercel.app/zh-HK) and [authenticated workspace](https://buyer-os-nu.vercel.app/app) were accessible. The selected live workspace/project was FIMMICK / Golden Resources. The overview exposed the existing navigation, daily work queue, profile/history and usage panels.
- At that observation, the work queue showed 24 awaiting review, 24 unassigned and 24 unknown-fit companies. These are displayed operational counts, not 24 qualified leads. Pilot budget and lead-progress panels showed service-unavailable errors. No retry, research execution, upload, save, approval, account connection, export or send was performed.
- The Offer screen showed the four-step form and saved source documents, including PowerPoint originals. One presentation explicitly reports images without editable slide text. A redesign must preserve this limitation rather than infer extracted facts.
- The Buyers screen exposed search/fit/review/queue filters, sorting, pagination, company import, explicit and filtered selection, segmented maintenance, saved lists and saved filters. Imported source notes were visible while structured source counts and fit fields were still empty/unknown. A chat summary must distinguish those notes from reviewed, structured evidence rather than automatically upgrading their status.

### Local source review

The primary checkout remains `C:/Users/laich/Documents/BuyerOS`, local `main` at `3f10f4191a4c22653afffeee4218f1bd91c38581`. It contains unrelated untracked files, which were preserved. A newer retained checkout is `C:/Users/laich/.codex/worktrees/buyeros-t21-20261022/BuyerOS`, recorded in Git worktree metadata at `84bf9d589e7e684f74ec0beef36fa148d247e68c`.

Code discovery used the `BuyerOS_T21` knowledge graph, followed by focused snippets and current documentation. Reviewed seams include `LiveWorkspace`, `LiveNavigation`, `LiveOfferDocuments`, buyer results/detail/import, run progress, drafts, lead preparations, policy settings and their live operation adapters. The graph did not reveal a general conversation/thread orchestration module in the searched application paths. Existing grounded draft templates are a useful foundation, but are not a complete task-template system.

The package retains React, TypeScript, Vinext and Next APIs with existing framework scripts and a Python API/domain layer. Keep the current runtime and service boundaries. The deployed commit was not reconciled to a local SHA, and no regression suite was run. Before implementation, select and verify the actual target branch, current files and deployment baseline; do not build against the older primary checkout by assumption.

## 3. Approaches considered

| Approach | Benefit | Tradeoff | Decision |
|---|---|---|---|
| Conversation as project home, with linked work surfaces | Easiest start; one place to ask, resume and see outputs; retains structured workflows | Requires durable threads, context selection, action orchestration and clear saved-state feedback | **Selected by the user** |
| Current dashboard plus an assistant side panel | Smaller initial navigation change | New users still need to understand the existing screens before choosing a task | Considered; not the selected default |
| Replace the application with chat only | Minimal initial screen | Makes comparison, bulk review, version history and repeatable operations harder to reach | Not recommended |

## 4. Proposed information architecture

**Workspace → Project → Discussions + Project records.**

The persistent sidebar contains the project switcher, **Home / New discussion**, recent project discussions, and **Project work** with the existing destinations. Preserve their names in the first release: Overview, Offer, Buyers, Research runs, Drafts, Results, Settings and Operations. Add a shared Documents view and Connections entry as clearly scoped additions. Role-dependent navigation retains existing permissions.

Put the workspace/project selector in the application header once, replacing repeated large selector panels on every working screen. Retain access details and support diagnostics in a disclosure. Always keep project identity visible above the composer.

### Home

1. A specific invitation: **“What would you like to achieve for this project?”**
2. A composer with **Attach document**, **Choose sources** and visible project context. Show which selected sources will be used before submitting.
3. Six task cards with outcome labels, one-line explanations, required inputs and an honest availability state.
4. **Continue working**: recent discussions with title, last activity and action state.
5. A compact **Needs your attention** list drawn from the existing work queue: missing facts, pending review, interrupted work or unavailable services. Keep the full overview one click away.

For a new user, offer **“Guide me through my first project”**. Ask one necessary question at a time and accept either short answers or document input. Preview inferred product facts and buyer criteria before saving or approving them. A question that does not need a tool should not start a research job.

### Discussion screen

Use a three-part desktop layout: narrow navigation and thread list, a readable conversation column, and an optional output/context panel. The right panel has **Results / Sources / Decisions**. It opens when there is relevant content; it is not an empty permanent column.

Messages can contain an editable brief, a sourced answer, an existing buyer-table preview, a run-progress card, a document card or an action proposal. Each result has **Open full view**, its saved state and its source/version. Tables and long documents can expand into the existing full-width work surface while the discussion remains available.

Keep the FIMMICK/BuyerOS identity and restrained green accent. Use generous spacing, clear type hierarchy, quiet surfaces and compact status labels. Avoid the long stack of equally prominent panels on the current home. Do not expose request IDs, hashes, internal states or protocol names in the ordinary path; retain them under details where useful.

On mobile, show Conversation / Results / Sources as separate views and open navigation in a drawer. Do not shrink three columns onto one screen. Preserve keyboard operation, visible focus, readable zoom, English and Traditional Chinese, and unsent text across navigation.

## 5. Initial template library

Templates describe a repeatable task, required inputs, allowed tools, output shape and completion conditions. They are more than prompt text. Start with six cards and expand only after validating their usefulness.

| Template | Guided inputs | Saved output and destination |
|---|---|---|
| Guide my first project | Product, target market, buyer type, available documents, constraints | Project brief and proposed buyer profile → Offer; approval stays explicit |
| Understand my documents | Selected files; missing information to resolve | Document summary, candidate facts and gaps → Documents / Offer |
| Research a market or buyer segment | Approved profile, market, scope and permitted sources | Cited research brief and, when enabled, existing research run → Research runs |
| Review and shortlist buyers | Existing/imported candidates, fit criteria, exclusions | Saved buyer view/list with evidence and review work → Buyers |
| Check a company or purchasing role | Selected company, source evidence, open questions | Company/person/channel evidence and review tasks → Buyers / Operations |
| Prepare a follow-up draft | Reviewed company, approved product facts, intended purpose and language | Cited preparation or eligible formal draft → Drafts; no automatic sending |

An additional **“Summarise progress and next actions”** template can live in the expanded library and produce a timestamped report from existing Results, usage and work-queue records. A unavailable source stays unavailable; an empty response is not treated as a zero count.

Each template has a version, locale, task category, input schema, capability requirements, permitted action IDs, result schema and review requirements. Track invocation separately from the conversation transcript. Pin the version for an in-progress task. Start with curated templates; workspace-admin customisation can follow after the execution contracts are stable. User-editable template text cannot expand tool permissions.

## 6. Discussion threads and shared context

Recommended starting topics are Project brief, Market research, Buyer shortlist, Company review and Follow-up preparation. Create threads on demand rather than adding empty topics to every project. Rename, pin, archive and search threads. Support **Continue in a new discussion** from a message or saved result, preserving a visible reference to the original.

A thread is fixed to one workspace/project. A company-specific thread also links to its buyer/company record. Changing project opens the relevant project's home; it does not silently repoint an existing thread. Cross-project comparison is a separate future capability.

Recommended visibility default: discussions are private to their creator; users can explicitly share a discussion with permitted project members. A private discussion can create an authorised shared project record through the normal save/review flow, with a clear **“Saved to project”** notice. Sharing the discussion never grants additional source-document or connector access. Hide inaccessible links and do not reveal private thread titles through shared result backlinks.

Shared project context consists of approved profile versions, confirmed product facts, selected document versions, saved buyer lists and explicit decisions. A new thread reads the current authorised project context but not every sibling transcript. Unconfirmed suggestions remain inside their thread until promoted through an explicit save/review action. A thread summary is a navigation aid, not an authoritative fact source.

Show **“Profile updated since this discussion started”** when context changes. Preview the change before a task restarts. Store the exact input versions used by a running operation; newer facts do not silently rewrite past results. Preserve source retention/deletion rules across messages, summaries, indexes and generated outputs.

## 7. Documents and useful outputs

Separate **source documents** from **generated outputs** in one project library. Retain originals, extraction status, source versions and approved/unapproved facts. Reuse the existing PPTX/PDF/text/Markdown ingestion path and the existing spreadsheet/company-import path. Chat attachments must not introduce a second uploader or silently broaden accepted formats.

Every factual result links to a source URL or document version and an available page/slide/row or excerpt. If extraction is incomplete, say so. If a page reference is unknown, label it unknown. Image-only presentations need a later explicitly scoped OCR capability or manual evidence; they do not become searchable facts merely because they were attached.

Generated outputs include research briefs, comparison tables, shortlist views, company evidence summaries, draft preparations and progress reports. An output stores references to canonical domain records plus its own revision when it contains authored text. Changes to buyers or drafts use the same services as the existing editor. Export keeps the current permission, policy and audit rules. Opening a saved result should not require finding its original chat message.

## 8. Connections and MCP

The product label should be **Connections** or **Data sources**. Administrators authorise a named connection and assign its permitted accounts/folders/projects. Buyers choose from the sources available to them; they do not need to know what MCP means.

MCP supplies a standard host/client/server connection and tool/context exchange. It does not choose BuyerOS's planning, context or approval behaviour; those remain application responsibilities. See the official [MCP architecture](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture).

Use two execution paths behind one capability registry:

- **BuyerOS actions:** typed adapters call the existing authenticated domain services for projects, documents, buyer review, runs, drafts and exports. Do not route internal operations through a new remote MCP server merely for consistency.
- **External sources:** selected, administrator-approved MCP servers or existing provider adapters. Add an MCP adapter where it brings a needed integration; retain a working direct API adapter where appropriate.

A connection card shows owner, authorised scope, allowed read/write actions, last successful check and status: Available, Not connected, Needs sign-in, Restricted, Unavailable or Disabled by policy. A connected account is not proof that the current user may invoke every tool. Scope and role checks happen on every call. Credential handling stays server-side; outbound tokens are audience-scoped, not passed through indiscriminately. Apply the official [MCP security guidance](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices) for consent, scope minimisation, token handling and network access.

Initial connector priorities are the **existing permitted research source**, an approved shared-document source, and later a read-only CRM source if needed. Provider selection, credentials, commercial terms and data handling remain deployment decisions; this proposal does not connect or purchase a service. Mailbox sending is outside this release. A document or tool response is untrusted input and cannot authorise a new action.

## 9. Execution and persistence

Add a small conversation layer alongside the existing application modules, rather than growing the workspace component further. Proposed modules: conversation home, thread view/list, template catalogue, context selector, output panel and server-side conversation orchestration. Reuse the current shell, session boundary, navigation, typed service clients, domain permissions, job queue, budgets and operation recovery.

The request flow is:

`User message → scoped context → structured plan → capability/permission/budget validation → existing action or approved connector → durable result → cited response and linked output`.

The model may suggest an action; it cannot construct trusted tenant authority, approve a profile, accept a buyer, remove a hold, grant access or bypass policy. The server derives actor/workspace/project scope from the authenticated membership. Validate all typed inputs and source references again at execution.

Keep conversation text streaming separate from job execution. Reuse existing durable jobs for operations that already have them. A new message must not create a second execution of an existing action merely because streaming failed. A proposed new persistence model adds threads, messages, template invocations, output links and action receipts; receipts reference existing jobs/intents/approvals rather than duplicating their state machines. Use the existing migration authority and tenant constraints.

Classify actions explicitly:

- Permitted reads execute within the selected scope; any metered call also observes current budget controls.
- Reversible internal changes show a precise proposed change and the normal Save/Apply action. The canonical readback confirms completion.
- Research/contact spend uses the existing quotation, reservation and approval rules. A conversational “yes” is not a substitute for exact reviewed scope and cost where the current workflow requires it.
- External publication, access expansion and sending retain explicit separate approval boundaries. Disabled actions stay disabled in chat as well as in the old UI.

Represent lifecycle states as Preparing / Needs input / Awaiting approval / Queued / Running / Completed / Partially completed / Failed / Cancel requested / Cancelled / Outcome unknown. Only the states relevant to a particular action are shown. On connection loss, resume from durable event position and original action identity. Retry presentation or perform readback first; do not repeat a side effect with uncertain acceptance. Cancellation reflects the backend's confirmed outcome and remaining liability.

If the model is unavailable, preserve the message, context and saved outputs and offer the relevant existing screen. If budgets or lead progress are unavailable, show a scoped explanation and supported recovery action. Do not fabricate progress, quietly switch to sample data or reset unavailable totals to zero.

## 10. Preservation map

| Current capability / route | Conversation addition | Preservation requirement |
|---|---|---|
| Overview `/app` | Conversation becomes the selected project home; compact next actions | Full overview remains at proposed `/app/overview`; old root links preserve project context and land on home |
| Offer `/app/discover/new`, `/app/discover/edit` | Guided brief and document-based candidate facts | Original wizard, project edits, originals, profile confirmation and history remain accessible |
| Buyers `/app/discover` | Inline shortlist / comparison preview | Full table, filters, search, pagination, import, lists, ownership, evidence, review and bulk actions remain |
| Buyer details and source checks | Company-specific discussions | Existing record IDs, sources, dates, review semantics and detail views remain authoritative |
| Research `/app/runs`, existing run-detail URLs | Linked progress cards and request preparation | Original runs, budgets, cancel/retry/reconciliation and deep links remain |
| Drafts `/app/outreach` | Preparation templates and discussion about edits | Preparation versus formal draft distinction, exact revisions, review/approval invalidation and exports remain |
| Results `/app/results` | Narrative progress report with evidence links | Existing outcomes, usage definitions, time windows, cost accounting and provenance remain |
| Settings `/app/settings` | Connections and available-capability explanations | Existing budgets, policy, roles, locale and suppression controls remain |
| Operations `/app/operations` | Next-action links and recoverable task states | Existing operational queue and manual ownership/due-date meaning remain; no accidental scheduling |
| Authentication / tenancy / demo boundary | Scoped context on every conversation | Same normal login, membership checks, tenant isolation and explicit demo separation |

Add `/app/chat/:threadId` and `/app/documents` only after checking the current route parser and deep-link handling. Preserve workspace/project query context and back/forward behaviour. Invalid IDs produce a real unavailable/not-found state. Do not fall back to another project's data.

## 11. Delivery sequence and acceptance

**Stage 0 — baseline and service health.** Reconcile the actual deployment/source target; record all existing screens and key workflows. Investigate the observed budget/progress failures as a separate reliability item. Establish the feature-preservation matrix and fixtures before changing navigation.

**Stage 1 — home, threads and existing-data guidance.** Add the new shell entry, six templates, durable threads, selected context and read-only summaries/deep links. Validate a first-project journey and a resume-existing-project journey. Gate actual model use behind an explicitly configured provider and cost policy. Deterministic template guidance remains available without a model.

**Stage 2 — durable outputs and reviewed internal actions.** Add linked research briefs, shortlist previews and draft preparations through existing services. Add output history, context-change warnings, canonical readback and exact action review. Retain existing full screens throughout.

**Stage 3 — approved connections.** Introduce one real connector at a time, initially with the smallest useful read scope. Verify permission revocation, expired sign-in, outages, source deletion, metered usage and rate limits before adding another.

**Stage 4 — controlled rollout.** Use a workspace feature flag. Turning it off restores the prior navigation while keeping saved discussions and outputs available for recovery. No destructive schema migration is needed to roll back the entry experience.

Required acceptance covers:

1. A first-time user reaches a reviewable brief from a template or their own question; a document-only start handles missing input and limited extraction honestly.
2. Every preservation-map capability has a reachable screen and its original permission/behaviour regression checks.
3. Different threads retain drafts, context and outputs across reload; cross-workspace/project access and stale-context writes fail safely.
4. A generated claim opens the actual source/version; unknown facts and unavailable systems remain visibly unknown.
5. An interrupted stream resumes without duplicate paid work or duplicate writes; concurrent tabs and repeated clicks preserve idempotency and version checks.
6. Private discussion content does not appear in another user's summaries/search/backlinks; explicit sharing still respects underlying source access and revocation.
7. Old approvals become stale when their material input changes; chat cannot approve or send on behalf of a human reviewer.
8. Source deletion/retention propagates to messages, summaries, retrieval indexes and outputs; disconnected sources are not reused from stale context.
9. English and Traditional Chinese, keyboard, mobile layout, zoom, back/forward and direct links are verified at the selected build.
10. Measure template-to-first-saved-output completion, abandonment, corrections, unresolved failures and time to a reviewable result. Establish a baseline before choosing numeric improvement targets.

## 12. Recommended defaults and remaining decisions

Recommended defaults for design review: private discussions with explicit project sharing; shared canonical project records retain current access rules; six curated templates; optional right panel; one connector at a time; existing provider and domain boundaries; no sending in this release. The attached visual concept uses illustrative content and does not represent completed research or connected services.

Before building, confirm this design, select the exact implementation branch, and choose the model/connector configuration and data-processing scope for any live AI stage. These are not prerequisites for reviewing the proposed interface. This session delivers design advice and a concept only; no product code, database schema, provider connection or deployed application was changed.

An independent builder review of this proposal returned **“nothing important left.”** This is a design-completeness review, not implementation validation, security certification or acceptance of the live application.

The illustrative concept was rendered in a desktop browser. Checked interactions: template to discussion, a guided answer updating the decision panel, output to the retained-workflow preview, return to discussion, local follow-up input, document library and connection availability. The preview also restored its selected view across reload. These are concept-only checks; mobile/device testing, backend integration, live model execution and regression acceptance are not claimed.
