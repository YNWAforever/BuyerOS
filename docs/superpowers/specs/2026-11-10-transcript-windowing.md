# Increment 3.3 contract — transcript windowing for long discussions

Status: implementation contract. Frontend + gate only; no backend change.

## Why

Phase 3.1 of the objective is message pagination/virtualisation. The server contract
caps a discussion at **100 notes** (`MESSAGE_LIMIT`), so a thread read is already
bounded at the data layer; the remaining scale problem is rendering: the transcript
mounts every persisted entry (with rich parts, proposals, citations) plus live
entries. This increment bounds the rendered window without changing the data
contract or losing content, so a full 100-message discussion stays responsive.

## Contract

- **Bounded initial window**: the transcript renders only the most recent `WINDOW`
  persisted entries (pick a small constant, e.g. 25 entry groups; document it). When
  more persisted entries exist, a `Show earlier messages` button appears above the
  list; each activation reveals the next batch (e.g. 25) until all are shown, then
  the control disappears. No network request is made; data stays in memory.
- **Never lose or duplicate an entry**: after revealing, every persisted entry is
  present exactly once in order; a newly loaded/streamed entry never displaces the
  user's revealed older entries and is always visible when it arrives if the user is
  at the latest position.
- **Scroll stability**: revealing earlier messages must not jump the viewport — keep
  the previously visible message anchored (adjust scrollTop by the height added
  above), and keep the existing jump-to-latest behaviour only when the user is not
  already at the latest content.
- **Accessibility**: the control is a real button with an accessible name and batch
  count if useful (but no secondary-label bloat per AGENTS.md); the transcript keeps
  its `role="log"` semantics; live additions are still announced; the revealed
  entries are not announced as new messages (they are historical).
- **Empty/short discussions**: no control when the entry count fits the window; a
  single-page thread renders exactly as today.
- EN + zh-HK for the new label(s). 320 px and 200% zoom keep working (the control
  wraps, no horizontal overflow).
- No backend, `.github` (except the core gate constant), dependency or part-type
  change; do not rename existing classes/semantics relied on by the 29 scenarios.

## Tests

- Unit: window state reducer — initial visible subset, reveal batch math, boundary
  exactly `WINDOW`, no-op when everything is shown, live entry appended keeps the
  revealed set stable, total revealed never exceeds persisted total.
- Browser gate (1 new scenario, keep the 29 existing strong): fixture thread with 100
  messages → initial rendered entries are bounded and the control appears; each
  activation adds exactly one batch with no duplicates/loss and no jump while
  anchored; control disappears after all are shown; a live reply still arrives and is
  visible; jump-to-latest works; zh-HK label; 320 px no overflow; 200% zoom keeps the
  control reachable; no page errors. Report the new core count (currently 183) and
  the scenario count (29 → 30).
