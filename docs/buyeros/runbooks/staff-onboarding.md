# Controlled staff onboarding and recovery (C61-03)

This tool reviews exact existing canonical identities and changes authorized
memberships. It is an administrative reconciliation path; the Settings member
directory remains management of existing members. Self-service invitations need
a separate expiry, single-use and acceptance design.

## Authority and review

Use the ordinary non-owner `buyeros_api` login (NOSUPERUSER/NOBYPASSRLS) and an
unexpired admin access token that passes the current API gateway's configured
signature, issuer, audience and algorithm rules. Set the token only in the
process environment as `BUYEROS_STAFF_ADMIN_TOKEN`; do not place it in argv,
the manifest, logs, Git or tickets. `BUYEROS_DATABASE_URL` is the server-only
runtime connection. Migration-owner credentials and owner `SET ROLE` are refused.

The token must resolve to an existing canonical User and a currently active
workspace_admin membership in every affected workspace. A waiting writer
rechecks that membership after acquiring the same lock as the normal management
API. No password reset, email lookup, role claim, identity linking, UUID rewrite
or self-elevation is performed. New identities not yet verified/registered stay
`pending-identity`. A workspace with no active authorized admin needs a separately
authorized recovery process; this command cannot bootstrap its own authority.

Use a JSON array of 1..100 unique workspace/user rows. Every row has exactly:
`canonical_user_id`, `workspace_id`, `roles`, `reason`, `proof_ref`, and
`expected_version`. Roles use the existing viewer/operator/reviewer/workspace_admin
contract, without duplicates. Include an approved staffing-change proof reference;
the audit stores a digest binding the complete row to its proof, actor and target.
Unknown keys, email-based targets, duplicate JSON keys/targets, missing proof,
bad versions and oversized input are rejected before writes.

For a new membership use expected_version=0 and an existing canonical User UUID.
For an inactive membership use its current version and exactly its previous roles.
The tool restores that same row/UUID and advances its version. Role changes and
demotions continue through normal versioned membership management, with the shared
last-active-admin guard. A stale version or conflicting roles grants nothing.

## Commands and outcomes

From `services/api`, with the reviewed manifest and authorized runtime environment:

```text
uv run --frozen python tools/reconcile_staff_membership.py --manifest PATH
uv run --frozen python tools/reconcile_staff_membership.py --manifest PATH --apply
```

The default command uses READ ONLY transactions. It creates no User, membership,
audit, idempotency or rate-window rows. `would-create`/`would-restore` is a proposal
from the current database snapshot; apply independently checks current authority,
target and version. Review the dry-run and proof before running apply in an
environment for which the human has already authorized these exact changes.
The local implementation authorization does not authorize production memberships.

Apply returns `created` or `restored`, including canonical IDs, current version
and an audit reference. The deterministic receipt binds the exact immutable row,
actor, target and precondition. Repeating that row returns `replayed` with the
same membership/audit, if its current state still matches the receipt. A subsequent
revocation/version/role change returns `conflict`; the old manifest never restores
access. `unchanged` has no mutation/audit. `pending-identity`, `conflict` and `denied`
exit nonzero and require a fresh reviewed decision. The bounded administrative
CLI does not perform API rate admission; normal HTTP routes retain their admission.

Each row commits independently. Preserve the complete report: a later denied row
does not roll back earlier successful rows. An apply connection/commit failure
returns `unknown-commit`; retain the exact manifest, inspect its receipt and current
membership with an authorized read, and reconcile that same intent. Do not invent
a new version/proof/key to conceal the uncertain result. Dry database errors report
`database-unavailable`; no exception message or credential is printed.

## Readback, support and rollback

In the declared environment, use the actual operator/reviewer/admin accounts to
sign in and check workspace pagination, role-gated actions and current membership
through UI and API. Refresh/check access after grant, logout/login where required.
A zero-membership user remains unable to enter private modules. Existing en/zh-HK
copy provides Check access again / Contact your workspace administrator / Copy
diagnostics; diagnostics exclude token/email/claims. The designated workspace ID
in the supplied audit is a target reference and supplies no administrative authority.

Human account/UAT and production readback remain separate gates from signed local
fixtures. This task does not create or send an external invitation/email.

Rollback source by reverting the C61-03 commit. Reverse an applied membership only
through the normal admin API with current ETag, explicit reason and audit retention;
preserve the last active admin, canonical User UUIDs and all historical FKs. Do not
delete users, rewrite receipts or blindly reverse every successful batch row.
