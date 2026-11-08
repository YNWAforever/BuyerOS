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
  "template_id": "one of the seven thread templates | null"
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

Only nonbillable capabilities are proposed in this increment
(`documents.read` on `understand-documents`, `research.read` on
`sales-research`/`sales-quick`). A workspace without sales admission receives a
`SALES_ADMISSION_DISABLED` notice instead of a proposal or execution. Paid Xverum
dispatch and `opencode-go` model admission remain behind their existing,
separately-reviewed gates.

## Persistence

Alembic revision `0066_conversation_turns`:

- `conversation_thread_messages` + `role`, `seq` (unique per thread, backfilled
  from `created_at, id`), `client_message_id` (partial unique per thread),
  `turn_id`, `parts`.
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
