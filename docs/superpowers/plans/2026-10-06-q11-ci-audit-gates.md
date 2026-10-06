# Q11 PR11 CI audit gates — 2026-10-06

Spec: 2026-10-03-buyeros-gpt61-fixes.md Global Constraints/Q01/Q05/Q06/Q08/Q11/Q12. BASE 38c55228489a12bfc493f27d2ed27e177117366e, isolated worktree/branch codex/n00-api-request-context, published Draft PR11. Current CI37360072047: six jobs pass; API810pass2fail0skip; workbench7pass1fail0skip.

## Global Constraints

No agents, merge, manual deployment, production DB/schema/accounts/membership/linking/mail/providers/paid resources or Cloudflare cutover. Preserve historical evidence, live authentication/application behavior, destructive DB guards and original N00/NA01/302 limitations. Owned loopback Docker fixtures only, BUYEROS_STRICT_INTEGRATION=1, no required skips. Current push authorization covers repairs to this existing PR; no other shared branch update.

## Review Focus

Do not disable language to satisfy a stale pre-Q01 test. Await actual preference GET before versioned PATCH, preserve a manual locale while GET is held, assert zero premature writes and exact If-Match version, verify reload against actual persistent preference. Do not remove operation coverage: explicitly declare six already-implemented extensions and assert every declared contract method/path exists in runtime OpenAPI. Historical Q06 comparison must run exact baseline source b083ea4 and retain real HTTP bytes/SQL replay; supply history instead of substituting a synthetic baseline or suppressing failure.

## Task 1: Repair CI prerequisites and current contract assertions

Interfaces/predecessors: runtime route registry/OpenAPI and unchanged 84-operation proposal; Q01 updateLocale local-display and guarded versioned save; Q06 job-poller-traffic historical git show. The API job requires complete Git history, browser job requires current Q01 language behavior. No domain API or migration owner change.

- Reproduce registry RED from services/api (nonzero actual six-extension mismatch), and old T29 language RED in owned HTTP/Postgres/browser fixture. Retain initial wrong-cwd FileNotFound setup failure separately.
- Add missing implemented extension IDs plus method/path coverage of all declared operations.
- Configure only API checkout fetch-depth:0 for exact historical Q06 baseline. Prove shallow history cannot read it and complete local history can; do not change benchmark scheduling/baseline/constants.
- Replace obsolete language-disabled assertion with stronger held-GET/manual-language/no-premature-PATCH/exact-If-Match/persisted-reload checks. Preserve existing later status/locale assertions.
- Run targeted API contract/Q06 strict persistent suites, full strict API suite, required zero-skip checker, full daily-workbench suite, Q01 auth-entry suite, types/lint/generated84/routes; inspect diff and preserve original evidence/task objects. No new build for unchanged app source; report built fixture scope separately.
- Commit source/tests/config, record exact commands, reports, failures, source SHA and rollback; update current Q11 checkpoint and TASKS.json without closing full Q11/N00/F20/NA01.

## Task 2: Publish the reviewed CI repair and read back

After required local checks are green, push only the authorized current PR branch, verify remote SHA/PR diff and attach existing PR. Read back CI results and report hosted checks separately from local proof. No merge or production/live acceptance. Retain worktree.

## Rollback and next

Revert following checkpoint then this repair source; no schema/data rollback, retain original N00 hold journal. Full N00 OS containment composition and real auth/cleanup remain open. Cached runtime inspection found no dedicated Linux Chromium image; this is a feasibility input, not a blocking product-wide provider decision. Independent review remains pending under no-agents restriction.
## Local execution checkpoint

Task1 local gates: strict API812pass/0fail-error-skip (172warnings,1990.14s); final workbench8pass/0fail-error-skip; Q01 discovery7 then actual built Linux entry7pass/0fail-error-skip; types/scopedlint/generated84/routes exit0. Genuine old workbench RED1failure and first corrected full5pass/3beforeEach errors retained; no assertion/timeout weakening. Original shallow git show failure is repaired by supplying full history. Scope includes isolated Playwright output to protect sibling temporary evidence. Required evidence preservation/cleanup verification and Task2 publication are recorded in the following committed checkpoint.

## Hosted readback completion — 2026-10-06

Task2 readback complete for head0e100d9: all8 hosted jobs SUCCESS; actual PR merge5c97cc7 tree equals branch tree. Hosted API812; continuity4/8/1/3/1 pass,zero fail/error/skip; required checkers0. Initial continuity CANCELLED before test steps due to GitHub hosted-runner acquisition; targeted retry only,seven successful timestamps retained. Evidence Q11_PR11_HOSTED; full Q11/N00/NA01 and release gates open. Metadata-only follow-up does not change application/tests/schema or authorize merge/deploy.
