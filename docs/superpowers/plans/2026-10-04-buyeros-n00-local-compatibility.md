# N00 local compatibility execution

Spec: docs/superpowers/plans/2026-10-03-buyeros-gpt61-fixes.md (N00 / F20 / NA01).
Base: 27f1412369edb6ea8581aa15d3d2a7a0e84882d3.
Global constraints: no production/auth cutover, no real accounts/email/provider, no schema/roles/DB change, no framework upgrade, no push/deploy, no agents. Source overlays only. Real Neon NA01 remains blocked.

## Task 1: Guard and pin the fixture/build harness
Interfaces: exact SDK0.5.0-beta; source inventory; loopback only; clean emitted outputs. Consumes current framework build commands. Produces reusable local-only overlay/build runner.
1. Write Node safety regression tests, run RED.
2. Implement source path/URL guards and isolated Docker build runner.
3. Run Node tests GREEN and baseline contracts/types.
Expected: tests execute, zero skips; framework pins unchanged.
Verify: node --test tests/neon-compatibility-harness.test.mjs.

## Task 2: Exercise both actual built outputs
Interfaces: official createNeonAuth().handler()/getSession(), createAuthClient().token(); fixture upstream session/cookies/JWKS; isolated FastAPI EdDSA diagnostic (not production verifier).
1. Write audit-neon-compat.spec.ts/config; build unpatched official SDK fixtures using pnpm build and node scripts/run-vercel.mjs build.
2. Run actual browser flow login/session/token/FastAPI/logout plus cookie/callback/reload and negative tokens. Record actual interoperability failures; smallest adapter only if evidence requires it.
3. Freeze SDK/runtime contract, fixture evidence, NA01 limitation, review and rollback; local commit.
Expected: real output requests, no dev server substituted, no real Neon pass claim.
Verify: pnpm exec playwright test --config playwright.neon-auth.config.ts tests/e2e/audit-neon-compat.spec.ts.

## Review Focus
No secrets or env files in overlay/build; no public spike route in BuyerOS tree; old Auth0 unchanged; EdDSA diagnostic explicitly not domain trust; no fixture accepted as live; every built runtime failure retained; necessary DB tests are not skipped (no DB required by this protocol-only slice).
