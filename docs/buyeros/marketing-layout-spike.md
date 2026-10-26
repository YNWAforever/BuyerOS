# Step 4 compatibility spike

Approved on 2026-10-25 (Hong Kong): evidence-based buyer research positioning, Request a demo CTA, zh-HK default/en, and separate public/product layouts. This revision implements the compatibility sample only. The full marketing website, intake and deployment are separate work.

Initial implementation: `7388c0edcf1ed085491de291bf557de6d3fe30ba`; initial report: `5c16025f80284f0c73ddda4a7d11cbfdf426a7cf`. Both remain preserved. The supported Nitro development follow-up is tested at `5c6d0128dfaf20e3af6be26f3cbe3403d5cf51d7`, plus the unchanged uncommitted core patch described below. Documentation is committed separately. The initial independent review's bare-app finding and the follow-up's two compatibility notes were addressed with runtime regression evidence.

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

- Follow-up at5c6d012: default Cloudflare/Vite development11/11; the Vercel service's direct Nitro development11/11; Nitro/Vercel local built output11/11; built SSR/auth gate checks9/9.
- Follow-up compiled public auth/OIDC checks11/11 and proxy checks5/5. TypeScript, Vercel build and Lint pass; lint retains four pre-existing warnings (draft hooks ×3, workspace-picker unused disable ×1). All nine commands and exits are recorded in `nitro-final-commands.json`.
- Contracts cover raw SSR language/title/headline/noindex, redirects, unknown paths and missing assets404, healthy subsequent SSR, product deep links, API non-interception and fail-closed responses, callback recovery, signed synthetic PKCE with three return destinations, back/locale navigation, no-JS content, keyboard focus and390/768/1440.
- Retained initial evidence at7388c0e: Cloudflare built10/10 and its successful build; offline Node238/238 across39 files, SDK3/3, domain11/11 and adapter74/74. These unchanged paths were not rerun solely to restate their results for this Nitro-development-only repair.
- The initial five owner-directory browser setup failures were resolved with installed system Chromium through an output-only preload, without editing those tests.
- No database used, no real identity/provider traffic, no outreach. These checks do not establish production authentication, deployment or full product acceptance.

Docker cleanup/deployment suites and DB/worker journeys were not rerun for this route-only spike. The previous core-flow results remain historical evidence, not new executions.

## Local reproduction

Use the existing installed toolchain. Set only synthetic public build settings, never application secrets:

```sh
export COREPACK_HOME=/workspace/.cache/corepack
export BUYEROS_API_BASE_URL=/
export BUYEROS_AUTH_PROVIDER=neon
export BUYEROS_INTERNAL_API_URL=
export BUYEROS_NEON_AUTH_ROUTE_ENABLED=0
export MARKETING_SPIKE_CHROMIUM=/usr/bin/chromium

corepack pnpm build
MARKETING_SPIKE_RUNTIME=cloudflare-built node_modules/.bin/playwright test --config playwright.marketing-spike.config.ts
node scripts/run-vercel.mjs build
MARKETING_SPIKE_RUNTIME=vercel-built node_modules/.bin/playwright test --config playwright.marketing-spike.config.ts
MARKETING_SPIKE_RUNTIME=vercel-dev node_modules/.bin/playwright test --config playwright.marketing-spike.config.ts
node_modules/.bin/playwright test --config playwright.marketing-spike.config.ts
node --test tests/vercel-render.test.mjs tests/neon-auth-built.test.mjs
node --conditions=react-server --test tests/neon-auth-server-production.test.mjs
node tests/live-auth-checks.mjs
node_modules/.bin/tsc --noEmit
corepack pnpm lint
```

Omit `MARKETING_SPIKE_CHROMIUM` where the normal Playwright browser is installed. The config starts and stops its own server and waits for readiness on port 5193; do not run its runtimes concurrently. It uses project-local XDG tool state. The built Vercel adapter serves the emitted function/static files locally and denies all upstream server fetches.

### Nitro development closure — 2026-10-25 UTC

`vercel.json` explicitly sets the app service's `devCommand` to `node scripts/run-vercel.mjs dev`. It is a supported development path, so the previous characterization as an additional unaccepted diagnostic was insufficient. The earlier failing evidence remains retained rather than being relabelled as passing.

The failure was a duplicate HTTP handler, not a product/auth defect: Nitro creates a fetchable RSC environment without a Node `.runner`, but the generic RSC Node fallback still tried `environment.runner.import`. A missing public SVG consistently returned500 instead of404. The new HTTP regression was watched RED before the repair; the current-revision baseline also reproduced7/10 passing and3 responsive console failures.

The repair uses the installed plugin's public top-level `rsc: {serverHandler: false}` setting only when the target is Vercel, `command === 'serve'` and `!isPreview`. Nitro owns development HTTP handling; `vinext()` and all its RSC registration/helpers remain intact. Builds, Cloudflare and preview retain their previous configuration. No copied private entry IDs, dependency upgrade, auth code or security/network setting changes are needed.

The final chosen setting passes Nitro development11/11, including the new404 regression, raw bilingual SSR, all three signed synthetic PKCE callback destinations and390/768/1440 console checks. The same11 contracts pass in default Cloudflare/Vite dev and built Vercel output. Evidence: `nitro-missing-asset-regression-red.log`, `nitro-final-vercel-dev.log`, `nitro-final-vercel-dev.json` and the per-command receipts. The two compatibility notes from read-only review were addressed by keeping Vinext helpers and excluding preview; there were no Critical or Important findings. No known reproduced local compatibility defect remains from this spike.

Supported local commands remain the existing default `corepack pnpm dev`, the Vercel service's `node scripts/run-vercel.mjs dev`, and built previews. Automated contracts use `MARKETING_SPIKE_RUNTIME=dev`, `vercel-dev` or `vercel-built` with the existing Playwright config and synthetic public settings above. This verifies local protocol behavior, not real identity, providers, DB or deployment acceptance.

## Preservation and next scope

Baseline `3c79793bea0c0defdf62cec28fa8ef9d3d8ffda2`; local feature branch `codex/marketing-layout-spike`. The prior seven dirty/untracked core-flow files and `outputs/core-acceptance.patch` were hashed before edits and remain byte-identical (8/8). `pnpm-lock.yaml`, auth/proxy handlers, product CSS and provider implementation remain unchanged. Marketing commits must not stage those prior seven files.

All checks run against the marketing revision **plus the preserved uncommitted core-flow patch**; these are not clean-HEAD-only product acceptance results.

The layout structure can support the full bilingual site. The next user decision is approval to implement the complete bilingual public pages using the already-approved positioning, CTA and layout; those design choices need no repeat approval. Existing authorization ends at this compatibility spike. Lead intake still needs its recipient/sink, data handling/privacy details and separate abuse-control contract before activation. Canonical domain/legal/pricing inputs remain owner-supplied. No push, merge, deployment, analytics transmission or lead collection is part of this spike.

Evidence is retained under `outputs/marketing-spike/`: baseline/preservation receipts, failed and passing logs, per-target browser JSON, screenshots and the original routing mismatch. The Step 3 archive remains an unchanged historical proposal; this document records the approved continuation.
