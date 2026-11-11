# Increment 3.6 contract — per-turn metrics and budget dashboard

Status: implementation contract. Backend aggregate endpoint + read-only client
panel; no migration, no new producer, no provider call.

## Why

Phase 3 asks for per-turn metrics and budget visibility next to the conversation
studio. The persisted rows already contain everything needed: turn statuses,
derived turn-event timestamps, inline proposals with `cost`, decisions and
`CONVERSATION_MODEL_UNAVAILABLE` notices. Adding a producer or a metrics table
would duplicate authority; instead the dashboard is a bounded read over existing
tenant-scoped rows.

## Contract

`GET /v1/workspaces/{workspace_id}/projects/{project_id}/conversation-turns/metrics?window_days=<n>`

- `window_days` is an integer `1..30`, default `7`; any other value is
  `422 INVALID_REQUEST`. The service re-validates (bounded and type-strict) so
  no other caller can widen the scan.
- The window filters on `conversation_turn_events.created_at` so turns whose
  events were retained away are not counted as fresh activity; turn, proposal
  and decision counts are joined through that same bounded window turn set.
- Latency is `turn.started` → `turn.final` per turn. A turn missing either
  boundary contributes no sample; `p50`/`p95`/`max` are `null` when there are no
  samples (the UI renders an em dash, never `0 ms`).
- Proposal budget is derived from `ConversationTurnProposal.cost` JSON: priced
  proposals sum by unit as exact decimal strings, `known:false` counts as
  unknown price, no-cost proposals are counted separately and
  `may_incur_provider_charges` is surfaced without inventing a tariff.
- Response contains aggregate counts only: no thread text, message text,
  proposal arguments, citations or user identifiers. No dispatch, reservation,
  retry or re-pricing occurs.
- READ authority: the same project access check as other conversation reads; any
  access role may read aggregates. Response is `Cache-Control: no-store`.
- OpenAPI operation id: `readConversationTurnMetrics`. Route is registered only
  with the conversation-home flag, like the other turn routes.

## Verification

- DB tests (`services/api/tests/test_conversation_metrics_db.py`): project
  isolation within one workspace, bounded window excluding aged events, invalid
  windows rejected as `422`, honest `CONVERSATION_MODEL_UNAVAILABLE` counting and
  empty budget estimates.
- Core tests (`tests/core-conversation-metrics.test.mjs`): URL/scope building,
  fail-closed payload validation (unknown statuses, inconsistent totals,
  negative/fractional counts, unbounded window, unknown units/exponents), honest
  latency formatting and exact decimal formatting.
- Browser gate (`tests/conversation-home-responsive.test.mjs`): the context panel
  exposes a keyboard-reachable "Turn metrics" tab, renders the bounded
  aggregates with no thread content in the request, and a failed read shows an
  honest notice with no invented zeros.
