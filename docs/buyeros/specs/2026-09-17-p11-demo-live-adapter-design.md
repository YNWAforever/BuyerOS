# P11 design — demo/live adapter boundary (BO-006)

**Status: PROPOSED / PLAN ONLY.** Plan revision v1. Recorded 2026-09-17 (Hong Kong).

No application code, lockfile, dependency install, migration, cloud resource, deployment, Site access change, paid provider call, mailbox connection, message, or send is authorized by this document. Execution happens only under an explicit dependency waiver, on the separately approved task.

Related records: [P1 boundary](2026-09-15-p1-boundary-design.md), [P9 API surface](2026-09-15-p9-api-surface-design.md), [P10 bearer identity](2026-09-16-p10-bearer-identity-design.md), [BO-006 task](../tasks/BO-006-separate-demo-state-from-authenticated-live-adapters.md), [03 contracts](../03_DATA_API_AND_STATE_CONTRACTS.md), [contracts/openapi.proposed.yaml](../contracts/openapi.proposed.yaml). Base: `main` @ `3f10f41` (P9 merged); branch `p11-demo-live-adapter`.

## Scope

Introduce an explicit demo/live data-source boundary in the browser client, so the existing screen shell can serve a live tenant without ever mixing live data with the demo fixtures. Live reads are wired against the API P9/P10 shipped; the live path is gated, off by default, and proven against a stubbed fetch. No live writes, no real token acquisition, and no UI redesign.

**What exists today.** The whole workspace is one client component (`features/workspace.tsx`, ~47 KB) holding `useState<Store>(seed)` and importing the demo fixtures, the mock helpers and the run engine directly. `services/http-client.ts` re-exports a mock whose `request()` throws `NOT_CONFIGURED`; it has **no callers**. There is no `services/live/`, no client-side configuration mechanism, and no JS test runner — the repository's convention is standalone node scripts (`tests/domain-checks.mjs`, run as `node tests/domain-checks.mjs`).

**Relationship to BO-006.** The task's proposed file list (`services/live/client.ts`, `services/live/mapping.ts`, `features/providers/data-mode.tsx`, `features/providers/workspace-session.tsx`, a frontend test) is adopted, with two recorded deviations: the test is a node script rather than Playwright (see §F), and there is no client-side mode switch (see §B).

## A. Boundaries and units

```
app/layout.tsx                             server: resolve mode once, pass down
features/providers/data-mode.tsx     NEW   read-only mode + apiBaseUrl context and availability helper
features/providers/workspace-session.tsx NEW live read state; scope key; abort; no demo coupling
services/live/client.ts              NEW   typed fetch: bearer header, error envelope, abort
services/live/mapping.ts             NEW   API payloads -> narrow read models, strictly
services/http-client.ts              MOD   becomes the mode-aware resolver
features/live/overview.tsx           NEW   live workspace/project context panel
features/live/projects.tsx           NEW   live project and ICP version reads
features/live/buyers.tsx             NEW   live buyer reads
features/live/unavailable.tsx        NEW   shared availability notice (state + reason)
features/workspace.tsx               MOD   four targeted edits; shell and demo sections unchanged
tests/live-adapter-checks.mjs        NEW   node-script checks (domain-checks.mjs convention)
locales/index.ts                     MOD   labels for live, partial and unavailable states
```

Each unit has one job and can be understood without reading the others:

- `client.ts` knows HTTP, headers, the error envelope and abort. It knows nothing about UI or about demo fixtures.
- `mapping.ts` knows how to turn an API payload into a view model, strictly. It knows nothing about transport.
- `data-mode.tsx` knows which mode is active and what each section's availability is. It holds no data.
- `workspace-session.tsx` knows live reads, the scope key and invalidation. It never reads demo state.
- `features/live/*` are thin renderers over the read models and availability values.
- `workspace.tsx` chooses between two already-built views and gains no new data logic.

## B. Mode resolution and the adapter contract

**Mode is a server decision, never client state.** The root layout is a server component; it resolves the mode once and passes it to the workspace as a prop wrapped in the data-mode provider.

- The API base URL comes from server configuration (`BUYEROS_API_BASE_URL` in the server runtime environment). **Absent or empty means `demo`.** Present means `live`. The `BUYEROS_` prefix matches the API service's own environment convention.
  **Assumption to verify (NOT RUN):** that the worker runtime exposes `process.env` to server code (`vite.config.ts` enables `nodejs_compat` and `scripts/sites-env.mjs` reads `process.env`, so this is expected but unproven). If it does not, the resolution falls back to the equivalent Cloudflare binding. The implementation must confirm this before wiring the layout, and record the observed mechanism.
- There is no UI control that changes mode and no browser-storage key that influences it. The demo banner is rendered *from* the resolved prop, so removing the banner cannot change the mode or make a connection appear live.
- Live is off in this phase because no identity provider is configured (B-IDENTITY). The resolution logic is written and tested now, so enabling live later is a configuration change, not a code change.

