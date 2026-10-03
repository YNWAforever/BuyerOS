# Q15: first-round audit repair (F19)

## Review range

- Base: `fc8fae75dfd743feaf590e73a099443d23e34788`
- Head: `3efd1f3f97036e1988751d1dfb54d37d48d0929a`
- Branch containing candidate: `codex/audit-fixes-20261003`.
- Exact binary diff: `docs/buyeros/evidence/audit-fixes-20261003/diffs/Q15.patch`.
- Four distinct task boundaries are reviewed in Q01 → Q03 → Q04 → Q15 order. Q01 supplies the shared audit fixture config; Q03/Q04/Q15 product logic does not depend on Q01 UI behavior. Split/cherry-pick the Q01 test infrastructure if publishing independent bases.
- No GitHub PR has been created or pushed in this session. This is the precise local PR description.

## Change

Share Save/Discard/Cancel across Refresh/Open/Job materialization; await successful save, preserve dirty buffer/baseline on Cancel or 401/412/503, compare latest separately, restore focus, fence old scope responses.

Cases: D02. Findings: F19.

## Verification

UI10/0/0; guard unit7/0/0; strict draft API27/0/0; worker11/0/0; final shared UI verifies actual clipboard. Counts use pass/fail/skip. The final shared fixture gate is 22/0/0; auth8/0/0, adapter74/0/0, combined unit11/0/0; generated78-operation check/type/lint exit0.

RED evidence: Q15-buffer-red-verified.log. GREEN evidence: Q15-ui.xml; Q15-db.log; Q15-worker.log; final-ui.xml; final-audit-draft-clipboard.json; final-audit-draft-dialog-zh-mobile.png. Logs and screenshots are under `docs/buyeros/evidence/audit-fixes-20261003/`; exact commands/environment are indexed in the final handoff and `commands.json`.

HTTP/DB/browser integration uses owned local PostgreSQL and fictional principals. Fixture job completion is test-owned, while existing strict worker tests separately prove durable materialization. No paid provider, real login, production RLS, staff UAT or deployed verification is claimed. Q04 admission creates a run budget ceiling; provider operations and reservations stay 0, so this is not provider acceptance verification.

## Compatibility and rollback

No schema revision, domain endpoint, generated schema, membership, identity mapping, approval model or Cloudflare HMAC change. Delivery stays disabled/403. Auth0 retained; Neon migration separate.

Copy/preserve local buffers before revert; retain saved revisions/approvals; no database rollback.

## Review limits

Author performed a separate diff/requirements pass. Independent reviewer has not run; no agent was spawned. Q16/Q17 remain blocked on driver/SQLSTATE evidence. Performance/goldset/full eight-module journey are not measured by this first repair suite.

## Changed files

- `TASKS.json`
- `docs/buyeros/CURRENT_STATUS.md`
- `docs/buyeros/REMAINING_DEVELOPMENT_STATUS.md`
- `docs/buyeros/evidence/audit-fixes-20261003/Q15-buffer-red-verified.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q15-db.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q15-green-final.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q15-green-verified.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q15-green.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q15-lint-final.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q15-types-final.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q15-ui.xml`
- `docs/buyeros/evidence/audit-fixes-20261003/Q15-unit-final.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q15-worker.log`
- `docs/buyeros/evidence/audit-fixes-20261003/audit-draft-dialog-zh-mobile.png`
- `docs/buyeros/evidence/audit-fixes-20261003/audit-draft-failure-401.png`
- `docs/buyeros/evidence/audit-fixes-20261003/audit-draft-failure-412.png`
- `docs/buyeros/evidence/audit-fixes-20261003/audit-draft-failure-503.png`
- `docs/buyeros/remaining/AUDIT_FIX_CASE_STATUS_20261003.csv`
- `features/live/draft-dirty-guard.tsx`
- `features/live/drafts.tsx`
- `services/worker/tests/fixtures/audit_drafts.py`
- `tests/audit-draft-guard.test.mjs`
- `tests/e2e/audit-draft-dirty.spec.ts`
