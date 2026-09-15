# FIMMICK BuyerOS — ChatGPT Sites Frontend Master Instruction

Version: 1.0 · Proposed frontend specification
Working name: FIMMICK BuyerOS. This is a temporary label, not an approved product name.
Scope: An editable, interactive frontend MVP in demo mode. No live outreach, paid enrichment, production database, or public publication.

---

@Sites

Build the actual editable frontend described below. Do not stop at a design proposal, wireframe, homepage, screenshots, or implementation plan.

## 1. Product and scope

Create a premium B2B software workspace for FIMMICK that helps exporters and overseas business-development teams find suitable buyer companies, understand the evidence for each match, identify appropriate business contacts, and prepare outreach for human review.

Product line: **Find overseas buyers. Understand the fit. Approve the next step.**

The central journey is:

**Company/product → Target market → Buyer requirements → Discovery → Evidence review → Accept buyer → Optional contact lookup → Draft outreach → Human approval → Track outcomes.**

Design an account-first product: a company is a potential buyer; its people and contact points are related records. Finding three contacts at one company must not count as three buyer companies.

Translate the OpenOutreach-inspired fit explanation/cost-gate concept and AI_Find_Customer-inspired company research workflow into a coherent new frontend. These are capability references, not permission to copy arbitrary source code, branding, or dependency licenses. Do not claim either engine has been integrated in this frontend preview.

Make commercial fit, evidence quality, human acceptance, contact validity, and outreach permission separate concepts. A company matching an ideal buyer profile is not proof that it intends to purchase.

### Build boundaries

Build local interactions, editable forms, filtering, selection, evidence inspection, sample workflow state changes, sample CSV export, and responsive layouts. Simulate backend jobs explicitly.

Do not implement live web scraping, call lead-data/LLM providers, purchase contact data, send messages, connect mailboxes, create accounts in external services, collect API keys, provision a database, or deploy to Vercel. Do not claim research or sending occurred when it did not.

Keep the Site in its private editing/review experience. Do not publish, redeploy a production URL, or alter sharing/access settings. If an existing editing project is selected, confirm its identity and preserve its routes, approved assets, access settings, and newer work. With no existing target, create a distinct new review project; never modify an unrelated FIMMICK Site.

## 2. Frontend architecture

Inspect the actual Sites starter and preserve its supported framework and build configuration. Prefer React + TypeScript, Tailwind CSS, reusable shadcn/ui-style accessible components, and Lucide-style icons where available. Use the existing router. Add dependencies only when necessary and compatible; do not force a framework migration.

Keep React feature components portable for later engineering integration. Do not invent a Next.js server environment or place Python/LangGraph logic inside the browser. Future integration is through typed API adapters to the buyer-discovery backend. PostgreSQL/Neon, identity, queues, hosting, and Python workers remain outside this frontend task; they are not confirmed live services.

Organise by feature rather than one giant component:

```text
src/
  app/                     # Routing, app shell, providers
  components/ui/           # Buttons, dialogs, tables, forms, badges
  components/buyer/        # Buyer row, fit summary, evidence drawer
  features/
    overview/
    discovery/
    buyers/
    lists/
    outreach/
    results/
    settings/
  services/
    contracts.ts
    mock-client.ts
    http-client.ts         # Explicit not-configured stub, not pretend integration
  data/demo/
  lib/                     # Validation, selectors, currency, CSV, permissions
  locales/
  tests/
```

Adapt paths to the existing project without duplicating application roots. Use schema-validated inputs and structured error objects. Keep domain state, derived metrics, and UI state separate.

All screens must read from one canonical store through shared selectors/adapters. Never hard-code contradictory dashboard counts on separate pages.

## 3. Product layout and visual direction

This must feel like software a sales team can work in every day, not a marketing website, chatbot, CRM clone, or agency brochure.

Use a light, restrained interface: proposed background `#F7F8FB`, white surfaces, text `#111827`, borders `#E5E7EB`, and primary blue `#2563EB`. These are provisional product tokens, not a claim about an approved FIMMICK brand guide. Preserve approved branding if available; otherwise use a simple FIMMICK text wordmark and editable BuyerOS label.

Use a roughly 224px desktop sidebar, 64px top bar, 24px content gutters, 14–16px body text, 28–32px page headings, and restrained 10–14px radii. Use subtle shadows and compact tables. Show status through text/icons as well as colour. Avoid decorative gradients, robot imagery, floating blobs, oversized hero areas, country-flag emoji, and charts without a user decision attached.

