# Step 4 compatibility spike

Approved on 2026-10-25 (Hong Kong): evidence-based buyer research positioning, Request a demo CTA, zh-HK default/en, and separate public/product layouts. This revision implements the compatibility sample only. The full marketing website, intake and deployment are separate work.

Tested implementation commit: `7388c0edcf1ed085491de291bf557de6d3fe30ba`, plus the preserved uncommitted core patch described below. Documentation is a separate local commit. One independent review found the bare-app ambiguity; both added regressions failed first and pass after the single fix pass. No Critical or Minor findings were reported.

## Decision and diff

Keep Vinext 1.0.0-beta.5/Vite 8, without changing dependencies or either deployment target. Use independent root documents under route groups:

| URL | Root / behavior |
| --- | --- |
| `/` | `(entry)`; temporary redirect to `/zh-HK` |
| `/zh-HK`, `/en` | `(marketing)/[locale]`; server language, title/description, preview noindex, independent stylesheet, no product providers |
| `/login` | `(entry)`; existing `/app` entry |
| `/app`, `/app/**`, `/auth/**` | `(product)`; explicit static app entry, required deep-path catch-all, original providers/CSS/persistent app shell |
| `/api/auth/**`, `/v1/**` | Original route handlers, unchanged |
| Unsupported locale / unknown public path | Framework 404, no generic public catch-all |

The sample contains the approved headline, workflow and demo CTA. The CTA reaches an explicit inactive request section; it never acknowledges a submitted lead. No pricing, customer results, legal policies, real account/provider acceptance or outbound delivery claims are added.

### Why there is no public catch-all

A real synthetic PKCE browser test failed after the initial route split: callback returned to `/app/settings?spike_return=preserved`, then lost its in-memory token through a full document load. The pinned Vinext server trie selected `/app/:slug*`, but its client planner's manifest scan selected `/:slug+` first, from a different root. Evidence: `outputs/marketing-spike/catchall-root-mismatch.json`, `browser-cloudflare.log` and extracted RSC payloads. Removing the unnecessary generic catch-all fixed this; framework 404 behavior is tested. Neither auth guards nor framework internals were changed.

The default dev check also reproduced `/api/auth/get-session` returning 500 before its disabled gate. The installed app resolves Zod 3; Better Auth resolves its own Zod 4. Vite's optimized bare `zod` entry collapsed both onto Zod 3, which lacks `.meta()`. The only bundler change excludes `zod` from dependency optimization, retaining normal per-importer resolution. No dependency version or auth code changes. RED evidence: `dev-auth-reproduction.log`.

The independent review found the related bare `/app` case: the generic locale pattern still preceded the optional app catch-all. Both `/app` and `/app?spike_return=preserved` reproduced token loss with real synthetic PKCE (two RED browser cases). The final fix registers `/app` explicitly and changes the deep route to required `[...slug]`, preserving the product layout. Tests cover all three callback destinations. Failure logs/traces are retained in `review-bare-app-red.log` and `review-bare-app-failures/`.

## Verification

- Cloudflare local built output: 10/10 HTTP/browser contracts after the review fix.
- Default Cloudflare/Vite development configuration: 10/10 after the Zod optimization and bare-app fixes.
- Nitro/Vercel local built output: 10/10 same contracts; 9/9 existing built SSR/auth gate checks.
- Contracts cover raw SSR language/title/headline/noindex, default/login redirects, unknown routes, product deep links, API non-interception and fail-closed responses, callback failure recovery, synthetic signed-token PKCE return with query preservation, back navigation, locale navigation without JS, keyboard skip/focus and widths 390/768/1440.
- Existing offline Node suite: final 238/238 across 39 files using installed system Chromium through an output-only preload. The initial five owner-directory browser setup failures came from absent bundled Chromium, and were resolved in the harness without editing their tests.
- Offline SDK server checks: 3/3. Domain checks: 11/11. Live adapter checks: 74/74. Compiled public auth/OIDC checks: 11/11.
- TypeScript passes. Both builds pass. Lint: zero errors and four pre-existing warnings (draft hooks ×3, workspace-picker unused disable ×1).
- No database used, no real identity/provider traffic, no outreach. These checks do not establish production authentication, deployment or full product acceptance.

