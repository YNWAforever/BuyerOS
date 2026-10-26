# Workspace route and screen-state inventory

Read-only source inventory for the existing workspace at `b09fe39`, before CSS alignment. No application source, behavior, routes, data, labels, selectors, or translations were changed. This is source evidence, not a claim that these states have been browser-verified.

## Route ownership and modes

`features/app-workspace.tsx` → `features/workspace.tsx`: `mode === 'live'` renders `LiveWorkspace` from `features/live/workspace-picker.tsx`; otherwise `DemoWorkspace` renders `features/workspace/*`, `features/discovery/wizard.tsx`, and `features/buyers/detail.tsx`. The old `mode==='live'` branch inside `DemoWorkspace` is unreachable through this entrypoint and must not be mistaken for active live routing. The `/app` wrapper returns null for `/auth/callback`; auth pages have their own content in the shared product layout (see auth inventory below).

Every row below needs both `en` and `zh-HK` coverage. Existing translation fallbacks and English-only strings remain existing behavior; CSS alignment does not authorize fixing or replacing them.

| Route pattern | Active live content | Demo content / distinctions |
|---|---|---|
| `/app` | `LeadProgressPanel(mode=overview)`, `PilotBudgetPanel(summary)`, `LiveWorkQueue`, `LiveUsage`, `LiveProfilePanel`, admin `LiveProjectManager` | `DemoOverviewView`: review/contact/draft metric links, fictional project and activity |
| `/app/discover` | `LiveBuyers` alias of `LiveBuyerResults`, nested buyer drawer and maintenance panels | `DemoDiscoveryRunView` + `DemoBuyerTable`, nested sheets/dialogs |
| `/app/discover/new` | `LiveOfferWizard(mode=create)` for authorized creators | Four-step `Wizard` |
| `/app/discover/edit` | `LiveOfferWizard(mode=edit)` for authorized editors with known active project | Falls through to discovery/run/table surface; demo `isWizard` recognizes only `/new` |
| `/app/runs` | `LiveRunProgress` index/start surface | Falls through to discovery/run/table surface |
| `/app/discover/:runId` | `LiveRunProgress(runId)`; excludes reserved `new` and `edit` | `DemoDiscoveryRunView` + table; missing ID falls back to first stored run |
| `/app/lists` | `LiveUnavailable(unavailable)` | `DemoListsView` + current-list buyer table |
| `/app/lists/:listId` | `LiveUnavailable(unavailable)` | Same, selected list; unknown ID yields no members |
| `/app/buyers/:buyerId` | `LiveUnavailable(unavailable)` | `DemoFullBuyerView` → `BuyerDetail`; missing buyer has return action |
| `/app/outreach` | `LeadPreparationsPanel` + `LiveDraftEditor` | `DemoOutreachView` |
| `/app/results` | `LiveResults` → `LiveBuyerResults` + `LiveUsage` + `LiveOutcomes` | `DemoResultsView`: Outcomes / Usage tabs |
| `/app/settings` | Project `PilotBudgetPanel`, `LiveSettings`, `LivePolicySettings` → `PolicyActivationPanel` | `DemoSettingsView` |
| `/app/operations` | Project `LeadProgressPanel(mode=queue)`, `LiveOperations` job operations; `?acceptance=unknown` selects separate provider-receipts view | Falls through to discovery/run/table surface |

Live lists and dossiers exist within the Buyers/Results page, not as dedicated list/detail routes. Do not introduce navigation to live `/app/lists` or `/app/buyers/:id` as part of styling.

## Shared live frame, authentication, scope and permissions

Sources: `features/live/workspace-picker.tsx`, `shell.tsx`, `navigation.tsx`, `auth-locale.tsx`, `unavailable.tsx`.

