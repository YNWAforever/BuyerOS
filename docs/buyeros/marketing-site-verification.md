# BuyerOS marketing implementation — verification

Implemented locally in the existing task and worktree. The eight pages are
available in zh-HK and English, with Request a demo / 預約示範 as the main CTA.
Pricing uses the approved contact fallback. Privacy and terms are visibly draft;
real collection and external analytics remain off.

## Revision and preservation

- Base: `1e77c3fa57b90fdc8433e50c2850885b05be35fe`.
- Intake: `f5668f1` — independent schema/API and same-origin proxy.
- Public implementation: `eb0723a` —16pages, copy, assets, form, SEO and tests.
- Branch/worktree: `codex/marketing-layout-spike`, `/workspace/BuyerOS`.
- The tested composition includes these marketing changes plus the unchanged
  seven pre-existing uncommitted core files listed in
  `outputs/marketing-full/baseline.json`. They were excluded from marketing
  commits. All8 protected hashes match; reverse-apply validation of the historical
  core patch succeeds. Its SHA256 remains
  `eeb08445b3aa77d9a272dfcbc3e65a4f9dc6c27280df73256db6a69a4d508fcf`.

The final documentation commit changes no executable source. File fingerprints
and commands are in `outputs/marketing-full/source-manifest.json` and
`verification.json`. The API contributor's26-test evidence matches executable
source; one final blank line was removed from its test file after that run,
with AST equality checked.

## Verified locally

| Layer | Actual result |
| --- | --- |
| Public built browser |12/12:16SSR pages/head metadata, redirects404s, locale navigation,390/768/1440, noJS, keyboard/reduced motion, disabled intake/legal drafts, crawler endpoints, FAQ/schema, PII-free local events and heading navigation |
| Synthetic intake browser |7/7 in Nitro dev and7/7 in emitted Vercel output: hydration gate, email validation, actual committed receipt, dropped-response replay, reload,409/429/503 input retention |
| Supported Nitro dev follow-up |2/2 final head/heading regressions covering16pages; previous full public10/10 and synthetic intake7/7 retained |
| Product regression |11/11 on Cloudflare built and11/11 on Vercel built: entry/API boundaries, missing assets, root transitions, deep links and three synthetic PKCE return paths |
| Frontend offline suite |236passed;5owner-directory cases initially could not launch the default browser, then5/5passed with workspace-local system Chromium selection;241 total cases covered |
| Additional Node checks |Proxy6/6, metadata3/3, public SDK3/3, emitted function/Auth9/9; metadata3 are included in the241 count |
| Independent API |26/26 intake contracts, plus36/36 existing Auth/settings/precondition regressions; exact target and restricted-role proof retained |
| Types/lint |tsc passed; repository lint0errors/4pre-existing warnings; all owned TypeScript/JS files lint with0warnings |
| Builds |Existing Cloudflare build and Vercel/Nitro build both passed after final runtime changes |
| Independent review |Whole-change review plus focused metadata/delivery review: no critical/important findings; minor email mismatch reproduced and fixed |

Intake tests used only the independently verified owned PostgreSQL16 target
`buyeros_test_marketing_7de839a3a3aa` on127.0.0.1:32770 and local API8013.
Readback confirmed an unchanged replay yields one committed receipt and reload
shows the same UUID. Tests were synthetic only. The fixture container, its volume,
API and private handoff were removed through the runner's ownership-checked
cleanup. Receipts remain under
`outputs/marketing-full/intake/run-5b8a81fe58d8/`.

Intake browser acceptance preceded only the final metadata/heading corrections;
form and executable intake file hashes remained identical. The final public,
product and build checks cover the subsequent rendering corrections.

## Lighthouse — actual local measurements

Lighthouse13.5, mobile defaults/simulated throttling, system Chromium, emitted
Vercel function/static output. The local adapter applies gzip and the immutable
`/_next/static/` cache header from emitted Vercel configuration. This is local
measurement, not deployed-site acceptance. Original uncompressed baseline
78/100/100/50 is retained separately; it exposed missing head metadata.

