# Increment 2.7 contract — "Why this proposal" in the thread

Status: implementation contract. UI-first increment; it adds **no authority** and
no provider behaviour. It surfaces what the server already persisted.

## Goal

A proposal card in the transcript can be expanded to explain itself: what the
assistant proposes, why, on what evidence, at what cost/policy state, by whom and
when. A reviewer should be able to decide without leaving the thread.

## Data sources (already persisted — do not invent)

| Field | Source |
| --- | --- |
| capability, title, rationale, arguments preview, cost, requires_approval | the persisted `proposal` part |
| evidence | `citations` parts of the same turn (ids must already be authorised) |
| state (proposed/executed/rejected/failed/outcome_unknown) | the proposal row + `tool_activity` parts |
| decision actor + time | the persisted decision row (`conversation_turn_decisions`) |
| policy/cost state | the notice parts of the same turn (never a fabricated "approved") |

No new endpoint is required for the first version: the thread response already
carries parts. If a field is missing, the expansion says it is unknown instead of
inferring it.

## UI

- Proposal card gets a disclosure: **Why this proposal**.
- Expanded content, in order: rationale → arguments preview (bounded) → evidence
  citations (linked, same allowlist as transcript citations) → cost basis
  (credits/USD wording from the persisted metadata; `known:false` stays
  "cost review required") → policy/approval state → decision actor/time when one
  exists.
- Collapsed by default; keyboard operable; state survives nothing (purely local
  disclosure) and never mutates the turn.
- Unknown/missing fields render as an explicit unknown row, not as blank space and
  not as an inferred value.
- No internal ids, hashes or protocol names in the ordinary path.

## Non-goals

- No new action from the card beyond the existing Approve/Reject.
- No re-fetch of the turn just to expand (unless a field is genuinely absent and a
  single bounded re-read is justified — prefer showing unknown).
- No model/provider call.

## Tests

- Unit: expansion projection from persisted parts (rationale/evidence/cost/state
  mapping, unknown fields, no internal ids).
- Browser gate: expand a proposal → rationale, citations, cost-review wording and
  approval state are visible; Approve remains available; collapse works; a
  terminal proposal shows the decision actor/time and no actions; EN + zh-HK
  labels.
- No weakened assertions in existing rows; the five-plus existing screenshots stay
  intact.
