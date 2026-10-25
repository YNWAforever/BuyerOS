# BuyerOS bilingual marketing site implementation plan

> **For agentic workers:** Use superpowers:executing-plans for the public site and product-development-execution for the independent isolated intake subsystem. Test before implementation; keep commits local.

**Goal:** Deliver eight complete public pages in zh-HK and English, evidence-based copy, synthetic product visuals, SSR/SEO, accessible navigation and locally verified demo intake, while preserving the product.

**Architecture:** Keep Vinext/Vite and independent public/product roots. Register explicit /zh-HK and /en routes, avoiding generic locale patterns that can shadow product catch-all routes in the pinned client planner. Share one bilingual content source and server page components. Intake uses a separate default-disabled same-origin boundary and independently configured PostgreSQL schema, never tenant endpoints or outreach.

**Tech Stack:** Existing React19/Vinext1.0.0-beta.5/Vite8/Tailwind4, native HTML controls, existing UI library, FastAPI/SQLAlchemy/PostgreSQL, Playwright/Node tests. No framework migration or paid integration.

**Spec:** Approved outputs/marketing-plan.M4lEBk/site-plan.md and copy-deck.zh-HK-en.md; user2026-10-25 explicitly approved full home/features/how-it-works/pricing/FAQ/demo/privacy/terms implementation after the completed layout spike.

## Global constraints

- Same existing task/worktree/feature branch; baseline1e77c3f. Preserve the seven original core files and historical evidence, protected in outputs/marketing-full/baseline.json.
- Local commits only; no push/merge/deploy, production data, real Auth/providers, paid calls or outreach.
- zh-HK default/en equivalents. Primary CTA Request a demo; no free-trial promise, invented prices/KPIs/customers/logos or sending claims.
- Preview noindex until canonical/legal/publication values are confirmed. Legal text is a clearly labelled draft where owner details are absent. No invented controller, jurisdiction, retention, terms or contact details.
- Public copy/metadata and native locale navigation must not initialize product providers or carry workspace/token query values. /app,/auth,/api/auth,/v1 preserve behavior.
- Real intake disabled by default. Synthetic local writes only after exact fixture target/ownership verification. No application credential inspection. Required values and secure entry locations are documented.
- Analytics hooks default no-op/local CustomEvents only; no external transmission or PII.

## Review focus

1. Generic public routes cannot shadow product deep links or reset callback sessions; test /app and public-slug-shaped product paths.
2. Locale switch preserves the current public page while dropping query secrets; test all16 URLs with/without JS.
3. Intake may acknowledge only a committed write; test retry after lost response, duplicate/conflict,429/503, reload/readback and input retention.
4. Anonymous intake cannot disclose tenant data or trust arbitrary forwarding headers; test origin/key/body/abuse boundaries and disabled configuration.
5. Missing publisher values cannot produce invented legal/canonical/offer claims or indexable drafts; test preview vs configured metadata and visible legal state.

### Task1: public routes, content and complete page design

**Files:** features/marketing/{content.ts,routes.ts,site-config.ts,site.tsx,pages.tsx,marketing.css,sample.tsx,events.tsx}; explicit app/(marketing)/{zh-HK,en}/ page wrappers/layouts and app/(entry)/ aliases; tests/e2e/marketing-site.spec.ts; tests/marketing-content.test.mjs.

**Interfaces:** Locale='zh-HK'|'en'; PageId='home'|'features'|'how-it-works'|'pricing'|'faq'|'demo'|'privacy'|'terms'; publicPath(locale,page), content[locale] and renderMarketingPage(locale,page). Public root documents contain no product providers.

- [x] Write/run browser contracts before code. Expected RED: features and other requested public pages return404.
- [x] Implement single bilingual content source and explicit routes, sticky desktop/mobile nav, accessible native FAQ,8 pages, pricing contact fallback and honest legal drafts. Preserve /app route roots.
- [x] Add synthetic hero/sample visuals and actual synthetic product captures with visible sample labels. No customer outcomes.
- [x] Verify16 SSR pages, same-page language switch, no-JS navigation, keyboard/reduced motion, all three viewports and product/auth regression. Expected GREEN.
- [x] Commit only owned public files after verification; preserve unrelated core diff.

### Task2: isolated demo intake (independent contributor)