- Initializing sign-in; configuration error/unavailable; signed-out Sign in; auth error; session-expiry preparation-cleared alert; signed-in frame; pending navigation `Opening page…` with reload-requested-page link. Language selector exists on sign-in and workspace surfaces.
- `LiveFrame`: branded side navigation, workspace/project identity footer, breadcrumb/title/description, live indicator, language picker and Sign out. Navigation order is explicitly a tested contract: Overview, Offer, Buyers, Results, Research runs, Drafts, Settings, Operations.
- Workspace selection: loading; request error + retry; no memberships + invited-account guidance; ready options + no selection; check-access pending/status/timestamp/error; copy-diagnostics copying/success/failure, with read-only diagnostic textarea on copy failure.
- Project selection: loading; error/retry; no projects; ready options/no selection; New project / Edit offer conditionally present. Selection and locale errors render separate alert panels.
- Shared scope must remain visible even when page content is gated. Project-dependent content requires `authorized && projectKnown`; settings and operations can render with workspace alone. Offer create/edit requires corresponding role; edit additionally requires active project.
- Role flags are not interchangeable: creation/assignment, offer editing, buyer editing, approval, quote, import, archive/admin, and active-project restrictions are passed separately to children. Preserve conditional absence vs disabled controls and each component's current role handling, including places without an active-project flag.
- Archived project: edit/approval/start/draft preparation gates disable or omit applicable actions; admin ProjectManager displays status but archive form only for active project. Archive success clears selected project and reloads project list.
- `LiveUnavailable` has existing `unavailable`, `not_configured`, `denied`, `transient`, `not_found` status copy and optional reason; these strings currently render directly in English.

## `/app`: live overview states

Sources: `lead-workflow/progress-panel.tsx`, `lead-workflow/budget-panel.tsx`, `overview.tsx`, `results.tsx`, `profile.tsx`, `project-manager.tsx`.

- Lead progress: loading/error/ready, refresh; five linked distinct-company targets: Company evidence 24, Priority companies 8, Purchasing people 6, Direct channels 4, Reviewed preparations 4; as-of time, fixture exclusion note.
- Daily work queue (`LiveWorkQueue`): project required/loading/error/ready; per-kind count, available/unavailable reason and navigation; technical Project disclosure. Do not substitute fixture metrics.
- Usage: UTC date-range fields and Apply period / Refresh usage; invalid increasing range; loading/error/ready; as-of, settled metered cost, active holds, remaining approved budget, accepted/contactable counts, two blended costs (em dash for zero denominator); Technical details and Cost categories disclosures.
- Profile: loading/error; no saved profile; historical version buttons with pressed/current-approved state; missing requested profile 404; facts with provenance/source document/excerpt; requirements/markets/languages/buyer types/roles; changes vs previous/no previous/no change; stale offer basis warning; exact-version confirmation and Approve profile only when eligible; approving/error/Reload profile recovery.
- Project management (admin): project loading/error, active/archived status; archive reason, reason-length disabled state, archiving/error/success.
- Pilot summary: loading/error/no saved policy/ready; disabled-pilot activation and configuration mismatch; known or unknown remaining/settled/external cost; holds and carried holds; UTC period + Hong Kong display; reconciliation, >=80% warning, over-limit warning, blocker list; provider credit units separate from USD; refresh and original-operation recovery.

## Offer create/edit states

Sources: `offer-wizard.tsx`, `offer-documents.tsx`.

- Four live steps: Your offer → Target buyers → Buyer requirements → Review and save. Back and reached-step navigation; future steps and busy steps disabled. Missing edit project, loading edit, field-validation alert, busy save, partial project-save/profile-save status, dirty state and native leave confirmation exist.
- Your offer: company, product/service, value proposition, optional website. Create explains save-first attachments. Edit embeds offer document manager.
- Target buyers: markets/languages, six buyer-type checkboxes, desired roles. Requirements: must/nice/exclude textareas, one-per-line/semicolon helper, profile confirmation checkbox. Final summary preserves multiline values and long-token wrapping; save starts no research/provider call.
- Documents: file chooser; upload/refresh buttons; loading; paused upload requiring same-file reselection; hashing/uploading/completing percentage + progress; errors; per-file status/failure code/deleted state. Ready documents expose Use in profile, candidate facts and Apply candidate, Download original; PPTX ready metadata exposes slide-text viewer. Delete for nondeleted rows.
- Slide source: text/no editable text, paginated Load more slides, Close slide text. Image-only presentations display original-file/no-extracted-facts warning. Source facts still require reviewer approval.

