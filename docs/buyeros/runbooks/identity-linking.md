# Canonical identity expansion and controlled linking (C61-09)

Local delivery only. Actual Neon project/branch, provider trust, real accounts,
deployment and live readback remain gates. This CLI does not activate Neon,
create tenant membership, change roles, reset passwords or send email.

Apply the reviewed additive 0039 SQL with a separately authorized migration
owner before deploying the active-mapping resolver. Backfill maps each existing
issuer/subject to the exact original User UUID. Compare counts, uniqueness,
historical FK row hashes, policies and API NOSUPERUSER/NOBYPASSRLS flags. Stop on
any conflicting association; never repair a conflict by changing canonical IDs.
Legacy User issuer/subject and all historical ownership/FKs remain unchanged.

Review each bounded manifest row using both verified identities or an actual
administrator verification record. The CLI currently accepts only
`proof_kind: administrator_verified`, an existing canonical UUID, its active
workspace membership, exact issuer/subject, nonempty proof_ref/reason and
expected_version. Email, display name and extra fields cannot select a User.
An arbitrary proof label is not a verification record. Retain the underlying
verification privately; the operator remains responsible for its accuracy.

The manifest has 1..100 distinct principals and at most 1 MiB, rejects duplicate
JSON keys and defaults to dry-run:

```text
uv run --frozen --project services/api python services/api/tools/link_user_identities.py --manifest reviewed-identities.json
```

Credentials are supplied only through environment/secret storage, never argv:
`BUYEROS_IDENTITY_ADMIN_TOKEN` is a currently verified admin JWT;
`BUYEROS_IDENTITY_WRITER_DATABASE_URL` is an explicitly authorized privileged
writer for the reviewed target database. There is no fallback to DATABASE_URL,
the general API DSN or a guessed migration owner. The API role cannot INSERT or
UPDATE mappings and cannot read proof_ref. Issuer/subject/user_id/proof/creation
time are immutable; the only supported update is active -> revoked at version+1.
Transaction-local proof metadata cannot grant a runtime role write authority.

Dry-run reads current DB membership/role and emits per-row would-link, replayed,
conflict or denied results without mutation. Applying requires a separate
authorized operation using the exact reviewed manifest plus `--apply`. It
rechecks the current admin and active target membership, freezes the association,
appends a redacted audit digest and commits each row. Replaying the same initial
receipt does not create a second mapping or audit. Conflicting UUID, revoked
mapping, changed proof or stale version cannot reassign an identity.

On unknown-commit, preserve the exact manifest. Do not automatically apply again.
Run the default read-only reconciliation: a matching committed mapping/receipt
reports replayed; an unavailable DB remains unavailable. Inspect the receipt and
current mapping before authorizing any further write. Results omit tokens, DSNs
and raw database errors. No provider intent or budget hold is released by linking.

For a genuinely new verified principal, the internal privileged helper inserts
one canonical User with the currently required issuer/subject fields. The primary
trigger creates the same-UUID mapping and records verified proof metadata. A
concurrent loser rolls back its insert and reads the one committed winner. A
revoked identity cannot create a replacement User. Membership is assigned later
through the existing controlled workflow.

Rollback keeps the additive table, mappings, revocations and Neon-only User rows.
The retained SQL only moves Alembic revision metadata to 0038. Keep an app artifact
that understands active mappings; do not restore a resolver that ignores revoked
identities. An Auth0-only artifact does not prove Neon-only users can log in;
compatible app/provider rollback and actual login acceptance belong to C61-13.
The local DB rehearsal proves row/FK/policy retention and canonical resolution,
not real Neon sessions or production acceptance. Worker schema admission adds
only exact reviewed 0039 and continues to refuse unknown future revisions.