**Files:** separate services/api marketing schema/service/router/tests and app/api/marketing/leads/** proxy; features/marketing/intake/** boundary helpers; isolated owned fixture runner. Do not touch root marketing pages/content/CSS.

**Interfaces:** GET /api/marketing/leads/challenge -> {challenge_id:string} or503; POST /api/marketing/leads with JSON {name,email,company,message,locale,challenge_id,website:''}, Idempotency-Key UUID ->201/200 {receipt_id:string,status:'received',synthetic:boolean}; errors {code:string,retryable:boolean}, statuses403/409/422/429/503. Default disabled. Body <=8192 bytes. Field limits name120/email254/company160/message2000. Local-only synthetic fixture accepts .test data; never real providers.

- [x] Read existing target identity/cleanup procedures. Allocate a uniquely labelled disposable PostgreSQL16 fixture and prove container/image/port/database/role ownership before first SQL write. Missing skill reference is recorded; use the established repo receipt gate, never infer isolation from localhost.
- [x] Write RED tests for disabled gate, origin/internal gateway identity, validation/body cap, honeypot, server-issued2s minimum/15min challenge, durable global/email rate limits, committed acknowledgement and idempotent replay/conflict.
- [x] Implement independent schema/store and default-disabled API. Require separate configured DB connection/gateway key; no tenant authorization weakening, IP-header trust, email sending or credentials exposed to browser.
- [x] Run integration tests against the owned fixture; prove persisted receipt/readback, duplicate/retry semantics and denied tenant paths. Preserve evidence and use ownership-checked cleanup only.
- [x] Supply exact frontend/server settings and local fixture commands; root commits this subsystem separately.

### Task3: frontend form, SEO and publication controls

**Files:** features/marketing/{demo-form.tsx,seo.ts,publishing.ts}; public/marketing/og-*.png; app sitemap/robots/llms routes; tests/marketing-seo.test.mjs; browser intake tests.

**Interfaces:** form consumes Task2 endpoints, keeps one idempotency key for unchanged payload until committed receipt, retains entries on failures and exposes accessible errors. Publishing config supplies only public domain/controller/contact/legal flags; secrets remain server-only.

- [x] Add failing tests for metadata, structured data matching visible content, preview noindex, sitemap/robots/llms, form error/retry and PII-free events.
- [x] Implement per-language/page titles/descriptions/OG/hreflang, safe JSON-LD Organization/SoftwareApplication/FAQ without offers/reviews. No fabricated canonical origin when unset.
- [x] Implement validation/challenge/submit/retry and local event hooks, disabled/available forms accurately. No fake receipt or success state.
- [x] Verify real local synthetic receipt persistence, same-key retry, transient/conflict/rate limit states and no external requests.

### Task4: verification and reviewable delivery

- [x] Run relevant Node/API/browser suites, tsc/lint and both builds; record tested revision plus preserved core patch. No repeated installations or unrelated broad product acceptance.
- [x] Measure Lighthouse on local built output, targeting90+ in Performance/Accessibility/Best Practices/SEO; report actual per-page results and any justified publishing gates. Run viewport/keyboard/contrast checks, update claim-to-code table and single bilingual copy deck.
- [x] One independent whole-change review; reproduce/fix material findings, then relevant final checks. Local commits only.
- [x] Update setup/publication notes with exact public values, secure server settings, unverified real integration steps and user decisions. No passwords/secrets requested in chat; no real activation/deploy inferred.

Execution approval is already supplied by the user. No repeat design/plan approval is required. Public owner/legal values were requested asynchronously; complete independent local work while waiting.

## Completed implementation notes

Runtime commits: `f5668f1` (isolated intake) and `eb0723a` (public site). Full results and exact tested composition are recorded in `docs/buyeros/marketing-site-verification.md`. All changes stay local.

- `publishing.ts` and `config/marketing.public.json` own public settings instead of the proposed site-config.ts. Bilingual copy is checked through strict types,16SSR routes, visible FAQ/schema equality and browser flows rather than a static-copy mirror test.
- Public wrappers use static metadata exports: the pinned Vinext streams generated metadata into body for ordinary browsers. A head-only regression first reproduced the defect and then passed after the local correction; no framework patch or upgrade.
- Form inputs stay disabled before hydration to prevent native GET fallback/data loss. Email syntax matches the API and errors focus the invalid field. Feature/workflow headings use h2 on standalone pages; layout is unchanged.
- Lighthouse90+ remains a target. Noindex/robots deliberately reduce preview SEO; the actual scores and the pricing-page variance are retained, not disguised as publication acceptance.
- Owner legal/domain/retention values and real-intake activation remain unapproved. Legal drafts, contact pricing and default-disabled collection are the completed preview behavior. No production or external integration acceptance is inferred.