## Research index/detail and candidate-review states

Sources: `run-progress.tsx`, `research-candidates.tsx`.

- No project; index loading/error + Retry loading/empty/ready runs and pagination (10); target/max-cost inputs and start pending. No current approved profile disables start with guidance. Provider capability loading/not-ready/error and refresh remain visible.
- Unknown start outcome: retained intent guidance, frozen target/cost, Retry same research; Start new research intent native confirmation. Preserve same-intent recovery semantics and appearance.
- Detail loading/error/ready; All runs return. Status/stage, actual/target yield, raw/assessed counts, spent/hold/max; Technical details hides attempt/event/connection; next-step copy by status.
- Distinct statuses include queued, running, awaiting_reconciliation, cancel_requested, partial, paused_budget, failed, completed. Reconciliation-pending holds, stopped-new-work note, completed-below-target note, failure code, safe-discovery-retry warning.
- Stop new work for applicable states requires reason; Retry safe work only for retryable partial/paused-budget/failed fit stages; Review committed buyers always in detail. Native status announcement is concise; detail article is not a blanket live region.
- Candidate observations: loading/error/retry/empty/paginated observations; metadata is not verified evidence; technical observation-ID disclosure. Reviewer opens Entity source review in-page.
- Entity review: existing-company selection/load, outside-project company UUID disclosure, selected material loading/error, exact page quote, review reason, source context/confirmation; already-existing review guidance; locked unknown save with same-key retry, expired source with retained key, accepted saved result. Entity review does not imply fit/buyer-role evidence.

## Buyers and Results shared buyer surface

Sources: `buyer-results.tsx`, `buyer-import.tsx`, `buyer-management-controls.tsx`, `bulk-actions.tsx`, `bulk-manifest.tsx`, `export-dialog.tsx`.

- Snapshot loading/loaded total/clipped-first-1000; buyer loading/error including expired snapshot; empty results; rows with unknown domain/market/rationale/freshness, fit/review pills, notes, Details. Results additionally has Log outcome per buyer.
- Filters: search + Enter/Apply filters; fit match/needs_review/not_a_match; review awaiting_review/accepted/rejected/needs_information; queue all/unassigned/unknown; name/best-fit sort; Refresh results. Existing query/list/preset/snapshot selection behavior remains authoritative.
- Selection states: none; selected page; explicit across pages; all filtered with exclusions; clipped snapshot disables select-all; clear. Sticky named Selected buyer actions summary appears only with selection, links to `#selected-buyer-tools`. Per-row checkboxes, details trigger dataset and focus restoration must survive.
- Pagination previous/next, counts, 8/12/24 rows. Human review tools require selection/permission; status/reason/apply, reviewing busy, updated/blocked/conflict result and per-row reason codes.
- Import disclosure: collapsed/expanded; CSV/XLSX file + preview, busy/recovering; row preview table (keyboard-focusable horizontal scroll region); ready/duplicate/invalid counts and row errors; invalid rows block confirmation; confirmation checkbox; confirm/check status/choose another file; unknown response freezes confirmation and exposes Retry same import; completed counts and Import another file. Import recovery without preview exposes Check import status.
- Lists/saved filters remain in-page: loading requests/errors/status; choose list with membership count; create/rename/add/remove selected actions gated by manage permission; Show list buyers / Show all buyers; choose/apply preset; name/save current filter.
- Owner assignment panel: absent without permission or selection (may retain result summary); selected-scope preview, Technical details; colleague search/pagination/loading/error/reload; owner/no owner/me/retained unseen owner; assignment reason; preview confirmation + submit. Unknown result locks fields and preserves Retry same assignment; success and failures retain summary/details.
- Segmented maintenance: operation assign owners/review buyers/change list memberships based on permissions; colleague/list paging/search; review status; list add/remove; maintenance reason and excluded-ID textarea. Preview freezes up to 10000 IDs/versions. Unknown-preview retry retains request/key; frozen manifest status/count/digest/expiry/operation/target/reason/filters; Technical details JSON; expired preview requires new preview; exact-digest checkbox, execute; unknown execution offers same confirmation/recheck; synchronous result or async job.
- Bulk job panel: loading/error/status with processed/updated/unchanged/blocked/conflict/cancelled counts; refresh/close; cancel pending rows while queued/running; failure-ID/reasons download; retry failed only with current versions or preview failed manifest rows; show/hide results and 20-row result pagination; retry result summary.
- Authorized export is an inline region despite its `ExportDialog` name: company-only vs eligible-contact CSV, selection count; prepare/busy/error/status; export job allowed/excluded counts and reasons, expiry; only ready job exposes release/download. Draft mode has text/clipboard choice and approved-copy preparation.

