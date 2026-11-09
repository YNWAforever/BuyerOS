# Increment C review — streamed turn events and reconciliation

Reviewer: `reliability` (independent of the implementation streams)
Date: 2026-11-09 (Asia/Singapore)
Worktree: `C:\Users\laich\Documents\BuyerOS\.worktrees\conv-studio`, branch `feat/conversation-streaming`, commit `89efa1eeb` (stacked on `feat/conversation-studio`).
Contract: `docs/superpowers/specs/2026-11-09-streaming-turns-contract.md` plus the Increment A/B contracts.
Scope: `0068_conversation_turn_events`, event append/allocator, SSE endpoint, reconciliation, cancel semantics, frontend stream client/studio integration, and regression risk to the shipped gate. **No implementation file was modified by this review; the only file written is this document.**

Snapshot note: findings and line numbers refer to commit `89efa1eeb` as reviewed (2026-11-09 ~09:44–09:56 SGT). The owning streams began landing fixes for the reported findings while this review was being written (e.g. a `0069_conversation_turn_reconciliations` migration and edits to `conversation_turns.py`/`conversation_turn_recovery.py`/`stream-events.ts`/`conversation-turn.ts` appeared at ~09:55), so re-run the cited tests and re-check the findings against the final SHA. Reviewer re-verification on the tree at 09:56 SGT (partial fixes already present): core suite 133/133, `tsc --noEmit` exit 0.

Verification legend:
- **[READ]** verified by reading source at the cited `file:line`.
- **[TEST]** verified by a test executed in this sandbox (frontend `node:test`/tsc/lint only — see §7).
- **[BLOCKED]** PostgreSQL and browser execution are unavailable here: Docker's named pipe is denied by the sandbox (`docker ps` → permission denied), the uv cache is read-only so no Python env can be created, and Playwright launch fails with `spawn EPERM`. CI runs these; no DB/browser result is claimed by this review.
- **[ROUTED]** reported to the Lead/owning stream.

## 1. Findings summary

