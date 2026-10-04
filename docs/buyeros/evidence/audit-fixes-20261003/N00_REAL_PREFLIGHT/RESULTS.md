# N00 / F20 / NA01 — local real-auth preflight component

Author-reviewed source ef0b4373fa6e4e6ca5db603d949062bec688f14b. Local only; N00 full gate stays OPEN. No deployment SHA or real Neon evidence.

## Implemented

Four files/351insertions: separate inert preflight script,36guard tests, unpopulated target template, and exact runbook usage/limits. Rejects missing/new-target mismatch, other owner/cloned data, known production/CF preview IDs, paid plan/email methods/hooks, extra DSN/config, wrong JWT algorithm/curve/audience, unexpected JWKS origin, and extended/expired TTL. Canonical users, memberships, ownership, approvals, audits/job actors, Auth0/domain API and Cloudflare HMAC are untouched.

A persistent single-machine journal reserves before execution, includes failed/lost results, survives actual process exit/restart, blocks the same operation ID from replay, protects20cleanup/reconcile requests inside a total200, and persists two bounded build slots. Exclusive writer lock/corrupt-state checks fail closed. Exact cleanup planning includes at most one new Auth-directory identity and fresh matching IDs; no deletion executor. Runtime/build env helpers remove inherited DB/Auth0/provider config and separate explicit runtime trust/cookie values from build env. The CLI intentionally denies the null template.

## Fresh verification

68Node pass /0fail /0skip, including36new preflight cases. Types0; focused lint0. Current Alembic heads0037;0schema migrations/DB connections. Meaningful RED33pass2fail observed before repair; earlier skeleton RED and Windows teardown error retained. Exact commands/counts/raw logs: COMMANDS.md / SUMMARY.json. Patch reverse applicability0, not applied.

## Open gates and evidence separation

Input JSON metadata validation does not authenticate provider readbacks or grant permission. Approval reference is provenance only; no real approval record/journal/account/target/secret was generated. No SDK/browser/CLI HTTP interception, new real-only built overlay/diagnostic wiring, secret handling on built outputs or automatic cleanup executor exists yet. Wire all traffic paths and prove built runtime config before any real execution. FS journal is for one owned local runner, not deployed/serverless/shared-state enforcement or tamper-proof storage.

Existing fixture output evidence is carried unchanged from2fd84ef: each whole built suite4pass1fail0skip. The original synthetic302 test remains failing (portable500 /Vercel200); managed callback new2tests passed previously, but neither is real OAuth acceptance or proof of a productionSDK defect. No new UI/build/API/provider/DB integration run or screenshots this turn. Prior Auth0API34pass is carried from2f14645 and not current rerun. No performance/SLA/staff-journey/live acceptance claimed.

## Next work / external boundary / rollback

Continue local real-only runtime/config/accounting wiring while new target/account approval remains pending. Before actual auth, obtain specific authorization for the fresh-empty project/Auth and one human-operated Google test identity in the named org, US$0/200checks/two-hour cleanup; previous preview approvals expired. Keep issuer/audience/JWKS NULL until authenticated actual readback/review. Do not use fixtures as live proof. New production Auth0/Cloudflare/env/DB/role/mail/provider/deployment changes remain outside this proposal.

Rollback this source slice: git revert ef0b4373fa6e4e6ca5db603d949062bec688f14b and the accompanying metadata checkpoint. No DB or resource undo is necessary. source.patch.gz +rollback.json retains exact reviewed diff/reverse applicability evidence; no patch applied. Original frozen inputs and prior247payloads/fourDBguards untouched. Independent review pending per no-agent instruction.

Diff hygiene: source/authored metadata0; full staged check2 only four verbatim RED-log whitespace lines. See DIFF_HYGIENE.md/raw capture; source/test outcomes unchanged.
