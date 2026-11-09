# Phase 3.2 review — bounded turn deadline and timeout taxonomy

Reviewer: `reliability` (independent of the implementation streams)
Date: 2026-11-09 (Asia/Singapore)
Worktree: `C:\Users\laich\Documents\BuyerOS\.worktrees\conv-studio`, branch `feat/conversation-turn-deadline`, head `c997093cb` (stacked PR #60 on `feat/conversation-proposal-why`).
Contract: `docs/superpowers/specs/2026-11-09-turn-deadline.md` plus the Increment A/B/C/2.7 contracts.
Scope: `TURN_DEADLINE_SECONDS` setting, `services/turn_deadline.py`, deadline placement in create/decide/cancel/reconcile, timeout notices, idempotent replay, and regression risk. **No implementation file was modified by this review; the only file written is this document.**

Verification legend:
- **[READ]** verified by reading source at the cited `file:line`.
- **[TEST]** verified by a test executed in this sandbox (frontend `node:test`/tsc only — see §8).
- **[BLOCKED]** PostgreSQL is unavailable here (Docker named pipe denied; uv cache read-only, no Python env). The new API/DB tests are CI-only; no DB result is claimed by this review.
- **[ROUTED]** reported to the Lead.

## 1. Findings summary

| Id | Severity | Finding | Evidence | Status |
| --- | --- | --- | --- | --- |
| BLOCKER-1 | Blocker (acceptance: spent work) | The post-executor deadline branch returns a failed deadline continuation **after** the executor has already persisted canonical rows in the same transaction, and does not roll them back. A deadline crossed during/after a completed `documents.read`/`research.read` step leaves a `sales_tasks` row (and `sales_outputs` for documents) committed while the response reports `failed`/`outcome_unknown`; `proposal.result.task_id` is then set to `None`, losing the link. | `services/api/buyeros_api/services/conversation_turns.py:1090-1095` (check after `executor(...)` at :1076-1089); `_execute_documents` :771-792 (`create_task`+`save_output`); `_execute_research` :795-819 (`create_task`); `_deadline_failure` :617-637 (sets `task_id=None`, commits continuation) | [READ] [ROUTED] |
| MAJOR-2 | Major (double notice) | Deadline paths persist a `TextPart` containing the deadline message **and** the same message in `turn.notices`. The live transcript renders the persisted thread message plus the turn payload (`parts.ts` builds turn parts from `turn.parts` + notices), so the same message appears as persisted text + turn text + notice in the submit/decision response (reload collapses it to one). | `_stage_deadline_create` :586-604; `_deadline_simple_continuation` :607-614; `_deadline_failure` :617-637; `features/live/conversation/parts.ts:25-47,62`; API tests only assert `turn.notices` | [READ] |
| MAJOR-3 | Major (decision semantics) | The deadline check runs before the reject branch, so an explicit Reject that arrives after the bound becomes a failed deadline continuation instead of a recorded rejection (reject dispatches no work; the contract says decisions are unaffected). | `_apply_decision` :1035-1038 | [READ] |
| MAJOR-4 | Major (state guard ordering) | In reconcile, the deadline check (:1310-1311) runs before the `turn.status != 'outcome_unknown'` guard (:1329), so an expired-deadline reconcile on a normal/completed turn returns 200 failed instead of the contract's `409 INVALID_STATE`. | `reconcile_turn` :1267, :1310-1311, :1329 | [READ] |
| MAJOR-5 | Major (contract: dropped parts) | `_stage_deadline_create` filters out every `ProposalPart`, so a deadline crossed after plan construction erases the produced proposal parts, contrary to "parts produced so far are persisted / nothing erased". It is a defensible choice (no dangling proposal row) but undocumented; the second check also drops `grounding_notices`. | `_stage_deadline_create` :591; create path second check :708-710 | [READ] |
| MAJOR-6 | Major (documentation honesty) | `TURN_BUSY_RETRY` exists only as a constant. The contract spec claims "a bounded single retry when a lock wait exceeds a short threshold" (`2026-11-09-turn-deadline.md:30-31`) and the API contract says it "names the bounded single retry taxonomy" (`conversation-turns.v1.md:80`); there is no wiring, no code comment saying it is deliberately reserved, and no test. The known gap is not honestly documented. | `services/api/buyeros_api/services/turn_deadline.py:17`; both docs above | [READ] |
| MINOR-1 | Minor (unknown liability not reconcilable) | Post-dispatch deadline records `proposal.status='outcome_unknown'` but the continuation status is `failed`; reconcile accepts only turns whose status is `outcome_unknown` and the source turn stays `needs_approval`. The UI recovery action keys on the outcome_unknown tool part, calls reconcile on a `failed` turn and gets `409` ("no longer awaiting a result check"). | `_deadline_failure` :627-634; reconcile guard :1329; `features/live/conversation/studio.tsx` recovery derivation | [READ] |
| MINOR-2 | Minor (mislabel) | The same post-executor branch marks `dispatched=True` for proposal-only executors (`xverum.enrich_company`, `drive.read`) which never dispatch anything, reporting `outcome_unknown` and discarding their honest configuration notice. | `_apply_decision` :1090-1095; `_execute_xverum_proposal_only` :827-858; `_execute_drive_proposal_only` :860-880; `EXECUTORS` :882 | [READ] |
| MINOR-3 | Minor (observability) | Cancel and reconcile deadline continuations append no audit row (normal cancel/reconcile do); the create deadline path does audit; a decision deadline records the decision audit even though nothing executed. | `cancel_turn` :1196-1204; `reconcile_turn` :1296-1311; `_stage_deadline_create` :600-603; `decide` audit | [READ] |
| MINOR-4 | Minor (consistency) | `_stage_deadline_create` hard-codes `steps_count=0` even when the plan was already computed (third check), unlike a normal turn which stores the planned step count. | `_stage_deadline_create` :595-598 | [READ] |
| MINOR-5 | Minor (doc typo) | Contract text renders the range as "5?90" and the response sentence as "turn ? never a 5xx" (en-dash encoding artifacts). | `2026-11-09-turn-deadline.md:17,28` | [READ] |

No 5xx path was found in the covered deadline branches, and no duplicate **dispatch** was found: pre-dispatch checks stop before the executor, and the post-executor branch does not re-run it (it leaks the completed work instead — BLOCKER-1).

## 2. Deadline semantics per continuation path [READ]

**Deadline primitive** (`services/turn_deadline.py`): `TurnDeadline(seconds, clock=time.monotonic)`; `should_start()`, `exceeded()`, `remaining()`, constant bucket `over_deadline`; localized EN/zh-HK message contains only the bucket (no ids/provider refs); `validate_seconds` integer 5–90; `turn_deadline()` reads the validated setting. Unit tests use a `FakeClock` (no sleeps).

**create** (`create_turn` :640-760): deadline created after version checks; checks before grounding (:701), after grounding/drive reads (:708), and after plan/answer parts (:720). Each branch calls `_stage_deadline_create`, which persists the user message + an assistant message whose parts are the produced non-proposal parts + the deadline TextPart, status `failed`, notices merged (single `TURN_DEADLINE_EXCEEDED`), events appended in the same transaction, audit, HTTP 200. No executor/work is started. Gaps: MAJOR-2 (duplicate live notice), MAJOR-5 (proposal parts/grounding notices dropped), MINOR-4.

**decide** (`_apply_decision` :1032-1120): pre-check before reject (:1035 — MAJOR-3), pre-dispatch after gate serialization (:1067-1070 → `dispatched=False`, tool state `skipped`, proposal `failed`, decision recorded `failed`, no executor), post-executor (:1090-1095 → `dispatched=True`, tool state `outcome_unknown`, proposal `outcome_unknown`, continuation `failed`, BLOCKER-1 + MINOR-1/2). Replays are handled before the deadline object is created (`begin_idempotency` replay at :~990; existing-decision path before :1035) so a replay never re-executes.

**cancel** (`cancel_turn` :1170-1220): terminal/recorded turns return before the deadline; deadline created after `_check_version`; expired → `_deadline_simple_continuation` (failed continuation + one notice), idempotency completed, 200; no proposals mutated, no work created. No audit (MINOR-3); replay same key is handled before the deadline check.

**reconcile** (`reconcile_turn` :1267-1400): idempotency replay before the deadline; expired before probe (:1310) and after probe (:1321) → `_deadline_simple_continuation` (failed continuation + notice), no resolution row, source turn stays `outcome_unknown`, 200; no work created. Gap: MAJOR-4 (status guard after deadline check), MINOR-3.

**Terminal event atomicity**: every deadline path persists through `_stage_turn` or `_continuation_turn`, both of which call `append_turn_events` in the same transaction as the turn status (`conversation_turns.py:595-599,612-613`; `_continuation_turn` appends at :851-852). API test asserts the persisted terminal event payload is `{'status':'failed'}` for create. ✓

## 3. Spent work / unknown liability (focus 2) — BLOCKER-1 detail

`_execute_documents` (:771-792) and `_execute_research` (:795-819) write canonical rows through `create_task`/`save_output` on the same session before returning. The post-executor deadline check (:1090-1095) then calls `_deadline_failure(dispatched=True)`, which appends the continuation/decision and commits; there is no savepoint rollback of the executor's writes. Consequences:

1. **Spent canonical work on a failed deadline turn**: `sales_tasks` (both capabilities) and `sales_outputs` (documents) remain committed while the turn is `failed`/`outcome_unknown` — this violates the acceptance invariant "the deadline path must create no sales task/stage/quote/receipt/budget reservation" and "no spent work". The API test's table checks would fail for this branch, but the branch is untested (all tests use an already-expired deadline, so `must_not_dispatch` never runs and the executor is never called).
2. **Liability is misreported**: the executor returned a known outcome (`output`/`notice`/`failed`), but the response says `outcome_unknown`; `proposal.result.task_id=None` loses the link to the persisted task, so the unknown state cannot be reconciled.
3. **No duplicate dispatch**: the executor is not re-run, so the "never re-run a dispatched step" part of the contract holds; the problem is that completed work is discarded from the response while remaining persisted.
4. **Proposal-only capabilities**: `xverum.enrich_company`/`drive.read` never dispatch; if the deadline crosses after their terminal-notice return, the branch marks `outcome_unknown` and discards the honest configuration notice (MINOR-2).

**Recommended fix**: wrap the executor in its own `session.begin_nested()` and, when the deadline has crossed, roll back that savepoint and record `dispatched=False` (`skipped`) for the two current nonbillable/no-provider executors; if a provider-dispatched step is added later, keep the receipt/task id and `outcome_unknown` with a reconcile path instead of discarding it. Add a deterministic test with a clock advanced inside a slow executor (or an executor that advances an injected clock) asserting zero sales_tasks/sales_outputs, exactly one notice, and replay idempotency.

## 4. Idempotency (focus 3) [READ]

- `create`: durable `client_message_id` replay is checked before the deadline object is created (`_existing_turn`/`_replay` at :~665-690); a recorded deadline failure is returned with no new work; API test covers same-key replay.
- `decide`: idempotency replay and existing-decision lookup run before the deadline object (:~985-1030); same-key replay returns the recorded continuation; API test covers same-key replay.
- `cancel`: replay runs before the deadline check; expired path calls `complete_idempotency`; same-key replay returns the recorded continuation (source reasoning; not separately tested for the deadline branch).
- `reconcile`: replay runs before the deadline check; expired path calls `complete_idempotency`; same-key replay returns the recorded continuation (source reasoning; not separately tested for the deadline branch).
- No path re-executes work on replay; the only replay weakness is that the deadline continuation ids are deterministic by fingerprint, so a repeated expired call with a different key returns the same continuation rather than a new one (desirable).

## 5. Setting, clock and observability (focus 4–6) [READ]

- `turn_deadline_seconds: int = Field(default=60, ge=5, le=90)` in `settings.py`; `BUYEROS_` prefix makes the documented env var `BUYEROS_TURN_DEADLINE_SECONDS`; pydantic-settings parses numeric env text and raises `ValidationError` for non-integer/out-of-range text, and `create_app()` evaluates `get_settings()` during app construction (`api/app.py:154,177`), so invalid env text fails closed at startup rather than silently defaulting. Unit test covers constructor/string validation and the default; the env var itself is not exercised end-to-end (minor coverage note).
- Clock is injectable (`TurnDeadline(clock=...)`), unit tests use a fake clock, API tests inject an already-expired deadline object — deterministic, no real sleeps. Placement: checks before starting work in all four paths, after long reads in create/reconcile, after gate serialization in decide; the post-executor placement is the BLOCKER-1 problem.
- Notice text is a constant localized string containing only the `over_deadline` bucket; no request ids, provider refs, payloads or unbounded internals. The persisted notice is one entry in `turn.notices`; MAJOR-2 is the duplicate rendering, not a server-side duplicate notice row.
- `TURN_BUSY_RETRY` is defined but unused and not documented as deliberately reserved (MAJOR-6).

## 6. Regression (focus 7) [READ]

- No frontend/browser files changed; the browser gate is untouched (diff has no `tests/conversation-home-responsive.test.mjs` change), core suite unchanged at 141.
- No changes to admission/budget/provider code; the deadline pre-dispatch paths return before the executor, and the post-executor path reuses the existing executor (the new defect is the missing rollback, not a new provider path).
- Existing turn/decision/event/reconcile contracts are otherwise intact: event append helpers unchanged, no schema/migration, notice codes additive, replay/idempotency ordering preserved.
- CI inventory 4009→4017 matches the 8 added backend tests (3 unit + 5 API).

## 7. Test gaps (why CI is likely green despite BLOCKER-1)

- All five new API tests inject an already-expired deadline (`ExpiredDeadline` with `should_start()==False`), so they never exercise: the post-executor branch, the pre-dispatch-after-gates branch, a real clock advancing between checks, or produced parts being persisted.
- No test for reject-after-deadline (MAJOR-3), reconcile-on-non-unknown-with-expired-deadline (MAJOR-4), duplicate live transcript rendering (MAJOR-2), dropped proposal parts (MAJOR-5), cancel/reconcile deadline replay, or `TURN_BUSY_RETRY` documentation (MAJOR-6).
- The create test's `turn['parts']` assertion only proves the deadline TextPart exists, not that pre-existing produced parts survive.

## 8. Verification executed / BLOCKED

Executed here: core client suite `tests/core-*.test.mjs` + `tests/audit-research-intent.test.mjs` → **141 tests, 141 pass** (unchanged from the parent branch); `tsc --noEmit -p tsconfig.json` → exit 0. No frontend files changed in this increment, so no browser-gate or lint delta is expected; the browser gate was not touched.
**BLOCKED locally**: all PostgreSQL pytest — `test_turn_deadline_unit.py` (3 tests) and the five new deadline API tests (`test_deadline_exceeded_turn_returns_200_failed_with_parts_and_replays`, `test_decision_continuation_honours_the_deadline_without_dispatch`, `test_cancel_deadline_stops_before_any_step`, `test_normal_turn_is_unaffected_by_the_default_deadline`, `test_reconcile_deadline_stops_before_resolution`), plus the existing turn/decision/event/reconcile suites. Docker named pipe is denied; uv cache read-only; no Python env. CI is authoritative.

## 9. CI artifacts that prove acceptance

| Criterion | Proof | Artifact |
| --- | --- | --- |
| Deadline returns 200 + failed + one notice + persisted parts + terminal event | `test_deadline_exceeded_turn_returns_200_failed_with_parts_and_replays`, `test_decision_continuation_honours_the_deadline_without_dispatch`, `test_cancel_deadline_stops_before_any_step`, `test_reconcile_deadline_stops_before_resolution` | job `api`: `services/api/artifacts/tests.xml` (artifact `buyeros-neon-cutover-local-rehearsal`), inventory 4017 |
| No spent work on the pre-dispatch paths | same tests' `sales_tasks`/`sales_executions`/`xverum_stages`/`xverum_tool_receipts`/`budget_reservations` count checks | same `tests.xml` |
| Normal turn unaffected | `test_normal_turn_is_unaffected_by_the_default_deadline` + existing suite | same `tests.xml` |
| Setting validation/default/env | `test_turn_deadline_unit.py` (arithmetic, notice privacy, 5–90/default/env-text validation) | same `tests.xml` |
| Regression (frontend unchanged) | core count gate 141 | job `frontend`: `test-results/core-client.xml` (artifact `buyeros-core-client`) |
| Browser gate untouched | no browser files in the diff | n/a (unchanged 23-case gate) |

**Unproven by any artifact**: the post-executor branch (BLOCKER-1), reject-after-deadline, reconcile 409 ordering, duplicate live notice, dropped proposal parts, cancel/reconcile deadline replay, and the `TURN_BUSY_RETRY` documentation gap.

## 10. Recommendations (owner: orchestration)

1. Fix BLOCKER-1: savepoint the executor and roll it back on a crossed deadline (or accept the completed result and stop further work); keep the task/receipt id if a genuinely dispatched step must stay `outcome_unknown`. Add the missing deterministic post-executor test.
2. Move the deadline pre-check after the reject branch so an explicit Reject is still recorded (MAJOR-3).
3. Move the reconcile deadline check after the `outcome_unknown` status guard (MAJOR-4).
4. Stop duplicating the notice in `parts` (MAJOR-2): either persist only the notice (and let the transcript render it) or only the text, never both; add a transcript-count assertion.
5. Document the dropped-proposal-parts rule in the contract (MAJOR-5), and add the explicit "TURN_BUSY_RETRY reserved, not wired in 3.2 (would require re-taking the thread lock)" note to both docs and the constant (MAJOR-6).
6. Minor: audit the cancel/reconcile deadline paths, keep `steps_count` consistent, fix the en-dash typos, and exercise the env var in the unit test.

## 11. Not reviewed / out of scope

- No production deployment/promotion/Vercel changes; no implementation edits (only this document).
- Real provider/paid behaviour, production data and browser runtime were not exercised here; the CI artifacts above are the substitute.