| Id | Severity | Finding | Evidence | Status |
| --- | --- | --- | --- | --- |
| BLOCKER-C1 | Blocker (CI, DB job) | New API test `test_reconcile_is_read_only_terminal_and_idempotent` asserts exactly one `conversation_turn.reconciled` audit row, but the third step (new Idempotency-Key on the still-`outcome_unknown` turn) re-runs `append_audit` after `_continuation_turn` returns the recorded continuation, producing a second audit row. | `services/api/tests/test_conversation_turns_api.py` (audit assertion in `test_reconcile_is_read_only_terminal_and_idempotent`); `services/conversation_turns.py:1187-1190` (dead `continuation_id` pre-check), `:1191-1197` (key replay), `:1200-1203` (status guard), `:1225-1233` (`_continuation_turn` early return), `:1236-1238` (unconditional audit) | [READ] [ROUTED] |
| MAJOR-C1 | Major (recovery semantics) | Reconciliation can never upgrade a recorded `unknown`: the deterministic continuation id used by the pre-check (`uuid5(turn,'conversation-turn-reconcile')`) never matches the id `_continuation_turn` creates (`uuid5(turn,'continuation:'+fingerprint)`), so a later reconcile re-probes but returns the first recorded continuation; the source turn also never leaves `outcome_unknown`. Different editors get different continuations (actor is in the fingerprint), so the same unknown turn can accumulate duplicate recovery records. | `services/conversation_turns.py:1184-1190,1225-1233`; contract §4 ("persists the resolved outcome completed/failed/stays outcome_unknown"; "idempotent replay returns the recorded continuation/result") | [READ] [ROUTED] |
| MAJOR-C2 | Major (QA obligation) | Contract §6 requires a DB test that append is "ordered/unique under concurrent writers". No such test exists. Safety is currently an invariant of every caller holding the discussion row lock (`create_turn`, `decide`, `cancel_turn`, `reconcile_turn`); `next_turn_event_seq` alone is not concurrency-safe, so a future caller that appends without the thread lock reintroduces the previous UniqueViolation class. | `services/conversation_turn_events.py:46-53`; lock sites `conversation_turns.py:588-590,883-884,1086-1087,1182-1183`; `services/api/tests/test_conversation_turn_events_db.py` (allocator/unique tests only, no concurrent writer) | [READ] |
| MAJOR-C3 | Major (QA fidelity) | The browser "progressive render" fixture returns a POST thread **without** the persisted assistant message, while the real turn/decision responses always include the persisted assistant message with parts in the same response. In production the persisted-parts-win branch therefore suppresses the provisional entry immediately, so the "progressive render" row proves a response shape the backend never returns. Likewise the reconcile browser row raises `outcome_unknown` from a turn POST, but production only produces it from a decision continuation. | `tests/conversation-home-responsive.test.mjs:585-598` (pending thread user-only), `:677-706`; real responses `api/routes/conversation_turns.py:100-103,119-123`; `services/conversation_turns.py:662-689,1022-1031`; persisted-wins `features/live/conversation/parts.ts:161-172` | [READ] |
| MINOR-C1 | Minor (client memory bound) | `SseParser` has no maximum buffer size; a frame that never terminates (or a proxy injecting garbage) grows `buffer` without bound until the stream ends. Task check 5 explicitly asks for "no unbounded stream memory". | `features/live/conversation/stream-events.ts:91-119` | [READ] |
| MINOR-C2 | Minor (bounded revocation window) | SSE ACL/membership is checked once when the route starts; the streaming generator does not re-check the thread ACL, so a share revoked mid-stream keeps receiving events until the 20 s deadline. Reconnects re-run the route check. | `api/routes/conversation_turns.py:41-68,146-156`; `services/conversation_turns.py:1159-1166` | [READ] |
| MINOR-C3 | Minor (client deadline) | The SSE fetch has no connect/headers timeout (only the caller abort signal); a stalled proxy before response headers can hang the client until the browser network stack errors. The 20 s bound exists only server-side. | `services/live/conversation-turn.ts:161-214` (`fetch` with parent signal only) | [READ] |
| MINOR-C4 | Minor (recovery discoverability) | `persistedOutcomeTurnId` returns on the last assistant entry only, so once a later turn exists, an earlier persisted `outcome_unknown` turn's recovery action disappears after reload. | `features/live/conversation/studio.tsx:239-252` | [READ] |
| MINOR-C5 | Minor (consistency) | Reconcile does not validate a thread-version precondition (the client sends If-Match; the route ignores it). Contract says it "requires the same write permission as a decision", and decisions require the strong precondition. Risk is low because reconcile is read-only + recorded. | `api/routes/conversation_turns.py:159-175`; client `services/live/conversation-turn.ts:274-285` | [READ] |
| MINOR-C6 | Minor (schema drift) | ORM metadata names the event unique constraint `uq_conversation_turn_events_turn_id_seq` (naming convention) while the migration creates the inline name `conversation_turn_events_turn_id_seq_key` (which the DB test asserts). Functional today, but autogenerate/readiness drift risk. | `db/conversation_turn_events.py:22-23` vs `alembic/versions/0068_conversation_turn_events.py:98-109` | [READ] |
| MINOR-C7 | Minor (latent recovery blind spot) | `_finish_failure` records `proposal.result.task_id=None` even when the executor persisted a sales task before raising; if that path ever produces `outcome_unknown` (today it records `failed`), the reconcile probe could never see the partial task. | `services/conversation_turns.py:1048-1066`; `services/conversation_turn_recovery.py:36-49` | [READ] |
| MINOR-C8 | Minor (coverage gaps) | No DB/API test asserts terminal events are emitted for decision/blocked/failure/unknown/cancel continuations (only reconcile and turn creation are asserted), no test for SSE heartbeat/deadline bounds or cross-workspace SSE 404, and no committed i18n test for the new labels. | `services/api/tests/test_conversation_turn_events_db.py`, `test_conversation_turns_api.py` streaming additions; `features/live/locale.ts` additions | [READ] |
| MINOR-C9 | Minor (style) | Unused `EVENT_KINDS` import in the event service. | `services/conversation_turn_events.py:17` | [READ] |

