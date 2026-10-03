# PR-11 / Q02 — Searchable member directory and safe identity projection

Base: `338ee8e623b0f9b117c5cd6d3f84dc63a0a05b9d`. Source commit: fb184819d038dc2ad56b7f1746362fe9b7a6089a. Local review preparation; no GitHub PR/push/deployment is implied.

## Outcome

Close local F03/F04 coverage for U06/U07/U08/S06: 250 memberships can be read in 13 pages of20 and searched by display name/full canonical ID/membership ID; duplicate names and ID suffixes remain distinguishable. Preserve existing role-write If-Match, reason, idempotency, audits and last-admin rule. Recheck current admin after waiting for its advisory lock.

## Changes

- Strict generated Membership now carries authorized display_name/full-ID fallback; literal bounded server search shares its filter with total.
- New `listEligibleAssignees` extension for current operator/admin callers, projected safe fields only. Current active-member target rule is shared by lookups, individual/synchronous/bulk owner submissions and chunks; inactive targets are rechecked and rejected. No invitations/email/account creation or bulk role endpoint.
- Independent `MemberDirectory` component derives visible data from current request identity. Page/filter changes and A-B-A discard stale responses. Read failure returns no synthetic rows; explicit read retry recovers.
- Unknown role-write results disable further role editing until a successful directory read reconciles current state. Lost committed response test observes exactly one PATCH and durable version2; no retry write.
- Settings stops reapplying late locale reads; the existing global preference flow owns language. Existing canonical IDs/memberships/actors/Auth0 remain unchanged.
- Legacy idempotency responses add only the missing name projection to the outgoing envelope. Original business result/ETag/audit and stored response remain unchanged; no data migration.

## Evidence and review limits

See `docs/buyeros/evidence/audit-fixes-20261003/Q02/RESULTS.md` for exact RED/GREEN commands, environment, counts, original failures and artifacts. All required DB suites use strict mode and disposable Docker Postgres, runtime role, unchanged guards. Browser fakeOIDC is fixture evidence, not live Auth0/Neon/provider verification. Author review performed inline; independent reviewer approval remains pending. Production grant, activation, auth migration and deployment are separate gates.

## Contract and rollback

79 source/generated operations = original70 + nine extensions. Q02 adds one read-only operation; no schema migration. Source head stays0036_checkpoint_schema_grants. Revert this source/contract commit as one unit; reverse patch applicability is checked locally. Do not reverse already audited membership changes automatically.