**Recorded deviation.** The BO-006 task text says "Switching to demo requires an explicit mode action, never an error handler." This design has no client mode action at all: mode is resolved server-side. That satisfies the intent more strongly (no error path can ever switch mode) and matches the task's own step 6, but there is deliberately no in-app mode switch in this phase.

**Capability is not permission.** Mode selects the adapter; it grants nothing. In live mode the API remains the only authority, and its `401`/`403`/`404` is the answer. The client never infers access from mode.

**The adapter contract** (`services/live/client.ts`): one entry point.

```
request<T>({ path, method, scope, token, signal }) -> Promise<T>
```

- **Envelope.** Success responses are `{data, request_id, data_mode:"live"}`; the client unwraps `data`. Any non-2xx is rejected as a typed `LiveError {code, message, requestId, retryable, status}` built from the API's error envelope, so callers branch on `code` and never on status text.
- **Bearer.** A token is attached only when the session supplies one. Tokens are held in memory only: never in `localStorage`, never in a URL, never logged.
- **Scope.** Every request carries a scope key (mode + actor + workspace + project). A response whose scope no longer matches the session is discarded rather than applied.
- **Abort.** Switching scope aborts in-flight requests. Abort is a normal outcome, not an error.
- **No demo coupling.** No live response is ever written into the demo `Store` or into any demo storage key.

**Reads only.** This phase wires exactly `listWorkspaces`, `listProjects`, `getProject`, `listICPVersions`, `listBuyers`. The module is shaped so a later write is a new method carrying its own idempotency and version-precondition handling; no write is wired now.

## C. Live read models and availability

**Narrow read models** (`services/live/mapping.ts`), mapped from the generated `buyeros-api.ts` types, containing only fields the API actually returns:

| Model | Fields | Source operation |
|---|---|---|
| `LiveWorkspace` | `id`, `name`, `roles` | `listWorkspaces` |
| `LiveProject` | `id`, `name`, `status` | `listProjects` / `getProject` |
| `LiveIcpVersion` | `id`, `number`, `contentHash`, `status`, `approvedAt` | `listICPVersions` |
| `LiveBuyer` | `id`, `name`, `note` | `listBuyers` |

Mapping is **strict**: if a payload lacks a field the model requires, the mapper raises a typed error rather than coercing to an empty string or null. An absent value must never render as if it were a finding. This applies to every required field without exception — including `roles`, which is contract-required and must **not** default to an empty list, since "a member with no roles" is a different and misleading claim. Wrong-typed values inside a required field (for example a non-string element in `roles`) are shape surprises and raise too. Only genuinely nullable fields (`note`, `approvedAt`) may be `null`, and only when the payload says so.

**Availability is explicit.** Each section carries one of `available | unavailable | not_configured | denied`, and it is never inferred from empty data.

- **Available in live mode:** workspace selection, project list and detail, ICP version list, buyer list and detail.
- **Unavailable in live mode:** Find Buyers (fit, evidence, runs), Buyer Lists, Outreach (drafts, quotes), Results (outcomes, usage). Where the API is actually called it answers `501 NOT_IMPLEMENTED` and that code is shown; where a section has no backing operation the UI says so without calling.
- **Not configured:** live is off; the banner states it and no live request is made.
- **Denied:** a `401`/`403` from the API is shown as-is, with no automatic replay.

**Isolation guarantee.** In live mode the fixture-derived state and the demo storage keys (`buyeros-demo-v1`, `buyeros-drafts-v1`, `buyeros-prefs-v1`) are neither read nor written, and the demo `Store` is never constructed. Only locale and non-sensitive preferences may persist. Demo mode is unchanged.

## D. Workspace wiring and isolation

The workspace shell (sidebar, navigation, header, banner, drawers, tables, styling) is preserved. `features/workspace.tsx` receives four targeted edits and no new data logic:

1. Read the mode from the data-mode provider.
2. Gate the demo-only effects on demo mode: the `buyeros-demo-v1` restore, the preferences write, the run-progress timer, and the `modelContext` tool registration. In live mode none of these runs — the isolation guarantee is enforced at the effect boundary, not by hoping the data goes unused.
3. Wrap the existing section blocks in a demo-mode branch and add a sibling live-mode branch. The demo branch is unchanged.
4. Render the banner and connection state from the resolved mode.

The live view is composed from the new small components in `features/live/`, including a shared `LiveUnavailable` that renders an availability state with its reason. `features/providers/workspace-session.tsx` owns the live read state, the scope key, the abort controller and the in-memory token, and is the only unit that calls the live client.

Transient UI state (drawer, tabs, filters, modals) stays component-local and is never persisted.

