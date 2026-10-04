# BuyerOS U05 existing-page membership withdrawal

Spec: frozen audit-20261003 case U05/F04 and the human-selected U05 continuation on 2026-10-04.
Base: e8e478c9e5a5812d43169759d39ddea1d5529098.

## Global Constraints
Retain canonical identities/current BuyerOS memberships and RLS, Auth0, in-memory bearer tokens, domain API and delivery 403. No agents, push, remote PR, deployment, production mutation, paid resources, mail or auth/Cloudflare cutover. Only the existing owned loopback/Docker fixture may mutate data. Preserve original audit inputs and unrelated work. Required DB checks use strict mode with zero skips.

## Review Focus
A scoped 403/404 is not proof of revoked membership. Recheck current membership through the existing paginated workspace API. Current-identity cancellation must defeat held requests, A-B-A races and older access checks. Failed rechecks cannot claim revocation or replay writes. A legitimate member's ordinary forbidden/missing resource must retain scope and dirty edits. Locale and explicit retry remain available without membership. Withdrawal must not create users/memberships or reactivate them. Provider fixture and live verification remain separate.

## Task 1: U05 withdrawal and access recheck
Interfaces: Q01 auth/locale recovery; Q02 current DB authority/directory; Q03 generation/abort; Q15 dirty editor. Consumers: live client, LiveWorkspace and SessionScope. Existing next-request API revocation test is unchanged.

- [x] Add audit-access-revocation.spec.ts on playwright.audit-fixes.config.ts with owned HTTP/PostgreSQL: real admin withdrawal after operator opens a page, denied next read/write, automatic current-membership recheck, explicit recheck, held old rows/access results, scope races, negative legitimate 403/404 and recheck failure. Cover en and zh-HK/390px. Observe meaningful RED before product changes.
  Expected: baseline keeps revoked cached scope or lacks current-page recheck; retained failure evidence. Setup errors are not RED.
- [x] Implement the smallest current-identity access-denial notification and current-membership recheck; clear revoked scope/URL/private UI, abort outstanding scope requests. Never classify all 403/404 as revocation or retry writes.
  Expected: regression tests pass with unchanged current server membership authority, no synthetic API rows.
- [x] Run UI new + auth-entry + memberships + affected dirty-draft suites, Node client/auth/scope/intent checks, strict DB auth-cache/membership/authorization suites, types/lint/generated contracts and Alembic heads.
  Expected: all named gates pass, required DB zero skips; exact counts/commands retained.
- [x] Inspect diff; author review and reverse-patch rollback applicability; preserve frozen inputs, guards and unrelated work. Commit source/tests then case/status/evidence metadata locally.
  Expected: clean reviewable commits, U05 only repair fields updated, no deployed SHA and independent human/live gates remain open.
