# BuyerOS retention operation (T28)

This runbook describes the local lifecycle code. It does not set a lawful retention period or authorize production deletion. The controller must approve the policy version, source/contact deadlines and restore window before activation.

## Configuration and scope

- `BUYEROS_RETENTION_POLICY_VERSION` enables the worker sweep. Its unset default makes no automatic retention decision. Source `retention_until` and contact `retention_expires_at` must each be explicitly set; null is not interpreted as permission to retain indefinitely.
- `BUYEROS_CHECKPOINT_DATABASE_URL` is a server-only connection for the existing `buyeros_worker` graph role. Keep it out of browser bundles and logs. Without it, a source linked to a run remains tombstoned but its `source.delete` intent stays nonterminal for retry. Do not mark that intent done manually.
- Each sweep is bounded by the worker batch size and opens a transaction-local tenant context per workspace. It does not perform object I/O inside the tombstone transaction.

## Deletion sequence

1. Confirm the affected workspace, subject IDs, approved policy version and elapsed deadlines using a read-only scope report. Pause new paid admission/dispatch if source generation may still be active; retain reconciliation for accepted or unknown provider operations.
2. `expire_subject_data` locks the due subject. Source expiry redacts source URL/excerpt and cited evidence, marks dependent fit and drafts stale, removes copied fit/draft text, invalidates project approvals, clears invalidated approval snapshots and revokes ready exports. Contact expiry scrubs the address and due linked person data, redacts addressed drafts, invalidates recipient approvals and revokes contact exports. Audit rows contain IDs and a policy-version digest, not content.
3. A committed `source.delete` outbox intent drives private-object deletion and, for run-linked sources, graph checkpoint deletion. The worker fences the intent and uses only the existing graph role. Object/checkpoint deletion is idempotent; failure leaves the intent dispatched for lease recovery. A replay of a tombstoned source recreates a missing intent after an isolated restore.
4. Verify redacted database fields, revoked exports/approvals, outbox terminal state and zero matching private objects/checkpoint rows. The sweep returning a subject ID alone does not prove physical deletion.

## Restore and rotation boundary

A restore from a backup taken before a tombstone can reintroduce old content. Preserve a separately controlled deletion journal and reconcile it against the restored target before permitting reads; a local two-container fixture covers a backup taken before one source tombstone and replays a test journal while API reads return 503 `READ_DISABLED`. It does not establish durable external journal capture, authenticity, completeness or object-store deletion. The operator must reconcile every deletion since the backup, verify downstream cleanup and keep reads disabled until that is complete. Keep reads disabled during this reconciliation. Rotate compromised DB, broker, R2 or provider credentials in the secret manager, then restart the relevant processes; do not paste credentials into an issue or log. Production backup restore and legal retention activation remain unverified.
