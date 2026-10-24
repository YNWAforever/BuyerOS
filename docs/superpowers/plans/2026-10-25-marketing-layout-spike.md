# BuyerOS marketing layout compatibility spike

User approved positioning, Request a demo CTA, zh-HK/en and separate marketing/product layouts on 2026-10-25 (Hong Kong). This is the bounded Step 4 spike, not the complete website.

## Contract

- Keep Vinext/Vite, existing product providers, /app deep links, /auth callback, /api/auth and /v1 handlers.
- Public zh-HK/en landing samples render their language, headline and metadata in SSR without product providers or auth bootstrap. / defaults to /zh-HK; /login uses the existing /app entry. Unknown public paths return 404.
- Use route groups with independent root documents. Public CSS stays separate from product CSS. Test crossing roots and browser history, native locale links, keyboard navigation and widths 390/768/1440.
- Minimal landing sample only: approved headline, positioning, workflow, demo CTA to an explicitly inactive demo-request section. No intake, invented contacts/prices/policies, analytics or external requests.
- Preserve the eight hashed prior-work artifacts recorded in outputs/marketing-spike/baseline.json. No DB, provider, credential, security, network or deployment changes.

## Tasks and verification

1. Add HTTP/browser contracts and run against existing app. Expected RED: /zh-HK currently redirects to the product rather than rendering public SSR; unknown paths redirect instead of 404.
2. Split root layouts using (product), (marketing)/[locale] and (entry). Keep product provider body unchanged. Add minimal bilingual server content and scoped public stylesheet. Expected GREEN: same contracts pass without DB/services.
3. Verify default Cloudflare build and Vercel/Nitro build, typecheck, lint, relevant existing Node auth/proxy tests, full offline frontend checks where feasible. Run contracts against built output as well as dev. Investigate concrete failures before changes.
4. Obtain one independent read-only final review, resolve material findings with reproducing tests, and record evidence, limitations and implementation decision. Commit only spike files on the local feature branch.

## Interfaces / review focus

Tasks 1/2 share URL and SSR contracts; task 3 must test the same URLs under both deployment targets. The root product layout moves but its loadPublicAuth argument is unchanged; existing compiled-auth tests must follow its actual location without weakening checks. Review route priority, unknown paths/locale errors, root-transition hydration/history, auth callback query preservation, API non-interception, stylesheet/provider isolation and accidental claims.

Source spec: outputs/marketing-plan.M4lEBk/site-plan.md and copy-deck.zh-HK-en.md. Reviewable prior Step 3 evidence remains in that directory. No fresh task required.

## Result

Implementation `7388c0edcf1ed085491de291bf557de6d3fe30ba`. Default CF dev and both built targets each pass10/10; built Node9/9, offline Node238/238, types and both builds pass; lint0 errors/4 prior warnings. The reviewed bare-app route defect is fixed with two RED→GREEN PKCE regressions. Auth/provider implementation, handlers, product CSS and lockfile are preserved. See docs/buyeros/marketing-layout-spike.md for commands, evidence, tested working-tree composition and the separately unaccepted Nitro dev lifecycle diagnostic. No push/merge/deploy or real integration acceptance.
