# C61-13 identity cutover and cold rollback

This is a reviewable local procedure, not permission to switch production auth.
Neon-only, Release A and native send remain NOT ACCEPTED. Exact real Neon
project/branch/auth URL/audience/JWKS, provider sessions, C29 canary and human
role acceptance are separate gates. The historical workspace500 root is still
UNCONFIRMED; this rehearsal does not establish its cause.

## Expand and verify

1. Pin the current release source, compatible frontend/API artifacts, schema
   version, exact trust configuration digest and a finite dual-trust deadline.
   Record the actual deployment/account/branch; do not infer it from an SDK URL.
2. Apply reviewed0039 only within authorized migration scope. Preserve every
   canonical User UUID and membership/owner/approval/audit FK. The retained
   table rollback to0038 changes metadata only; it does not delete identities,
   proof, revoked status or versions. Prefer leaving expanded schema intact
   during an application rollback.
3. Collect proof for both exact principals and the intended canonical UUID.
   Dry-run the bounded1..100row manifest using the explicit identity writer and
   a verified current DB administrator. No email-based linking, password export
   or automatic membership creation. Old email/password users require the
   official provider-supported enrollment/reset flow and separately verified
   linking proof; real recipients/providers remain a gate.
4. Apply the exact reviewed manifest in one transaction. Tenant admin locks
   are acquired in deterministic workspace order; each row checks its current
   administrator, active target membership and identity version/proof. Any
   conflict/denial rolls the entire batch back, with no surviving new links or
   link audits. Other rows return`not-applied/IDENTITY_BATCH_ABORTED`.
   A lost commit acknowledgement marks ALL rows`unknown-commit`. Preserve the
   exact manifest and run read-only reconciliation; do not issue another write
   or release unknown provider holds to make the deployment look healthy.

## Canary, switch and monitor (C29 gate)

Prepare a bounded canary with both migrated and Neon-only accounts and current
viewer/operator/reviewer/admin roles. Proposed review window:30minutes and20
authenticated tenant reads with0wrong actor/tenant/role decisions and0critical
login failures; the owner must approve the actual target/window before release.
Use a separately authorized budget for any provider work. Stop immediately on
one wrong actor/tenant, critical login failure or replayed external side effect.
Observe role/mapping revocation with the same warmJWT and preserve exact intent,
digest, revision and accepted/unknown receipts. Record source/config/deployment
readback. Auth0 retirement is C14 after C29, never an indefinite dual-trust mode.

## Compatible application rollback

The local cold API candidate is pinned to
`0f2ac905c852403c3a30a966df18272acc723bf1`(C11, includes C09/C10). The rehearsal
extracts that exact API package into a new directory and imports it in fresh
processes against the restored runtime-role PG16 cluster. Real Ed25519
signatures are verified; only the exact approved JWKS response is synthetic.
There is no Principal override. Migrated and Neon-only identities obtain their
existing project200; a revoked alias stays404. Canonical IDs, all catalog-derived
historical user-FK row hashes, identities/revokes, cost ledger and unknown holds
must exactly match before/after.

This proves compatible API authorization with owned signed tokens. It does not
prove a real Neon provider session, browser login, physical Safari or production
rollback. The previous C11 frontend/SDK proof is separately recorded. Retain a
compatible Neon frontend AND API artifact for production; an Auth0-only artifact
cannot recover Neon-only users. Keep identity writes paused during rollback and
use the current atomic CLI only for read-only reconciliation until reviewed.

## Cold database restore

1. Isolate the restore cluster and hold all application/worker ingress before
   restoration. Keep live reads closed(`READ_DISABLED503`). Retain the external
   deletion/retention journal and reconciliation records outside the backup.
2. Restore the older backup with its reviewed roles/grants; confirm NOBYPASSRLS
   and FORCE RLS. Immediately pause the runtime selector and advance its epoch
   before replay. Old worker envelopes must return stale and make0new provider
   submissions/status calls; no copied lease can authorize a new side effect.
3. Verify the external journal's provenance/authenticity and bounded scope.
   Replay tombstones through the runtime tenant boundary, then replay again to
   prove idempotence. Deleted content must remain redacted with one audit and
   one deletion outbox intent. Private-object deletion completion is a separate
   object-provider gate; this fixture retains the deletion outbox/object key.
4. Reconcile ledger amounts, immutable operation receipts and ALL unknown holds.
   An unknown operation remains active with its full hold. Never convert unknown
   to proven-unsent or replay submit merely because a lease/backup is old.
5. A reviewer may reopen reads only after tombstones and ledger checks succeed.
   Workers/readiness remain unavailable until fresh approved runtime/probe
   evidence exists. Reconcile uncertain provider outcomes through status only;
   activating the worker is a separate gate.

The two C13 cold rehearsals use actual pg_dump/pg_restore on four owned
disposable containers. They prove the older backup initially contains private
content,503before and after replay while held, exact ledger/FK hashes, an active
unknown0.100000USD hold, a retained0.050000USD settled event, immediate epoch
fencing, and a fresh compatible API process before the local read gate opens.
No real provider or production data is used. Timeline/count/hash/login evidence
is retained in`artifacts/c61/C61-13-cold-*-rehearsal.json`.

## Verification and rollback points

The focused RED batch suite records4real DB failures. The minimal transaction
fix and prior reconciliation checks pass10cases. Cold fixture attempts retain a
quoting syntax error and Windows InterfaceError; the latter was corrected by
matching the existing test harness's Windows selector-loop prerequisite, with
no production/JWT/RLS changes. The final required suite/discovery receipts are
`C61-13-required-final`and`C61-13-required-discovery`; CI explicitly checks both
named cold cases and the earlier T28 restore case and requires nonempty/no-skip
JUnit results. Inspect actual receipts for counts/status rather than assuming a
workflow declaration passed hosted CI.

Rollback the atomic linking change by reverting its source commit only while
identity writes remain paused; this would restore the unsafe per-row behavior,
so retain the new batch negative tests and prefer disabling writes. Existing
schema0039, canonical rows, revokes/history and accepted/unknown holds remain.
For auth/runtime rollback, retain the compatible Neon artifact and reviewed
finite trust, keep reads/worker gates closed as needed, and preserve evidence.
