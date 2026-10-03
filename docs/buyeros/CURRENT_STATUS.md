# BuyerOS current repair status — 2026-10-03

This file is the current first-round repair record. Earlier checkpoints are historical evidence.

- Scope: Q11 baseline, Q01, Q03, Q04, Q15; Q16 read-only investigation.
- Reviewed/main/audit source: `a78859fe474f5722be3755b10e2586436b53bf97`; remote main checked this session.
- Isolated branch: `codex/audit-fixes-20261003`; original checkout and dirty Neon Auth worktree preserved.
- Evidence ZIP SHA256: `19369591a175edad7dd2e9f3ddb5bfdebc6cdc5130a2770243b1e9de2a42d35a`; nested CRC and all 31 manifest hashes passed; outer manifest 8/8 passed.
- Deployment: audit reports `dpl_7A95afQdDSUsaPRw2RnPFouQ1hEp`, source a78859f. No new deployment/readback in this repair round yet.
- Schema source head: inspect before any schema edit. No migration proposed by these four UI repairs. Production schema/runtime role/jobs selector/epoch: unverified this round.
- Provider activation: blocked; selected live provider allowlist empty in reviewed source. Mailbox/CRM disabled; delivery remains 403.
- Auth: Auth0 retained. Neon migration is outside this first round. No membership or identity mutation.
- Staff journey/live verification: blocked, not inferred from fixture tests.

## Finding reconciliation at start

Main is exactly the audit source; no committed source drift for F01–F21. Uncommitted Neon candidate changes are not main evidence and are excluded.

| Finding | Current classification | This round |
|---|---|---|
| F01 | still open (external evidence gate) | Q01 UI recovery; U01 membership gate remains blocked |
| F02 | fixed with local fixture evidence (Q01) | Q01 |
| F03 | still open (audit-source code unchanged) | outside selected first round |
| F04 | still open (audit-source code unchanged) | outside selected first round |
| F05 | fixed with local integration/UI evidence (Q03) | Q03 |
| F06 | still open (audit-source code unchanged) | outside selected first round |
| F07 | still open (audit-source code unchanged) | outside selected first round |
| F08 | fixed with local durability/UI evidence (Q04) | Q04 |
| F09 | still open (audit-source code unchanged) | outside selected first round |
| F10 | still open (external evidence gate) | outside selected first round |
| F11 | still open (audit-source code unchanged) | outside selected first round |
| F12 | still open (external evidence gate) | outside selected first round |
| F13 | still open (audit-source code unchanged) | Q11 baseline only |
| F14 | still open (audit-source code unchanged) | outside selected first round |
| F15 | fixed with local render/UI evidence (Q01) | Q01 |
| F16 | still open (audit-source code unchanged) | outside selected first round |
| F17 | still open (audit-source code unchanged) | outside selected first round |
| F18 | still open (audit-source code unchanged) | outside selected first round |
| F19 | still open (audit-source code unchanged) | Q15 |
| F20 | still open (external evidence gate) | outside selected first round |
| F21 | still open (external evidence gate) | Q16 blocked: OperationalError alone has no root cause |

## Verification

Pending new regression RED/GREEN evidence. Original 98-case CSV and 25-task CSV are preserved unchanged in inputs/audit-20261003; current case results are separate in remaining/AUDIT_FIX_CASE_STATUS_20261003.csv.

Baseline commands: `node tests/live-auth-checks.mjs` 8 pass; `node tests/live-adapter-checks.mjs` 74 pass. Locked pnpm install exit 0 (offline attempt failed missing policy metadata; online frozen install succeeded). Initial pre-install module-not-found attempts are environment failures, not counted passes. Node 24.18.0, pnpm 11.25.0, uv 0.11.27, Docker 29.7.2, Windows PowerShell.

## Q01 repair

Hydration is explicitly initializing; configuration failure is distinct. Language works before membership/preferences, persists only a non-sensitive display choice and ignores late preference overwrites. Empty/error access has read-only retry and allow-listed diagnostics. No auto membership or write before authorization.

RED: render 1 fail; UI 1 pass/5 fail. GREEN: render 1 pass; UI 7 pass/0 fail/0 skip; strict auth+contract DB suites 13 pass/0 fail/0 skip; auth 8, adapter 74; tsc/lint exit 0. Exact commands and full logs in evidence/audit-fixes-20261003. No schema migration; source head 0036_checkpoint_schema_grants. Rollback: revert Q01 commit, retaining baseline docs. U01 stays externally blocked; no live login/provider/production verification.

## Q03 repair

Operations uses generated AsyncJob/BulkItemResult.id and typed getAsyncJob with offset/limit=20. Complete IDs can be copied; zero results show 0–0. Per-request sequence, cancellation and session generation reject late job/page/workspace A-B-A responses. Filter changes clear result selection.

RED UI: 3 failures, 0 skips. GREEN UI: 4 pass/0 fail/0 skip, actual PostgreSQL/API producer payloads for 21/101 rows fully traversed without repeats. Different actor/tenant reads return 404. Strict bulk DB suite 10 pass/0 fail/0 skip includes real producer persistence and migration downgrade/upgrade in an empty disposable database. Generated check, tsc and focused lint exit 0. No schema or server changes. Rollback: revert Q03 consumer/test commit; persisted jobs remain. Next: Q04.

## Q04 repair

Research starts use existing ActionIntent and the complete normalized generated RunCreate body plus actor/mode/workspace/project/ICP. Fixed-point caps use six decimals; token and UI generation are excluded from durable fingerprint. UI generation still rejects stale results. Session-owned memory keeps key/body across route remounts; unknown results permit explicit same-intent Retry, with separate explicit confirmed reset for a new intent. Hard refresh has no trustworthy handle, displays a check-existing-runs instruction and never auto POSTs.

RED UI: same request used a different key; actual DB grew to 2 runs/outboxes/economic intents after committed lost 202. GREEN UI: 1 pass/0 fail/0 skip; original target 35/cap 2 restored after a settled route remount, exact same key/body/run ID on Retry, DB 1 run/1 admission outbox/1 bounded run budget account. Admission creates no provider operation/hold: 0 operations/0 reservations, not a claimed provider acceptance check. Strict admission validation+integration: 14 pass/0 fail/0 skip, including durable restart checks and new lost-response economic ceiling assertion. New unit 3/3 covers token renewal, full-body changes, double-start and A-B-A; existing adapter 74/74; tsc/lint exit 0. Backend admission/worker/hold semantics and schema unchanged. Rollback: disable new admission UI or revert consumer, preserving runs/outbox/ceilings and never replaying unknown operations. Next: Q15.
