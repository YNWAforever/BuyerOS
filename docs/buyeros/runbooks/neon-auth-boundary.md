# C61-08 server boundary and deployment payload

Local source/build delivery only. N00 remains open until the exact authorized
Neon project/branch and real login/JWT contract are verified. Auth0 remains the
business session provider in this change. The new auth route defaults to503.

| Variable | Authoritative source | Scope |
| --- | --- | --- |
| BUYEROS_NEON_AUTH_ROUTE_ENABLED | Reviewed release gate; default absent/off | Server |
| BUYEROS_NEON_ENVIRONMENT | Explicit local/preview/production target | Server |
| BUYEROS_NEON_AUTH_URL | Auth URL of the separately authorized Neon branch | Server |
| BUYEROS_NEON_EXPECTED_AUTH_URL | Independently reviewed target manifest | Server |
| BUYEROS_PUBLIC_ORIGIN | Exact application origin of that deployment | Server |
| BUYEROS_NEON_EXPECTED_PUBLIC_ORIGIN | Independently reviewed target manifest | Server |
| BUYEROS_NEON_COOKIE_SECRET | Independently generated32+ character secret, secret store | Server only |
| NODE_ENV / VERCEL_ENV | Actual runtime environment, consistent with target | Runtime |

No values are supplied by this payload. Never copy fixture URLs, JWTs, passwords,
cookie canaries, developer branches or guessed account values into a deployment.
Auth URL must match the independent expected binding exactly and be HTTPS on
.neon.tech; public origin must match its independent binding exactly. Missing,
inconsistent environment/branch/origin, fixture trust or test credentials refuse
initialization. Errors omit secret values and provider details. Local origin can
be loopbackHTTP only when the runtime is development/test; auth stays HTTPS.

The unmodified public@neondatabase/auth0.5.0-beta SDK is a runtime dependency.
createNeonAuth from/next/server owns the dedicated/api/auth/[...path] handler.
Only this route receives auth cookies; the business gateway contract continues
to use its bearer-only allowlist. The wrapper validates request host and Origin,
requires exact Origin forPOST, preserves SDK body/status/cookies and always
uses no-store. Provider failure stays503. Cookie signing secret is never given
to browser code. SDK configuration choosesLax, no cookie domain and300-second
signed session cache; real browser cookie attributes remain a separate gate.

The actual pinned SDK uses__Secure-neon-auth.session_token and may fetch session
data once more to mint its signed cache. Its social sign-in response carries a
JSON redirect URL; a generic302 mock does not prove its OAuth callback flow.
Node-only tests resolve the original Next.js extensionless public imports to
their unchanged.js files. No SDK/BetterAuth peer patch is adopted. The existing
peer dependency warning is retained; successful local build/transport tests do
not establish all real provider features or resolve every peer compatibility.

Both portable andVercel builds pass local secret-canary public-output scans.
The initialVercel artifact compiled successfully but its actual function returned
500 because a transitive tslib Node export was absent. Nitro traceDeps=[tslib*]
now retains the package's Node andESM entry files, while preserving the existing
tslib alias. The same actual built function now returns default/missing-config
503 and foreign-Origin403 without a provider call. CI runs config/boundary,
original SDK transport and actual built-output suites with freshJUnit; its
required-suite checker rejects empty discovery, failures, errors andskips.

Sources: [Neon Next.js API guide](https://neon.com/docs/auth/quick-start/nextjs-api-only),
[public SDK guide](https://github.com/neondatabase/neon-js/blob/main/packages/auth/NEXT-JS.md),
[Nitro traceDeps](https://nitro.build/config#tracedeps), pinned package source/types.

To prepare an authorized deployment: bind independent environment values in a
secret store, build with the frozen lockfile, run all required gates and review
the resulting source/bundle hashes. Keep the route off until C61-10/11/12/13 and
the real account/browser gates permit activation. No production auth switch,
deployment, migration, paid operation or outward email is performed here.

Rollback: set the new route gate off; keep Auth0 usable. Revert this task's app
artifact/config if needed. Retain canonical identity mappings, revocations,
Neon-only User rows, existing UUID/FKs and all unknown provider holds. This
boundary rollback does not by itself prove Neon-only users can still log in;
the compatible provider/application rehearsal belongs toC61-13.

C61-08 installation follow-up: the unmodified auth SDK adds core-js3.50.0.
Its optional postinstall prints a banner and writes a temporary banner stamp;
`allowBuilds.core-js: false` explicitly skips it. `strictDepBuilds: true` and
other script policies remain enforced. Owned Linux install/build + four actual
HTTP/PG/Chromium cases pass after ERR_PNPM_IGNORED_BUILDS RED.
