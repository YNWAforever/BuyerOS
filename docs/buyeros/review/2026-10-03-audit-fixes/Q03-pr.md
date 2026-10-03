# Q03: first-round audit repair (F05)

## Review range

- Base: `8251027ddcf781e5cae713da4190d32a77a81dbd`
- Head: `f5936cef6b363e3662c9b84c6153ea2c43f8117b`
- Branch containing candidate: `codex/audit-fixes-20261003`.
- Exact binary diff: `docs/buyeros/evidence/audit-fixes-20261003/diffs/Q03.patch`.
- Four distinct task boundaries are reviewed in Q01 → Q03 → Q04 → Q15 order. Q01 supplies the shared audit fixture config; Q03/Q04/Q15 product logic does not depend on Q01 UI behavior. Split/cherry-pick the Q01 test infrastructure if publishing independent bases.
- No GitHub PR has been created or pushed in this session. This is the precise local PR description.

## Change

Use generated AsyncJob/BulkItemResult.id, full IDs and 20-row result pagination; reject delayed jobs/pages and workspace A-B-A responses.

Cases: B10/B11. Findings: F05.

## Verification

UI4/0/0; strict bulk10/0/0; generated check/type/lint exit0. Counts use pass/fail/skip. The final shared fixture gate is 22/0/0; auth8/0/0, adapter74/0/0, combined unit11/0/0; generated78-operation check/type/lint exit0.

RED evidence: Q03-red.log. GREEN evidence: Q03-ui.xml; Q03-green-final.log; Q03-db.log; audit-job-payload-21.json; audit-job-payload-101.json. Logs and screenshots are under `docs/buyeros/evidence/audit-fixes-20261003/`; exact commands/environment are indexed in the final handoff and `commands.json`.

HTTP/DB/browser integration uses owned local PostgreSQL and fictional principals. Fixture job completion is test-owned, while existing strict worker tests separately prove durable materialization. No paid provider, real login, production RLS, staff UAT or deployed verification is claimed. Q04 admission creates a run budget ceiling; provider operations and reservations stay 0, so this is not provider acceptance verification.

## Compatibility and rollback

No schema revision, domain endpoint, generated schema, membership, identity mapping, approval model or Cloudflare HMAC change. Delivery stays disabled/403. Auth0 retained; Neon migration separate.

Revert consumer/test commit; persisted jobs and outcomes remain.

## Review limits

Author performed a separate diff/requirements pass. Independent reviewer has not run; no agent was spawned. Q16/Q17 remain blocked on driver/SQLSTATE evidence. Performance/goldset/full eight-module journey are not measured by this first repair suite.

## Changed files

- `TASKS.json`
- `docs/buyeros/CURRENT_STATUS.md`
- `docs/buyeros/REMAINING_DEVELOPMENT_STATUS.md`
- `docs/buyeros/evidence/audit-fixes-20261003/Q03-db.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q03-generated.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q03-green-final.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q03-lint.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q03-red.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q03-types.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q03-ui.xml`
- `docs/buyeros/evidence/audit-fixes-20261003/audit-job-payload-101.json`
- `docs/buyeros/evidence/audit-fixes-20261003/audit-job-payload-21.json`
- `docs/buyeros/evidence/audit-fixes-20261003/audit-operations-101.png`
- `docs/buyeros/evidence/audit-fixes-20261003/audit-operations-21.png`
- `docs/buyeros/remaining/AUDIT_FIX_CASE_STATUS_20261003.csv`
- `features/live/locale.ts`
- `features/live/operations.tsx`
- `services/worker/tests/fixtures/audit_jobs.py`
- `tests/e2e/audit-operations.spec.ts`
