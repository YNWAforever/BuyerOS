# SME workspace clarity — conversation studio pass (2026-11-13)

Status: PR 1 implemented on `codex/sme-workspace-clarity`; no production alias movement.

## Why

The shopper (SME owner) opens `/app` and still meets an administrator's workspace:
a page heading for the route, a separate workspace/project selector panel, retained
module links beside the discussion surface, and a conversation studio whose first
view is a saved thread. Nothing says “start here”, so the owner cannot tell what the
product is for or what to do next on a Friday afternoon.

The target is the Ads-Copilot shape the owner asked for: one durable conversation
surface, task-first, with the project's native work reachable from it.

## Shape after this pass

Desktop: fixed sidebar (brand, one workspace/project context, `New discussion`,
`Home`, `This project` destinations, account control) plus the studio. Mobile: the
same parts become stacked strips and the studio keeps its drawer/panel views.

### Home (`/app`)

- One h1 (`Home`) in the studio header; no duplicate page heading.
- Project name as a kicker, then `What do you want to get done?`, then the composer.
- Six guided outcome cards. Choosing one prefills the composer for review; it never
  sends on its own.
- `Continue where you left off` — at most three saved threads.
- `Needs attention` — bounded work-queue counts (awaiting review, pending approvals,
  unassigned buyers, failed jobs) with `See all` to `/app/overview`. Reads are
  provider-free and scope-aware; honest loading/empty/error states.

### Navigation

- `New discussion`, `Home`, then `This project` (`Offer`, `Buyers`, `Research`,
  `Outreach`, `Results`, `Documents`).
- `Settings` and `Operations` move into a compact `Manage` group at the end of
  the sidebar instead of sitting beside the conversation. The account control keeps
  identity, language, access details and sign-out.
- Flag OFF navigation is unchanged.

### Shell

- `LiveFrame` accepts a one-time `scope` slot and can hide the repeated page heading
  on conversation routes.
- `LiveTopbar` is breadcrumb-only for conversation routes and is omitted on the
  compact strip when it would be empty.
- `ScopeSwitcher` owns the labelled Workspace/Project comboboxes, `New project`,
  `Check access` and access notices. It is omitted on first-run denial, where the
  full access card remains.
- `AccountMenu` is one disclosure for identity, language, access details, diagnostics
  and Sign out; workspace administration is a single `Manage` navigation entry.

## Second pass (stacked branch `codex/sme-workspace-clarity-2`)

- The context panel is closed until asked for: the thread header owns `Show context panel`
  and the mobile `Details` view; no third column appears on first load.
- `GuidedSales` moves from a disclosure under the composer into a header `Task form`
  drill-down, keeping the transcript and composer as the only primary surfaces.
- Device-only notes move from the bottom of the workspace into the thread-list footer;
  opening one shows a full-width floating panel instead of a squeezed sidebar column.
- Mobile header hides the repeated privacy badge and wraps its actions cleanly.

## Tests

- Static audit (`tests/audit-conversation-home.test.mjs`): navigation destinations,
  permission gates, hidden page heading, scope/account semantics, home copy.
- Browser fixture (`tests/conversation-home-responsive.test.mjs`): task-first home,
  card prefill, draft survival, three mobile views, closed-by-default context panel,
  task-form drill-down, zh-HK, 200% zoom, shell overflow at 320–1440px, account
  reachability.
- `pnpm test:core`: 191/191.
- TypeScript and ESLint clean for the changed files.

Screenshots (local fixture, not production): `work/sme-clarity/*.png` in the main
checkout — home and thread at 1440/1024/390, EN and zh-HK.

## Not in this pass

- No deployment, alias switch or protected promotion. Production remains on the
  audited build until the owner explicitly approves.
- No backend, schema, API or permission changes.
