# FIMMICK BuyerOS — frontend review handoff

Date: 14 September 2026. Working product name; not an approved brand identity.

## Working local functionality

- Five primary workspace sections, Settings, four-step search wizard, buyer full-page detail, search-run detail and list detail. `/` opens Find Buyers; no pretend login.
- Twenty-four canonical fictional companies, 14 Match / 6 Needs review / 4 Not a match. Two additional raw candidates explicitly map to existing companies. Buyer counts are distinct companies, not contacts.
- Company search, market/type/fit/review/contact/source/recency filters, sorting, pagination, session filter presets, current-page checkboxes and an explicit all-filtered selection action.
- Evidence drawer with Overview, Evidence, Contacts and Activity; in-app fictional source panels; unknowns and contrary evidence; full-page view.
- Accept/reject with reason, list creation/rename, duplicate-safe membership, removal without deleting company evidence, owner and notes, sample CSV export.
- Email draft editing, configurable objective/tone/language/value proposition, one optional follow-up, review, approval revision/actor/time, copy and download. Material edits invalidate approval. Approval also requires the exact sample recipient associated with the valid contact, buyer acceptance, no suppression, sender identity, opt-out wording and policy review.
- Settings: locale, default markets, illustrative discovery/contact limits, configurable sample per-company lookup price, suppression editor, integration-requirement dialogs, device-local save and reset.
- Canonical in-memory state survives route navigation. Locale is remembered. Explicit Save locally stores synthetic workflow status; custom notes, owners, offers, files and free-form draft text are excluded from that general save. A separate explicit draft-save dialog explains recipient/subject/body storage and only permits `.example` recipients. Restored drafts require review again. Reset clears only BuyerOS keys.

## Simulated workflows

- Deterministic search stages with partial results, cancellation, retry, unavailable provider, failed-stage and budget-cap states. Retry does not duplicate event charges. Custom offers/profile fields outside the fixture are an empty/limited demonstration, never relabelled as real research.
- Contact quotes have USD currency, identifiers, expiry, reserved amount and maximum cost. Only accepted, suitable, unsuppressed, policy-allowed, unresearched companies qualify. Confirmation rechecks eligibility and budget; repeated confirmation is idempotent. Sample results can be valid, catch-all or unavailable.
- Outcome stages are manually recorded fictional replies/meetings/opportunities/disqualifications. They do not originate from an inbox. Drafts never become Sent.
- Usage is derived from the synthetic cost ledger, reservations and distinct-company denominators. Zero denominators display an em dash. All prices are demo assumptions, not vendor quotations.

## Unconnected backend services

No live discovery, scraping, LLM, contact-data provider, payment, database, queue, authentication, mailbox, CRM, LinkedIn or WhatsApp is connected. No API keys or credentials are collected. No send/schedule action or mailto shortcut exists. The live adapter explicitly throws a structured `NOT_CONFIGURED` error; it never silently substitutes fixtures.

## Component / route inventory

| Area | Implementation | Routes |
|---|---|---|
| Persistent client shell and canonical store | `features/workspace.tsx`, mounted by `app/layout.tsx` | All workspace routes |
| Buyer review | `features/buyers/detail.tsx` | drawer, `/app/buyers/:buyerId` |
| Search wizard | `features/discovery/wizard.tsx` | `/app/discover/new` |
| Discovery | workspace + `services/run-engine.ts` | `/app/discover`, `/app/discover/:runId` |
| Overview | workspace | `/app` |
| Lists | workspace | `/app/lists`, `/app/lists/:listId` |
| Outreach | workspace | `/app/outreach` |
| Outcomes / usage | workspace | `/app/results` |
| Preferences / suppression | workspace | `/app/settings` |
| Accessible primitives | `components/ui/` and `features/ui.tsx` | Shared |
| Fixtures / domain contracts | `data/demo/fixtures.ts`, `services/contracts.ts` | Shared |
| Locale dictionaries | `locales/index.ts`, `locales/context.tsx` | English, zh-HK |

## State transitions and future integration

`services/contracts.ts` describes Workspace, Project, ICPVersion, SearchRun, Company, LeadAssessment, Evidence, ContactPoint, HumanReview, BuyerList, ListMembership, EnrichmentQuote/Job, OutreachDraft, Approval, Suppression, CostEvent and OutcomeEvent. The proposed `BuyerDiscoveryClient` interface includes project/profile writes, run start/get/cancel/retry/subscription, offset pagination, buyer reviews, contact quotes, draft saving/approval, usage and outcomes. This interface is a proposed boundary, not a claim that network endpoints exist. The UI currently implements one fixture project and calls local domain functions.

