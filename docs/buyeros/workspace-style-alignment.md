# Workspace style alignment

Base: `b09fe39e7d470be32a9b0a542906eb48535912cb` on `codex/bilingual-site-20261025`.
Delivery branch: `codex/workspace-align-preview`.

## Scope

Shared styling covers English and zh-HK for `/app`, `/app/discover`, `/app/discover/new`, `/app/discover/edit`, `/app/runs`, `/app/discover/:runId`, `/app/lists`, `/app/lists/:listId`, `/app/buyers/:buyerId`, `/app/outreach`, `/app/results`, `/app/settings`, `/app/operations`, `/auth/sign-in`, and `/auth/callback`. `/login`, `/en/login`, and `/zh-HK/login` retain their existing redirects. The companion [route and state inventory](workspace-route-state-inventory.md) records mode differences, permission gates, loading/empty/error/recovery states and nested forms/dialogs.

## Changes

- Extracted homepage colours, system font stack, spacing, radii and control sizing into a plain shared CSS token sheet. Existing homepage variables alias these tokens; public documents retain their separate lightweight stylesheet.
- Applied the shared tokens to the product shell, navigation, headings, cards, tables, forms, buttons, dialogs/drawers, status pills and keyboard focus. Preserved distinct warning, error and success styles and improved secondary text/input-border contrast.
- Reused the sign-in card styling for callback loading/recovery states. Both native and component primary buttons use the homepage hover colour; the comparison was proven red before the final override and is included in the responsive theme regression. Adjusted the desktop selected-buyer action bar below the sticky header; preserved the mobile placement.
- Removed duplicate CSS declarations and rules. Product layout now explicitly emits `noindex, nofollow` for workspace and auth documents.
- No service, hook, API, auth handler, event handler, translation, accessibility-label or application test-selector changes. Callback changes are class names only; its AST is identical to the baseline when class attributes are ignored. The sole inline component colour change is BudgetRow’s border alias to `var(--border)`; its AST is otherwise identical, with border width/style and layout preserved.

## Validation

Local tests use synthetic identities/providers and disposable owned databases. No production data, real outbound delivery or paid provider calls. Screenshots and generated runtime/test artifacts are excluded from the commit.

Responsive coverage includes 390, 768 and 1440px in both locales, visible keyboard focus and document noindex checks. Token contrast checks: primary/white 5.48:1, muted/background 5.30:1, input borders 3.19–3.63:1 on applicable surfaces, status text/background at least 5.78:1.

Verification is not fully green: the completed browser matrix has six managed-policy blockers and two native timing failures, detailed below. Real external identity acceptance and opt-in load benchmarks are outside this local/no-production/no-paid run.

### Completed unit/backend verification

| Coverage | Result |
|---|---|
| TypeScript | `pnpm exec tsc --noEmit`: passed |
| Root lint | `pnpm lint`: passed |
| Cloudflare build | `pnpm build`: passed |
| Vercel build | `node scripts/run-vercel.mjs build`: passed |
| Node tests | 285 passed |
| React-server auth SDK tests | 3 passed |
| Standalone job-poller unit tests | 17 passed |
| Domain / adapter / import / upload / auth / run checks | 11 / 74 / 5 / 14 / 11 / 4 passed |
| Policy client Vitest | 11 passed |
| Cloudflare controller Vitest | 27 passed; types, lint and binding check passed |
| API | All 3,035 discovered names have passing evidence; see qualification below |
| Worker | 469 passed |
| Root Python | 415 passed |
| Linux standby | 2 passed |

The original full API invocation retained 3,009 passes, one failure caused by a missing historical Git object and 25 marketing tests skipped under the generic fixture. Fetching the exact object restored the first prerequisite; that unchanged case passed its guarded rerun. The dedicated marketing fixture passed all 26 of its tests, including every skipped API name. Exact-name reconciliation covers all 3,035 original API cases without synthesizing a merged JUnit report. Worker and root Python discovery/execution sets also match exactly. All 45 backend-owned PostgreSQL container IDs were verified removed; backend sources remained unchanged.

The full browser run found an existing stale admin-test assertion for “Research provider.” Baseline and current `features/live/settings.tsx` were byte-identical and already rendered “Provider capabilities.” The test now uses that existing region and existing research capability data attribute, asserting both visibility and a loaded status enum. The same legacy test also had a non-exact reason-field match and a suffix-based member name predating the existing accessible display names. It now scopes the exact reason field to member management and finds the same reviewer through the existing full UUID in Technical details before using its existing Roles group. The role mutation and success checks remain unchanged. Reload/login and shared-preference steps use the existing exact English/zh-HK control names, and the reload explicitly asserts persisted `zh-HK` instead of incorrectly expecting English sign-in after a successful language change. No application copy/labels/selectors or timeout was changed, and the old failures are retained as evidence.

