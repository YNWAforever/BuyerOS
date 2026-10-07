# C61-06 current-actor workspace directory

Status: local implementation verified by 39 required cases (0 fail/error/skip)
and an owned 4-stage benchmark. Full API regression executed 832 cases: 818 pass and 14 diagnostic failures;
C61-04 correction is focused-verified, and full rerun remains pending. C61-02 whole
built acceptance and actual Neon owner/deployment/readback remain separate
gates. No deployment.

The reviewed peer `fa198ae533be3dc93eda73bc45331c2d80eb9540` uses an extra
self-discovery RLS SELECT policy. That policy is not adopted: the original
tenant policy and FORCE RLS must remain exactly in force. Reuse its pagination,
signed-fixture, query-count, same-pool actor-switch and benchmark ideas.

The observed current baseline is 8/26/206/2006 SQL statements at added unrelated
workspace counts 1/10/100/1000. Two existing seeded workspaces explain the
difference from historical 4/22/202/2002. The required bound stays <=6.

## Trusted boundary and restricted function

The API first verifies JWT issuer, audience, keys and algorithm, then resolves
the existing canonical User UUID by exact `(issuer, subject)`. There is no
public user_id parameter, email linking, identity creation or role claim trust.
The trusted API credential sets `app.user_id` only locally for that transaction.
Database credentials are the server boundary: a compromised API SQL credential
is not an untrusted end-user principal and is outside this function's guarantee.

The implemented `public.buyeros_workspace_directory(uuid,bigint,integer)` is
STABLE, SECURITY DEFINER, fixed `search_path=pg_catalog, public`, with every
table reference schema qualified. EXECUTE is revoked from PUBLIC and worker;
only buyeros_api may execute, with exact session_user, canonical actor binding,
valid bounded pagination and a read-only transaction. It reads only active
memberships for that actor, builds one snapshot page/count ordered by UUID,
and has no mutation or dynamically constructed SQL. The active user/workspace
partial index supports this predicate. Route and load_membership share the
resolver; permissions still come from current BuyerOS memberships.

FORCE RLS and the existing tenant policy are untouched. API and worker remain
non-owner, NOSUPERUSER, NOBYPASSRLS. Migration must fail closed unless its
already-existing owner is privileged enough for the restricted definer read;
it does not create a privileged role or grant BYPASSRLS/superuser. The actual
Neon migration owner's eligibility is a separate unverified deployment gate.
Do not change role privileges or RLS merely to make that gate pass.

Directory transactions use REPEATABLE READ, READ ONLY; actor/workspace GUCs
are SET LOCAL and cleared when the transaction returns to the real pool.
Revocation is observed on the next request's snapshot. Tests must use the
actual buyeros_api login, not owner SET ROLE, and verify actor A/nonmember B/
revoked A on the same backend connection. Very large public offsets produce
an empty page rather than integer overflow; no UUID or historical FK changes.

## Evidence and deployment payload

Required DB suites need positive testcases and zero failures/errors/skips.
The owned benchmark refuses inherited DSNs, collection overrides and reused
output, verifies an owned marker and exact container identity for cleanup,
and retains every failed request in its denominator. Its zero-case/skip/failure/
error report holes were reproduced in four failing unit cases and corrected
using the shared required-suite validator (7 cases green).

Collect 30 actual requests per W=1/10/100/1000 after three primers, including
SQL counts, bytes, errors and latency. n=30 p99 is explicitly unstable; local
in-process ASGI plus loopback PG16 is not geographic or production load.
EXPLAIN the actual readonly function under the runtime role. Its nested page/
count SQL is additionally explained under the migration owner and labelled
diagnostic; that owner plan cannot stand in for runtime authorization proof.

Before migration, verify the latest single Alembic head, owner eligibility,
function ownership/grants and unchanged RLS; review the ordinary index-build
lock window on actual data. Deployment and live readback require separate
authorization/evidence. This performance work does not explain or close the
historical workspace500 incident or authorize C61-05.

## Rollback

Revert the new route/resolver path first, retaining the additive function/index.
The old route's O(W) performance then returns, but tenant authorization does
not relax. Optional administrative downgrade drops only this function/index;
it must preserve canonical users, memberships, audit and historical FKs.
Production migration/rollback is not executed by this local evidence.


## Actual local execution

The first implementation suite had 23 passes and one reproducible schema-head
compatibility failure: the operator runtime tool only allowed through 0037.
The additive 0038 head was added to that explicit allowlist; unknown heads,
epoch checks, drain checks and default dry-run remain enforced. The resulting
39-case required suite passes with zero failures, errors or skips, including
actual downgrade/upgrade and preservation of canonical rows, FK definitions,
FORCE RLS, policies and restricted grants. Artifacts:
`artifacts/c61/C61-06-directory-required-green.json` and its fresh JUnit/log.

`artifacts/c61/c61-directory-measured.json` records 30 warm real HTTP/PG requests
per W=1/10/100/1000. SQL/request is exactly 4 in all four stages; all 120 measured
requests have zero HTTP, transport or context failures. Runtime role is
buyeros_api, non-owner, non-superuser and NOBYPASSRLS. Actual same-pool identity
reuse/revocation and both runtime EXPLAIN and labelled owner diagnostics are
included. Other owned verification was running on this local host; latency is
not a production or geographic performance claim, and n=30 p99 is unstable.

The checked offline SQL payload and rollback are under `artifacts/c61/` as
`c61-workspace-directory-upgrade.sql` and `c61-workspace-directory-rollback.sql`.
Only owned fixture migrations were applied/rolled back. Required API regression
results will be recorded separately; focused success does not imply that suite,
production 500, Neon-only, Release A or native delivery is accepted.
