## Task 1: U05 withdrawal and access recheck
Interfaces: Q01 auth/locale recovery; Q02 current DB authority/directory; Q03 generation/abort; Q15 dirty editor. Consumers: live client, LiveWorkspace and SessionScope. Existing next-request API revocation test is unchanged.

- [ ] Add audit-access-revocation.spec.ts on playwright.audit-fixes.config.ts with owned HTTP/PostgreSQL: real admin withdrawal after operator opens a page, denied next read/write, automatic current-membership recheck, explicit recheck, held old rows/access results, scope races, negative legitimate 403/404 and recheck failure. Cover en and zh-HK/390px. Observe meaningful RED before product changes.
  Expected: baseline keeps revoked cached scope or lacks current-page recheck; retained failure evidence. Setup errors are not RED.
- [ ] Implement the smallest current-identity access-denial notification and current-membership recheck; clear revoked scope/URL/private UI, abort outstanding scope requests. Never classify all 403/404 as revocation or retry writes.
  Expected: regression tests pass with unchanged current server membership authority, no synthetic API rows.
- [ ] Run UI new + auth-entry + memberships + affected dirty-draft suites, Node client/auth/scope/intent checks, strict DB auth-cache/membership/authorization suites, types/lint/generated contracts and Alembic heads.
  Expected: all named gates pass, required DB zero skips; exact counts/commands retained.
- [ ] Inspect diff; author review and reverse-patch rollback applicability; preserve frozen inputs, guards and unrelated work. Commit source/tests then case/status/evidence metadata locally.
  Expected: clean reviewable commits, U05 only repair fields updated, no deployed SHA and independent human/live gates remain open.