The legacy scope-only browser mock returned a project object for the usage endpoint, causing baseline `LiveUsage` to crash on a missing `categories` array. The mock now supplies a complete generated-type-checked, explicitly synthetic empty Usage DTO and valid member preferences. Authentication and scope security checks are retained. The missing-profile check targets its existing Profile details alert, and initial directory pagination now asserts exactly two reads at offsets 0/100 before selecting a workspace; required later membership revalidation remains unchanged. The bulk fixture explicitly chooses English through the existing signed-out picker before its English workflow, while its zh-HK pagination assertion checks the existing translated row range.

Final application syntax validation compared callback and BudgetRow against `b09fe39`: all nodes match after excluding only JSX class attributes and the one border-colour value respectively. Final `tsc`, unchanged `pnpm lint`, both builds and the extra compiled-demo build passed after these changes. Each completed browser run retains per-group source/artifact proofs; final affected reruns are recorded separately from earlier attempts.

Legacy policy/run tests were also updated to target existing form regions and heading levels, and to open the native Technical details disclosure before asserting visible transport/event text. Policy permit restrictions, real run transitions, SSE/polling fallback, viewer checks and deadlines remain intact.

The native six-page/reload drivers unnecessarily repeated fictional issuer installation, RSA generation and a third page navigation after an explicit reload. The two affected call sites now reuse the already-installed issuer routes and perform the real sign-in, observe the same workspace request and wait for the same project readiness. All actual reloads/auth transactions, PKCE/state/nonce verification, revision/save/acknowledgement checks and original test/assertion deadlines remain. No production authentication code changed.

## Final browser results and limitations

All 42 ordinary config groups / 71 mapped spec files are accounted for: **385 exact identities = 377 passed, 6 environment-blocked, 2 timing failures**. No config remains pending. Executed native discovery and JUnit identities match exactly; blocked identities are explicitly distinguished from executed cases. Earlier failed attempts and affected reruns are retained separately.

Passing groups include isolated core 2, full audit 138/140 (the other two are the blocked probes below), responsive/accessibility 21, final theme 7, final admin 3, bulk 3, scope/security 12, workbench 8 (AA text and 3:1 control boundaries), joined C61 workflows 16, Cloudflare acceptance 7, marketing intake 7, built marketing site 13, marketing spike 11, synthetic built Neon runtime 9, public sign-in audit 12, auth 5, policy activation 9, policy 2, run lifecycle 2, private attachments 4, offer/profile 8 and the other mapped regression groups. Both locales and 390/768/1440px are covered; the final theme compares normal and hovered primary buttons with the actual homepage.

### Unresolved native timing failures

The final original guarded lead suite is **44/46**, with all original test/assertion limits retained:

- `lead-preparations.spec.ts::N21-PREP-03 paged readback cannot substitute another preparation during Save then Archive`: the original 5-second archived-state assertion expires while the edited body/revision 2 remains protected and archive is busy.
- `lead-workflow.spec.ts::six_pages_preserve_project_and_progress_after_reload`: the original 30-second whole-test deadline expires during real page reload; the snapshot shows sign-in initializing.

The three retained full native runs were 44 passed / 2 failed, 42 / 4, and 44 / 2. A qualified union has passing evidence for 45/46 identities; the six-page case never passed. This is **not a clean native suite**. Local request timings include approximately 0.9–3.3 seconds per affected read/write request. No application flow, acknowledgement ordering, data protection, deadline, or assertion was relaxed to conceal these results.

### Managed browser policy blockers

The system Chromium policy blocks the injected extension required by actual tab-zoom tests and forbids `data:` main-frame navigation. The normal official pinned-browser download was also denied by outbound policy. No policy bypass or alternative download route was used.

- Actual Chromium 200% demo zoom: English attempted and blocked; zh-HK not attempted after the same gate.
- Actual Chromium 200% API workbench zoom: both locales blocked by the known extension gate and not attempted.
- Two standalone keyboard probes navigating synthetic `data:` documents: attempted and blocked. Actual application keyboard journeys passed.

These six checks are not reported as passes. Ordinary responsive/effective-zoom and keyboard checks remain separately passing.

### Scope and retained evidence

Two real external Neon acceptance tests require external authenticated accounts and are excluded. Standalone opt-in load/capacity benchmarks (including the 30-minute mixed workload) are not ordinary specs and were not run. No hosted deployment, production/provider/paid acceptance or human UAT is claimed.

Raw local logs, native XML, traces, exact identity reconciliation, source/output fingerprints and prior failures remain under the ignored `work/workspace-alignment/` directory; they are excluded from this commit along with screenshots. Main summaries are `browser/final-browser-report.md`, `browser/final-test-identities.json`, `browser/final-group-evidence.json`, and `backend/reconciliation.json` within that evidence directory.

All test-owned servers and containers were verified stopped. The original local pnpm store was restored after tests. Generated tracked screenshot/acceptance artifacts were preserved locally and restored to their original Git contents. The final canonical application manifest contains 201 files with SHA-256 `ce6a432f76f61511b081b927b18dc8acc88acc34100f3977f4cc288e8170f686`; pre-commit verification confirms those application bytes still match the last suite.
