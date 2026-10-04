# Local PR boundary — U05/F04 current membership withdrawal

Prepared locally, no remote PR/push. Base `e8e478c9e5a5812d43169759d39ddea1d5529098` -> source `25694d3b938e704e883f9915cf0604bbdbac1daf` (2source commits;6paths).

## Change

`features/live/workspace-picker.tsx` and `services/live/client.ts`: scoped denial notification,current-membership recheck,current-identity queued check,confirmed withdrawal clears/aborts private scope,explicit retry available on open page; legitimate dirty editor survives role denial and failed checks. No API/schema/auth adapter changes.

New `tests/e2e/audit-access-revocation.spec.ts`,`tests/audit-access-denial.test.mjs`,`services/worker/tests/fixtures/audit_access_revocation.py` and execution plan.10 U05 real HTTP/owned DB UI cases;fourclient boundary cases. Existing destructive guards unchanged. Auth0/current DB membership remains authority; no email linking/grants/delivery activation.

## Verification

36relatedUI/38strictAPI/17relatedNode pass0fail/error/skip. Full-root Node42pass2inherited/environment failures, so whole-branch gate remains open. Types/lint/generated84 pass,0migrations. [Exact evidence](../../evidence/audit-fixes-20261003/U05/RESULTS.md).

## Review/rollback

Author review found one current-check race; meaningful RED and full36GREEN after fix. Independent review pending. Reverse code/test-only patch applicability0; runtime rollback not performed. Keep canonical identities,memberships,audits,actor-bound records; never restore/re-add membership to roll back code. No deployedSHA.