**WebMCP stays synthetic.** The `modelContext` tool surface is demo-only: in live mode it is not registered, so no live record can pass through a demo tool.

## E. Errors, abort and tenant-switch safety

Every non-2xx becomes a typed `LiveError`; the UI branches on `code`:

| API result | UI state | Retry |
|---|---|---|
| no token configured | `not_configured`; no request is sent | no |
| `401 UNAUTHENTICATED` | `denied`, sign-in required | no |
| `403 PERMISSION_DENIED` | `denied` for that section | no |
| `404 NOT_FOUND` | not-found for that resource, never an empty success | no |
| `501 NOT_IMPLEMENTED` | `unavailable` (the expected state for unsupported sections) | no |
| `429`, `503`, network error, timeout | `transient`, with a manual retry | yes, manual |
| malformed or unexpected payload | `error`, surfaced | no |

Two rules matter more than the table: a failure **never** falls back to demo data, and `empty` and `unavailable` are distinct states so a missing list can never read as "we searched and found nothing".

**Scope, abort and late responses.** The session holds a scope key (mode + actor + workspace + project) and one abort controller:

- Changing workspace or project, or unmounting, aborts in-flight requests and advances the scope key.
- A response that resolves with a stale scope key is discarded before it can touch state, so a slow response for workspace A cannot overwrite what the user sees in workspace B.
- An abort produces no toast, no error state and no retry.
- A rapid A to B to A switch leaves only the newest scope's result rendered; older resolutions are dropped by key, not by arrival order.

**Token handling.** With no token, authenticated calls are not attempted: the section reports `not_configured` rather than provoking a pointless `401`. A token that is present but rejected produces the API's real `401`, and nothing is replayed automatically.

## F. Testing and acceptance mapping

Testing follows the repository's convention: a new `tests/live-adapter-checks.mjs` run as `node tests/live-adapter-checks.mjs`, using `node:assert` and the already-installed `typescript` to transpile the units on the fly. **No new dependency is added**, and the existing 11 `tests/domain-checks.mjs` checks must remain green.

All live behaviour is exercised against a **stubbed fetch**: no network, no identity provider, no credentials.

- **TEST-BO-006-01** — with the stub returning `503`, a parse failure, a timeout, and malformed JSON, the live state is `unavailable`/`error` with zero buyers, no demo fixture identifier ever appears, and the demo store is never consulted (a spy that throws if touched). Separately, `seed()` still yields 24 distinct companies, so demo is provably unaffected.
- **TEST-BO-006-02** — a deferred response for workspace A is resolved only after switching to B; A's response is discarded by scope key, B's renders, and A's request was aborted. The A to B to A race is included.
- **TEST-BO-006-03** — with a recording fake storage, live mode writes no demo key and no token-shaped value; the WebMCP tool registration is skipped in live mode.

Unit coverage supporting those: mode resolution (`apiBaseUrl` absent means demo, present means live, no client control); each API `code` to its UI state (`501` to unavailable, `401` to denied, `404` to not-found, `429`/`503` to transient, `403` to denied); and a payload missing a required field raising a typed error rather than yielding an empty value.

**Recorded deviation.** The BO-006 task specifies `pnpm exec playwright test tests/frontend/data-mode.spec.ts`. Playwright is a new dev dependency with browser downloads under this repository's strict pnpm supply-chain policy. The node-script convention is used instead, consistent with `tests/domain-checks.mjs`.

**Honest limit.** A node script cannot render React. These checks cover every seam decision as a pure function; `features/live/*` and the `workspace.tsx` branch are thin renderers over those functions. DOM-level assertions are not covered this phase.

## G. Out of scope (recorded, not silently dropped)

- **Live writes** (`createProject`, `saveICPVersion`, `approveICPVersion`) and their idempotency and version-precondition semantics.
- **Real token acquisition and Auth0 activation** (B-IDENTITY). Live mode is gated and off; the authenticated round trip is not exercised.
- **CORS and CSRF posture.** With live off there is no cross-origin traffic; no wildcard-credentials CORS is introduced. This must be decided before live is enabled.
- **Audit hooks** carrying actor/workspace/request identifiers.
- **Live implementations** of discovery, outreach and results; they remain labelled unavailable.
- **DOM/browser tests** and any real-browser harness.
- **UI redesign.** The shell, navigation, tables, drawers and styling are preserved.

## Completion criteria

The phase is complete only when its acceptance evidence is recorded and reviewed. A demo-mode session rendering 24 fixture companies is the working state; live mode being off is expected, not a failure. The passing integration is a stubbed live fetch proving isolation, tenant-switch safety and storage hygiene.

## Rollback / roll-forward

Disable live by removing the API base URL from server configuration; demo mode continues unchanged and no live record enters demo state. Revert the adapter wiring without migrating anything between modes. Supersede this design with a dated successor for design changes.