No blocker-level **security** defect found: approval remains explicit, SSE/reconcile are tenant-scoped, reconcile never dispatches, and no provider module is reachable from a turn.

## 2. Event durability (check 1)

**Append is inside the state transaction [READ].**
- Only writer is `append_turn_events` (`services/conversation_turn_events.py:85-97`); it is called from `create_turn` inside the same `session.begin_nested()` as the turn/message/status write (`conversation_turns.py:662-669`) and from `_continuation_turn` after the turn/message/thread flush (`:823-852`). Every continuation path funnels through `_continuation_turn`: reject `:960-974`, success `:1008-1032`, blocked `:1035-1045`, failure `:1048-1066`, unknown-outcome result (same success path with `kind='unknown'`), cancel `:1108-1147`, reconcile `:1223-1238`. There is no second event writer and no post-commit append.
- `build_turn_events` derives the terminal payload from the same `status` argument that is stored on `ConversationTurn.status` (`:56-82` vs `:833-840`), so `turn.final.status` and the persisted turn status cannot disagree within a transaction. Replays (`_existing_turn`, idempotency records, `_recorded_cancellation`, existing decisions) return recorded payloads without re-appending.
- Failure semantics: if payload validation or the insert raises, the surrounding savepoint rolls back the turn/parts/status together with the events (DB test `test_terminal_event_and_turn_status_require_one_transaction` simulates this at the SQL layer — BLOCKED here).

**Sequence allocation [READ].** `next_turn_event_seq` calls `session.flush()` first, then `max(seq)+1` scoped by workspace+turn (`:46-53`), so pending rows from the same transaction are visible and no repeated seq can be allocated within one append loop. `UNIQUE(turn_id, seq)` backs it in the migration (`:101-106`). Cross-transaction ordering relies on the discussion row lock held by all callers (sites above); that invariant is not tested under real concurrency (MAJOR-C2).

**Tenant scope / RLS / grants [READ].** Table carries `workspace_id, project_id, thread_id, turn_id` with a composite FK to `conversation_turns` (`db/conversation_turn_events.py:20-38`); RLS is forced with a `current_setting('app.workspace_id')` policy; `REVOKE ALL` from PUBLIC/api/worker then `GRANT SELECT,INSERT` to the API role only (`0068:113-120`). No UPDATE/DELETE grant; downgrade refuses while events exist (`:124-132`). Schema readiness includes the table for API, excludes it for the worker (`schema_readiness.py` relations/worker pop, `:140-145,167-175`), and the readiness head list/worker recovery allowlist both append 0068 (worker recovery also keeps 0065/0066/0067 — the earlier replacement defect is fixed). Event payloads are bounded: 32 KiB total plus strict per-kind pydantic models (`turn_contracts.py:173-216`, `conversation_turn_events.py:34-42`) and a DB validator with key-set equality and per-kind bounds (`0068:42-94`).

## 3. SSE endpoint (check 2)

**Semantics [READ].** `GET …/conversation-turns/{turn_id}/events?after=<seq>` (`api/routes/conversation_turns.py:146-156`):
- ACL first: `access(...)` (conversation-home flag, membership, live-read switch) then `service.stream_turn` (turn scoped workspace+project; thread ACL owner/editor/viewer — `conversation_turns.py:1159-1166`). A turn outside the workspace/project is `404`; a non-shared thread is `404`.
- `after` is `Query(0, ge=0)`: negative/non-integer → `422`.
- `text/event-stream`; headers `Cache-Control: no-store`, `X-Accel-Buffering: no`.
- The generator reads `seq > after` ordered by seq (`conversation_turn_events.py:100-106`) in a fresh tenant session per poll, yields each frame, and returns on `turn.final`. Terminal turn without persisted events returns immediately (client refetch fallback).
- Bounded: 0.25 s poll, 5 s heartbeat comment, 20 s deadline (`routes:27-29,41-68`).
- Read-only: the endpoint never runs a turn, dispatches, or mutates; every event is derived data.
- Payloads contain `seq, turn_id, kind, payload` only; payloads are the validated persisted part/notice/tool/proposal shapes — no tokens or foreign data. Scoping is workspace+project+turn with forced RLS.
- Reconnect with the last seen seq replays exactly `seq > after`, so no duplicates server-side; the client additionally drops `seq <= cursor` (`stream-events.ts:35-37`; `conversation-turn.ts:196-205`).