Docker cleanup/deployment suites and DB/worker journeys were not rerun for this route-only spike. The previous core-flow results remain historical evidence, not new executions.

## Local reproduction

Use the existing installed toolchain. Set only synthetic public build settings, never application secrets:

```sh
export COREPACK_HOME=/workspace/.cache/corepack
export BUYEROS_API_BASE_URL=/
export BUYEROS_AUTH_PROVIDER=auth0
export BUYEROS_INTERNAL_API_URL=
export BUYEROS_NEON_AUTH_ROUTE_ENABLED=0
export BUYEROS_AUTH0_ISSUER=https://oidc.marketing-spike.test/
export BUYEROS_AUTH0_CLIENT_ID=synthetic-public-client
export BUYEROS_AUTH0_AUDIENCE=synthetic-api
export MARKETING_SPIKE_CHROMIUM=/usr/bin/chromium

corepack pnpm build
MARKETING_SPIKE_RUNTIME=cloudflare-built node_modules/.bin/playwright test --config playwright.marketing-spike.config.ts
node scripts/run-vercel.mjs build
MARKETING_SPIKE_RUNTIME=vercel-built node_modules/.bin/playwright test --config playwright.marketing-spike.config.ts
node_modules/.bin/playwright test --config playwright.marketing-spike.config.ts
node --test tests/vercel-render.test.mjs tests/neon-auth-built.test.mjs
node --conditions=react-server --test tests/neon-auth-server-production.test.mjs
node tests/live-auth-checks.mjs
node_modules/.bin/tsc --noEmit
corepack pnpm lint
```

Omit `MARKETING_SPIKE_CHROMIUM` where the normal Playwright browser is installed. The config starts and stops its own server and waits for readiness on port 5193; do not run its runtimes concurrently. It uses project-local XDG tool state. The built Vercel adapter serves the emitted function/static files locally and denies all upstream server fetches.

### Development limitation

Direct Nitro development reproduced `Cannot read properties of undefined (reading 'import')` from the RSC plugin after dependency optimization. That diagnostic, with the final bundler config but before the bare-app review fix, passed five routing/auth contracts and failed three responsive console checks. This entry is **not** accepted as a clean runtime; it was not rerun after that routing fix. Logs/JSON/traces are retained in `browser-vercel-dev.log`, `browser-vercel-dev-results.json` and `nitro-dev-failures/`. The supported, finally verified acceptance paths are default Cloudflare/Vite development and each built target. The spike does not upgrade dependencies or repair Nitro's lifecycle.

## Preservation and next scope

Baseline `3c79793bea0c0defdf62cec28fa8ef9d3d8ffda2`; local feature branch `codex/marketing-layout-spike`. The prior seven dirty/untracked core-flow files and `outputs/core-acceptance.patch` were hashed before edits and remain byte-identical (8/8). `pnpm-lock.yaml`, auth/proxy handlers, product CSS and provider implementation remain unchanged. Marketing commits must not stage those prior seven files.

All checks run against the marketing revision **plus the preserved uncommitted core-flow patch**; these are not clean-HEAD-only product acceptance results.

The layout structure can support the full bilingual site. Next scope is approved page/copy implementation and public quality checks, retaining native navigation across root layouts. Lead intake still needs its recipient/sink, data handling/privacy details and separate abuse-control contract before activation. Canonical domain/legal/pricing inputs remain owner-supplied. No push, merge, deployment, analytics transmission or lead collection is part of this spike.

Evidence is retained under `outputs/marketing-spike/`: baseline/preservation receipts, failed and passing logs, per-target browser JSON, screenshots and the original routing mismatch. The Step 3 archive remains an unchanged historical proposal; this document records the approved continuation.
