# Build approval record — P11 demo/live adapter (BO-006)

**Status: APPROVED (owner-authorized this session).** Plan revision v1. Recorded 2026-09-17 (Hong Kong).

| Field | Value |
|---|---|
| Task | **BO-006** — separate demo state from authenticated live adapters |
| Phase | **P11 demo/live adapter boundary** (first client-side connection to the live API) |
| Scope | A server-resolved demo/live mode boundary; pure, dependency-free seam modules (mode, mapping, transport, session scope, read path, storage guard); thin React providers and live panels; four targeted edits to the workspace shell; a node-script check suite |
| Spec | `docs/buyeros/specs/2026-09-17-p11-demo-live-adapter-design.md` |
| Plan | `docs/buyeros/plans/2026-09-17-p11-demo-live-adapter-implementation.md` |
| Base | branch `p11-demo-live-adapter` from `main` @ `3f10f41` (P9 merged) |
| Allowed files | create `services/live/{mode,mapping,client,session,read,storage,workspace-logic}.ts`, `features/providers/{data-mode,workspace-session}.tsx`, `features/live/{unavailable,overview}.tsx`, `tests/{ts-loader,live-adapter-checks}.mjs`; modify `services/http-client.ts`, `app/layout.tsx`, `features/workspace.tsx`, `locales/index.ts`, `tests/domain-checks.mjs`; docs under `docs/buyeros/**` |
| Dependencies with evidence | BO-004 and BO-005 are complete as far as the P9/P10 phases carried them. The B-IDENTITY blocker (no live Auth0) is accepted below |
| Approver | Owner (execution mode = subagent-driven) |
| Environment/spend | none; no network, no identity provider, no credentials. Checks run against a stubbed fetch |
| Excluded | live writes (create project, ICP save/approve), real Auth0 activation and token acquisition, CORS/CSRF posture, audit hooks, live discovery/outreach/results, DOM/browser tests, UI redesign |

## Dependency waiver (explicit)

B-IDENTITY is unresolved, so no configured identity provider can issue a token the API would verify. The owner
waived that prerequisite: P11 proves the **client seam** — mode resolution, strict mapping, the typed transport with
its error envelope and bearer handling, the abort and late-response scope discipline, storage hygiene, and the
"never fall back to demo" rule — entirely against a stubbed fetch with no network. Consequences accepted: live mode
is built but stays gated and off; the authenticated round trip is not exercised; the token source is a later phase.
This waiver does not mark BO-006 complete in the task index and authorizes no other phase.

## Recorded deviations from the BO-006 task text

1. **No client-side mode switch.** The task text says switching to demo requires an explicit mode action. This design
   resolves mode server-side and passes it down, so no client action can change it — stronger than the requirement,
   but there is no in-app toggle.
2. **Node scripts, not Playwright.** The task specifies `pnpm exec playwright test`. Playwright is a heavy new dev
   dependency with browser downloads under this repository's strict pnpm supply-chain policy. The existing
   `tests/domain-checks.mjs` convention (node + `node:assert` + the installed `typescript`) is extended instead, so
   **no new dependency** is added.

## Sign-off (owner)

Recorded from the owner's in-session direction on 2026-09-17: the owner approved the P11 spec, approved the P11
implementation plan, and selected subagent-driven execution of that plan. This record captures that authorization;
it is not a verbatim quotation and no remote push, deploy or activation is authorized by it.