## Buyer modal dossier and nested lead/contact states

Sources: `buyer-detail.tsx`, `buyer-import-source.tsx`, `contact-quote.tsx`, `lead-workflow/evidence-panel.tsx`, `case-panel.tsx`, `operation.tsx`.

- Live dossier is custom backdrop + `role=dialog aria-modal=true`, title focus, previous/next/close, Escape and focus return. Four tabs Overview / Evidence / Contacts / Activity; loading dossier/error; navigation is blocked while a source check is unresolved.
- Overview: identity/domain/fit/stale evidence/rationale, review/owner/evidence counts; Prepare grounded draft only accepted + current match + editing permission; imported-source metadata with Original spreadsheet fields disclosure; notes save/save-and-next/busy/error; assign-to-me/clear owner; individual status/reason and save-review-and-next.
- Evidence: manual lead evidence + research evidence with supporting/refuting relationship, original/translated excerpt, requirement linkage, availability/kind, permitted source URL, retrieved/observed/retention/language/hash. Empty evidence and unavailable source links are distinct.
- Public source checks: loading/error/empty/records with A/B/C grade, date/rationale/limitations/source links/recorder; date/grade/rationale/limitations form; 1–10 title/URL source rows with add/remove; validation and saving; pending save locks form and navigation, exposes Retry same source check; saved status. Existing numbered source input aria-labels remain as written.
- Manual lead evidence: loading/error/empty/list; redacted/unavailable evidence; employment/procurement/channel-ownership claim, person/new person/department or referral choice, new name/role, channel type email/phone/form/referral, observed Hong Kong datetime, source stance supports/refutes/uncertain, title/URL/excerpt/publication date/type/rationale/limitations and save; operation recovery.
- Contacts: contact research status; `LeadCasePanel`; optional quote. Eligible retained-recipient guidance; validity and sending permission remain separate.
- Lead case: loading/error/quality blockers/current vs pending purchasing role and channel ownership; review deadline (30-day employment/procurement, 7-day ownership); priority/reason/next-action/due reminder form; person/channel selection; three judgements uncertain/accepted/rejected; cite all current observations, rationale/conflict resolution/confirmation; save work/save purchasing review; load historical review pages, redacted old sources.
- Quote: operator-required status or requested role + View contact quote; busy/error; quote status/ID/max/expiry/eligible/blocked reasons; refresh; unused cancellation reason/button; confirm only eligible quoted quote. Contact job displays status/reconciliation/held/settled/completed/found/unknown; queued/reserved explanation; unknown-provider hold warning; refresh/cancel with reason. Terminal statuses suppress cancel controls.
- Activity tab: human review status/reason/time.
- Shared LeadRecovery: checking original operations; refresh original operations; pending original read/continue (prepared and unredacted only)/cancel; busy/error/message. Unknown outcomes lock ordinary edits until original operation is reconciled.

## Outreach preparations, editor and exact approval

Sources: `lead-workflow/preparations-panel.tsx`, `company-picker.tsx`, `drafts.tsx`, `draft-dirty-guard.tsx`, `draft-grounding-review.tsx`, `delivery-history.tsx`, `export-dialog.tsx`.