| Locale/page | Performance | Accessibility | Best practices | SEO |
| --- | ---: | ---: | ---: | ---: |
| `/zh-HK` | 99 | 100 | 100 | 69 |
| `/zh-HK/features` | 97 | 100 | 100 | 69 |
| `/zh-HK/how-it-works` | 99 | 100 | 100 | 66 |
| `/zh-HK/pricing` | 81 | 100 | 100 | 66 |
| `/zh-HK/faq` | 97 | 100 | 100 | 66 |
| `/zh-HK/demo` | 98 | 100 | 100 | 66 |
| `/zh-HK/privacy` | 99 | 100 | 100 | 66 |
| `/zh-HK/terms` | 99 | 100 | 100 | 66 |
| `/en` | 98 | 100 | 100 | 69 |
| `/en/features` | 98 | 100 | 100 | 69 |
| `/en/how-it-works` | 99 | 100 | 100 | 66 |
| `/en/pricing` | 99 | 100 | 100 | 66 |
| `/en/faq` | 99 | 100 | 100 | 66 |
| `/en/demo` | 98 | 100 | 100 | 66 |
| `/en/privacy` | 99 | 100 | 100 | 66 |
| `/en/terms` | 99 | 100 | 100 | 66 |

The zh-HK pricing first sample had a696ms framework long task and683ms total
blocking time. Two additional sequential samples, with no code changes, scored
**99 and99** (TBT12.5ms/14.5ms); all three samples are retained. The initial81 is
not discarded. A fixed performance score across executions is not established.

Every scored SEO failure is the intentionally blocked indexing directive
(`noindex,nofollow` and preview robots). Scores vary66/69 because the applicable
check denominator differs by page. The90+ SEO target remains unmet until approved
publication settings permit crawling; no gate was weakened for a score. Automated
accessibility100 does not establish a full manual WCAG certification.

Reports: `outputs/marketing-full/lighthouse/delivery/` and
`lighthouse/pricing-repeat/`. Sample assets and local screenshots are under
`public/marketing/` and `outputs/marketing-full/`.

## Repaired during acceptance

- Prevented pre-hydration form entry/native GET fallback and preserved controlled
  inputs; raw form data is not written to query strings/session storage.
- Matched the API's conservative email syntax and focused invalid fields rather
  than suggesting endless generic retries.
- Changed sync public metadata functions to static exports so the pinned Vinext
  puts description/robots/canonical/OG metadata in head. A head-only test first
  failed, then passed for all16pages; no framework upgrade/global workaround.
- Corrected standalone feature/workflow heading levels and the redundant brand
  accessible label; retained the approved layout.
- Kept screenshot caret style injection from racing hydration, with all console
  errors still asserted. This was a test fixture issue, not a product suppression.

## Exact remaining inputs and untested boundaries

[Setup/publication notes](marketing-site.md) list every public JSON field and
secure Node/API environment variable. Enter the final canonical HTTPS origin,
legal publisher/controller, public contact email, approved1–365day retention and
approved bilingual privacy/terms in `config/marketing.public.json` and
`features/marketing/content.ts`. Do not mark legal booleans approved before that
review. Server secret values belong only in secure hosting controls, never chat.

Real intake additionally needs an approved dedicated DB target/migration and
restricted role, matching server-only gateway secrets, exact public/API origins,
an operational scheduled deletion job and an approved owner/retrieval process
for incoming requests. Notification sending is not implemented. Current expiry
cleanup occurs on successful intake activity, so deletion during inactivity is
not yet established. No identity-provider account or paid provider access is
needed for this local site.

Not tested/performed: real Auth or production identity, real research/provider
calls, paid models, outreach, external analytics, AISO scan, push, merge,
deployment or production data changes. Existing deterministic core-flow evidence
remains separate; this marketing acceptance is not full production-product
acceptance.
