# Increment 2.5 contract — thread management polish (pin, archive, share ACL)

Status: implementation contract. Backend is complete; this is UI + tests only.

## What exists (verified)

- `PUT /v1/workspaces/{ws}/projects/{pj}/conversation-threads/{id}/preferences`
  takes `{pinned, archived}` and stores a **viewer-scoped** preference (workspace
  member), returning the stored payload. Any access role can set its own view.
- Thread list is already viewer-scoped: `pinned`/`archived` are projected per
  viewer, `pinned` sorts first in the client, and the studio already filters
  archived rows out of the normal view and has an archive-view toggle.
- Shares are complete server-side: `GET /shares` (owner only) returns
  `{version, items:[{member_id, display_name, role:'viewer'|'editor', active}]}`,
  `GET /share-recipients?q=` (owner only, limit 25),
  `PUT /shares/{member_id}` `{role}` and `DELETE /shares/{member_id}` (owner only,
  audited, 25-share limit, idempotent, thread version bumped).
- `ShareThread` already renders the dialog (list/search/grant/revoke/role change)
  and `WorkspaceBadge` renders owner/shared/viewer/editor state.
- Gap: the studio never calls `preferences` (so no pin/unpin or archive/unarchive
  from the conversation surface), and `ShareThread` is rendered for every loaded
  thread, so a non-owner opens a dialog whose reads 404.

## Contract

- **Pin/unpin** from the loaded-discussion menu: `Pin discussion` / `Unpin
  discussion`, persisted through `preferences` with the current `archived` value
  preserved (never clobber the other flag). The row and menu reflect the state
  (`aria-pressed` on the toggle, pin glyph in the list) and the list keeps pinned
  threads first. Available to every access role (it is a personal preference).
- **Archive/unarchive**: `Archive discussion` moves it out of the normal list and
  into the archive view; the archive view offers `Restore discussion` and it
  returns to the normal list. Same preference plumbing, `pinned` preserved.
- **Honest failure**: on a preferences error nothing is optimistically claimed —
  keep the previous state and show the existing inline notice (`role=status`), no
  silent success, no lost draft.
- **Share ACL**: `ShareThread` renders only when the loaded thread's `access` is
  `owner`; viewers/editors get the existing `WorkspaceBadge` pill and no dialog.
  The dialog keeps its current behaviour and version handling; a share change
  updates the header badge (share count) from the returned thread.
- **List consistency**: after a preference change, the affected row's `pinned`/
  `archived` reflects the persisted result without a full reload; a subsequent
  reload/list read agrees with the server.
- EN + zh-HK for every new string; the dialog/toggle keep keyboard access
  (menu summary is a button, Escape closes the menu, focus returns to the trigger
  where the existing pattern does).
- No backend change, no new dependency, no part-type change.
- 320 px: the menu actions stay inside the viewport (no overflow), and the pin
  glyph does not change row width.

## Tests

- Unit: preference payload preserves the other flag (pin sets `archived` from the
  current view, archive sets `pinned` from current row), role-independent
  availability, share visibility only for owner, failure keeps state.
- Browser gate: pin from the menu → row shows pinned and pinned-first ordering and
  `aria-pressed`; reload → still pinned (server-backed); archive → row disappears
  from normal list, appears in archive view, restore returns it; a viewer/editor
  can pin/archive but has **no** `Share discussion` control; a preferences 500
  shows the inline notice and leaves the row unchanged; 320 px open-menu overflow
  guard. Keep the 26 existing scenarios strong (core 174 now).
