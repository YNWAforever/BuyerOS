# Q01: first-round audit repair (F01/F02/F15)

## Review range

- Base: `576c3b182819b392f8b73697457769d6f16a496c`
- Head: `8251027ddcf781e5cae713da4190d32a77a81dbd`
- Branch containing candidate: `codex/audit-fixes-20261003`.
- Exact binary diff: `docs/buyeros/evidence/audit-fixes-20261003/diffs/Q01.patch`.
- Four distinct task boundaries are reviewed in Q01 → Q03 → Q04 → Q15 order. Q01 supplies the shared audit fixture config; Q03/Q04/Q15 product logic does not depend on Q01 UI behavior. Split/cherry-pick the Q01 test infrastructure if publishing independent bases.
- No GitHub PR has been created or pushed in this session. This is the precise local PR description.

## Change

Separate hydration initialization from configuration failure; permit locale and read-only access retry without membership; preserve manual locale across delayed preferences. No automatic membership.

Cases: U02/U03/U13; U01 externally blocked. Findings: F01/F02/F15.

## Verification

UI 7/0/0; render1/0/0; strict auth/routes/contract13/0/0; auth8; adapter74. Counts use pass/fail/skip. The final shared fixture gate is 22/0/0; auth8/0/0, adapter74/0/0, combined unit11/0/0; generated78-operation check/type/lint exit0.

RED evidence: Q01-red-linux-port.log; Q01-render-red.log. GREEN evidence: Q01-ui.xml; Q01-green-verified.log; Q01-db-contracts.log. Logs and screenshots are under `docs/buyeros/evidence/audit-fixes-20261003/`; exact commands/environment are indexed in the final handoff and `commands.json`.

HTTP/DB/browser integration uses owned local PostgreSQL and fictional principals. Fixture job completion is test-owned, while existing strict worker tests separately prove durable materialization. No paid provider, real login, production RLS, staff UAT or deployed verification is claimed. Q04 admission creates a run budget ceiling; provider operations and reservations stay 0, so this is not provider acceptance verification.

## Compatibility and rollback

No schema revision, domain endpoint, generated schema, membership, identity mapping, approval model or Cloudflare HMAC change. Delivery stays disabled/403. Auth0 retained; Neon migration separate.

Revert this UI/test commit; keep membership and identity records untouched.

## Review limits

Author performed a separate diff/requirements pass. Independent reviewer has not run; no agent was spawned. Q16/Q17 remain blocked on driver/SQLSTATE evidence. Performance/goldset/full eight-module journey are not measured by this first repair suite.

## Changed files

- `TASKS.json`
- `app/auth/callback/page.tsx`
- `docs/buyeros/CURRENT_STATUS.md`
- `docs/buyeros/REMAINING_DEVELOPMENT_STATUS.md`
- `docs/buyeros/evidence/audit-fixes-20261003/Q01-adapter.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q01-auth.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q01-db-contracts.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q01-empty-zh.png`
- `docs/buyeros/evidence/audit-fixes-20261003/Q01-green-verified.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q01-lint-final.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q01-list.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q01-red-linux-port.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q01-render-green.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q01-render-red.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q01-types-final.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q01-ui.xml`
- `docs/buyeros/remaining/AUDIT_FIX_CASE_STATUS_20261003.csv`
- `features/live/locale.ts`
- `features/live/workspace-picker.tsx`
- `features/providers/workspace-session.tsx`
- `playwright.audit-fixes.config.ts`
- `scripts/serve-audit-ui-fixture.mjs`
- `tests/audit-auth-render.test.mjs`
- `tests/e2e/audit-auth-entry.spec.ts`
- `tests/e2e/audit-teardown.ts`
- `tests/e2e/fixtures/workbench-auth.ts`
