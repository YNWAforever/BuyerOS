# Increment C contract addendum — streamed turn events and reconciliation

Status: **implementation contract.** Extends
`docs/superpowers/specs/2026-11-08-conversation-turn-contract.md`. It does not
change authority: every event is derived from the persisted turn, approvals stay
explicit, and no provider spend is introduced.

## 1. Event store

New table `conversation_turn_events`:

| column | notes |
| --- | --- |
| `id` | uuid |
| `workspace_id`, `project_id`, `thread_id`, `turn_id` | tenant scoped; FKs |
| `seq` | per-turn monotonic, `UNIQUE(turn_id, seq)` |
| `kind` | see below |
| `payload` | validated JSON (bounded) |
| `created_at` | server time |

RLS forced tenant policy, no worker grants, `SELECT, INSERT` for the API role
only. Events are derived data: pruning them never changes `parts` or the turn
state. Append happens in the same transaction as the state change it describes;
the terminal event is written in the same transaction as `turn.status`.

## 2. Event kinds

| kind | payload | notes |
| --- | --- | --- |
| `turn.started` | `{status: "running"}` | first event |
| `part` | `{index, part: MessagePart}` | a persisted assistant part became available |
| `tool` | `{call_id, capability, state, summary?, error_code?}` | tool activity transition |
| `proposal` | `{proposal_id, capability, requires_approval}` | inline proposal available |
| `notice` | `{code, message}` | honest configuration/failure notice |
| `turn.final` | `{status}` | terminal; never followed by another event |

No deltas in this increment (there is no streaming model yet). Deltas are additive
later and must never be required to reconstruct a turn.

## 3. SSE endpoint

`GET /v1/workspaces/{ws}/projects/{pj}/conversation-turns/{turn_id}/events?after=<seq>`

- `text/event-stream`, `Cache-Control: no-store`, `X-Accel-Buffering: no`.
- Replays persisted events with `seq > after` in order, then live-tails new events
  until `turn.final` or the bounded stream deadline; emits `: heartbeat` comments.
- Reconnect with the last seen `seq` produces no duplicates and never re-executes.
- Returns `404` for a turn outside the workspace/project; `403`/`404` follow the
  same ACL as the turn GET.
- `after` defaults to `0`; non-integer or negative is `422`.

## 4. Reconciliation

`POST …/conversation-turns/{turn_id}/reconcile`

- Only valid when the turn is `outcome_unknown`; otherwise `409 INVALID_STATE`.
- Performs a **read-only** probe of existing receipts/ledger state for the turn's
  steps. It must never dispatch, reserve, or retry a provider call.
- Persists the resolved outcome (`completed` / `failed` / stays `outcome_unknown`),
  appends the corresponding `tool` + `turn.final` (or `notice`) events, and
  records the decision in the existing audit path.
- Idempotent: replay returns the recorded continuation/result.
- Requires the same write permission as a decision, and revalidates membership at
  execution time.

## 5. Client rules

- Stream on turn submission; on failure fall back to the existing
  `{thread, turn}` response and then to a thread refetch.
- Persisted parts win over streamed parts; a streamed part is rendered as
  provisional only until `turn.final`.
- Reconnect with bounded backoff and the last seen `seq`; if the server reports the
  turn already terminal, refetch the thread instead of retrying.
- Cancel calls the existing cancel endpoint and stops the stream after
  `turn.final`.

## 6. Testing obligations

- Unit: event ordering, cursor resume, backoff, provisional-merge rules.
- DB: append is ordered/unique under concurrent writers; terminal event and turn
  status commit atomically; RLS isolation.
- API: replay with `after` never duplicates; foreign turn is 404; reconcile is
  read-only and idempotent; reconcile on a non-`outcome_unknown` turn is 409.
- Browser: progressive render, reconnect mid-turn, cancel, reconcile with a
  fixture connector; no paid dispatch is reachable from reconcile.
