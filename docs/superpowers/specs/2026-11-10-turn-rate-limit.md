# Increment 3.2 contract — per-workspace turn rate limit

Status: implementation contract. Backend increment (orchestration) plus a small
client mapping (conversation-ui, separate file scope).

## Why

Phase 3.4 asks for per-workspace turn rate limits. Today a turn POST is only
subject to the generic API limiter, which is actor-scoped and classifies the route
as a plain `write`; a workspace (or a scripted member) can start expensive turns at
the generic write rate without a turn-specific ceiling. The conversation surface is
the expensive path and needs its own admission control with a truthful, retryable
error.

## Backend contract

- **Table** `conversation_turn_rate_windows` (migration `0070_turn_rate_windows`,
  short revision id), workspace-scoped: `workspace_id`, `window_start` (minute,
  UTC), `hits`. Primary key `(workspace_id, window_start)`. Enable RLS with the same
  pattern as existing tenant tables (`ENABLE`/`FORCE`, tenant policy, grants) and add
  the guard test style used by the previous migrations.
- **Admission**: on `POST /v1/workspaces/{ws}/projects/{pj}/conversation-turns`
  (turn creation only — not decisions, cancel or reconcile), after authentication,
  access check and idempotency replay detection, and before any turn/task writes,
  perform one atomic upsert `hits = hits + 1 WHERE hits < limit` and return the new
  count. Use a separate transaction/session so a later business failure cannot roll
  the counter back (same pattern as `services/api_rate_limit.py`).
- **Limit**: new setting `turn_per_minute: int = Field(default=30, ge=0, le=1000)`
  (`BUYEROS_` prefix makes it `BUYEROS_TURN_PER_MINUTE`); `0` disables the limit
  (documented). Window = current UTC minute.
- **Rejection**: `ApiError(429, 'TURN_RATE_LIMITED', 'turn rate limit reached',
  retryable=True)`, raised before any turn row, event, task, budget reservation or
  idempotency record is written. Replaying an already-accepted idempotency key must
  return the replay response and must **not** consume admission.
- **Per-workspace**: the counter is keyed by workspace only (all members share the
  ceiling); another workspace is unaffected.
- **Tests** (pytest, DB-backed, deterministic): under-limit accepted; the
  limit-th+1 request gets 429 `TURN_RATE_LIMITED`/`retryable` and leaves **no** turn
  row, event, task or idempotency record behind; separate workspace unaffected;
  idempotent replay does not consume; window rollover (inject/monkeypatch the clock
  or the window helper) accepts again; limit `0` disables. Include the guard/CI
  inventory updates required by the repo's pytest discovery test and report the new
  expected count (currently 4032).
- No change to existing turn semantics, contracts, or the generic API limiter.

## Client contract (conversation-ui)

- Map `TURN_RATE_LIMITED` (and only that new code) to a truthful localized notice
  in the composer/transcript path, e.g. EN "Too many turns were started just now.
  Wait a moment and try again." / zh-HK equivalent, marked retryable where the
  existing retry affordance applies. Keep the draft and the exact-once client message
  id so a retry is safe. Do not change other error mappings; add a unit test; report
  the new core count (currently 182).