- Lead preparations precede formal drafts; sending-disabled, tab-only text/session-expiry and separate-content-review notices. Company search/loading/error/retry/selected-company-unavailable, selector and paging.
- Preparation: sources loading/error; incomplete product extraction caveat; missing approved product facts; create cited preparation; saved preparation selector/pagination; state/revision/hash/context/blockers/review attribution/reasons; redacted/expired sources; purchasing review selector; subject/body/language/fact checkboxes, cited product facts with attachment links/page/excerpts/source links; save revision; content-review reason/confirmation/mark reviewed/request review/archive; archived form readonly/disabled and actions removed; history load/historical revision content; refresh/recovery.
- Unsaved preparation/draft transitions show native modal `DraftDirtyDialog`: Save / Discard / Cancel, disabled Save when unauthorized/blocked, cancel initial focus, Escape stays, focus restoration. Preparation recovery may add leaving-does-not-cancel-original-operation notice.
- Draft workspace loading/error/status; reviewed sender summary or missing sender; Sender details disclosure opens when missing, reviewer-editable identity fields + confirmation/reason/save.
- Generation context: initial/follow-up, free-template language caveat; missing current approved profile/accepted buyer alert; approved fact and eligible evidence checkboxes; retained recipient selector or unaddressed; internal work objective and template language en/zh-HK; generation eligibility/busy; draft job status/refresh.
- Draft list: loading/error/empty/ready, pending approval filter notice, refresh/open/pagination (8). Open draft revision/status/language; workflow ordered list; subject/body/language, Save revision, Prepare follow-up. Dirty/baseline data attributes retained.
- Conflict comparison retains local unsaved content/copy alongside latest persisted content. Claims/source references; human-edited/no claims triggers Manual source review. Stale context diff alert; refresh; addressed draft with claims may Request exact review; review-requested draft shows exact confirmation and Approve exact revision. Approval requires exact persisted revision with no unsaved edits.
- Manual source review: dirty/read-only reviewer guidance; loading/error/reload; source cards/link fallback/observed/retrieved/excerpt and Source details; Revision details; each exact subject/body segment has preformatted text and read-only selectable textarea; keyboard Shift+Arrow/caret selection and Use selected text split; factual/non-factual classification/reason; factual evidence and offer-fact checkbox citations; Advanced segment offsets with code-point position/split; overall reason and whole-message/source confirmation; Submit source review validation. Dense 2–200 segments are supported.
- Exact review panel includes recipient/sender/evidence/policy/context/content hashes; missing eligible addressed/current-policy explanation; current/stale/review_requested/approved states, save or approval errors and notices.
- Native delivery history: loading/error/empty/records, pagination/refresh, record detail disclosure. It displays existing native records, not a new send flow. Approved draft exposes inline Authorized export described above; delivery remains disabled.

## Results manual outcomes

`results.tsx`: Buyers includes Log outcome selector. Manual outcomes displays no buyer selected vs selected buyer name; stage reply/meeting/opportunity/disqualified; occurrence datetime, notes, record; correction mode adds reason and Append correction/Cancel; loading/error/empty/history with manual source, actor display-name fallback, correction attribution; Technical details hides IDs; pagination/refresh. Corrections append history and do not erase original events. Usage section is the same as overview, with UTC date state retained across locale changes.

## Settings and policy states

Sources: `settings.tsx`, `member-directory.tsx`, `budgets.tsx`, `policy-settings.tsx`, `policy-activation-panel.tsx`, `policy-terms-summary.tsx`, `lead-workflow/budget-panel.tsx`.

