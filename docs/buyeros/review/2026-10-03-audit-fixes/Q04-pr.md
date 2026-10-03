# Q04: first-round audit repair (F08)

## Review range

- Base: `f5936cef6b363e3662c9b84c6153ea2c43f8117b`
- Head: `fc8fae75dfd743feaf590e73a099443d23e34788`
- Branch containing candidate: `codex/audit-fixes-20261003`.
- Exact binary diff: `docs/buyeros/evidence/audit-fixes-20261003/diffs/Q04.patch`.
- Four distinct task boundaries are reviewed in Q01 → Q03 → Q04 → Q15 order. Q01 supplies the shared audit fixture config; Q03/Q04/Q15 product logic does not depend on Q01 UI behavior. Split/cherry-pick the Q01 test infrastructure if publishing independent bases.
- No GitHub PR has been created or pushed in this session. This is the precise local PR description.

## Change

Reuse existing ActionIntent with full normalized body, actor/workspace/project/ICP; retain lost-response key/body across route remounts and token renewal. Unknown result requires explicit same-intent retry or confirmed reset. Hard reload never auto POSTs.

Cases: B05/B06. Findings: F08.

## Verification

UI1/0/0; unit3/0/0; strict admission14/0/0; adapter74. Final shared UI includes two synchronous actual Start handlers. Counts use pass/fail/skip. The final shared fixture gate is 22/0/0; auth8/0/0, adapter74/0/0, combined unit11/0/0; generated78-operation check/type/lint exit0.

RED evidence: Q04-red.log; Q04-durability-red.json. GREEN evidence: Q04-ui.xml; Q04-db.log; Q04-unit-final.log; final-ui.xml; final-audit-research-intent.json. Logs and screenshots are under `docs/buyeros/evidence/audit-fixes-20261003/`; exact commands/environment are indexed in the final handoff and `commands.json`.

HTTP/DB/browser integration uses owned local PostgreSQL and fictional principals. Fixture job completion is test-owned, while existing strict worker tests separately prove durable materialization. No paid provider, real login, production RLS, staff UAT or deployed verification is claimed. Q04 admission creates a run budget ceiling; provider operations and reservations stay 0, so this is not provider acceptance verification.

## Compatibility and rollback

No schema revision, domain endpoint, generated schema, membership, identity mapping, approval model or Cloudflare HMAC change. Delivery stays disabled/403. Auth0 retained; Neon migration separate.

Disable new admissions or revert consumer; preserve admitted runs/outbox/budget ceilings/holds; never replay unknown operations with a new key.

## Review limits

Author performed a separate diff/requirements pass. Independent reviewer has not run; no agent was spawned. Q16/Q17 remain blocked on driver/SQLSTATE evidence. Performance/goldset/full eight-module journey are not measured by this first repair suite.

## Changed files

- `TASKS.json`
- `docs/buyeros/CURRENT_STATUS.md`
- `docs/buyeros/REMAINING_DEVELOPMENT_STATUS.md`
- `docs/buyeros/evidence/audit-fixes-20261003/Q04-adapter.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q04-db.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q04-durability-green.json`
- `docs/buyeros/evidence/audit-fixes-20261003/Q04-durability-red.json`
- `docs/buyeros/evidence/audit-fixes-20261003/Q04-green-verified.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q04-lint.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q04-recovered.png`
- `docs/buyeros/evidence/audit-fixes-20261003/Q04-red.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q04-types-final.log`
- `docs/buyeros/evidence/audit-fixes-20261003/Q04-ui.xml`
- `docs/buyeros/evidence/audit-fixes-20261003/Q04-unit-final.log`
- `docs/buyeros/remaining/AUDIT_FIX_CASE_STATUS_20261003.csv`
- `features/live/locale.ts`
- `features/live/run-progress.tsx`
- `services/api/tests/test_run_admission_integration_db.py`
- `services/live/runs.ts`
- `services/worker/tests/fixtures/audit_intents.py`
- `tests/audit-research-intent.test.mjs`
- `tests/e2e/audit-research-intent.spec.ts`
- `tests/e2e/fixtures/workbench-auth.ts`