The initial viewport should immediately show the active project, the next action, and buyer results. It must not require scrolling past promotional copy.

Keep explanations short in the main workspace: one sentence per lead, short field labels, and details on demand. Display evidence, technical traces, and advanced filters in drawers or expandable sections. No generic chat panel as the primary interface.

## 4. Navigation and routes

Use five main navigation items and a bottom Settings entry:

| Navigation | Route | Main purpose |
|---|---|---|
| Overview | `/app` | Projects, pending work, next actions |
| Find Buyers | `/app/discover` | Search runs and buyer results |
| Buyer Lists | `/app/lists` | Saved and accepted companies |
| Outreach | `/app/outreach` | Drafts, review, approval |
| Results | `/app/results` | Outcomes and usage |
| Settings | `/app/settings` | Demo preferences, policies, connection status |

Additional routes: `/app/discover/new`, `/app/discover/:runId`, `/app/buyers/:buyerId`, and `/app/lists/:listId`.

Open first-time previews on Find Buyers with a clearly labelled, completed sample run. Show both **New buyer search** and **Use sample project**. Do not put the demonstration behind a pretend login page.

Top bar: workspace label, project selector, language selector, and persistent **Demo mode · No live services connected** indicator. Keep controls purposeful; omit fake notification centres and non-functional global search.

In UI terminology, a **Project** holds the offer, markets, and buyer requirements; a **Search run** is one execution. The future backend may call a project a `campaign`. Do not confuse this with an email sequence.

## 5. Overview

Show three compact, derived cards: buyers awaiting review, accepted buyers needing contacts, and drafts awaiting approval. Each card opens the relevant filtered view.

Under them, show project cards containing offer, markets, last run status, accepted buyer count, and a contextual next action. Include **Create project / New buyer search** and **Continue last search**.

A small activity list can show sample approvals, lookups, and draft edits. Mark it as demo activity. Avoid invented revenue, ROI, conversion lift, customer logos, or commercial success claims.

## 6. Four-step buyer-search wizard

Use a focused main form with a compact sticky summary panel on desktop and a summary accordion on mobile. Save synthetic demo progress across navigation. Always provide Back and edit controls.

### Step 1 — Your offer

Collect company name, product/service, short value proposition, and optional website. Support **Load sample offer**.

Advanced fields: product categories, minimum order, price band/currency, supply capacity, available certifications, and preferred commercial relationship. Do not invent these from the company name.

Offer local file selection for PDF, text, or Markdown with file size/type validation and removal. Text/Markdown may be read locally when actually implemented. PDF selection must say **Selected locally; document extraction is not connected** unless real parsing is implemented and tested. Never show fabricated extraction results.

For a user-entered URL, do not pretend to visit or analyse it. Explain that live website analysis is not connected; allow manual editing or the explicit sample offer.

### Step 2 — Target buyers

Collect countries/regions and buyer types: distributor, importer, wholesaler, retailer, system integrator, or end-user business. Include language preferences and optional company size/buyer roles.

Keep exclusions visible: competitors, existing customers, wrong markets, and do-not-contact companies. Use local-language query previews, but label template-generated previews correctly rather than implying a model ran.

### Step 3 — Buyer requirements

Show three editable groups: **Must have**, **Nice to have**, and **Exclude**. Include desired buyer roles and supporting signals. Explain “ideal buyer profile” in plain language rather than requiring users to know ICP terminology.

Distinguish user-provided facts, sample suggestions, and unknown information. Require explicit confirmation of this profile before running discovery. Editing the profile creates a new version and must not silently rewrite old lead assessments.

### Step 4 — Search plan and budget

Show target buyer count, selected markets/languages, source categories, maximum discovery budget, and a separate optional contact-lookup budget. Use USD for the sample; every amount must carry its currency. Sample prices are configurable demo assumptions, not current provider quotes.

Default to **Find and assess companies first**. Leave automatic paid contact lookup off. Explain that contacts are researched only after appropriate review and confirmation.

Primary action: **Run demo search**. Secondary: **Save demo draft**. No credit card or provider credentials required.

When custom inputs fall outside the fixture dataset, show an honest empty/limited demonstration state. Do not relabel unrelated sample companies as researched results for an arbitrary user input.

## 7. Search progress and results