- Search: Running → Completed / Failed / Cancelled / Provider unavailable / Paused at budget cap. Failed/cancelled/unavailable may retry with the same run ID; costs use run-stage event IDs.
- Quote: Reserved → Confirmed / Cancelled. Expired reservations are excluded from available-budget calculations. Confirmation may cancel an invalid/expired quote without charging.
- Draft: Draft → In review → Approved. Edits create a new revision and invalidate approval. Restoring a locally saved draft resets it to Draft.
- Suppression is independent of contact validity, fit and human acceptance, and blocks paid lookup/approval.

Future engineering must enforce tenant identity, roles, policy, suppression, immutable assessments, budget reservation atomicity, idempotency, recipient validity and approval checks on the server. Browser checks are not security boundaries. Replace fixture storage via the typed adapter; do not add secrets or Python/LangGraph workers to the client.

## Validation executed

| Check | Result |
|---|---|
| TypeScript `tsc --noEmit` | Passed after implementation repairs |
| Supported Vinext production build | Passed |
| Domain regression checks | 11 passed; execute `node tests/domain-checks.mjs` |
| Fixture count / fit distribution | Passed: 24 canonical; 14 / 6 / 4 |
| Browser evidence drawer | Opened DeltaGrid dossier; fit, missing facts and contrary evidence visible |
| Browser acceptance and contact gate | Accepted DeltaGrid; quote showed 1 eligible, USD 0.30 reserved; confirmation produced a valid sample contact and USD 6.90 total spend |
| Browser draft review | Generated draft, entered sender, checked policy review, requested review, approved revision |
| Approval invalidation | Editing subject removed prior approval; sending remained disabled |
| Shared totals across routes | Overview showed 6 accepted buyers and 17 awaiting review after DeltaGrid acceptance |
| Wizard confirmation validation | Continue blocked without explicit buyer-profile confirmation; four steps reached |
| Custom / limited state | Limited demonstration rendered 0 results and USD 0.00 run spend with recovery guidance |
| Search cancellation / retry / failure / caps | Passed in domain tests, including retained partial results and no duplicate event charges |
| Company filter / selection / list action | Search for Ardenne returned one row; selected it and saved through the list dialog; the existing list remained at 3 companies, confirming no duplicate membership |
| CSV data generation | Escaping, newlines, formula-prefix neutralisation and `data_mode=demo` passed domain tests |
| Browser CSV download observation | Button invoked; the testing browser did not emit a download event in two observation attempts. Actual browser download capture remains unverified. Implementation creates a local Blob download rather than a success-only toast. |
| Responsive inspection | Harness rendered 390 / 768 / 1280 / 1440px frames; page-level scroll/client widths matched. Narrow tablet table was changed to cards. Final mobile screenshot inspected in Traditional Chinese. |
| Localisation | English/Traditional Chinese selection exercised; main navigation, filters, cards and status text switched |
| WebMCP | Read-only `list_demo_buyers` tool implemented with feature detection, input validation and cleanup. Browser tool discovery transport failed; execution not verified. |

Browser testing found and fixed an insecure-HTTP `crypto.randomUUID` issue using a synthetic-ID fallback, a first-load module fetch failure, and narrow-table crowding. Some browser action calls timed out; state was inspected before retry. No claim is made that every control, reload case, mobile interaction or 200% text-zoom path was exhaustively exercised.

## Known limitations

- A single coherent fixture project is fully demonstrated. Custom offers are session-only and intentionally receive no fabricated results. Real multi-project backend persistence and immutable per-run assessment history are future work.
- Search profile versions are tracked on runs; richer separate profile history and project APIs are typed proposals, not implemented backend services.
- English and zh-HK cover primary product copy. Fictional original evidence, authored excerpts, some advanced explanations/activity text and user-entered content remain in their source language; a full language audit is still appropriate before production use.
- PDF selection validates type/size but does not extract text. TXT/Markdown can be read locally and removed.
- No real authentication or server authorisation. All content is a UI demonstration.
- Evidence recency uses the fixed September 2026 sample dates, not a live current-date research feed.
- Browser download-event capture and WebMCP execution could not be verified in this environment.
- This environment has no user-facing local preview handoff. The Site is saved without deployment as requested; no production URL or access setting was changed.

## Runtime

Preserved Sites Vinext / React / TypeScript / Tailwind / Radix-backed shadcn starter, with the existing lockfile and managed-linux execution profile. No production database or external service was provisioned. `tests/responsive-harness.html` can be temporarily served from `public/` for local responsive QA; it is not included in the delivered public assets.