**Gaps.** No test exercises heartbeat/deadline (MINOR-C8). No cross-workspace SSE 404 test (random-uuid 404 exists). Mid-stream revocation is bounded by the 20 s deadline but not rechecked (MINOR-C2).

## 4. Reconciliation (check 3)

**Accepted semantics [READ].** `POST …/{turn_id}/reconcile` (`routes:159-175`) requires an Idempotency-Key, takes no body, and runs with the sales mutation access mode (membership revalidated, policy+budget serialized). `reconcile_turn` (`conversation_turns.py:1169-1238`): scoped turn lookup → ACL `load(edit=True, lock=True)` → idempotency record → `409 INVALID_STATE` unless the turn is `outcome_unknown` → read-only probe → continuation turn + events + audit → replay returns the recorded continuation.

**Read-only proof [READ].** The probe (`conversation_turn_recovery.py:16-67`) reads only `ConversationTurnProposal.result`, `SalesTask` and `SalesOutput` scoped by workspace+project+thread; it imports no provider/transport module and constructs nothing. No stage/quote/receipt/reservation/outbox is created; the only writes are the recorded continuation turn/message/events, the audit row and the idempotency record. The API test monkeypatches `xverum_mcp.XverumTransport` to fail if constructed (BLOCKED here, but the source path has no such import).

**Defects.** BLOCKER-C1 (audit duplicate → new test red) and MAJOR-C1 (recorded-unknown can never be upgraded; dead continuation-id pre-check; actor-scoped duplicate recovery records; source turn stays `outcome_unknown`). MINOR-C5 (no version precondition) and MINOR-C7 (latent probe blind spot) are recorded above.

## 5. Cancel semantics (check 4)

`cancel_turn` (`conversation_turns.py:1082-1147`) now performs durable replay before the version precondition, serializes on the thread row lock, records the cancellation continuation through `_continuation_turn` (so its events, including terminal `turn.final {status:'cancelled'}`, commit atomically), marks open proposals `cancelled`, and appends an audit row. `_recorded_cancellation` makes same/different-key repeats return the recorded continuation. The route takes no body and the client was corrected to send no body (`services/live/conversation-turn.ts:294-300`), which also fixes the Increment B client/route mismatch. Viewer cannot reach cancel (route `access` + `load(edit=True)`); UI hides it (browser assertion added in the existing viewer test). No defect found.

## 6. Frontend (check 5)

