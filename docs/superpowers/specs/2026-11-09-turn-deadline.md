# Increment 3.2 contract — bounded turn deadline and timeout taxonomy

Status: implementation contract. Backend-only, additive. It does not change
authority, approvals, budgets or provider behaviour; it bounds how long a
synchronous turn may occupy a request and makes every timeout outcome explicit.

## Problem

A turn is a synchronous, bounded request. Today nothing caps the wall-clock time a
turn may spend across its steps and reads: a slow database or a future async step
could hold the request until the hosting timeout (90 s on Vercel) and return an
opaque platform error. The 60-second read incident class must not return as an
unexplained stall.

## Contract

- A reviewed setting `turn_deadline_seconds` (default **60**, allowed 5–90) bounds
  one turn's server work.
- The deadline is checked before each step and before/after long reads, not only at
  the end, so the turn stops as soon as the bound is crossed.
- When the deadline is crossed:
  - the turn terminates as `failed` with a persisted notice
    `{code: 'TURN_DEADLINE_EXCEEDED', message: <localized>}`;
  - parts produced so far are persisted and visible (nothing erased);
  - the terminal `turn.final` event is appended in the same transaction;
  - no new step is started; a step already dispatched is not duplicated, and its
    liability is reported honestly (`outcome_unknown` when it cannot be known);
  - the response is `200` with the failed turn (not a 5xx and not a silent hang).
- Timeout taxonomy (each maps to a persisted notice code, never raw provider text):
  `TURN_DEADLINE_EXCEEDED`, `TURN_BUSY_RETRY` (a bounded single retry when a lock
  wait exceeds a short threshold), and the existing configuration/admission codes.
- Idempotency: replaying the same `client_message_id` returns the recorded failed
  turn; it does not start the work again.
- Decisions are unaffected: a decision continuation has the same deadline bound and
  the same honest terminal notice.

## Non-goals

- No queue/worker; the turn stays synchronous.
- No change to retry, admission or pricing semantics.
- No new external call.

## Tests

- Unit: deadline arithmetic, check placement, notice mapping, no second step start.
- API/DB: a turn with an exhausted deadline returns 200 + `failed` +
  `TURN_DEADLINE_EXCEEDED`, persists produced parts and the terminal event, does not
  create a provider stage/receipt/reservation, and replays idempotently; a decision
  continuation does the same; a normal turn is unaffected.
- Registry/contract: the setting is validated (5–90, integer) and documented.

## Observability

The terminal notice carries the elapsed bucket only (e.g. `over_deadline`), never a
request id, provider reference or payload.