Run a deterministic, clearly labelled demo sequence:

**Prepare profile → Generate queries → Discover companies → Remove duplicates → Assess evidence → Results ready.**

Do not animate fictional live research logs. Show elapsed demo time, stage, candidate count, unique-company count, fit distribution, and illustrative spend. Support cancellation, failed-stage retry, partial results, a provider-unavailable scenario, and budget-cap pauses.

Cancelled runs retain results already created. Retry must not duplicate records or simulated charges. Stop at the budget cap; do not pretend every target is achievable. A completed run may find fewer suitable companies than requested.

### Results workspace

Use one concise run summary, an actionable filter bar, and a table. Filters: market, buyer type, fit verdict, human review status, contact status, source type, and evidence recency. Implement sorting, search by company, page size, pagination, and saved filter presets.

Table columns: selection, company/market, buyer type, **Why it fits** with fit badge and evidence count, contact status, review status, and row action. Keep optional detail columns behind a view control.

Show fit as **Match / Needs review / Not a match**, not an unexplained 94/100 score or a purchase-probability claim. Keep human acceptance separate.

Selecting rows opens a bulk action bar for save to list, accept, reject with reason, request sample contact lookup, and export sample CSV. Show eligible/blocked counts before gated actions. Clearly distinguish selecting the current page from all filtered results. Never silently act on hidden rows.

Clicking a company opens a 440–520px detail drawer on wide screens. Offer a full-page view. Use a full-screen sheet or route on mobile.

## 8. Buyer detail and evidence

The buyer detail is the primary differentiator. Show company identity, market, buyer type, fit verdict, human review, contact readiness, and a contextual next action.

Use four tabs: **Overview, Evidence, Contacts, Activity**.

Overview: one short fit explanation, matched requirements, contrary evidence, missing information, and a suggested next step. Acknowledge unknowns such as purchasing authority, order volume, or certification requirements instead of inventing answers.

Evidence: connect every important claim to an evidence record with source title/type, URL or sample source identifier, excerpt, original language, optional labelled translation, observation time, and the requirement it supports or contradicts. Label direct observations versus AI/sample inferences. Do not show hidden chain-of-thought or model scratchpads.

Seeded evidence is fictional. Its source action must open the in-app sample source panel, not an invented live webpage. Only a genuine, validated live source may later open externally. Do not use another real company’s logo or website to make invented findings look verified.

Contacts: show business role, fictional identity where present, contact source, last-check metadata, and status. Separate **not researched**, **public address/unverified**, **provider-marked valid**, **catch-all**, **unavailable**, and **suppressed**. In the prototype, every such result is marked sample. Email validity is not outreach permission.

Activity: show sample changes with actor, time, previous/new state, and rationale. Human feedback must change the current record and the relevant counts; it must not claim to retrain a model.

## 9. Contact lookup and budget gates

Label the action **Find business contacts**, not “unlock email” when no address has actually been found.

Open a confirmation dialog showing selected companies, eligible companies, skipped companies and reasons, selected roles, estimated price/cap, and remaining illustrative budget. Default to work email; phone lookup is off and out of scope.

A demo lookup requires an accepted, suitable buyer, no suppression, an allowed lookup-policy state, and a valid budget reservation. Unknown policy conditions block the simulated paid action with an explanation. Do not conflate data-lookup permission with outreach permission.

Use simulated quotes with an identifier, expiry, currency, and maximum cost. Repeated confirmation/retry must be idempotent. Account for spent and reserved amounts. Clear unused reservations on cancellation. Show found, not found, and uncertain results honestly; do not always return a successful contact.

All currency here is **illustrative demo spend — no charge**. Never hard-code vendor pricing as verified current pricing or claim percentage savings without measured evidence.

## 10. Buyer Lists

Provide functional list creation/rename, add/remove buyers, bulk selection, list search/filtering, and sample CSV export. A company saved twice to the same list remains one membership. Removing list membership must not delete the company or its evidence.

Each row has an owner, optional note, next action, and separate fit/review/contact states. Notes and list changes update shared state.

CSV export must generate an actual local download of selected synthetic records, not a success toast alone. Include company, market, fit rationale, evidence reference, review status, and contact status. Mark rows `data_mode=demo`; use a `DEMO_` filename. Quote/escape CSV fields and neutralise spreadsheet-formula prefixes. Never export real customer data in this build.

## 11. Outreach drafting and approval