- Workspace settings: language output (topbar controls change), default markets, save disabled before load/pending, status/error. Role responsibilities description is present for viewer/operator/reviewer/workspace_admin.
- Provider capability cards: loading/error/refresh, each capability's status/action explanation and Technical details reason codes. Preserve blocked/unknown states.
- Approved budgets: loading/error/status, workspace/project or scope rows, approved/settled/reserved/carried/remaining values and frozen-for-new-spending state; admin limit/reason/save controls vs nonadmin read-only.
- Member directory (admin only): search/reason/loading/error/reload; paginated verified members, name-unavailable fallback; Technical details IDs, role checkboxes, active checkbox, unchanged/no-role/pending/uncertain disabled save; version-conflict/unknown-save recovery states; final-admin protection message.
- Pilot monthly budget full panel includes summary states above plus admin monthly-limit/reason save; accounting evidence title/URL/reason and shared-usage checkbox/reconcile; external economic cost unknown/committed/settled/corrected with charge key/month/settled or upper bound/currency/original amount/FX/previous event/native ID/tax and minimum confirmations; credit provider/unit/Hong Kong period/observed/used/remaining; cost history with redaction and pagination; original operation recovery. These are existing dense forms, not optional design samples.
- Controlled purpose activation: admin denial; loading/error/status/history-refresh-failed; no eligible controller designation; designation choice, purpose, professional-data/subject/scope terms, allowed manual-action checkboxes, UTC validity/expiry/application deadline, retention; submit. Selected application shows request/effective state, canonical terms summary and hash/JSON disclosure; submitted state exposes reason/confirmation/approve/reject/withdraw; new application; inspect history. Unknown submit/decision locator freezes request and offers check/retry original operation.
- Policy and suppression: read denial/loading/error/status; policy prerequisite notice. Admin restrictive policy form (blocked/requires_review only) with purpose/version/basis/provenance/country/retention/expiry; domain suppression/reason/add; policy history empty/records; suppression history empty/active/removed, remove with reason. Preserve purpose distinctions and qualified-review copy.

## Operations states

Sources: `operations.tsx`, `lead-workflow/progress-panel.tsx`.

- Lead queue: loading/error/refresh; work-stage select find_person/verify_employment/verify_procurement/verify_channel/refresh_evidence/review_preparation/complete; owner search/load/error/retry/more/select mine/unassigned/current fallback; due-on-or-before; clear filters; linked metrics/qualifying criterion; empty/matching rows, stage/next action/due/owner/blockers; expandable company-evidence and lead-case controls; dossier/content-preparation navigation; 20-row pagination.
- Operational work queue: profile approval loading/none/pending/current/stale/unavailable; failed count loading/available/unavailable; open buyers disabled without project.
- Admin readiness: loading/database/queue/worker ready/not ready. Integrations render capability status/reason codes.
- Jobs: project/workspace scope (project option disabled without project), scope Technical details, own-jobs-only notice for nonadmin; status all/queued/running/cancel_requested/cancelled/completed/failed; loading/error/retry/empty/list/20-row pagination; job ID lookup/load/details status/counts; persisted per-row reason/current-version retry eligibility; result paging and busy; polling errors. Existing bulk-job panel handles cancellation/retry flows where mounted.
- Admin audit trail: action/time/entity/reason/request IDs and pagination.
- `?acceptance=unknown` replaces job operations with Unknown provider acceptance (the lead queue above remains): loading/error/empty-count/record list with updated time/capability/status; Technical details IDs; pagination, Refresh receipts (disabled without project), Back to daily queue. No-project currently continues to show Loading rather than a dedicated empty guidance screen. Preserve this existing uncertainty view and query-based access.

## Demo-specific states and overlays

