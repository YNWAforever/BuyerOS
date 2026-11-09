# Conversation turns v1 — backend contract (2026-11-08)

Status: implemented in the backend increment behind
`NEXT_PUBLIC_CONVERSATION_HOME=true`. This file is a read model for clients and
reviewers; the authoritative prose stays in
`docs/superpowers/specs/2026-11-08-conversation-turn-contract.md`.

## Endpoints

All under `/v1/workspaces/{workspace_id}/projects/{project_id}/conversation-turns`.

| Method + path | Purpose |
| --- | --- |
| `POST /conversation-turns` | One bounded turn. `thread_id` optional: absent ⇒ create thread + first user message + assistant parts atomically. |
| `POST /conversation-turns/{turn_id}/decisions` | Explicit approve/reject of one persisted inline proposal. Returns a continuation turn. |
| `POST /conversation-turns/{turn_id}/cancel` | Stops undispatched steps; reports already-dispatched liability honestly. |

Headers: `Authorization: Bearer …`, `Idempotency-Key: <8..200 chars>`,
`If-Match: "<thread.version>"` (required for an existing `thread_id`, decisions
and cancel). Responses use the existing `{data, request_id, data_mode}` envelope
and are `no-store`.

### Turn request

```json
{
  "thread_id": "uuid | null",
  "client_message_id": "uuid",
  "expected_thread_version": 7,
  "language": "en | zh-HK",
  "text": "Research this buyer and prepare a follow-up",
  "skill_id": "sales-research | null",
  "template_id": "one of the seven thread templates | null",
  "buyer_id": "uuid | null (only honoured when this request creates the thread)"
}
```

`text` is 1..4000 non-blank characters; `skill_id` must resolve in the
code-owned registry. A replayed `client_message_id` for the same actor returns
the recorded turn; a different payload under the same key is
`409 IDEMPOTENCY_CONFLICT`.

### Turn response

```json
{
  "thread": { "…ServerThread with messages[]…" },
  "turn": {
    "id": "uuid",
    "status": "completed | needs_input | needs_approval | failed | outcome_unknown | cancelled",
    "parts": [ "MessagePart" ],
    "notices": [ { "code": "…", "message": "…", "recovery": {"label": "…", "href": "/…"} } ]
  }
}
```

### Turn events, SSE stream and reconciliation (Increment C)

`conversation_turn_events` (Alembic `0068_conversation_turn_events`) stores
derived, tenant-scoped, append-only turn events: `turn.started` (first),
`part` `{index, part}`, `tool` `{call_id, capability, state, summary?,
error_code?}`, `proposal` `{proposal_id, capability, requires_approval}`,
`notice` `{code, message}` and exactly one terminal `turn.final` `{status}`.
Events are written in the same transaction as the turn/part/status they
describe, so the terminal event can never disagree with the persisted turn
status. Per-turn `seq` is allocated by a shared allocator that flushes pending
rows first; `UNIQUE(turn_id, seq)`.

`GET ?/conversation-turns/{turn_id}/events?after=<seq>` returns
`text/event-stream` (`Cache-Control: no-store`, `X-Accel-Buffering: no`),
replays persisted events with `seq > after`, emits `: heartbeat` comments, and
live-tails until `turn.final` or a bounded deadline. Reconnecting with the last
seen seq never duplicates and never re-executes work. A foreign turn is `404`;
a non-integer/negative cursor is `422`.

`POST ?/conversation-turns/{turn_id}/reconcile` (Idempotency-Key required) is
valid only for an `outcome_unknown` turn (else `409 INVALID_STATE`). It performs
a strictly read-only probe of already-persisted evidence (canonical sales task
and output state; no provider receipts are created), then persists a
continuation turn with the resolved `completed`/`failed`/`outcome_unknown`
outcome, its events and an audit row. It never dispatches, reserves or retries
a provider call; replays return the recorded continuation.

### Thread company link

`POST /conversation-turns` accepts `buyer_id` **only on the thread-first path**.
The server validates that the canonical buyer exists in this workspace and
project, that the actor has the native buyer-read permission, and rejects
unknown/foreign ids with `404` (no existence leak). The link is immutable for
the discussion: a later turn that supplies a different `buyer_id` fails with
`409 BUYER_LINK_MISMATCH`. `ServerThread` gains `"buyerId": "uuid | null"`.

A turn-first request has no selected source yet (Amendment A1 creates the
thread shell); the created turn is therefore honestly `needs_input` with a
`SOURCES_REQUIRED` notice. Citations and inline proposals require an explicit
source selection on an existing thread (or an enrichment proposal, which only
needs the linked buyer). At most two proposals are emitted per turn so the
persisted step counter stays within the reviewed ceiling.

