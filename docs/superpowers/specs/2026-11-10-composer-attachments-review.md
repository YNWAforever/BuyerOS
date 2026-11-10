# Increment 2.3 review — composer attachments via the existing ingest path

Reviewer: `reliability` (independent of the implementation streams)
Date: 2026-11-10 (Asia/Singapore)
Worktree: `C:\Users\laich\Documents\BuyerOS\.worktrees\conv-studio`, branch `feat/conversation-attachments`, head `43eba7108` (stacked PR #63 on `feat/conversation-output-preview`).
Contract: `docs/superpowers/specs/2026-11-10-composer-attachments.md`.
Scope: composer attachment client/state machine, sources persistence, lifecycle/authority, honesty, and regression. **No implementation file was modified by this review; the only file written is this document.**

Verification legend:
- **[READ]** verified by reading source at the cited `file:line`.
- **[TEST]** verified by a test/command executed in this sandbox (`node:test`, tsc, eslint — see §6).
- **[BLOCKED]** browser execution is unavailable here (Playwright `spawn EPERM`). CI run 42725557989 is authoritative; no browser result is claimed.
- **[ROUTED]** reported to the Lead.

## 1. Findings summary

| Id | Severity | Finding | Evidence | Status |
| --- | --- | --- | --- | --- |
| MAJOR-1 | Major (authority/contract + undocumented caveat) | Archived detection is only the current list-page flag: `archivedLoaded` scans `list.items` for `row.archived===true`. `ServerThread` has no `archived` field (`ServerSummary&LocalThread`; server thread GET `data()` omits it; only list items get `pinned/archived`). An archived thread opened directly (URL/deep link, or beyond the first list page, or while the list is filtered) is therefore not detected, so the Attach control mounts and an upload + sources PUT can succeed into an archived thread. The code comment claims "archived and viewer threads never mount the control" and no caveat exists in the spec/runbook; the contract says archived threads must have no control and issue no request. Fix: include archived in the thread GET (or fetch preferences before enabling) / reject server-side, or document the limitation and test the direct-open case. | `features/live/conversation/studio.tsx:606-608`; `services/live/conversation-threads.ts:9,86`; `services/api/buyeros_api/api/routes/conversation_threads.py:117-125,185`; spec `2026-11-10-composer-attachments.md:40` | [READ] |
| MAJOR-2 | Major (contract: context panel status) | The uploaded document does not appear in the context panel with its ingestion status until the panel is remounted/reloaded. `SourcePicker` loads project context once per identity+thread and caches it in a ref (`context-panel.tsx:58-68`); attaching updates only `loaded.chat.sources` (selected-sources label list, no status), not the cached context sections. The status pill added at `context-panel.tsx:79` only renders for items from that stale context list. The browser gate's assertion is too weak: it waits for `project-evidence.pdf` and a `ready` pill from the pre-existing fixture context, not for the uploaded document's own status. | `features/live/conversation/context-panel.tsx:58-79,105-106`; `studio.tsx:463-488`; browser scenario `tests/conversation-home-responsive.test.mjs` (new attach case) | [READ] |
| MAJOR-3 | Major (abort/lifecycle) | Only the upload is abortable; the sources PUT and the stale-refresh GET are not. The combined controller+session signal is used by `createDocumentUpload(...).upload(...)` (`studio.tsx:425-444`), but `attachmentAbort.current` is set to `null` before `attachDocumentToThread` (`:445`), and `ConversationThreads.request` always uses only `session.controller().signal` (`conversation-threads.ts:46-49`). Route change/unmount during attach therefore cannot abort the PUT/refetch; the PUT may persist the attachment after the user left (and the stale closure may target the previously loaded thread if the thread changed after the upload). The unmount cleanup aborts only `attachmentAbort.current`, which is already null. Fix: one controller for the whole attach (don't clear before PUT), thread an `AbortSignal` through `ConversationThreads.sources/get`, and test abort-on-route-change. | `studio.tsx:244,425-445,463-493`; `conversation-threads.ts:46-49`; `attachment.ts:66-89` | [READ] |
| MAJOR-4 | Major (honest retry classification) | Upload failures are classified by error class, not semantics: `LiveError` → `failure:'upload'` retryable; every plain `Error` → `failure:'rejected'`, non-retryable (`studio.tsx:450-458`). The uploader throws plain `Error` for recoverable upload states too ("Invalid upload status. Keep the original file and check the connection.", "Upload recovery belongs to a different scope or is invalid.", "An attachment upload is already in progress.", "Upload expired…", "The file could not be parsed…"), so these lose the Retry attachment affordance and are presented as file rejections. The message is honest (comes from the uploader), but the contract distinguishes rejected vs upload failure and retry only where meaningful. Fix: export typed uploader errors (`code`/`retryable`) and classify by them. | `studio.tsx:450-458`; `services/live/document-upload.ts` error throws (e.g. `checkedStage`, `pending`, `upload`) | [READ] |
| MINOR-1 | Minor (duplicated limits) | The composer's `accept=".pdf,.txt,.md,.pptx"` duplicates the uploader's accepted-format/MIME map and size classes (`document-upload.ts:12,50`). The contract says do not duplicate or re-word the limits; drift risk if the uploader changes. Export the accepted extensions from the uploader (or drop `accept`). | `composer.tsx:84`; `document-upload.ts:12,50` | [READ] |
| MINOR-2 | Minor (visibility inconsistency) | Attach is hidden on the project home `/app` even when an existing thread is auto-loaded, because `attachAvailable` requires `threadId!==null` (the route target). The home composer sends turns to that loaded thread, so attach should be available there too; only `/new` (fresh) should hide it. | `studio.tsx:608`; `attachAvailable` gating | [READ] |
| MINOR-3 | Minor (progress monotonicity) | The reducer clamps progress to 0–100 but does not enforce monotonicity (`attachment.ts:34-35`). The uploader currently emits ascending progress per attempt, so there is no observed regression, but a resumed/retried event stream could move backwards; `Math.max(state.percent, next)` is cheap hardening. | `attachment.ts:30-48` | [READ] |
| MINOR-4 | Minor (i18n of uploader text) | Uploader rejection messages are English-only and rendered through `t(message)` (`studio.tsx:457`); zh-HK users see untranslated uploader text. Acceptable under "messages come from the uploader", but worth noting; new UI strings themselves are fully localized. | `studio.tsx:457`; `document-upload.ts` messages | [READ] |
| MINOR-5 | Minor (double-selection race) | `attachFile` guards on the rendered `attachment` state, not a ref; a second file selection before the re-render hides the control could start twice; the uploader then throws plain `Error('An attachment upload is already in progress.')`, which MAJOR-4's classification shows as a non-retryable rejection. Add a ref guard. | `studio.tsx:418-430`; `document-upload.ts` busy guard | [READ] |
| MINOR-6 | Minor (test gaps) | No browser assertion for: hidden-on-`/new`, direct-open archived thread (MAJOR-1), abort-on-route-change (MAJOR-3), or the uploaded document's own context-panel status (MAJOR-2). Unit tests do not cover abort or the `uploading→attached` edge. | `tests/core-conversation-attachment.test.mjs`; new browser scenario | [READ] |
| MINOR-7 | Minor (stale-closure edge) | If the thread changes between upload completion and the attach PUT, `attachDocumentToThread` runs with the closure's old `loaded` and may attach to the previous thread with no notice (same root as MAJOR-3; the abort fix should also re-check `loaded.chat.id`). | `studio.tsx:463-471` | [READ] |

**No blocker was found**: the shipped uploader is reused unchanged, there is no second upload path, and the sources PUT cannot bypass the server's current-version/ACL/label checks.

## 2. Ingest reuse (focus 1) [READ]

- The composer calls the shipped `createDocumentUpload(client, sessionStorage)` lazily once per studio (`studio.tsx:160-166,431-443`) and `workflow.upload(file, uploadContext, onProgress)` (`:441-443`); the uploader module is unchanged. The same accepted formats/size limits, SHA-256 manifest, chunk hashing, idempotency keys, resumable pending record and server-verified document checks are used (`document-upload.ts:12,50-52,73-120`); no second upload path exists in the conversation surface.
- Retry resumes rather than re-ingests: the uploader instance is cached (`uploaderRef`) and its pending record lives in sessionStorage keyed by actor/workspace/project, so a retry after an upload failure resumes the same upload/stage (`document-upload.ts:66-90`); attach failures retry only the sources PUT with the already-ingested `document.id` (`studio.tsx:463-495`). The browser scenario asserts one upload start/chunk/complete across the failed attach + retry.
- No bypass: the conversation code never builds upload requests itself; all chunk/hash/manifest checks stay in the uploader. MINOR-1 is the only duplication (the `accept` hint).

## 3. Sources persistence (focus 2) [READ]

- `api.sources(thread, sources)` sends `PUT /conversation-threads/{id}/sources` with body `{sources:[{id,label}]}` and `If-Match: "<thread.version>"` (`conversation-threads.ts:86`); the attached ref is `document:<uploaded id>` with the server-allowlisted label `Offer document` (`attachment.ts:8,50-52`; server allowlist `conversation_threads.py:26,48-52`).
- Duplicate suppression before any write; on a stale 412/`STALE_REVISION`, one refresh + one retry with the fresh version; a second failure is an honest retryable attach failure (`attachment.ts:66-89`; 7 unit tests cover duplicate, stale-once, second-stale, refresh-failure and non-stale paths).
- Nothing is marked attached before the response is parsed: `loaded` is only replaced after `chatThread(outcome.thread)` succeeds; the browser scenario asserts zero selected sources before success and one after.
- No request when the viewer/archived state forbids it: viewer is gated in the UI and in `attachFile`; archived is MAJOR-1 (incomplete detection).

## 4. Abort / lifecycle (focus 3) [READ]

- One `AbortController` per attach (`attachmentAbort`), combined with `session.controller()` for the upload (`studio.tsx:425-428`), aborted on thread change (`:219`) and studio unmount (`:244`); uploader guard checks the signal and `isCurrent` before every request.
- State updates after await are guarded by `current()`; the thread-change effect resets the attachment state and refs.
- Busy suppression: the reducer ignores `start` while uploading/attaching (`attachment.ts:30-33`), the composer hides the control while busy (`composer.tsx:82`), and the uploader itself refuses a concurrent upload.
- Progress is clamped 0–100 (`attachment.ts:34-35`; `studio.tsx:442`) and rendered as a determinate `progressbar` with `aria-valuemin/max/now` and a localized label (`composer.tsx:72-75`); no secondary prose.
- Gaps: PUT/refetch not abortable and the controller is cleared before attach (MAJOR-3), progress monotonicity hardening (MINOR-3), double-selection ref guard (MINOR-5).

## 5. Access / honesty (focus 4–5) [READ]

- Control visibility: live studio only, `threadId` present (existing thread), `loaded` present, `access!=='viewer'`, and not archived-in-list (`studio.tsx:606-608`). Hidden on `/new` (targetId null). Viewer browser scenario reloads as a viewer and asserts no file input and zero new upload/source requests.
- Honest states: rejected (uploader message, no retry), upload failure (retry), attach failure (retry), no access (control absent); `attachThreadSource` returns duplicate/attached/failed explicitly and the studio never fakes an attached state (`studio.tsx:463-493`). No internal ids/paths/hashes appear in the notices or labels.
- Uploader rejection text is not localized (MINOR-4); retry classification is class-based (MAJOR-4).

## 6. Regression (focus 6) [TEST]

- Browser gate: parent 19 top-level + 2 loop-generated pairs = 23 cases; head 20 + 4 = **24** cases — exactly one new scenario appended, no prior assertion modified and the six screenshot paths are identical to the parent (five original + stream-progress).
- Core: `node --test --experimental-test-isolation=none tests/core-*.test.mjs tests/audit-research-intent.test.mjs` → **161 tests, 161 pass**; matches the CI core constant 161 (parent 154 + 7 attachment tests). `tsc --noEmit` → exit 0; targeted eslint → exit 0.
- Locale: 6 new keys in both `features/live/locale.ts` and `locales/index.ts`; reviewer scan of the attachment files finds 0 missing keys.
- No backend change; `.github` change is only the core constant (154→161).

## 7. Verification executed / BLOCKED

Executed here: core suite 161/161; tsc; targeted eslint; static counts (24 browser cases, six screenshots unchanged, locale coverage). The browser gate is **BLOCKED** locally (Playwright `spawn EPERM`); no browser result is claimed. No backend tests are needed for this UI-only increment (no backend change).

## 8. CI artifacts that prove acceptance

| Criterion | Proof | Artifact |
| --- | --- | --- |
| State machine, duplicate suppression, stale-retry-once, source identity | `tests/core-conversation-attachment.test.mjs` (7 tests) | job `frontend`: `test-results/core-client.xml` (artifact `buyeros-core-client`, count 161) |
| Upload reuse/resume (one ingest across retry), sources PUT body/version, no optimistic state, viewer zero requests, zh-HK label | new browser scenario in `tests/conversation-home-responsive.test.mjs` (24 cases) | job `frontend`: `test-results/conversation-studio.xml` + `test-results/conversation-studio/*.png` (artifact `buyeros-conversation-studio`) |
| Regression: prior 23 cases untouched, six screenshots unchanged, tsc/lint | same browser + core artifacts; `pnpm lint`/`tsc` steps | job `frontend` |

**Unproven by any artifact**: archived direct-open behaviour (MAJOR-1), uploaded document's own context-panel status (MAJOR-2), abort-on-route-change of the sources PUT (MAJOR-3), uploader recoverable-vs-rejection classification (MAJOR-4), and hidden-on-`/new` (source-verified only).

## 9. Recommendations (owner: conversation-ui)

1. Fix archived detection (thread GET or preferences) and remove the false "archived never mounts" claim; add the direct-open test or document the limitation explicitly (MAJOR-1).
2. Refresh the context panel after attach (e.g. bump the SourcePicker read key / refetch project context on thread-source change) and strengthen the browser assertion to the uploaded document's status (MAJOR-2).
3. Keep one AbortController for the whole attach, pass a signal through `ConversationThreads.sources/get`, and abort on unmount/thread change (MAJOR-3).
4. Export typed uploader errors and classify retryable upload states as retryable (MAJOR-4).
5. Minors: derive `accept` from the uploader, allow attach on the home-loaded thread, monotonic progress, ref-based double-selection guard, localize uploader messages, and add the missing tests.

## 10. Not reviewed / out of scope

- No production deployment/promotion/Vercel changes; no implementation edits (only this document).
- Real provider/paid behaviour, production data and the browser runtime were not exercised here; the CI artifacts above are the substitute.
