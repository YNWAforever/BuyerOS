# BuyerOS inner-page alignment — 25 October 2026

Local changes on `codex/bilingual-site-20261025`, based on PR #29 head
`67a9b62ae6473903c00698542d31a8f8a3ece1ff`. No deployment, push or merge.

The homepage remains the reference. Its six before/after screenshots (both
languages, three widths) are pixel-identical. The existing `SiteShell`, feature
cards, steps, FAQ, sample workflow, product capture and closing CTA remain shared.

## Page coverage

All pages inherit the homepage title weight/size/leading/tracking, intro scale,
hero spacing and shared palette. Header, navigation, footer, buttons, FAQ,
feature cards and closing CTA retain their existing shared implementations.

| Page | Changes beyond the common hero/theme alignment |
| --- | --- |
| `/zh-HK/features` | Shared editorial typography; product captures stack at tablet width for readable imagery. |
| `/en/features` | Shared editorial typography; product captures stack at tablet width for readable imagery. |
| `/zh-HK/how-it-works` | Shared editorial heading/body scale; retained shared steps and sample workflow. |
| `/en/how-it-works` | Shared editorial heading/body scale; retained shared steps and sample workflow. |
| `/zh-HK/pricing` | Reused homepage pricing-panel background, border, padding, heading and CTA treatment; removed duplicate panel rules. |
| `/en/pricing` | Reused homepage pricing-panel background, border, padding, heading and CTA treatment; removed duplicate panel rules. |
| `/zh-HK/faq` | Hero aligns with the FAQ reading column; shared native disclosure component retained. |
| `/en/faq` | Hero aligns with the FAQ reading column; shared native disclosure component retained. |
| `/zh-HK/demo` | Section heading uses the homepage scale; form-only control/notice/error/receipt CSS moved into the existing demo stylesheet. |
| `/en/demo` | Section heading uses the homepage scale; form-only control/notice/error/receipt CSS moved into the existing demo stylesheet. |
| `/zh-HK/privacy` | Hero and legal body share the same reading column; consolidated legal/editorial prose styles and section spacing. |
| `/en/privacy` | Hero and legal body share the same reading column; consolidated legal/editorial prose styles and section spacing. |
| `/zh-HK/terms` | Hero and legal body share the same reading column; consolidated legal/editorial prose styles and section spacing. |
| `/en/terms` | Hero and legal body share the same reading column; consolidated legal/editorial prose styles and section spacing. |

## Verification

| Check | Result |
| --- | --- |
| `pnpm exec tsc --noEmit` | Passed. |
| `pnpm lint` | Passed, zero warnings/errors. |
| `pnpm build` | Cloudflare build passed. |
| `node scripts/run-vercel.mjs build` | Vercel/Nitro build passed. |
| `playwright.marketing-site.config.ts` | Existing 12 tests passed; added stylesheet-isolation test passed separately (13 cases covered). |
| `playwright.marketing-spike.config.ts` | 11/11 on Cloudflare built output and 11/11 on Vercel built output. |
| Frontend Node suite | 285/285, no failures or skips; separate React-server SDK checks 3/3. |
| Core domain/adapter/import/upload/auth scripts | 11 / 74 / 5 / 14 / 11 checks passed respectively. |
| `services/api/tools/run_core_isolated.py` | 2/2, including persisted unsent draft generation and lost-acknowledgement save recovery. |
| Responsive screenshots | 48 before + 48 after; all 14 inner pages plus both homepages at 390/768/1440 px; no document overflow. |
| Keyboard | All 42 inner-page/width combinations: skip link, main focus, visible 3 px focus outline, keyboard mobile menu and FAQ activation where applicable. |
| Text contrast | 2,042 rendered text samples across 42 combinations passed WCAG AA size-dependent contrast thresholds. Decorative `aria-hidden` glyphs and disabled controls excluded; not a full accessibility certification. |
| Content | Main text matches for all 48 views after normalizing the two loopback fixture origins in JSON-LD. `content.ts` is unchanged. |
| Static CSS isolation | Built static pages load only `site.*.css` (22,094 bytes; 5,252 bytes gzip). Only demo additionally loads `demo-form.*.css`; no product stylesheet on the other routes. |
| Boundaries | All public pages remain noindex; localized navigation, native/no-JS FAQ, disabled demo intake, redirects, `/app`, auth and API regression checks pass. No app/auth/API source files changed. |

Builds used only documented synthetic public auth settings. Browser fixtures
refuse external providers. Core used the runner's newly allocated, ownership-
verified disposable PostgreSQL container and fictional data; cleanup receipt
confirms its exact container was removed. No production data, paid provider
calls, delivery or outreach was used.

Initial runs exposed the environment's watcher limit (an in-checkout package
cache), missing synthetic build-time settings, and a reviewer session lost while
builds were running. Final regression runs use correctly configured built output;
core passed with source/builds held fixed. Original failed-attempt logs are
retained. A scratch source backup accidentally entered a typecheck/lint scan;
it was renamed as text and both checks then passed. No checks were weakened.

## Evidence

Open `outputs/marketing-alignment/index.html` for an interactive before/after
comparison of every page, language and viewport. Full PNGs and measurements are
in its `before/` and `after/` directories. Lazy images were explicitly decoded
for final captures, without changing production image loading.

Detailed command logs are under `work/marketing-alignment/`; a copy of the final
logs and source fingerprints is under `outputs/marketing-alignment/verification/`.
Core execution and cleanup are in `outputs/core-isolated-c6bb1a59c4fd/`.
Screenshots and reports are local repository artifacts; the chat output mount
was unavailable in this execution environment.