Grounding includes the linked buyer as a citation item
`{"id": "buyer:<uuid>", "label": "<display name>", "kind": "buyer"}`; only the
minimal projection (id, company id, canonical display name, domain, review
state) is used — never contact data.

### Thread messages

```json
{ "id": "uuid", "seq": 12, "role": "user | assistant", "text": "...",
  "client_message_id": "uuid | null", "turn_id": "uuid | null",
  "parts": [ "MessagePart" ] }
```

Legacy rows read as `role: "user"` with no `parts`. `seq` is monotonic per
thread. Unknown `role`/`parts[].kind` must degrade to plain `text`.

### MessageParts

| kind | JSON payload |
| --- | --- |
| `text` | `{text, language}` |
| `citations` | `{items: [{id, label, kind, href?}]}` |
| `tool_activity` | `{call_id, capability, title, state, started_at, finished_at?, summary?, error_code?}`; state is `proposed → approved → running → completed / failed / skipped / outcome_unknown` |
| `proposal` | `{proposal_id, capability, title, rationale, arguments_preview, cost?, requires_approval: true}` |
| `output_link` | `{output: {output_id, kind, revision, status}, title, href?}` |
| `notice` | `{code, message, recovery?}` |

Decision body: `{proposal_id, decision: "approve" | "reject",
expected_thread_version}`. Approval re-runs the current membership, role,
project/tenant, language, source-authority and policy/budget gate checks at
execution time. Execution reuses the existing typed services
(`create_task` + `assemble_or_core` + `save_output` from the sales-task /
sales-output owners); no new permission surface, no provider dispatch in this
increment.

Capabilities proposed in this increment: `documents.read`
(`understand-documents`), `research.read` (`sales-research`/`sales-quick`),
`xverum.enrich_company` (when the thread has a linked buyer and the intent is
company enrichment) and `drive.read` (when the thread selects an authorised
Drive source). The last two are **proposal-only**: approving one records the
decision and a terminal `failed` turn with an honest notice
(`SALES_ADMISSION_DISABLED`, `PAID_ADMISSION_DISABLED`,
`EXECUTION_RUNTIME_REQUIRED`, `XVERUM_NOT_CONFIGURED`,
`XVERUM_DISPATCH_NOT_ENABLED`, `DRIVE_NOT_CONFIGURED`,
`DRIVE_SOURCE_UNAVAILABLE`, `DRIVE_READ_NOT_ENABLED`); no provider transport is
constructed and no spend is reserved. A workspace without sales admission receives a
`SALES_ADMISSION_DISABLED` notice instead of a proposal or execution. Paid Xverum
dispatch and `opencode-go` model admission remain behind their existing,
separately-reviewed gates.

## Persistence

Alembic revisions `0066_conversation_turns` and `0067_conversation_buyer`:

- `conversation_thread_messages` + `role`, `seq` (unique per thread, backfilled
  from `created_at, id`), `client_message_id` (partial unique per thread),
  `turn_id`, `parts`.
- App-rollback compatibility: a `BEFORE INSERT` trigger
  (`conversation_thread_message_seq`) allocates `seq` for the previous
  application revision, whose inserts carry only the legacy columns. Downgrade
  refuses when any assistant turn, typed part, client message id or turn id
  exists; for legacy-only notes it drops the added columns and ordering falls
  back to `created_at, id` (note text is preserved; typed turn history is not).
- `0067_conversation_buyer`: `conversation_threads.buyer_id` (nullable
  workspace+project composite FK to `project_buyers`, `ON DELETE SET NULL
  (buyer_id)`); the proposal capability CHECK accepts
  `xverum.enrich_company`/`drive.read`; the parts validator is a backward-safe
  superset (buyer citation kind, credit-cost `known` flag). Downgrade refuses
  while any company link or proposal-only capability decision exists.
- `conversation_turns` — one row per user turn or continuation; unique
  `(workspace_id, thread_id, client_message_id)` and unique
  `(workspace_id, actor_id, client_message_id)` so a duplicate submission cannot
  create a second thread or a second turn.
- `conversation_turn_proposals` — trusted typed arguments/source refs, preview,
  status and revision; unique per proposal id.
- `conversation_turn_decisions` — at most one effective decision per proposal
  (`unique(workspace_id, proposal_id)`), with the continuation turn id.

Forced RLS on every table; no `buyeros_worker` grants; thread deletion cascades
the transcript, proposals and decisions.