| Rule | Evidence | Verdict |
| --- | --- | --- |
| Persisted parts win over streamed parts | `mergeStreamedEntry` appends a provisional assistant entry only when no persisted assistant entry for that turn exists (`parts.ts:161-172`); after `turn.final` the studio refetches the thread and drops the stream when the assistant row is persisted (`studio.tsx:325-350`); [TEST] `core-conversation-stream.test.mjs` | correct |
| No duplicate messages / repeated POST after mid-turn reconnect | `stream()` only GETs `…/events?after=cursor`; it never re-submits (`conversation-turn.ts:161-227`); reducer ignores seq ≤ cursor; browser reconnect row asserts one turn POST, cursor resume `[0,2]`, one user row (BLOCKED here) | correct by reading; browser row BLOCKED |
| Parser malformed/chunk-boundary safe | Incremental `SseParser` handles CRLF, comments, multi-line data and trailing partial frames; malformed JSON/unknown kinds/states/statuses degrade to null (`stream-events.ts:91-195`); [TEST] chunk-boundary/malformed cases | correct |
| Viewer cannot cancel | `cancelTurn` guard `loaded.chat.access==='viewer'` and the button is only rendered for non-viewers (`studio.tsx:373-377,460-470`); browser viewer row asserts no Cancel button | correct |
| Recovery actions only for allowed states | `outcomeTurn` only for `outcome_unknown` (latest turn or persisted outcome_unknown tool part); `failedTurn` only for `failed`; both gated to non-viewer (`studio.tsx:239-252,503-514`) | correct (discoverability gap MINOR-C4) |
| Bounded stream memory | Server bounds every turn's events; reducer arrays are per-turn and replaced by id/index; `SseParser` buffer is unbounded (MINOR-C1) and the client does not independently cap notices/parts arrays | partial — fix parser cap |
| i18n completeness | 13 new keys present in both `features/live/locale.ts` and `locales/index.ts`; reviewer scan of `features/live/conversation/**` + `conversation-turn.ts` finds 0 missing keys | complete; no committed test (MINOR-C8) |
| Honest progress/recovery copy | Coarse labels only ("Working…", "Running a step…", "Approval required", "Reconnecting…"); no capability ids in ordinary copy; notices for interrupted stream; cancel/recovery notices | correct |

## 7. Verification actually executed / BLOCKED

Executed in this sandbox (bundled Node v24; sandbox blocks `node --test` child spawn so `--experimental-test-isolation=none`, as in `scripts/test-core.mjs`):
- Core client suite: `tests/core-*.test.mjs` + `tests/audit-research-intent.test.mjs` → **133 tests, 133 pass, 0 fail** (includes the 10 new `core-conversation-stream` cases; matches the CI count gate 133).
- `tsc --noEmit -p tsconfig.json` → exit 0.
- Targeted eslint on `features/live/conversation`, `services/live/conversation-turn.ts`, the new core test and the browser gate/fixture → exit 0.
- Static: browser gate now has 18 top-level `test(` + 2 loop-generated pairs = **22 cases**; base branch had 15 + 4 = **19**; the diff is additive (helper extension + one viewer assertion + three new streaming rows) — no original assertion removed or weakened. Pytest discovery delta +13 matches the workflow's 3992. i18n scan 0 missing.
- Prior increment regressions re-checked by reading: decision/cancel replay now precedes the version precondition; failed decisions record the decision/proposal state; migration 0066 has the rollback trigger for old writers and a populated-data downgrade guard; worker recovery includes 0065–0068.

**BLOCKED (CI must prove; no local result claimed):** all PostgreSQL pytest (`test_conversation_turn_events_db.py`, `test_conversation_turn_events_unit.py`, `test_conversation_turns_api.py` streaming/reconcile additions, migration/RLS/lock-scope suites), and all Playwright/node browser tests (`tests/conversation-home-responsive.test.mjs`), and real-provider acceptance.

## 8. CI acceptance matrix (what proves each criterion)

