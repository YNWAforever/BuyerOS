# Conversation turn contract (draft v0 — 2026-11-08)

Status: **implementation draft for review.** Extends the existing server threads
(`conversation_threads`) and the flag-gated `conversation-reply` boundary. It does
not replace canonical BuyerOS records (buyers, runs, drafts, ICP, offer facts) and
does not introduce a new worker or a second agent host.

## Why

The delivered surface routes a user message into either a one-shot grounded reply
(`POST /conversation-reply`) or a guided task form (`sales-tasks`). Neither is a
continuous conversation: a turn cannot invoke more than one bounded action, cannot
pause for a mid-conversation approval inside the thread, and cannot return inline
tool results that later reload.

## Turn endpoint

`POST /v1/workspaces/{workspace_id}/projects/{project_id}/conversation-turns`

Headers: `Authorization: Bearer …`, `Idempotency-Key: <opaque>`.

```json
{
  "thread_id": "uuid",
  "client_message_id": "uuid",
  "expected_thread_version": 7,
  "language": "en | zh-HK",
  "text": "Research this buyer and prepare a follow-up",
  "skill_id": "sales-research | null"
}
```

Semantics:

- The user message is appended exactly once per `(thread, client_message_id)`.
  A replay returns the recorded result instead of re-running tools.
- `expected_thread_version` guards concurrent edits (existing `If-Match` rules).
- One bounded turn = at most the reviewed step ceiling; no unbounded pagination,
  no automatic retry of a possibly-billed call.

Response (`envelope`), `200`:

```json
{
  "thread": { "...ServerThread, extended with messages[].parts..." },
  "turn": {
    "id": "uuid",
    "status": "completed | needs_input | needs_approval | failed | outcome_unknown",
    "parts": [ "MessagePart" ],
    "notices": [ { "code": "...", "message": "..." } ]
  }
}
```

`status` is authoritative for the UI; `parts` are also persisted on the assistant
message so a reload reconstructs the same transcript without replaying tools.

## MessagePart (persisted, versioned with the message)

| kind | payload | notes |
| --- | --- | --- |
| `text` | `{ text, language }` | assistant prose; untrusted, escaped |
| `citations` | `{ items: [{ id, label, kind, href }] }` | ids must already be authorised sources/records |
| `tool_activity` | `{ call_id, capability, title, state, started_at, finished_at?, summary?, error_code? }` | state: `proposed → approved → running → completed / failed / skipped / outcome_unknown` |
| `proposal` | `{ proposal_id, capability, title, rationale, arguments_preview, cost?, requires_approval }` | rendered as an inline approval card |
| `output_link` | `{ output_id, kind, title, revision, status, href }` | points at a canonical saved revision |
| `notice` | `{ code, message, recovery? }` | recovery is a label + optional native route |

Rules:

- Capabilities come from the existing allowlist/registry. Chat text never expands
  tool permission, tenant identity, budget, or approval state.
- `proposal` requires an explicit decision before its capability executes; the
  decision is its own authenticated call (below), never inferred from prose.
- Provider/model output is untrusted data and is validated server-side before it
  reaches `text`, `citations`, or `output_link`.
- A failed or uncertain step keeps its part visible; it is never silently dropped.

## Decisions

`POST …/conversation-turns/{turn_id}/decisions`

```json
{ "proposal_id": "uuid", "decision": "approve | reject", "expected_thread_version": 8 }
```

Returns the same `{ thread, turn }` shape, where `turn` is the continuation turn
created by the decision. `agree`/approve must revalidate membership, policy,
suppression and budget at execution time, not at proposal time.

## Cancellation, recovery and unknown outcome

- `POST …/conversation-turns/{turn_id}/cancel` — stops undispatched steps and
  reports already-dispatched liability accurately.
- A lost provider response yields `outcome_unknown`, retains the reservation, and
  offers reconciliation rather than an automatic paid repeat.
- Reload/resume replays persisted parts only. It never replays jobs.

## What the UI must do

- Distinguish `loading`, `disabled`, and `unavailable` for entry capability.
  A capability read failure must never silently select the legacy shell.
- Keep unsent composer text across navigation and reload.
- Render inline parts; native screens remain reachable via `output_link.href`.
- Poll or refetch by thread version; do not duplicate reads on every rerender.

## Compatibility

- Existing `POST /conversation-reply` and `sales-tasks` endpoints stay valid;
  guided forms remain a secondary surface and are not required to start a turn.
- Disabling the entry flag keeps recovery routes and saved outputs readable.

## Amendment A — 2026-11-08 (Lead ruling on two ambiguities)

### A1. New-thread flow is turn-first

`POST /conversation-turns` must accept an **optional** `thread_id`:

- `thread_id` present → append to that thread (existing version/ACL rules apply).
- `thread_id` absent/null → the server creates the thread and appends the first
  user message **atomically in the same transaction**, deriving the title from the
  first message using the existing title rules, and returns the created thread.

Clients must NOT pre-create a thread with `POST /conversation-threads` and then
submit the same text as a turn: that path duplicates the first user message.
`POST /conversation-threads` stays valid for clients that need a thread with no
model/tool activity (for example sharing setup), but it is not the normal entry
point for a conversation turn.

Idempotency: a replayed turn request with the same `Idempotency-Key` and
`client_message_id` returns the original result and creates at most one thread.

### A2. Thread messages gain a role discriminator and parts

`ServerThread.messages[]` becomes:

```json
{ "id": "...", "seq": 12, "role": "user | assistant", "text": "...",
  "client_message_id": "...", "created_at": "...", "parts": [ "MessagePart" ] }
```

- `role` is required in responses for new writes; existing/legacy rows are
  migrated (or read) as `role: "user"` with no `parts`.
- `parts` is present on assistant messages that used the turn engine; user
  messages may omit it entirely.
- A client that receives an unknown `role` or `parts[].kind` must degrade safely
  (render text, never crash).

These two amendments are the shared interface for the current implementation.
Anything beyond them needs a report back to the Lead rather than a silent change.