- All demo routes use sidebar open/collapsed/mobile sheet, active navigation, project-switch dialog, topbar locale, fictional-mode notices/toasts. Demo loaded flag is `main[data-demo-ready=true]`. Mobile navigation closes after selection; Budget & usage opens Results/Usage.
- Discovery run summary: counts/match and needs-review quick filters, illustrative cost/dedup, next-action review; Running six-stage progress/cancel; Completed; Partial failure-derived Failed; Cancelled; Provider unavailable; Paused at budget cap/edit budget; Limited demonstration for custom offers; retry demo; Search run history disclosure.
- Buyer table: desktop rows vs mobile cards, search and five inline filters, sort, saved-session preset, sample CSV export; selection/current page/all filtered/bulk accept/reject/save/lookup/remove from list/clear; row-size/pagination; no-match empty/clear filters. Filters & view sheet adds source type, recency, optional Owner column; submit shows filtered count. Existing desktop/mobile visibility rules are essential.
- Demo buyer sheet and full page share Overview/Evidence/Contacts/Activity tabs; full-page return/missing-buyer return; overview requirements/missing/contrary evidence, owner/note; evidence opens fictional-source dialog; contact statuses and lookup; activity history; detail action footer accept/reject/save/lookup/prepare-draft. Contact states include Not researched, Provider-marked valid, Catch-all, Public address / unverified, Unavailable, Suppressed.
- Source dialog: authored excerpt/reference/source type/language/observed/requirement; direct vs contrary warning. Connection dialog: Research / Contact enrichment / Mailbox / CRM not-connected requirements.
- Shared action dialog variants: contact lookup quote selected/eligible/blocked, budget insufficient/no eligible/expired quote, confirm/cancel; reject reason; save to list; create/rename list name; active project; save draft locally (.example recipient eligibility); suppress/unsuppress reason. Reset demo uses separate AlertDialog Cancel/Reset demo.
- Demo wizard: four steps Your offer/Target buyers/Buyer requirements/Search plan and budget; load sample; advanced offer details disclosure; local PDF/TXT/MD attach/validation/text preview/remove; buyer types/language/roles/exclusion/query preview; requirements confirmation; target/discovery/contact budgets; scenario Completed sample/Partial failure/Provider unavailable/Exhausted budget; save draft/run validation; desktop summary vs mobile summary disclosure.
- Outreach: empty accepted-buyer prompt; recipient queue; selected Draft/In review/Approved; objective/tone/language/value proposition/generate sample; recipient/subject/body; Optional follow-up disclosure; save-local dialog/request review/copy/download; disabled Send email; evidence/review checklist, sender/policy confirmation and approval gating; editing invalidates approval.
- Results tabs Outcomes/Usage, fictional manual outcome selects and stage metrics; usage cards/breakdown/zero-denominator em dash. Settings preferences/default markets/budget/unit price/save-local success/reset; suppression list/select/add/remove and connection dialogs.

## CSS and selector preservation risks / existing layout assertions

- Keep all labels, translation keys, roles, `aria-label`, `aria-selected`, `aria-current`, `aria-pressed`, `aria-modal`, disabled/readOnly states, IDs/anchor targets, `data-*` markers, native input semantics and focusability. Do not hide unavailable/uncertain/stale/redacted states or replace them with successful-looking placeholders.
- Do not collapse native `details`/`summary`, modal/dialog backdrops, tab panels, fixed/sticky action surfaces, mobile navigation/cards/summary, horizontally scrollable preview tables or long hashes/URLs/JSON. Preserve min-width/overflow wrapping of form controls and human-readable full content.
- `tests/e2e/audit-daily-ux.spec.ts`: selected action summary computed `position: sticky`; no selection hides batch forms; `.live-scope-grid` has 2 columns at 1280 and 1 at 390; no overflow; keyboard focus outline not none; Escape closes buyer dialog and returns focus; concise native run status.
- `tests/e2e/offer-ingestion.spec.ts`: Upload document and Refresh document status bounding boxes have >=8px horizontal gap; mobile no overflow. `offer-profile.spec.ts`: 320/390px no page overflow and step-label scrollWidth <= clientWidth+1.
- `tests/e2e/audit-draft-dirty.spec.ts`: zh mobile dialog bounding box stays within 390px; dirty dialog keyboard behavior. `audit-draft-reground.spec.ts`: manual source review and approved export do not overflow at 390px.
- `tests/e2e/responsive-accessibility.spec.ts`: demo routes in both locales at 390/768/1280/1440, additional 320/720 cases; no page overflow; visible controls named; search/filter boundary contrast >=3:1 at 390 and 1280; full buyer route/missing buyer, mobile selection/list actions, modal/focus/tab behavior.
- `tests/e2e/daily-workbench.spec.ts`: live route reflow and named controls in both locales at 320/390/720/768/1280/1440; page overflow <=1px. Other explicit mobile overflow coverage includes buyer-import, bulk-actions, audit-bulk-confirmation, audit-bulk-manifest, draft-editor, draft-approval, contact-quote/confirm/job, exports, and audit-keyboard-workbench tests.
- Relevant functional-selector suites also include buyer-results, buyer-source-checks, buyer-management, run-lifecycle, audit-native-run-progress, audit-research-intent/admission, audit-reviewed-list-order, audit-memberships, audit-maintenance-settings, audit-operations, audit-workspace-recovery, lead-workflow/evidence/preparations, pilot-budget, policy/policy-activation, native-attachments and draft-reground tests. Existing screenshots are evidence captures, not evidence these tests were run in this inventory pass.