Build an email preparation/review workspace, not a bulk-sending machine.

Use a three-pane desktop layout: recipient queue, editable subject/body, and evidence/review context. Convert to tabs on mobile.

Support a single initial email per buyer and an optional follow-up draft. Inputs: objective, recipient language, tone, and approved value proposition. Template-generated sample text must be labelled as such. The evidence panel explains which facts were used; do not insert invented certifications, relationships, buying intent, savings, or personal details.

Actions: **Generate sample draft, Edit, Save, Request review, Approve draft, Copy draft, Download sample draft**. Draft edits must persist locally for synthetic records.

Approval stores a draft revision/hash, approver, and timestamp. Changing the recipient, subject/body, referenced evidence, material buyer profile, or policy decision invalidates prior approval and requires review again.

Show separate review items for buyer acceptance, contact status, sender identity, opt-out wording, suppression, jurisdiction/policy review, and human approval. A completed visual checklist does not mean legal compliance. Use wording such as **Policy review required**, not “GDPR compliant.”

Keep real sending and scheduling disabled with an adjacent explanation: **Delivery is not connected in this prototype**. No SMTP, Gmail, Outlook, LinkedIn, WhatsApp, or mailto-based delivery shortcut. An approved/copied/exported draft must never become “Sent.”

## 12. Results and usage

Use tabs for **Outcomes** and **Usage**, not separate oversized analytics modules.

Outcomes: a small buyer pipeline and table, with keyboard-accessible stage menus. Permit explicitly labelled **Record demo outcome** actions for reply, meeting, opportunity, and disqualification. Do not pretend an inbox was synchronised. Any historical sample sending/reply records must remain visibly fictional and separate from new unsent drafts.

Usage: illustrate discovery, extraction, assessment, and contact-lookup cost categories. Show spent, reserved, and remaining budget. Include cost per accepted buyer and cost per accepted buyer with at least one provider-marked-valid sample business contact. Explain the denominator and count distinct companies, not contact rows. Use “—” for zero denominators.

All figures derive from the same demo event ledger, current filters, and selected project. Separate estimates from final simulated charges. Do not invent conversion benchmarks, customer ROI, or guaranteed competitive advantage.

## 13. Settings, privacy, and demo roles

Provide working preferences for language, default markets, illustrative budget limits, and resetting demo data. Add a sample suppression-list editor with confirmation and visible effects on lookup/outreach eligibility.

Show integration cards for research, contact enrichment, mailbox, and CRM with status **Not connected** and a **View requirements** information panel. No fake connection success, credential fields, OAuth flows, or live connection claims.

Optional demo-role selector: Operator, Reviewer, Viewer. Label it a UI simulation, not real authentication or security. A viewer cannot mutate demo records. Browser permission checks are not production authorisation; document future server-side tenant and role enforcement.

Use versioned browser storage only for synthetic fixtures, their edits, and UI preferences. Keep user-entered proprietary content and selected files in memory by default. Any explicit “Save locally” action must explain what stays on this device and offer deletion. Never store secrets, real contact datasets, access tokens, or uploaded files in browser storage. A Reset demo action must clear the prototype’s own keys, not unrelated storage.

## 14. Demo dataset and localisation

Seed a coherent fictional project:

Seller: **HarbourSense Instruments**, an illustrative industrial-sensor supplier.
Markets: Germany, Netherlands, Belgium.
Buyer types: distributors and system integrators.

Create 24 canonical fictional companies: 14 Match, 6 Needs review, 4 Not a match. Include two additional duplicate raw candidates that merge into existing companies: 26 raw candidates, 24 unique companies. Human acceptance and contact states should be mixed and derived from records, not assumed from fit.

Prepare three especially complete dossiers: **Rheinwerk Controls GmbH**, **DeltaGrid Automation BV**, and **Ardenne Systems SRL**. They are fictional examples. Include missing facts, a rejected competitor, an uncertain contact, a suppressed buyer, a partial-failure run, and an exhausted-budget scenario.

Use synthetic names, reserved `.example` domains, and non-deliverable sample email addresses. Do not generate mailto links. Use monogram avatars rather than stolen or invented real-company logos. All source excerpts, timestamps, verification results, outcomes, and costs are sample data, never real research.

Support English and Traditional Chinese (`zh-HK`) using translation dictionaries. Default to English for this overseas B2B prototype and remember the selected locale. Translate navigation, forms, validation, statuses, tooltips, and empty/error states. Keep original source language separate from optional translated evidence. Do not mix Chinese variants.

