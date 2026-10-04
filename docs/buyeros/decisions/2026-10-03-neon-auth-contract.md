# N00 Neon Auth contract — local compatibility spike

Date: 2026-10-04 HKT. Audit F20 / NA01 / PR-05. Base27f1412369edb6ea8581aa15d3d2a7a0e84882d3. **No auth cutover. Real Neon compatibility remains unverified.**

## Runtime and dependency contract

This is Vinext/Vite with Cloudflare portable output and Nitro Vercel output, not a standard Next.js runtime. Root framework pins remain next16.3.4, vinext1.0.0-beta.5, vite8.0.13, nitro3.0.260903-beta, React19.2.6. Official `@neondatabase/auth` is pinned exactly to0.5.0-beta as a development dependency. Better Auth resolves1.6.23/jose6.2.5. Lockfile adds SDK dependencies and changes one same-version drizzle0.45.2 peer snapshot; it does not upgrade the framework. core-js lifecycle build is explicitly denied.

Official sources read: [Next server](https://neon.com/docs/auth/reference/nextjs-server), [API-only integration](https://neon.com/docs/auth/reference/nextjs-api-only), [JWT plugin](https://neon.com/docs/auth/guides/plugins/jwt), and the exact installed SDK/Vinext/Nitro exports. Installed Nitro declares `experimental.vite.services` and `fetchViteEnv`; this is a version-sensitive interface.

## Exact fixture contract (not a production allowlist)

| Field | Local fixture value / meaning |
|---|---|
| Auth base URL | `http://127.0.0.1:44891/fixture/auth` (guarded loopback) |
| Issuer and audience | Each explicitly `http://127.0.0.1:44891` |
| JWKS | `http://127.0.0.1:44891/fixture/auth/.well-known/jwks.json` |
| Algorithm/key | EdDSA / Ed25519 / OKP, ephemeral in-memory key |
| Handler prefix | `/api/auth/[...path]`; GET/POST official `auth.handler()` |
| Server session | Official `auth.getSession()` in built server page and diagnostic route |
| Browser client | Official `createAuthClient()` from `/next`, same-origin endpoints |
| Methods exercised | Fictional email/password, session, token, logout; redirect/cookie callback transport only |
| Session cookie | Fictional upstream `__Secure-neon-auth.session_token`, Secure/HttpOnly/Lax/Path=/, upstream1h expiry; SDK forwarding actually checked by browser |
| Local cache | SDK signed `__Secure-neon-auth.local.session_data`, explicit TTL300s; no claim for expiration after300s (not waited) |
| Cookie secret | Public fictional test literal, never a real secret; fixture only |
| Bearer | In-memory within one request, no persisted bearer/session; existing canonical locale-only prefs permitted |
| FastAPI verification | Dedicated diagnostic, explicit issuer/audience/JWKS/EdDSA, expiry/key checks; no BuyerOS DB/membership/production verifier |
| Configured real methods | Unknown; no real provider/account/email/auth target configured |
| Real issuer/audience/JWKS | **NULL / not observed**, must be read back from an approved isolated target |

JWT docs describe15min EdDSA tokens with Auth URL origin as issuer/audience and JWKS on full Auth base path. These are source expectations, not permission to infer production trust values. N03 must consume explicitly configured observed values and key/algorithm allowlists. The production Auth0 RSA adapter is unchanged. BuyerOS roles continue to come from current DB memberships/RLS; Neon roles and email do not link/promote identities. Canonical users.id, historical owners/approvals/audit/job actors and Cloudflare HMAC remain unchanged. Delivery remains403.

## Reproduced failure and local adapter decision

The unmodified official handler compiled, but the default Nitro output forwarded all requests to SSR. A real built request to `/api/auth/callback/fixture` returned200 HTML instead of302; the client did not complete login. Vercel browser runs retained2fail/1pass. An initial local platform bridge also incorrectly returned HTML for emitted JS; bridge static routing was corrected. After the public runtime adapter, login/session/token returned200 JSON, confirming dispatch reached the official SDK. The remaining callback200 HTML has a separate cause: the pinned SDK handleAuthRequest (server-b0OzGjXl.mjs1129) calls fetch without redirect:manual, following the upstream302; the fixture endpoint itself emits302. Destructured GET/POST exports were emitted correctly; changing SDK export syntax would not address this failure.

Nitro expects a default object exposing `fetch`; Vinext virtual RSC default is a request function. The disposable overlay registers the public `vinext/server/app-router-entry` as Nitro's `rsc` service and dispatches API, Flight and HTML through it via `fetchViteEnv`. The harness patches exactly one reviewed Nitro configuration marker in a staged copy; original and transformed hashes are retained. Production Vite config and routes are not edited. No SDK private implementation patch and no framework replacement.

| Option | Benefits | Risks / disposition |
|---|---|---|
| Official same-origin SDK + local public runtime adapter | Retains official handler/session/cookie implementation and one origin; limited build wiring | Tested local candidate only; pinned experimental Nitro interface; official callback regression remains open and real provider/Vercel/Safari unverified |
| Custom Request/Response same-origin proxy/session adapter | Could bypass Next shim behavior | Must reprove cookie signing/cache, CSRF, callback/state and refresh behavior; not implemented or accepted without a new contract/tests |
| Auth gateway on an explicitly supported runtime behind same origin | May isolate unsupported framework shims | Adds a service and operational trust boundary; requires an approved design/runtime and actual integration test; no resources created |

## Acceptance and downstream gate

Both clean Linux builds exit0. Final actual portable and Vercel suites each run3tests:2pass/1fail/0error/0skip. The full login→session→hard-reload→token→FastAPI→logout→reload flow and6negative-token requests pass; callback stays open (portable500, Vercel200 vs required302; direct upstream302 is asserted). Tests are not converted to expected-failure/skip. Chromium loopback accepts Secure cookies; real HTTPS/platform/Safari behavior is not thereby established. Portable also mounts the unchanged demo shell; screenshots are protocol-fixture evidence, not live BuyerOS membership/workspace verification.

Production vercel.json still exposes only app catch-all and binds app→internal api using BUYEROS_INTERNAL_API_URL. No public service/binding change is made. Local Vercel bridge uses genuine Build Output API emitted function + static assets; it does not simulate Vercel ingress, protection, binding injection or deployment. All fixture process/child env is reduced to an OS/tool allowlist before loading built code.

Local actual outputs and exact results are recorded in `../evidence/audit-fixes-20261003/N00_LOCAL/RESULTS.md`. No dev-server-only proof. Mock upstream and diagnostic signature verification do **not** close real NA01. Callback case exercises redirect/cookie transport and remains failing; it does not establish real OAuth/CSRF/state/email security. Cookie cache expiry, refresh/rotation, Safari/Firefox, production platform routing and signed-in workspace behavior remain external/downstream checks.

N00 full gate first requires a reviewed solution for the retained callback regression (no SDK private/global-fetch patch was made), and then an approved isolated real Neon Auth target + test account/provider methods and genuine portable/Vercel built login/session/token/API/logout rehearsal. Old cleaned/expired hosted preview approvals are not reused. N01/N02/N03/N04/N05–N07 are not marked complete by this spike. Q-series independent work remains eligible according to its own prerequisites; Q16 root cause and Q17 remain blocked without underlying evidence.

## Rollback

Revert the N00 fixture/SDK commits and its metadata, or leave the spike branch unintegrated. No DB migration/data undo/role reassignment needed. Existing Auth0 runtime remains the release path. Reverse patch applicability is recorded separately; no production rollback was performed. Independent source review is still pending (human requested no agents).
