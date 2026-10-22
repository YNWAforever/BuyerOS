# Public UI acceptance package

12 Playwright test instances. Delivered as **not executed**, with JavaScript syntax checked.
Cases cover four viewport sizes, English/Traditional Chinese, form validation, restart navigation, landmarks and primary control size.
The Google OAuth success case is manual N21-AUTH-05; this package does not press Google or supply credentials.

Use the existing BuyerOS repository's locked `@playwright/test` installation. Copy this directory under a clean repository checkout; do not copy the audit's partial source slice into a product repo.

```bash
BUYEROS_UI_BASE_URL=https://reviewed-preview.example \
BUYEROS_UI_ALLOWED_ORIGIN=https://reviewed-preview.example \
pnpm exec playwright test --config audit/automation/playwright.ui-audit.config.mjs
```

Replace both example origins with the same actual authorized origin and adjust the config path to the copied directory. The package fails closed if the origins differ. One worker, zero retries, no session storage, trace or screenshot capture.

Read-only public page tests can be run against the reviewed production origin, but business-journey, permissions, failure injection and performance cases must use an isolated owned environment. Existing fixture tests in `tests/e2e` can be extended for the CSV cases. Do not use force clicks, larger timeouts, skipped assertions or mocked navigation to hide the observed defects.

For F30, extend the existing `lead-preparations.spec.ts` fixture with N21-PREP-02 through 05 and 08. Seed two preparations and two companies, edit without saving, then exercise company/record/page/route/refresh/reload changes. Verify Save/Discard/Cancel and persisted exact revisions. A stub-only passing component test is insufficient for the production route composition.