## 15. State and future API contracts

At minimum model: Workspace, Project/Campaign, ICPVersion, SearchRun, Company, LeadAssessment, Evidence, ContactPoint, HumanReview, BuyerList, ListMembership, EnrichmentQuote, EnrichmentJob, OutreachDraft, Approval, Suppression, CostEvent, and OutcomeEvent.

Use stable IDs, project/workspace scoping, ISO timestamps, explicit currency, and `dataMode: demo | live`. The frontend build contains demo records only. Keep human review, fit verdict, contact status, policy status, and delivery state independent.

Expose typed adapter methods for create/update project, save ICP version, start/get/cancel/retry run, subscribe to run events, list/get buyers, review buyers, quote/confirm lookup, save/approve draft, get usage, and record demo outcome. These are proposed frontend contracts, not assertions that backend endpoints exist.

Use cursor/offset pagination consistently, include request IDs and structured errors, and model job events with a sequence/event ID to prevent duplicate application. Future streaming may use SSE through the adapter; the demo uses deterministic local events.

Default to the mock client. The live adapter must fail explicitly until configured and implemented. Never silently swap live errors for sample data. No provider credentials or database connections in client code. The future backend must enforce tenant scope, authorisation, suppression, budget reservations, and approvals independently of the browser.

## 16. Responsive behaviour and accessibility

Test at 1440px, 1280px, 768px, and 390px. Collapse the sidebar on smaller screens; convert company rows to readable cards on mobile. Make filters a sheet and the buyer panel full-screen. Prevent page-level horizontal overflow and overlapping sticky controls.

Provide keyboard navigation, visible focus, dialog focus trapping/return, Escape dismissal, labelled inputs, inline errors, accessible status announcements, and reduced-motion behaviour. Charts must have textual equivalents. Do not convey verdicts through colour alone. Use sufficiently large touch targets.

Show loading, empty, limited-results, unavailable, failed, retrying, cancelled, budget-blocked, and successful states. Use recovery actions instead of indefinite spinners or false success messages.

## 17. Build order and acceptance tests

Build in this order without pausing for approval after every page: app shell/design tokens/fixtures; discovery table and buyer evidence drawer; search wizard and job simulation; lists and cost-gated contacts; draft/review workspace; overview/results/settings; responsive QA and handoff.

Prioritise the complete buyer-search → evidence → accept → contact quote → reviewed draft path over decorative dashboards or extra features.

The demonstration must pass these tests:

1. A visitor understands the product and can open a buyer’s fit evidence within 30 seconds.
2. Search/filter/sort/pagination and explicit bulk-selection scope work; counts match the visible records.
3. Opening, accepting, rejecting, or saving a buyer updates all relevant views without duplicate buyers.
4. Each important fit claim opens its sample evidence; contradictory and missing evidence remain visible.
5. Wizard validation, back navigation, explicit profile approval, and custom-input limitations behave honestly.
6. Cancelling/retrying a simulated run preserves partial results without double-counting companies or costs.
7. Lookup rejects suppressed, unaccepted, policy-blocked, or over-budget records; repeated confirmation cannot double-charge.
8. Draft editing invalidates approval; approval/copy/export never creates a sent state.
9. Sample CSV export downloads correctly; no real service is contacted and no secrets are requested.
10. English/Traditional Chinese, mobile layouts, keyboard operation, empty/error states, reload, and reset work.
11. No broken internal routes, dead primary buttons, console exceptions, inaccessible core dialogs, or fabricated integration statuses remain.
12. Outcome and usage metrics reconcile with their underlying synthetic events and clearly distinguish estimates from simulated actuals.

## 18. Deliverables and completion report

Deliver the editable frontend and a private preview when the environment supports it. Do not publish or change sharing settings. Preserve the existing runtime and site identity where applicable.

Include a small developer handoff document covering component/route inventory, mock data, state transitions, proposed API contracts, environment assumptions, and future integration points. Include test results, including failures and anything that could not be checked; never report tests as passed unless executed.

Report four separate categories: **Working local functionality; Simulated workflows; Unconnected backend services; Known limitations**. Do not describe this frontend as a production-ready lead engine or a live outreach platform.

Build the workspace now, with the discovery results and evidence review experience as the visual and functional centre of the MVP.
