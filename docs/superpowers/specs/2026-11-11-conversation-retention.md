# Increment 3.4 contract — retention enforcement for derived conversation data

Status: implementation contract. Backend + worker only; no browser or core change.

## Why

Phase 3.4 requires retention enforcement next to the new per-workspace turn
limit. Two append-only structures grow with usage and are derived rather than
user content:

- `conversation_turn_events` — SSE replay events. The persisted transcript
  (`conversation_turns.parts`, thread messages, decisions) is authoritative; an
  event replay only reconstructs an in-flight turn.
- `api_rate_windows` and `conversation_turn_rate_windows` — per-minute counters
  whose only purpose is the current window.

Without a sweep both grow forever. User content (turns, parts, proposals,
decisions, reconciliations, thread messages) is never pruned by this increment.

## Contract

- **Explicit, reviewed windows** in `WorkerSettings`:
  `conversation_event_retention_days` (default 30, 0 disables) and
  `turn_rate_window_retention_minutes` (default 1440, 0 disables). Values are
  validated by pydantic bounds; the service also validates non-negative ints and
  a bounded sweep limit (≤ 5000) before any query runs.
- **Bounded, tenant-scoped sweeps** in
  `buyeros_api/services/conversation_retention.py`:
  - events: select at most `limit` expired ids per workspace, then delete
    exactly those ids in the same tenant transaction;
  - windows: delete rows with `window_start < now - retention_minutes` per
    workspace in both counter tables.
  The workspace directory is read once; every mutation runs inside
  `tenant_session`, so forced RLS applies. A second sweep is a no-op.
- **No evidence loss**: pruning events cannot change a turn's status, parts,
  notices or the thread version (asserted). A pruned replay degrades to the
  persisted transcript; no new recovery path is introduced.
- **Wiring**: the existing periodic worker `sweep_sync` calls both sweeps after
  the source/contact retention pass, before outbox sweeping. Limits use the
  existing `batch_size` with a floor of 100 so one sweep cannot occupy a worker.
- **Migration 0071** grants the worker role only what the sweeps need:
  `SELECT, DELETE` on `conversation_turn_events` (worker still cannot INSERT or
  UPDATE events; the API remains the only producer) and `DELETE` on
  `conversation_turn_rate_windows`. `api_rate_windows` already had
  `SELECT, DELETE` from 0033. The readiness function is refenced to
  `0071_conversation_retention`; downgrade revokes the grants and restores the
  0070 fence.
- No table/column/RLS-policy change other than the grants; no API route, UI,
  contract or dependency change.

## Tests

- New PostgreSQL tests (`tests/test_conversation_retention_db.py`, 4):
  expired windows pruned per workspace while fresh windows and the other
  workspace survive (counted return value, second sweep no-op); only expired
  derived events pruned while turn content and thread version are byte-identical
  before/after; `0` disables both sweeps; invalid retention/limit rejected
  before any query.
- Existing invariant tests updated: the event-store contract now expects the
  worker's least-privilege `SELECT, DELETE` (still no INSERT/UPDATE), and the
  rate-window migration test expects `DELETE` only for the worker.
- API pytest inventory 4039 → **4043** (CI `--expected-count` and its guard
  updated). Worker inventory unchanged. Browser gate and core client suite are
  unaffected (no frontend change).