## Sign-in entry, callback and provider presentation (expanded scope)

Sources: `app/(product)/auth/sign-in/page.tsx`, `app/(product)/auth/callback/page.tsx`, `app/(product)/layout.tsx`, `features/live/auth-locale.tsx`, `features/providers/workspace-session.tsx`, `features/providers/data-mode.tsx`.

| Route | Actual screen or redirect | States and controls |
|---|---|---|
| `/login` | Server redirect to `/app` from `app/(entry)/login/page.tsx` | No separate login UI |
| `/en/login` | Server redirect to `/app` | No English login UI; locale alias does not itself select workspace locale |
| `/zh-HK/login` | Server redirect to `/app` | No Chinese login UI; locale alias does not itself select workspace locale |
| `/app` while signed out | Live workspace gate sign-in card | Initializing/configuration-error, sign-in prompt/button, auth-error, session-expiry preparation-cleared warning, language picker; successful flow enters authenticated workspace |
| `/auth/sign-in` | `NeonSignInPage` | Initializing; Neon unavailable (including provider mismatch); ready email/password form; Google sign-in button; busy Signing in; failed sign-in alert; optional support diagnostic category/HTTP status/request ID; native Start again link to `/app` |
| `/auth/callback` | `AuthCallbackPage` | Completing sign-in; disabled-live status; configuration error alert; callback-failure alert + Start again link; successful callback replaces URL with validated return path; locale picker remains present |

- Auth routes inherit the same product `globals.css`, data-mode and workspace-session providers but do not mount the `/app` scope gate/readers. There is no `features/auth` directory in this revision; UI resides directly in the two route files and live auth-locale helper.
- Sign-in card uses `main.main-shell.live-workspace.live-signin`, `.live-signin-top`, `.panel.live-signin-card`, `LiveBrand`, `.live-auth-form`, `.live-primary`, `.live-secondary.live-auth-google`, `.live-auth-restart`, `.live-signin-note`. Callback uses `main.main-shell` + panel/status or alert, native recovery link, native language selector. Theme shared product CSS without requiring `/app` ancestry.
- Email is required `type=email autocomplete=username`; password is required `type=password autocomplete=current-password`; form has `aria-busy`, both inputs/buttons disabled while busy. Failed submission clears password and preserves email; support reference uses `data-testid=auth-support-reference`. Preserve all semantics, native links and pending/error states.
- `useAuthLocale` supports `en`/`zh-HK`, persisted optional `buyeros.locale`, sets document language, and disables picker until browser interaction readiness. It deliberately has a smaller translation dictionary than workspace locale and preserves unknown-string fallback. Localized aliases are redirects; no `/en/auth/sign-in` or `/zh-HK/auth/callback` screen was found.
- Session provider bootstrap kinds are disabled/initializing/configuration_error/ready with Neon or Auth0 adapter. It renders provider context only; its children own status/error UI. Provider/session binding skips ordinary hydration for `/auth/*`. DataModeProvider has no standalone loading/error screen.
- `app/chatgpt-auth.ts` also defines helper URLs `/signin-with-chatgpt`, `/signout-with-chatgpt`, `/callback` and safe-return handling; these helpers are not evidence of authored page components at those paths. Do not invent them as extra screens or alter their external authentication behavior for styling.
- Existing auth verification references: `tests/e2e/neon-session-production.spec.ts` asserts Google sign-in label fits its control (`scrollWidth <= clientWidth`); `n21-auth-local.spec.ts` covers keyboard Start again recovery/focus and fresh transaction; neon session/security/auth production suites assert pending/failure/recovery and provider boundaries. No auth calls or tests were run during this inventory.
