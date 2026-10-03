# Q02 directory contract delta

Base: `338ee8e623b0f9b117c5cd6d3f84dc63a0a05b9d`. Local continuation of the approved repairs; Auth0 and canonical identities remain unchanged.

- `listMemberships`: adds literal case-insensitive `q` (<=200 characters), searches display name/full canonical user ID/membership ID. Retains admin-only visibility and offset/limit <=100. Count and rows derive from one filter. Every membership response (including updates) has required `display_name`, using existing DB names or full user ID fallback. No identity claims or email projection.
- New extension `listEligibleAssignees`: GET `/v1/workspaces/{workspace_id}/eligible-assignees`, same q/offset/limit. Current operator/admin callers only, checked using the existing `assignBuyerOwners` permission. Projects `{membership_id,display_name,user_id,version}` for active workspace memberships. The existing target rule allows any active member; it does not restrict target roles. Lookup, synchronous assignment, individual buyer update, bulk admission and bulk chunks share that predicate. A result does not authorize a later submission.
- Pre-Q02 durable replay responses receive only a missing display-name projection. Original roles/active/version/ETag and audit counts replay unchanged; stored historical responses are not rewritten.
- Existing last-admin advisory lock retained; current admin authority is read again after acquiring it. Role writes retain individual If-Match, reason, idempotency, version and audit.
- Settings reads markets without reapplying locale; the existing global preference flow owns language selection, preserving a user's newer choice against a late Settings read.
- UI pages 20 rows and clears obsolete rows by request identity. Filter/page/scope A-B-A response races cannot repaint old data. Reads may be retried explicitly; unknown writes are not replayed automatically. After any unknown role-write outcome, further role controls stay disabled until an explicit successful directory read reconciles current versions.
- Contract operation map: 79 operations = original 70 + existing 8 extensions + this read-only extension. This is source/generated-contract coverage, not 79 live operations verified.
- Alembic source head remains `0036_checkpoint_schema_grants`; no schema migration, membership backfill, identity linking or external activation.

Rollback: revert Q02 source and contract artifacts together. Existing user IDs, membership and audit history are preserved. Do not automatically reverse audited membership changes.
