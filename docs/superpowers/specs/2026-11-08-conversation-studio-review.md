# Conversation studio — independent review and QA evidence plan

Reviewer: `reliability` (independent of the implementation streams)
Date: 2026-11-08 (Asia/Singapore)
Worktree: `C:\Users\laich\Documents\BuyerOS\.worktrees\conv-studio` (branch `feat/conversation-studio`, draft PR #57)
Reviewed source: `e651fee8a` (last reviewed release) plus the uncommitted conversation-studio change set and commit `a3696c89a`.
Scope: backend turn engine/parts/decisions/migration/task-4 lock-scope change; frontend conversation studio; QA evidence plan. **No implementation files were modified by this review.**

Snapshot note: findings and line numbers refer to the change set as reviewed (2026-11-08 ~18:20–18:29 SGT). The owning streams are landing fixes for the reported findings concurrently, so line numbers can move before the final commit; re-run the cited tests against the final SHA. Reviewer re-verification on the tree at 18:29 SGT (after some fixes landed): core suite 123/123, `tsc --noEmit` exit 0, targeted eslint exit 0.

## 0. Verification legend (used throughout)

- **[READ]** verified by reading the source at the cited `file:line`.
- **[TEST]** verified by a test I executed in this sandbox (frontend `node:test` only — see §6).
- **[BLOCKED]** could not be verified here: Docker named pipe is denied by the sandbox (`docker ps` → permission denied), the uv cache is read-only and `uv run --offline` cannot create a Python env, and Playwright browser launch fails with `spawn EPERM`. DB-backed pytest and all browser tests are BLOCKED for me; they are executable in CI.
- **[ROUTED]** reported to the Lead and routed to the owning stream.

## 1. Findings summary

| Id | Severity | Finding | Evidence | Status |
| --- | --- | --- | --- | --- |
| BLOCKER-1 | Blocker (contract + CI) | Durable idempotency replay is unreachable for existing-thread turns, decisions and cancel: the thread-version precondition runs before the replay lookup, so a lost-response retry with the same key/version gets `409 STALE_REVISION` instead of the recorded result. | `services/conversation_turns.py:405` (before `:409`), `:586` (before `:599`), `:758` (before `:761`); `services/sales_tasks.py:144` + `conversation_turns.py:566` bump the version; API tests that assert replay at `tests/test_conversation_turns_api.py:201-203,231-234,280-283` should fail | [READ] [ROUTED] |
| BLOCKER-2 | Blocker (state machine) | A failed decision execution returns before the decision row/proposal status are written (`_finish_failure` early return), so the same proposal can be approved repeatedly and a partially persisted sales task can exist with no decision record. | `services/conversation_turns.py:676-686` vs `:687-711`; partial task write at `:492`/`:516` via `sales_tasks.py:103-145` | [READ] [ROUTED] |
| CI-1 | Blocker (CI) | Core-test count gate hard-coded 86; suite now runs 123 node:test cases. | `.github/workflows/buyeros-ci.yml:63`; executed suite: 123/123 pass (§6) | [TEST] [ROUTED] (Lead bumped to 123) |
| MAJOR-A | Major (rollback) | Migration 0066 adds `seq` NOT NULL without a server default to `conversation_thread_messages`; the previous app version's INSERTs fail after the migration, so an application rollback breaks thread append. Downgrade drops `role`/`parts` silently for populated message rows (guard covers only the three new tables). | `alembic/versions/0066_conversation_turns.py:159-180`, `:270-287` | [READ] [ROUTED] |
| MAJOR-B | Major (deploy) | `worker_recovery.set_execution_runtime` replaced `0065_sales_lifecycle` with `0066_conversation_turns` instead of appending; a DB still at the current production head 0065 is rejected. | `services/worker_recovery.py:236` | [READ] [ROUTED] |
| MAJOR-C | Major (contention) | Task-4 is only half done for `native-sources`: the initial budget gate is gone, but the per-source policy evaluation still takes `pg_advisory_xact_lock` inside the read transaction and holds it until commit across the whole enumeration. | `api/routes/sales_tasks.py:35-49` → `sales/native_sources.py:61` → `services/policy_service.py:113-116,142`; `conversation_access.py:48-50` | [READ] [ROUTED] |
| MINOR-1 | Minor (concurrency) | Concurrent duplicate new-thread requests (same `client_message_id`, different keys): the loser's IntegrityError path compares the winner fingerprint against a fingerprint built with the loser's rolled-back thread id and returns `409 IDEMPOTENCY_CONFLICT` "belongs to a different turn request" instead of replaying. Exactly-once still holds (unique index + rollback); a later retry replays correctly. | `services/conversation_turns.py:424-434,458-469`; unique index `db/conversation_turns.py:21-22`, migration `:203-205` | [READ] |
| MINOR-2 | Minor (limits) | Continuation turns (`_continuation_turn`) do not check `MAX_THREAD_MESSAGES`, so a decision/cancel can push a thread past the 100-message limit by one. | `services/conversation_turns.py:304-307,544-569` | [READ] |
| MINOR-3 | Minor (defence in depth) | Decision-replay lookup is scoped by `workspace_id + proposal_id` only (no `project_id`/`thread_id`); turn sequence/user-text helpers filter by `thread_id`/`turn_id` only (ids always come from scoped loads). No exploitable cross-tenant path found; composite filters would harden it. | `services/conversation_turns.py:611-613,298-301,536-541` | [READ] |
| MINOR-4 | Minor (500 edge) | Existing-decision replay does not null-check the continuation turn (`_payload(row)` with `row=None` → AttributeError/500 if rows are inconsistent). | `services/conversation_turns.py:611-619` | [READ] |
| MINOR-5 | Minor (hardening) | The DB parts CHECK validates key sets/types/lengths but not the `href` pattern for citations/output_link/recovery (pydantic and the client do). A future writer bypassing the API could store a non-`/app` href in JSONB. | `alembic/versions/0066_conversation_turns.py:65-74,102-127` vs `sales/turn_contracts.py:52,102,107` | [READ] |
| MINOR-6 | Minor (audit) | New turn/decision mutations write no `append_audit` row (existing thread create/rename/sources do). No product requirement found, but the decision trail is only in `conversation_turn_decisions`. | `services/conversation_turns.py:739-745` | [READ] |
| GAP-1 | Major (QA) | No browser/API assertion that a skill chip sends `skill_id` in the turn body; chip mapping is only readable in source. | `features/live/conversation/studio.tsx:82-85,206-209`; `composer.tsx:59-61`; `tests/conversation-home-responsive.test.mjs` has no chip click | [READ] |
| GAP-2 | Major (QA) | No studio browser row for permission failure (403/404 on thread load, send or decision); the old-surface revoke test is the only coverage. | `tests/conversation-home-responsive.test.mjs:171-343` has no 403 row; backend `test_share_revocation…` BLOCKED | [READ] |
| GAP-3 | Minor (QA) | No committed locale-coverage test for the new conversation surface; I scanned it (0 missing keys) but the repo has no test that will catch a regression. | `features/live/conversation/**`, `services/live/conversation-turn.ts` scan §6 | [TEST] (reviewer scan) |

No open blocker-level **security** defect was found: approval cannot be bypassed, tenant isolation holds in every new query I read, and no paid/provider dispatch is reachable from a turn (§3).

## 2. Tenant isolation — proof table (all [READ])

Every new/changed query is tenant-scoped. `TenantMixin` supplies a non-null `workspace_id` (`db/base.py:41-47`); all three new tables are RLS-forced with a workspace policy (`alembic/versions/0066_conversation_turns.py:258-265`) and `tenant_session` sets `app.workspace_id` for the transaction (`db/session.py:21-30`). The table below covers application-level WHERE clauses as well.

| Query | File:line | Scope predicates | Verdict |
| --- | --- | --- | --- |
| existing turn by client message (durable replay) | `services/conversation_turns.py:274-279` | `workspace_id`, `project_id`, `actor_id`, `client_message_id` | scoped |
| turn by id (replay/decision/cancel) | `:282-286` | `workspace_id`, `project_id`, `id`; caller then `load()` thread ACL | scoped |
| replay thread load | `:289-295` via `conversation_access.load` (`:67-79`) | workspace+project thread + owner/share role | scoped |
| project existence (every turn) | `:266-271` | `workspace_id`, `project_id`, `status='active'` | scoped |
| message count / next seq | `:304-307`, `:298-301` | `workspace_id` + `thread_id` (seq: thread id only, from scoped thread) | scoped (MINOR-3 hardening) |
| user message text for execution | `:536-541` | `workspace_id`, `turn_id`, `role='user'` | scoped (MINOR-3) |
| thread messages read model | `api/routes/conversation_threads.py:104-117,120-127` | `workspace_id` + `thread_id` of ACL-loaded row; ordered by `seq` | scoped |
| message append | `:234-252` | ACL `load(edit=True, lock=True)` + `workspace_id`/`thread_id` | scoped, thread-row locked |
| proposal lookup for a decision | `services/conversation_turns.py:587-592` | `workspace_id`, `project_id`, `thread_id`, `turn_id`, `id`, `FOR UPDATE` | scoped |
| existing decision (unique per proposal) | `:611-613` | `workspace_id`, `proposal_id` (proposal id is uuid5 of the scoped thread) | scoped (MINOR-3) |
| cancel proposal sweep | `:774-779` | `workspace_id`, `project_id`, `thread_id`, `turn_id`, `status='proposed'` | scoped |
| proposal/decision/turn inserts | `:356-395`, `:741-745` | workspace/project from authenticated `Scope`; composite FKs include `workspace_id`+`project_id` (`db/conversation_turns.py:23-28,53-55,85-93`) | scoped |
| thread create + first message (turn-first) | `:427-434` | workspace/project from scope; new thread owned by actor | scoped |
| grounding sources | `:310-324` → `conversation_reply.resolve_sources` (`:36-117`) | project re-read by workspace+project; only current approved profile/facts/documents; Drive path via approved sources | scoped |

Foreign-id probes that were considered and rejected as leaks: decision `proposal_id` from another workspace (workspace filter), another project in the same workspace (proposal ids are uuid5 of a random thread id; additionally the thread ACL is rechecked), turn id from another tenant (`workspace_id` filter + RLS). `_existing_turn` is actor-scoped, so one user's `client_message_id` cannot replay another user's turn.

## 3. Approval, replay, decision-time revalidation, provider reachability

### 3.1 Approval cannot be bypassed [READ]

- A turn can only **propose**: `build_plan` creates a `ProposalPart` + a `proposed` row (`services/conversation_turns.py:172-234,382-391`); the only executor dispatch is `_apply_decision`, reachable only from `decide()` (`:580-637`), which is only exposed by `POST …/conversation-turns/{turn_id}/decisions` (`api/routes/conversation_turns.py:58-75`).
- `proposal.requires_approval` is DB-pinned `true` (`db/conversation_turns.py:72`; migration `:223,229`; contract `sales/turn_contracts.py:87`).
- Decision uniqueness is enforced twice: `UNIQUE(workspace_id, proposal_id)` (`db/conversation_turns.py:83`; migration `:244`) plus the application check (`conversation_turns.py:611-621`). A second, different decision is `409 ALREADY_DECIDED`; a same-decision replay returns the recorded continuation.
- Executors are a code-owned allowlist (`EXECUTORS`, `:43,533`) and the proposal capability is constrained by `CAPABILITY_BY_SKILL` (`:38-42`) and the skill registry (`:128-133`). Client text, model text and stored arguments cannot add a capability.
- Viewer/revoked share cannot decide: `load(edit=True)` rejects them (`conversation_access.py:67-79`); the route re-resolves current membership (`:44-56`). API test coverage exists but is BLOCKED here (`test_share_revocation…`).
- BLOCKER-1 and BLOCKER-2 above are the two real gaps in this area; neither allows a proposal to execute without an authenticated approve decision (they affect replay/audit semantics, not authorization).

### 3.2 Decision-time revalidation [READ]

`_apply_decision` re-reads the project (active) and rechecks sales admission and language before any execution (`:660-668`), then takes the current policy+budget gates (`:669-670`), then re-resolves the allowlisted executor (`:671-675`). The typed executors revalidate source authority and current policy through `create_task` → `resolve_context` (`services/sales_tasks.py:103-145,159`; `sales/context.py:58-69`; `require_scope` `:32-38`) and through `save_output` (`services/sales_outputs.py:286-331`). Budget: the two registered capabilities are `nonbillable` (`:232-233`), no reservation is created, and the gates are still taken. **No test of the decision-time policy/budget revalidation was executed** (DB BLOCKED); the API test `test_disabled_admission_returns_notice_and_executes_nothing_then_can_resume` covers the admission half only.

### 3.3 No reachable provider/paid dispatch from a turn [READ]

- The answer step is fail-closed: `model_answer` → `reply_from_grounding(grounding)` raises `503 CONVERSATION_MODEL_UNAVAILABLE` when no fixture adapter is injected (`services/conversation_reply.py:120-127`); `ROUTE` has `route_id=None` ("deliberately unselected, no live call", `:14-16`). Tests monkeypatch `conversation_turns.model_answer` only (`tests/test_conversation_turns_unit.py:138-161`, API fixture `:332-352`).
- Executors read existing canonical records only: `create_task`/`assemble_or_core`/`save_output`; `_execute_research` returns `NEEDS_NATIVE_PREREQUISITE` instead of starting a run (`conversation_turns.py:506-530`). No `providers.xverum_mcp`, `xverum_dispatch.dispatch`, `drive_mcp`, job/outbox creation appears in the turn service (only `gates` is imported, `:669`).
- API test asserts no `xverum_stages` and no `budget_reservations` for an approved turn (`tests/test_conversation_turns_api.py:204-216`) — BLOCKED here.
- Real Xverum/Drive/paid acceptance remains **BLOCKED** (no credentials/admission; and the turn engine deliberately has no such path).

### 3.4 Idempotency and concurrency [READ]

- Exactly-once append identity: deterministic turn id `uuid5(thread, client_message_id)` (`:351-355`), `UNIQUE(workspace_id, thread_id, client_message_id)` (`db/conversation_turns.py:20`; migration `:197`), partial unique actor index (`:21-22`; migration `:203-205`), message unique index (`migration :178-180`), plus `begin_idempotency` on the `Idempotency-Key` (`:416-423`, `api/idempotency.py:40-98`).
- New-thread concurrency (same `client_message_id`, two requests): both may pass the pre-check, the unique turn index blocks one; the savepoint rolls its thread back; the handler re-reads the winner and replays. Two threads cannot be committed. MINOR-1 is the only inconsistency (loser gets a conflict instead of a replay in that exact interleaving; a subsequent retry replays).
- Existing-thread append concurrency: the thread row is `FOR UPDATE`-locked (`conversation_access.py:70-71`), version precondition then fails the stale writer (`:405`) and sequence allocation is serialized (`:298-301,368-381`); `append` also locks (`api/routes/conversation_threads.py:237-248`).
- BLOCKER-1: replay after a lost response is broken by ordering (see summary). No double-append or double-execution results from it.
- The API tests for duplicate replay/conflict and version guards exist (`tests/test_conversation_turns_api.py:128-179`) but are BLOCKED here; per BLOCKER-1 some replay assertions are expected to fail.

### 3.5 Parts and message validation [READ]

- Request/part models are `extra="forbid"`, frozen (`sales/turn_contracts.py:38-39`); bounded `Text`/`ShortText`/`Code` (`:18-20`), bounded part lists (`MAX_MESSAGE_PARTS=24`, `:34-35,157-158`), discriminated union of six kinds (`:117-120`), strict citation `href` allowlist (`:52`), bounded `arguments_preview` (`:85`), `requires_approval: Literal[True]` (`:87`), output kinds allowlisted (`:28-32,90-102`).
- Persisted parts are re-validated on read (`validate_part_list`, `:193-196`) and defended in the database by `buyeros_turn_parts_valid` / `buyeros_turn_notices_valid` (key-set equality, type, length and count bounds; migration `:45-157`) plus table CHECKs (`migration :173-175,193-194`).
- Model/provider output cannot inject authority: the fixture adapter accepts exactly `{text,citations,status,fixture}`, requires `status='needs_review'`, `fixture=True`, and every citation must already be in the server-built grounding list (`conversation_reply.py:120-138`). `answer_parts` then builds citation items from grounding ids/labels, never from candidate fields (`conversation_turns.py:95-121,84-92`). Proposal arguments/source refs are server-built (`:222-234`), not model-built.
- Unknown part kinds: server read rejects them (DB CHECK prevents persistence); the client maps unknown kinds to a quiet `unsupported` marker and degrades unknown roles to the safer reading (`features/live/conversation/types.ts:84-158,170-174`; `inline-parts.tsx:112-127`). [TEST] `tests/core-conversation-parts.test.mjs` covers the reducer/unknown-part behaviour.
- MINOR-5 is the only hardening gap (DB does not pattern-check `href`).

## 4. Task-4 lock-scope review [READ]

`access()` now resolves membership + role + rate limit **before** any workspace advisory gate and only takes the gates for sales callers unless `locks=False` is explicit (`services/conversation_access.py:21-56`, ordering at `:43-50`). I mapped **every** `access()` caller in the four touched route files:

| Route class | Lock mode | Result |
| --- | --- | --- |
| All `GET` sales/sales-output/xverum routes (capability, native-sources, skills, task/output reads, connections, quotes, receipts, candidates, stages, liability) | `locks=False` | no policy/budget gate taken by `access()` |
| All `POST`/`PUT`/`PATCH` sales/sales-output/xverum routes (create task, cancel, followups, reviews, admit, execution-preview, exports, formal-draft, native-actions, save output, enrichment create/apply, connection assignment/rotate/disconnect, quote create/approve, reconcile, receipt cancel, stage quote approve) | default (`locks=None`) | policy+budget gates kept |
| `POST /conversation-turns` | non-sales `access()` (transcript write; no policy/budget decision) | no gates — reviewed as intentional: it only appends messages/proposals and cannot execute |
| `POST /conversation-turns/{id}/decisions`, `…/cancel` | sales default | gates kept, and `_apply_decision` re-takes `gates()` before execution (`conversation_turns.py:669-670`) |

- No admission/mutation/dispatch gate was removed; only the serialization scope of reviewed read routes was narrowed. Tenant scoping in `load()`/`thread_scope` is unchanged (`conversation_access.py:59-79`).
- Unauthorised/throttled callers fail before lock acquisition by construction (membership/rate before gates, `:43-50`); `tests/test_sales_lock_scope.py` pins this and the route wiring, but it is **BLOCKED** here (no Python env).
- **MAJOR-C** is the residual: `native-sources` still acquires the policy advisory lock per source via `evaluate_current_policy` and holds it to commit, so paid admission/mutation can still queue behind a long enumeration. The budget gate is no longer held by that read.
- Yellow flag (unchanged): `enforce_rate_limit` opens a second pooled connection inside the outer request transaction (`services/api_rate_limit.py:57-60`), now at least before any workspace gate.

## 5. Frontend review [READ unless marked]

| Check | Evidence | Verdict |
| --- | --- | --- |
| `internalHref` allowlist / open redirect / `javascript:` | `features/live/conversation/types.ts:64-70`: requires `/app` prefix (exact, `/app/`, or `/app?`), rejects `//`, control chars and backslashes; used for citation/output/recovery links (`:109,142,71-75`) and all navigation goes through the app router (`navigate` in `workspace-picker.tsx:255-262` builds a same-origin URL) | safe; `javascript:`/protocol-relative/foreign URLs are dropped. [TEST] `tests/core-conversation-parts.test.mjs` asserts `/app` allowed and `https:`, `javascript:`, `//evil`, `/app\evil`, null rejected |
| XSS on parts | No `dangerouslySetInnerHTML`/`innerHTML`/`eval` in `features/live/conversation/**` or `services/live/conversation-turn.ts` (reviewer grep); every part renders as React children (`inline-parts.tsx:112-127`), model preview data is primitives-only with a depth cap and sensitive-key filter (`:42-57`) | safe |
| Token/secret handling in browser | No token persisted; token is read from `session` in memory and passed to `client.request` only (`studio.tsx:60,129`; `conversation-turn.ts:81,98-120`). Draft storage holds only text + `client_message_id` | safe |
| Draft scoping | Key = actor+workspace+project+thread (`draft.ts:19-21`), versioned, bounded (16 KiB, 4 000 chars), id reused only while attempt text is unchanged (`:28-49`), storage failures degrade to tab-only (`:54-94`). [TEST] `tests/core-conversation-draft.test.mjs`; browser reload/scope row `conversation-home-responsive.test.mjs:269-290` (CI-only, BLOCKED here) | correct |
| Approval requires explicit user action | Buttons only, no auto-approval: `inline-parts.tsx:80-96`, `context-panel.tsx:108-125`, callbacks into `studio.tsx:279-294`; UI state machine hides/disables decisions for viewer/decided/unknown (`approval.ts:13-40`); server re-authorizes regardless | correct |
| Honest loading/disabled/unavailable | Capability probe states `checking/available/absent/unavailable` with retry (`conversation-turn.ts:89-112`; `studio.tsx:116,195-202`; `composer.tsx:54-58`); thread load states `loading/reloading/ready/missing/unavailable` with retry (`studio.tsx:164-180,362-366`); send failures keep the draft and show a retry with the same client id (`composer.tsx:39-51,70`); no fabricated parts on fallback (`studio.tsx:249-277`). Entry capability (task-1) stays explicit in `sales-skills/capability.ts` + `workspace-picker.tsx` | honest |
| Accessibility | Transcript `role="log" aria-live="polite"` and status live region (`transcript.tsx:59,80`); keyboard Enter/Shift+Enter (`composer.tsx:49-51`); Escape closes mobile drawers (`studio.tsx:323-326`); labelled tablist/panel (`context-panel.tsx:129-141`); sr-only labels; visible focus comes from shared styles | present; focus visibility not programmatically asserted (GAP minor) |
| No duplicate first message on new-thread flow | First send passes `threadId:null`, server creates thread+message atomically, client navigates after the response (`studio.tsx:240-248`; `conversation-turn.ts:123-143`); no pre-create+turn path. Browser assertion one POST, no `thread_id`, text once (`conversation-home-responsive.test.mjs:221-232`) | correct; server side depends on BLOCKER-1 only for retries |
| Request dedup preserved | Turn client single-flight per exact payload via `ActionIntent` (`conversation-turn.ts:84-88,138-167`); thread list/thread reads are one-per-target (`studio.tsx:132-180`); capability single-flight (task-1). SourcePicker re-reads per thread (not per rerender) and does not abort on unmount (`context-panel.tsx:58-66`) — minor | mostly correct |
| Minor frontend notes | capability probe treats any non-404 4xx as `available` (401/403/405) (`conversation-turn.ts:100-108`) → a session/permission problem shows as a send/decide error notice rather than "unavailable"; acceptable but slightly optimistic. SourcePicker read is not aborted on unmount. No committed locale test for the new surface (GAP-3) | minor |

## 6. Verification actually executed in this sandbox

Executed (bundled Node v24; sandbox blocks `node --test` child spawn so `--experimental-test-isolation=none` was used, same as `scripts/test-core.mjs`):

- `node --test --experimental-test-isolation=none tests/core-*.test.mjs tests/audit-research-intent.test.mjs` → **123 tests, 123 pass, 0 fail** (includes `core-conversation-approval/draft/parts/turn` and the task-1 capability/source tests).
- Targeted eslint on the new conversation files, changed discussion/shell files, `services/live/conversation-turn.ts` and the new tests → 0 errors, 1 warning (`postsTo` unused in the browser test; warnings do not fail `pnpm lint`).
- Repo-wide `eslint . --ignore-pattern …` (same arguments as `pnpm lint`) → exit 0 after excluding the sandbox-unreadable local `services/api/pytest-cache-files-*` directories (not present in CI).
- `tsc --noEmit -p tsconfig.json` → exit 0.
- Reviewer scan: all `t('…')` literals in `features/live/conversation/**`, `services/live/conversation-turn.ts`, `shell.tsx`, `discussion-workspace.tsx`, `discussion-server.tsx` have EN/zh-HK entries in `liveZh`/`zh` (0 missing). This is a scan, not a committed test (GAP-3).

BLOCKED in this sandbox (executable in CI):
- All DB-backed pytest (`test_conversation_turns_api.py`, `test_conversation_threads_api.py`, `test_sales_tasks_api.py`, `test_sales_lock_scope.py` is env-dependent, migration/RLS tests). `docker ps` → named-pipe permission denied; `uv run --offline` cannot initialise the read-only uv cache. **No backend test result is claimed by this review.**
- All Playwright/node browser tests, including the new studio gate in `tests/conversation-home-responsive.test.mjs` (browser launch `spawn EPERM`).

## 7. QA evidence matrix (CI acceptance contract)

Artifacts (as updated by the Lead): `test-results/conversation-studio.xml` (new junit for the studio gate), `test-results/conversation-studio/*.png` (screenshots), `test-results/core-client.xml` (core node:test, count gate now 123), plus normal CI logs. “Mocked” = browser fixture intercepts `/v1/**` (`tests/conversation-home-responsive.test.mjs:153-161`); no real provider or DB is involved.

| # | Flow | Exact assertion (CI test) | Mode | Artifact that proves it | What remains unproven |
| --- | --- | --- | --- | --- | --- |
| 1 | New discussion multi-turn | `/app/discussions/new` send → exactly one `POST /conversation-turns` with no `thread_id`/`expected_thread_version`, text once in transcript, navigates to `/app/discussions/s/<newThreadId>`; follow-up send appends one turn (`conversation-home-responsive.test.mjs:210-248`) | mocked | `conversation-studio.xml` + `home-desktop.png` | DB atomicity/unique-index behaviour under real concurrency (BLOCKED); BLOCKER-1 affects retry of an existing-thread turn |
| 2 | Skill invocation from composer | **No assertion today (GAP-1).** Add: click a chip → next turn `POST` body has `skill_id` from the code-owned registry and no form-only fields; unknown skill cannot be submitted (`studio.tsx:82-85,206-209`) | mocked | to add | actual registry/skill admission with real backend (BLOCKED) |
| 3 | Approval + inline result | One Approve/Reject card; exactly one decision POST with `{proposal_id, decision, expected_thread_version}`; approved notice; inline tool_activity state and output_link render (`:171-208`) | mocked | `conversation-studio.xml` + `transcript-inline-parts-desktop.png`, `proposal-approval-desktop.png` | decision-time membership/policy/budget revalidation and one-decision-per-proposal at DB level (BLOCKED; BLOCKER-2 needs fix first) |
| 4 | Save/reopen output | Output link navigates to `/app/documents/<id>`; backend API test asserts one saved output revision and no provider stage/reservation (`test_conversation_turns_api.py:204-216`) — BLOCKED | mocked (browser) / DB (BLOCKED) | `conversation-studio.xml`; DB junit **missing** | persisted revision content/reopen from a real DB; canonical output permissions (BLOCKED) |
| 5 | Reload resume | Reload renders the same persisted parts and issues **no** turn replay (`:196-200`); unsent draft survives in-app navigation and reload, clears on project switch and returns on switch-back (`:269-290`) | mocked | `conversation-studio.xml` | real server thread re-read with persisted parts (BLOCKED) |
| 6 | Unavailable tool/endpoint | OPTIONS 404 → `Notes only`, one append, no fabricated tool activity (`:250-267`); flag OFF renders legacy shell and performs zero conversation reads (`:322-330`) | mocked | `conversation-studio.xml` | real flag-off router/middleware 404 and real DB note append (BLOCKED) |
| 7 | Interrupted response | 503 on send keeps draft + unconfirmed notice; retry reuses the same `client_message_id` and same `Idempotency-Key` (`:233-244`) | mocked | `conversation-studio.xml` | server-side replay semantics (BLOCKER-1 must be fixed and this row re-run against the API tests) |
| 8 | Permission failure | **No studio row (GAP-2).** Add: thread GET 403/404 → `unavailable`/`missing` panel with retry; decision 403 → forbidden notice, proposal still visible; revoke mid-session hides actions | mocked | to add | server ACL/revocation tests (BLOCKED) |
| 9 | Duplicate-write prevention | First message exists exactly once; retry keeps same client id/key (`:222-244`); backend duplicate replay/conflict/version tests exist (`test_conversation_turns_api.py:128-179`) — BLOCKED | mocked + DB (BLOCKED) | `conversation-studio.xml`; DB junit **missing** | true concurrent duplicate requests (no test anywhere; MINOR-1) and BLOCKER-1 retry path |
| 10 | Responsive + mobile views | No horizontal overflow at 320–1440; conversation/threads/context are separate mobile views; Escape returns to conversation; Guided setup + Device discussions reachable (`:292-320`) | mocked | `mobile-390.png` + `conversation-studio.xml` | 200% zoom/keyboard focus order not programmatically asserted |
| 11 | EN/zh-HK | Approve/Reject labels translate (`:201-205`); locale scan 0 missing keys | mocked | `zh-hk-desktop.png` | committed locale regression test (GAP-3) |
| 12 | Device-only discussions stay local | Device discussion note saves without network and uses local storage only (`:331-343`) | mocked | `conversation-studio.xml` | none material |
| 13 | Tenant isolation / RLS / migration | DB tests (`test_conversation_turns_api.py` foreign-workspace row; RLS tests) and upgrade/downgrade tests | DB | **none produced yet** | BLOCKED here: all DB-level isolation, RLS, migration and lock-scope evidence |
| 14 | Real provider acceptance (Xverum paid search/enrichment, Drive) | — | real | **none** | BLOCKED by design/credentials: turn engine has no paid dispatch; existing provider acceptance is a separate release gate |

## 8. Residual risks / recommended follow-ups

1. Fix BLOCKER-1 (replay before version precondition) and add a regression test that replays an existing-thread turn, an approve and a cancel with the original expected version + same key; then re-run `test_conversation_turns_api.py` (currently expected red).
2. Fix BLOCKER-2 (persist failed/unknown decision + proposal status, or roll back partial executor writes) and add a failure-path DB test.
3. Fix MAJOR-A: either give `seq` a safe server default / keep the old writer compatible, or make the release procedure forbid app rollback across 0066 and document that downgrade loses parts; add a migration round-trip test with populated legacy messages.
4. Fix MAJOR-B: append `0065_sales_lifecycle` back to the compatible revision set.
5. Finish MAJOR-C: native-sources per-source validation outside the workspace lock (read-only snapshot or paging).
6. Close GAP-1/GAP-2/GAP-3 (skill_id browser row, permission-failure browser row, committed locale-coverage test) and keep the browser junit/artifact upload the Lead added.
7. Minor hardening: composite scope filters in MINOR-3, null-check MINOR-4, href CHECK in MINOR-5, audit rows in MINOR-6, continuation message-limit check MINOR-2, concurrency replay message MINOR-1.

## 9. Not reviewed / out of scope

- No production deployment, promotion or Vercel settings were touched.
- No implementation code was changed by this review; the only file written is this document.
- Real-provider behaviour, production data and the browser runtime were not exercised (sandbox); the QA matrix above is the CI-executable substitute.
