# Increment 2.5 review — inline sandboxed output preview

Reviewer: `reliability` (independent of the implementation streams)
Date: 2026-11-10 (Asia/Singapore)
Worktree: `C:\Users\laich\Documents\BuyerOS\.worktrees\conv-studio`, branch `feat/conversation-output-preview`, head `f628dbe14` (stacked PR #62 on `feat/conversation-turn-deadline`).
Contract: `docs/superpowers/specs/2026-11-10-output-preview.md`.
Scope: inline preview client, sandbox/fetch/bounds/error/no-leak behaviour, regression risk, and the extra commits present in PR #62. **No implementation file was modified by this review; the only file written is this document.**

Verification legend:
- **[READ]** verified by reading source at the cited `file:line`.
- **[TEST]** verified by a test/command executed in this sandbox (`node:test`, tsc, static checks — see §7).
- **[BLOCKED]** browser execution is unavailable here (Playwright `spawn EPERM`). CI run 42708397826 is authoritative for the browser gate; no browser result is claimed.
- **[ROUTED]** reported to the Lead.

## 1. Findings summary

| Id | Severity | Finding | Evidence | Status |
| --- | --- | --- | --- | --- |
| MAJOR-1 | Major (leak, pre-existing renderer surfaced inline) | The preview body can render internal `SourceRef` ids/locators: `render_output` walks the whole saved output content model and emits every field as text, including `Finding.evidence`, `PreparedMessage.evidence`, `CommercialTerms.evidence` and `FollowupPreparation.interaction_ref` (each a `SourceRef` with `id` UUID, `locator`, `version`, `retention_class`). The inline frame is user-visible content, so "no internal ids/paths/hashes rendered" is not met for most output kinds. This is pre-existing server behaviour (the endpoint predates 2.5) but the new inline surface exposes it prominently. No backend test covers `render_output` at all. | `services/api/buyeros_api/services/sales_outputs.py:43-49` (renders every dict key/value); `sales/contracts.py:55-62` (`SourceRef`), `:202-208` (`CommercialTerms.evidence`), `:353-357` (`Finding.evidence`), `:442-448` (`PreparedMessage.evidence`), `:456-461` (`FollowupPreparation.interaction_ref`) | [READ] |
| MAJOR-2 | Major (defence in depth / equivalence claim) | `srcDoc` in `<iframe sandbox="">` is **not strictly equivalent** to the endpoint CSP `default-src 'none'; sandbox`: the sandbox attribute blocks scripts/forms/popups/top-navigation/same-origin, but the srcdoc document may still load external subresources (images/styles/fonts/media) and navigate its own frame, and the fetched response's CSP header is not applied to a srcdoc document. No current exploit: the renderer escapes HTML and markdown links/images and emits only `h2/section/p`/`ul` (`sales_outputs.py:26-49`), so the HTML has no external-resource constructs. The safety currently depends on the renderer staying inert. Add a `<meta http-equiv="Content-Security-Policy" content="default-src 'none'">` to `render_output` (or sanitise server-side) and test it. | `features/live/conversation/inline-parts.tsx:126-129`; `output-preview.ts:7-12`; `sales_outputs.py:26-49`; endpoint headers `api/routes/sales_outputs.py:138-145` | [READ] |
| MAJOR-3 | Major (fetch discipline) | The preview fetch is never aborted. `OutputPreview` passes no `AbortSignal`; cleanup only bumps a counter so the late result is ignored (`inline-parts.tsx:100-112`; studio closure `studio.tsx:289-295`; `fetchOutputPreview` accepts a signal but none is passed, `output-preview.ts:71-88`). Unmount, collapse-with-scope-change or a revision change leaves the GET and body stream running (bounded by 64 KiB) until completion. Contract/task asks abort/cleanup on unmount. Add a per-component `AbortController`, abort on unmount/revision change, and pass `signal`. | see left | [READ] |
| MAJOR-4 | Major (bounds honesty) | `readCapped` can silently truncate without marking it: the loop is `while(total<maxBytes)` and when a chunk exactly consumes the remaining budget (`value.length===remaining`) it sets `total=maxBytes`, leaves `truncated=false`, does **not** cancel the reader, and exits. A body larger than 64 KiB delivered in aligned chunks (e.g. 4×16 KiB then more) is truncated with no notice and an unconsumed reader. Fix: after the loop, if `total>=maxBytes`, probe one more read (or treat as truncated when the stream is not done) and always `cancel()`; add a unit test with a stream that yields exactly the cap and then more. | `features/live/conversation/output-preview.ts:43-66`; unit tests only cover one-chunk-over-cap and exactly-cap-body | [READ] |
| MAJOR-5 | Major (PR scope / QA security) | PR #62 contains commit `20c917a3e` (QA deployment-protection bypass) in addition to the preview increment: `.github/workflows/buyeros-conversation-qa.yml`, `playwright.conversation-real.config.ts`, `docs/buyeros/runbooks/conversation-qa.md`, `tests/e2e/conversation-real-qa.spec.ts`, `tests/core-qa-protection.test.mjs`. This contradicts "no backend/.github change beyond the core constant" and explains core 141→150 (+9 = 7 preview + 2 QA), not the stated +7. Security detail: the config's `extraHTTPHeaders` sends `x-vercel-protection-bypass` with every request in the browser context (`playwright.conversation-real.config.ts:31-38`), including cross-origin redirects/assets (e.g. the sign-in identity provider), not only the candidate origin; the runbook's "never echoed into the app" claim covers app JS but not cross-origin header propagation. Scope the header to the candidate origin (route handler / storage state) or document/limit the QA context; consider splitting the QA commit. | `git log`/diff vs parent; `playwright.conversation-real.config.ts:31-38`; `.github/workflows/buyeros-conversation-qa.yml` bypass additions | [READ] |
| MINOR-1 | Minor (bounds, dead path) | If `response.body` is null, `readCapped` falls back to `response.text()` and checks the cap only afterwards — unbounded buffering on that path (`output-preview.ts:44-49`). Browser fetch returns a null body only for null-body statuses (204/205/304), which are practically empty, so this is not currently reachable with a large body, but it weakens the "only unbounded input is capped" claim. Reject null-body 2xx or precheck `Content-Length`. | see left | [READ] |
| MINOR-2 | Minor (deadline) | The preview fetch has no timeout: a stalled response leaves the card in "Loading preview…" indefinitely and the retry button only exists for the `unavailable` state. A bounded client deadline (or abort on a timeout) would match the rest of the app. | `output-preview.ts:76-81`; `inline-parts.tsx:112-116` | [READ] |
| MINOR-3 | Minor (auth plumbing) | The raw `fetch` bypasses `LiveClient`'s auth recovery/access-denied plumbing, so an expired token is reported as "You no longer have access…" and no refresh/global access-loss handling runs. `previewOutput` checks scope/identity but not `session.token()` (`studio.tsx:289-295`), so a signed-out race could issue an unauthenticated GET (server 401 → denied; no data leak). | see left | [READ] |
| MINOR-4 | Minor (content validation) | No `Content-Type` validation and default redirect following: a 2xx non-HTML or redirected login page is rendered in the sandbox (script-free, but misleading as the "preview"). Validate `text/html` and/or `redirect:'error'`. | `output-preview.ts:76-88` | [READ] |
| MINOR-5 | Minor (robustness) | `load()` has no try/catch around `actions.previewOutput`; an unexpected rejection would leave the component stuck in `loading` with an unhandled rejection. Wrap and map to `unavailable`. | `inline-parts.tsx:103-110` | [READ] |
| MINOR-6 | Minor (test gaps) | Unit tests do not cover: exact-cap-boundary truncation, null-body fallback, invalid-input no-fetch at `fetchOutputPreview` level, unmount abort, `Content-Type`/redirect handling, or server-side preview redaction. Browser gate covers lazy/one-GET/cached/denied/sandbox attributes but not abort-on-unmount or truncation. | `tests/core-conversation-output-preview.test.mjs` | [READ] |
| MINOR-7 | Minor (accounting) | The task statement says "core 150 matches the 7 added unit tests"; actual delta is +9 (7 preview + 2 QA-protection from the stacked QA commit). CI constant 150 does match the real suite, so no CI break; only the accounting/scope statement is off (see MAJOR-5). | `.github/workflows/buyeros-ci.yml:64`; executed suite 150 | [TEST] |

**No blocker was found**: no path renders un-sandboxed or script-executing content, and the client never sets `srcDoc` for a non-2xx status.

## 2. Sandbox safety (focus 1) [READ]

- Only one live HTML frame path exists: `inline-parts.tsx:126-129` renders `<iframe sandbox={PREVIEW_SANDBOX} srcDoc={state.html} referrerPolicy="no-referrer" title=…>`; `PREVIEW_SANDBOX=''` and `previewSandboxTokens()` is empty (`output-preview.ts:7-12`); no `allow-*` tokens; no `src` attribute; bounded height 18 rem. A repository grep finds no other `srcDoc`/`<iframe>` in the live conversation surface and no `dangerouslySetInnerHTML` there (the marketing `dangerouslySetInnerHTML` uses are JSON-LD, pre-existing and unrelated).
- `srcDoc` is only assigned in `state.kind==='ready'`, which is only produced after `previewStatusKind(status)==='ok'` (`output-preview.ts:82-87`); error/loading/idle states render no frame. The browser gate asserts the frame is absent before expansion and in the denied state, and that `sandbox=""`, `referrerpolicy="no-referrer"` and the server HTML are present on the frame.
- `sandbox=""` (no `allow-same-origin`) gives the srcdoc an opaque origin: no cookies/storage/DOM access to the parent, no scripts, forms, popups or top-window navigation; `referrerpolicy=no-referrer` prevents a referrer leak. The endpoint itself still sets `Content-Security-Policy: default-src 'none'; sandbox`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` (`api/routes/sales_outputs.py:138-145`) for direct navigation.
- The residual is MAJOR-2: the fetched response's CSP header is not enforced on the srcdoc document, so sandbox="" is not a full substitute for `default-src 'none'`; it is safe today only because `render_output` is inert. Add a meta CSP in the rendered HTML and a test.

## 3. Fetch discipline (focus 2) [READ]

- Lazy: the component fetches only from the `<details>` `onToggle` when opening and `state.kind==='idle'` (`inline-parts.tsx:108-112`); no effect/preload/poll. Browser gate asserts zero preview requests before expansion.
- Exactly one authenticated same-origin GET on expand: `fetchOutputPreview` builds `/v1/workspaces/{ws}/projects/{pj}/sales-outputs/{id}/preview?revision=N` with `encodeURIComponent` and `method:'GET'`, `cache:'no-store'`, `Accept: text/html`, `Authorization: Bearer …` from the session token (never in the URL); the token is not in the DOM (`output-preview.ts:22-28,71-88`; `studio.tsx:289-295`).
- Cached on re-expand: state is kept while mounted; the browser gate expands/collapses/re-expands and asserts no second request. Refetch only on id/revision change: `OutputPreview` is keyed by `${part.output_id}:${part.revision}` (`inline-parts.tsx:141`).
- No polling/automatic retry: the module never retries; the retry button appears only for `unavailable` (`inline-parts.tsx:113-116`); the browser gate waits 400 ms after a denied preview and asserts no extra request.
- Stale-response protection: `active` counter increments on unmount and each load; late results are ignored (`inline-parts.tsx:104-110`); keying covers revision changes.
- Gaps: no abort (MAJOR-3), no timeout (MINOR-2), token check/race (MINOR-3), raw-fetch auth plumbing (MINOR-3).
- Invalid scope/revision: `previewRequestUrl` returns null for blank scope/output or non-integer/revision<1 and `fetchOutputPreview` returns `unavailable` before any fetch (`output-preview.ts:22-28,74-75`); unit tests cover the builder (the fetch-level no-request path is untested — MINOR-6).

## 4. Bounds and error mapping (focus 3–4) [READ]

- Streaming cap: `readCapped` reads `response.body.getReader()` in ≤64 KiB chunks, stops at `PREVIEW_MAX_BYTES=65536`, slices the over-cap chunk, cancels the reader when a chunk exceeds the remaining budget, releases the lock, and decodes the bounded bytes (`output-preview.ts:43-66`); the component renders a "Preview truncated" notice when `truncated` (`inline-parts.tsx:130-131`).
- Gap: exact-cap chunk boundary leaves `truncated=false` and does not cancel (MAJOR-4); null-body fallback unbounded (MINOR-1).
- Error mapping: `previewStatusKind` maps 401/403→`denied`, 404→`missing`, other non-2xx→`unavailable`; the component shows the matching localized notice, the frame is absent in every failure state, `unavailable` has a manual retry, and "Open saved output" remains unchanged in all states (`output-preview.ts:29-42`; `inline-parts.tsx:112-121,135-142`). Denied/missing never fall back to a weaker rendering. The browser gate covers the denied case (notice, one request, no frame, open action present, no auto-retry).
- Empty/invalid content: `render_output` returns `<p>Output unavailable</p>` for unavailable outputs and escapes all rendered values; the client never parses HTML (only `srcDoc`), so empty/invalid bodies cannot throw (`sales_outputs.py:43-49`; `output-preview.ts:43-66`).

## 5. Leak review (focus 5) [READ]

- Client-side UI is clean: notices are constants; the iframe title is `${t('Preview')}: ${part.title}` (output title only); the output id/revision URL, API path and token are not rendered in text, tooltips or aria labels; the existing `Revision N` version number is pre-existing card metadata, not a hash.
- **MAJOR-1 is the leak that matters**: the preview body itself is server HTML that includes internal `SourceRef` ids/locators for most output kinds because `render_output` renders the entire content model. The CSP/sandbox do not redact content. Fix in `render_output` (whitelist human-authored fields, skip `evidence`/`interaction_ref`/id-bearing keys) and add a backend test asserting UUID/locator strings are absent.

## 6. Regression (focus 6) [TEST]

- Browser gate: parent and head both have 19 top-level tests + 2 loop-generated pairs = **23 cases**; the preview work only enhances the existing "conversation-first transcript renders typed inline parts and inline decisions" case (no new case), and the six screenshot paths are identical to the parent (`transcript-inline-parts-desktop`, `proposal-approval-desktop`, `zh-hk-desktop`, `home-desktop`, `mobile-390`, `stream-progress-desktop`) — no prior assertion was removed or weakened in the diff.
- Core: `node --test --experimental-test-isolation=none tests/core-*.test.mjs tests/audit-research-intent.test.mjs` → **150 tests, 150 pass**; matches the CI core constant 150. `tsc --noEmit` → exit 0.
- Locale: 7 new keys in both `features/live/locale.ts` and `locales/index.ts`; reviewer scan of `output-preview.ts` + `inline-parts.tsx` finds 0 missing keys.
- Preview increment itself has no backend change; the extra QA commit in the PR is MAJOR-5 (scope), and it is the reason core is +9 rather than +7 (MINOR-7).

## 7. Verification executed / BLOCKED

Executed here: core suite 150/150; `tsc --noEmit` exit 0; static diff/count checks (browser 23 cases, six screenshots unchanged, locale keys, no other live iframe/srcdoc path); React `renderToStaticMarkup` check that an empty-string `sandbox` prop renders `sandbox=""` (so the browser assertion is meaningful). The browser gate was **BLOCKED** (Playwright `spawn EPERM`); no browser result is claimed. Backend pytest was not needed for this UI-only increment, but note that no backend test covers `render_output` (relevant to MAJOR-1) and DB execution is blocked here anyway.

## 8. CI artifacts that prove acceptance

| Criterion | Proof | Artifact |
| --- | --- | --- |
| Lazy/one-GET/cached/denied/sandbox attributes/srcdoc-after-2xx | enhanced browser case in `tests/conversation-home-responsive.test.mjs` | job `frontend`: `test-results/conversation-studio.xml` + `test-results/conversation-studio/*.png` (artifact `buyeros-conversation-studio`), 23 cases |
| URL builder, status mapping, sandbox constant, cap/truncation (one-chunk-over-cap), auth header | `tests/core-conversation-output-preview.test.mjs` (7 tests) | job `frontend`: `test-results/core-client.xml` (artifact `buyeros-core-client`, count 150) |
| Regression: 23 browser cases, unchanged screenshots, tsc/lint | same browser + core artifacts; `pnpm lint`/`tsc` steps | job `frontend` |
| QA bypass wiring (extra commit) | `tests/core-qa-protection.test.mjs` (2 tests) | `core-client.xml`; real QA run only via the protected `buyeros-conversation-qa` workflow with secrets |

**Unproven by any artifact**: sandbox-vs-CSP equivalence (no test), abort-on-unmount, exact-boundary truncation, null-body fallback, preview-body id redaction, cross-origin propagation of the QA bypass header, and the real browser sandbox behaviour locally (BLOCKED; the CI browser gate is the substitute for the attribute/lazy assertions).

## 9. Recommendations (owner: conversation-ui / Lead for the QA commit)

1. MAJOR-1: redact/whitelist in `render_output` (never render `SourceRef`/id/locator fields) and add a backend preview test asserting no UUIDs/locators; if the intended preview is full fidelity, document the exception explicitly.
2. MAJOR-2: emit a `<meta http-equiv="Content-Security-Policy" content="default-src 'none'">` in the server preview HTML (or sanitise) so the srcdoc carries the endpoint's policy; keep sandbox="" and no-referrer.
3. MAJOR-3: per-component `AbortController` passed through `previewOutput`/`fetchOutputPreview`, aborted on unmount and revision change; keep the active-counter guard.
4. MAJOR-4: fix the exact-cap boundary (`truncated=true`/cancel when `total>=maxBytes` and the stream is not done) and add the missing unit test.
5. MAJOR-5: split/scope the QA bypass commit; restrict `x-vercel-protection-bypass` to the candidate origin (route handler or storage state) rather than every browser request.
6. Minors: reject null-body 2xx, add a client timeout, validate `text/html`/`redirect:'error'`, wrap `load()` in try/catch, add the missing unit tests.

## 10. Not reviewed / out of scope

- No production deployment/promotion/Vercel changes; no implementation edits (only this document).
- Real provider/paid behaviour, production data and the browser runtime were not exercised here; the CI artifacts above are the substitute.
