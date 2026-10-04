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


## 2026-10-04 callback contract follow-up (fixture only)

Official [OAuth setup](https://neon.com/docs/auth/guides/setup-oauth) distinguishes the provider's authorized redirect URI ({NEON_AUTH_BASE_URL}/callback/provider, on Neon) from the app callbackURL. The pinned SDK0.5.0-beta public middleware implements the app return exchange: neon_auth_session_verifier plus __Secure-neon-auth.session_challenge is sent to upstream get-session; on successful exchange it emits cookies and redirects to the same app URL with only the verifier parameter removed. Read installed public exports and next/server middleware; no SDK/internal/global-fetch patch.

The previous strict /api/auth/callback/fixture 302-forwarding test remains byte-equivalent after Git newline normalization and still FAILS on both outputs (portable500/Vercel200). It characterizes arbitrary redirect forwarding through the API proxy; it is not evidence of real provider callback incompatibility, and is not relabeled pass, skipped, or converted to expected-failure. The complete five-case suite remains red and full N00/NA01 stays open.

Added the official auth.middleware() in a disposable proxy.ts overlay with matcher only /compat/return and a dynamic return page. The fake upstream now models random one-use state/challenge/verifier, a fixed allowed app callback origin/path, five-minute fixture expiry, and fictional server session. It does not call Google, create a real account, prove real OAuth state/CSRF/email security, or change production trust/memberships/RLS. No domain API or migration owner added.

Two added cases observed RED before the new build (missing upstream then missing middleware307vs200). After both clean actual Linux builds, each target executes5cases:4pass1fail0error0skip. Added positives include307, resolved same-origin target/query preservation, Secure/HttpOnly/Lax host cookies and signed cache, challenge clear, server session/hard reload/token/FastAPI/logout, consumed verifier rejected in a separate context, and actual browser navigation through upstream302 -> app307 -> clean return page. Negative missing/mismatched challenge is rejected without a session; rejected attempts leave the owner's fresh verifier usable. Fixtures do not prove the provider's actual wire details.

Portable emits a relative Location, which resolves to the identical asserted absolute target; tests use browser URL resolution without relaxing exact status, destination, query, or cookie conditions. Replay/mismatch contexts clone actual SDK-minted cookie metadata instead of an invalid Chromium http-url Secure cookie setter. Original raw setup failures retained. Node32pass0skip, final types/lint0; both build exits0. Prior Auth0 API34pass is carried from the preceding checkpoint, not claimed as re-executed by this follow-up. No DB suite needed/skipped for this protocol-only fixture change, schema0037 unchanged.

Next concrete gate is a specifically approved fresh isolated real Neon Auth target/account/method rehearsal. Auth0 remains the release path; deployed SHA is null. Do not infer real issuer/audience/JWKS from the fixture or reuse expired hosted-preview approvals. New outputs, traces and rollback evidence are captured in ../evidence/audit-fixes-20261003/N00_CALLBACK/RESULTS.md; the prior N00_LOCAL record is immutable.


## 2026-10-04 real-runtime preparation source790a1b2 (contract gate open)

PinnedSDK0.5.0-beta unchanged. Shared target validation emits exact independent issuer/audience/JWKS/EdDSA trust without URL inference. Runtime-only complete manifest + fresh cookie secret are read on each owned server request; constructor caches only one target+secret context and rejects expiry/drift. Type-checked separate server-only overlay forwards official handler GET/POST/PUT/DELETE/PATCH and callback middleware without constructing SDK at module initialization. Cookie options SameSiteLax/sessionDataTtl300 match pinned types. This prepares only the interface: no real target, live cookie/domain or actual new build/runtime config proof.

30newunit plus110related tests pass; units use instrumented constructors. Existing actual SDK fixture outputs each6pass1original302callbackfail; no assertion suppression. Runtime-only real overlay/node:crypto/workerd behavior remains unbuilt/unverified, Google/browser/CLI accounting remains open. Contract remains provisional for N03/N04 consumption until fullN00. [Evidence](../evidence/audit-fixes-20261003/N00_REAL_RUNTIME/RESULTS.md). Auth0/canonical identity/membership/HMAC unchanged; deployednull.


## 2026-10-05 built runtime kernel sourcee683a89 (full contract gate open)

Both actual outputs now verify the pinned official SDK constructor, runtime-only full manifest/exact trust and node:crypto kernel using fictional metadata (6cases each, zero skips/global errors). A source fixture Nitro dispatcher is required; official SDK/emitted output is not patched. Marker-preserving secret-first owned cleanup has observed EBUSY recovery. This closes only the unbuilt configuration/constructor gap: SDK session/token/handler/middleware and real provider/browser/CLI accounting remain unverified; original302callback failure carried unchanged. [Evidence](../evidence/audit-fixes-20261003/N00_RUNTIME_BUILT/RESULTS.md). No Auth0/canonical identity/membership/HMAC change or deployedSHA; N03/N04 contract still provisional until fullN00.


## 2026-10-05 N00 built session/token checkpoint (c756596)

Reviewed source c756596406f41884f61a3b64c8549f569e34cfa4;27files518insertions/1deletion. Official pinned SDK login/session/token/handler/managed callback/logout and independent owned EdDSA FastAPI execute on both actual built outputs with fictional target/transport:each5pass0fail0skip0globalerror.144serialNode/8crypto pass;types/lint/contracts0;fourcleanbuildcommands0. Receipt binds server session subject/fingerprint;bearer stays in memory. Both30fixtureAuthHTTP/0pending0unknown;owned roots/journals/children removed. Body timeout,two0-test startups,parallel40ms regression and initial type/lint failures retained;original status/body/deadline assertions unchanged. No DB/migration/external action. True Neon/Google/full SDK-browser-CLI accounting/external cleanup/independent review and original strict302 gate remain open;N00/NA01/Task2 OPEN. Evidence: docs/buyeros/evidence/audit-fixes-20261003/N00_RUNTIME_FLOW/RESULTS.md. Reverse applicability0only;revert source plus following metadata;no DB/resource undo. NexteligibleN00accounting/cleanup preparation;fresh real-target/account approval pending;Auth0 retained/deployednull.

## 2026-10-05 N00 local execution-boundary checkpoint (b8a1084)

Reviewed source b8a10848b62090ff19544918961e54df3ebfa921;10files277insertions/0deletions. Owned loopback gateway durably counts SDK/browser/fixed Node fixture CLI/control HTTP; cross-channel write holds/manual redirects/limits/TTL; exact-resource cleanup model uses fresh matching readback and confirmed absence. Real provider/CLI/human Google containment and external cleanup API adapters remain unimplemented/unverified. Final related165pass0fail0skip(new21included),Chromium3pass0skip0globalerror/3ownedcleanup receipts,crypto8pass1existingwarning;types/lint/contracts0;0037singlehead/no migrations/DBconnections/skips. Attempted full30-fileNode234tests229pass5fail0skip: two missing mainVerceloutput gates,admin/mvp Docker30stimeouts and parent failure; unchanged tests/no weakened assertions. Full suite RED disclosed. Prior c756596 actual builtUI historicalcarried,not rerun.1401priorN00payloads+31inputs/84operations(70+14)/guards/24other tasks/97other cases/all98historicfields/legacyT registry/unrelated worktrees preserved. Reverse applicability0only;revert following metadata then source;no DB/resource undo. Evidence: docs/buyeros/evidence/audit-fixes-20261003/N00_EXECUTION_BOUNDARY/RESULTS.md. N00/NA01/Task2 OPEN;original302/realNeon/humanGoogle/fresh approval/independent review gates open. Auth0 retained/deployednull;no agents/external mutation/push/deploy. Nexteligible N00 transport coverage/provider cleanup adapters.
