# Increment 3.6 contract — per-turn metrics and budget dashboard

Status: implementation contract. Backend aggregate endpoint + read-only client
panel; one additive migration for event boundary instants
(`0072_turn_event_boundaries`), no new producer, no provider call.

## Why

Phase 3 asks for per-turn metrics and budget visibility next to the conversation
studio. The persisted rows already contain everything needed: turn statuses,
inline proposals with `cost`, decisions, notices and application-observed turn
boundaries. Adding a metrics producer or a metrics table would duplicate
authority; instead the dashboard is a bounded read over existing tenant-scoped
rows.

## Contract

`GET /v1/workspaces/{workspace_id}/projects/{project_id}/conversation-turns/metrics?window_days=<n>`

- `window_days` is an integer `1..30`, default `7`; any other value is
  `422 INVALID_REQUEST`. The service re-validates (bounded and type-strict) so
  no other caller can widen the scan.
- The window filters on `conversation_turn_events.created_at` so turns whose
  events were retained away are not counted as fresh activity; turn, proposal
  and decision counts are joined through that same bounded window turn set.
  The window is a time bound, not yet an index-backed range: a composite
  `(workspace_id, project_id, created_at)` index is a recorded Phase 3
  hardening follow-up (the current event index is `(workspace_id, turn_id,
  seq)`).
- Latency is **application-observed** `turn.started.payload.started_at` →
  `turn.final.payload.finished_at` per turn. Every event of a turn is appended
  inside the turn's transaction and therefore shares
  `conversation_turn_events.created_at`; that timestamp is never used as a
  latency sample. Historical events without boundary instants contribute no
  sample; `p50`/`p95`/`max` are `null` when there are no samples (the UI
  renders an em dash, never an invented `0 ms`). Migration
  `0072_turn_event_boundaries` extends the event predicate function to validate
  the optional instant fields without changing any table or column.
- Proposal budget is derived from `ConversationTurnProposal.cost` JSON. The
  split follows `cost.kind`: deterministic `nonbillable` work is counted as
  no-cost and never added to `estimated`; a `provider_credits` cost whose
  `known` is not exactly `true` (including the DB-permitted `null`) is counted
  as unknown price and never summed as zero; priced amounts sum by unit as
  exact decimal strings, and `may_incur_provider_charges` is surfaced without
  inventing a tariff.
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
  windows rejected as `422`, honest `CONVERSATION_MODEL_UNAVAILABLE` counting,
  empty budget estimates, and a deterministic latency sample that proves the
  metric reads the observed payload boundaries rather than the shared
  transaction `created_at`.
- DB constraint tests (`test_conversation_turn_events_db.py`): the 0072
  predicate accepts optional valid boundary instants, keeps old payloads valid,
  and rejects malformed/unknown fields.
- Unit tests (`test_conversation_metrics_unit.py`): window bounds, percentile
  behavior, boundary parsing and the priced/unknown/no-cost budget split.
- Core tests (`tests/core-conversation-metrics.test.mjs`): URL/scope building,
  fail-closed payload validation (unknown statuses, inconsistent totals,
  negative/fractional counts, unbounded window, unknown units/exponents), honest
  latency formatting and exact decimal formatting, and an empty state driven by
  turns (not by latency samples).
- Browser gate (`tests/conversation-home-responsive.test.mjs`): the context panel
  exposes a keyboard-reachable "Turn metrics" tab, renders the bounded
  aggregates with no thread content in the request, and a failed read shows an
  honest notice with no invented zeros.
