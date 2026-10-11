# C61-07 Neon production contract — reviewed 2026-10-07

N00 remains **open**. This decision records a verified public API contract and a
proposed production boundary. It does not adopt the diagnostic proxy, change
Auth0, activate a provider, or establish real Neon/Google acceptance.

## Source and dependency provenance

The existing clean `codex/n00-os-callback-api` HEAD is
`e17b699752a3c887abd44601f3148dd62171db09`. Its author-reviewed callback/API
source is `8123755c399b6403dee7fb8545a9a5b5249a1880`; its contained fixture does
not load BuyerOS membership/roles. Six public SDK redirect, token cache,
cross-tab cache and broadcast storage tests were re-executed and passed on the
peer HEAD. They use synthetic loopback protocol data and its pnpm patches.
Historical build counts are retained as historical evidence only.

The public package registry still reports `@neondatabase/auth 0.5.0-beta`.
Installed exports/types resolve `/next/server` to
`dist/next/server/index.d.mts` and `/next` to the corresponding public entry.
Better Auth is pinned to `1.6.23`. Existing patch SHA256 values are
`3a7cbf5af9f1f7205a958322ef02d378aa74e1ac444160238223290a504c8d76`
(Neon SDK) and
`02bd5ba59e01d1487da69ba2c6d03d1ed392e79011d4b538378605b879d8c494`
(Better Auth). The patches change redirect handling/header preservation,
token/session cache routing and cross-tab invalidation. They need explicit
review and same-candidate built verification before production adoption. The
original 302 failure and all prior failed attempts remain in the peer evidence.

## Chosen public boundary for local preparation

Use `createNeonAuth` from `@neondatabase/auth/next/server`, runtime server-only
`baseUrl` and `cookies.secret`, with a secret of at least 32 characters.
`auth.handler()` owns `/api/auth/[...path]`; the browser uses `createAuthClient`
from `/next` without a server secret. The SDK types expose `getSession()` and
`token()`, `cookies.sessionDataTtl` (default 300 seconds) and explicit SameSite.
Use Lax cookies for the callback path; secure cookies and exact trusted public
origins require environment-specific verification. Do not expose auth cookies
through the business API gateway. Business API requests carry the signed JWT.

The official session read returns a user/session; the public token method
returns `data.token`. An opaque session token is not an API bearer. Official
JWT documentation specifies EdDSA/Ed25519 and a 15-minute lifetime. Exact
issuer and audience are taken independently from a signed real target token;
the JWKS endpoint and expected branch are bound to an approved manifest.
The documentation's origin-based example is not a license to infer trust.
The server must require exact issuer/audience/algorithm/JWKS and reject wrong
branch, unknown kid, expiry and fixture trust outside the explicit test mode.

Use the SDK's supported sign-in/session/callback/logout paths; do not turn
Auth0 authorize/token/logout URLs into Neon URLs. The proposed callback may
return only to an allowlisted relative `/app` path with the original workspace,
project and locale. Validate and bind state/return path, preserve dirty work,
and verify reload, refresh, two-tab signout and denied/expired sessions.
Logout must clear browser/session state; an already-issued JWT's remaining
lifetime is addressed separately by the API trust/identity rollout, without
claiming immediate provider JWT revocation.

Vinext/Nitro compatibility must be proved on the normal BuyerOS build. The
peer diagnostic dispatchers and contained host relay are not production
middleware. A thin normal route adapter is preferred; any RSC/Nitro-specific
repair must have a focused failing test and explicit review before adoption.
There is no framework rewrite decision.

## External target and acceptance matrix

Neon project/branch/Auth ID, exact auth URL, issuer, audience, JWKS, public
origin, enabled email method and Google client configuration are currently
**unset/unverified**. The separately asked target question is still pending.
No prior proposal name, organization ID, spending budget or account approval
in peer documents is reused as authorization for this run.

Local SDK fixtures: 6 passed, zero failed/skipped/cancelled. Current-candidate
portable build flow, Vercel emitted flow, real Neon email, real Google,
authenticated BuyerOS workspace API, provider cleanup and human UAT each
remain independent pending/blocked gates. N00/NA01/NA04/NA05 are not closed.

`node scripts/neon-real-preflight.mjs --help` currently rejects with
`N00_REAL_USAGE_CHECK_TARGET_JSON`; the existing runner accepts
`check TARGET_JSON`. The help mismatch is recorded, not counted as acceptance.
It performs local manifest validation only. The runner's fixed old proposal
is not adopted. A new reviewed runner/manifest must bind the authorized
target, source, expiry, request/build cap, nonce and precise cleanup ownership.

Only after the normal built fixture is verified should the final concrete
real-target payload be presented for any missing external authorization.
Production auth cutover, provider account creation, spending and outbound
email remain disabled. Canonical user IDs, historical FKs, membership roles,
RLS and accepted/unknown intent records remain authoritative.

## Official sources checked this run

- [Next.js API-only guide](https://neon.com/docs/auth/quick-start/nextjs-api-only)
- [JWT plugin guide](https://neon.com/docs/auth/guides/plugins/jwt)
- [Production checklist](https://neon.com/docs/auth/production-checklist)
- Installed pinned public package exports and TypeScript declarations.

The JSON evidence stores retrieval hashes and dates, exact commands and
separate gate outcomes. Full downloaded official prose is transient review
input, not committed as project-owned evidence.

## Rollback

This ADR and read-only tests change no production route, schema or account.
Rollback is reverting this evidence commit. Keep Auth0 usable until the
explicit dual-trust/mapping/Neon-only sequence is accepted; never remove
Neon-only identities, rewrite UUIDs, auto-link by email or clear unknown holds.