| Criterion | Test(s) that prove it | CI job / artifact |
| --- | --- | --- |
| Event transactionality; terminal event == turn status | `test_conversation_turn_events_db.py::test_terminal_event_and_turn_status_require_one_transaction`, `test_conversation_turns_api.py::test_stream_replays_ordered_events_and_reconnect_has_no_duplicates` (`events[-1].payload.status == turn.status`), unit ordering test | job `api`, `services/api/artifacts/tests.xml` (uploaded as artifact `buyeros-neon-cutover-local-rehearsal`); discovery gate 3992 |
| Continuation events emitted (decision/blocked/failure/unknown/cancel/reconcile) | Reconcile asserted in `test_reconcile_is_read_only_terminal_and_idempotent`; the other continuations are only source-verified today (MINOR-C8) | job `api`, `tests.xml` — partially unproven |
| seq allocator flushes/unique | `test_conversation_turn_events_unit.py::test_event_allocator_flushes_pending_rows`, DB `test_event_allocator_flushes_pending_rows`, `test_event_validator_rejects_bad_payload_and_unique_seq` | job `api`, `tests.xml` |
| Concurrent-writer ordering | **no test (MAJOR-C2)** | unproven |
| 0068 RLS/grants/migration | `test_event_store_contract_rls_and_grants`, `test_populated_event_downgrade_refuses_and_empty_downgrade_round_trips`, `test_empty_event_downgrade_round_trips`, `test_conversation_turns_migration_db.py` (head 0068) | job `api`, `tests.xml` |
| SSE replay exactly once / no re-execution / foreign 404 / invalid cursor 422 / headers | `test_stream_replays_ordered_events_and_reconnect_has_no_duplicates`, `test_stream_cursor_validation_and_foreign_turn`; browser reconnect row asserts `after` cursor `[0,2]`, one POST, no duplicate user row | job `api` (`tests.xml`) + job `frontend` (`test-results/conversation-studio.xml` + screenshots, artifact `buyeros-conversation-studio`) |
| SSE heartbeat/deadline bound | **no test** (MINOR-C8) | unproven (source-verified constants 20 s/5 s) |
| Reconcile 409 / read-only / idempotent / audit / membership | `test_reconcile_requires_an_unknown_turn`, `test_reconcile_is_read_only_terminal_and_idempotent` (**expected red per BLOCKER-C1**), browser reconcile row | job `api` (`tests.xml`) + job `frontend` (`conversation-studio.xml`, screenshot `stream-progress-desktop.png` etc.) |
| Cancel terminal event + no body + viewer denied | API cancel tests; browser `a running turn can be cancelled from the keyboard without a new turn`; viewer row asserts no Cancel button | `tests.xml` + `conversation-studio.xml` |
| Frontend parser/reducer/backoff/provisional merge | `tests/core-conversation-stream.test.mjs` (10 cases) | job `frontend`, `test-results/core-client.xml` (count gate 133, artifact `buyeros-core-client`) |
| Browser flows (progress, reconnect, cancel, reconcile, responsive, i18n) | `tests/conversation-home-responsive.test.mjs` 22 cases | job `frontend`, `test-results/conversation-studio.xml` + `test-results/conversation-studio/*.png` |
| Regression: original 19 browser cases + existing turn/decision semantics | Same browser file (19 unchanged + 3 new); existing API tests in `tests.xml`; core count 133 | `conversation-studio.xml`, `core-client.xml`, `tests.xml` |
| Real provider / paid dispatch acceptance | — | **BLOCKED**: no credentials/admission; reconcile and turn engine have no provider path by design |

## 9. Recommendations (owner: orchestration / conversation-ui)

1. Fix BLOCKER-C1 + MAJOR-C1 together: make the recorded-resolution pre-check use the continuation id actually created, return the recorded continuation *before* probing/auditing, and update the source turn's outcome (or document explicitly that the continuation is authoritative and make the API/UI stop offering recovery for an already-reconciled source turn). Add a test for "first reconcile resolves unknown, later evidence resolves completed".
2. Add the concurrent-writer DB test required by contract §6 (two sessions appending to the same turn under/without the thread lock) and assert the lock invariant in code comments/tests.
3. Add heartbeat/deadline, cross-workspace SSE 404, and continuation-event assertions for decision/blocked/failure/cancel paths.
4. Cap the `SseParser` buffer (e.g. 64 KiB → abort) and add an independent cap for reducer notices/parts; add a client-side headers timeout for the SSE fetch.
5. Make the browser progressive-render fixture match the real POST response shape (persisted assistant parts present) and add a row for the "persisted wins immediately" rule; move the reconcile browser row to a decision-continuation flow.
6. Optional consistency: version precondition on reconcile, constraint-name alignment, remove unused import, recovery scan across all persisted entries rather than the last assistant row.

## 10. Not reviewed / out of scope

- No production deployment/promotion/Vercel changes; no implementation edits (only this document).
- Real provider, production data and browser runtime were not exercised here; the CI matrix above is the substitute and the rows marked unproven are the acceptance boundary.
