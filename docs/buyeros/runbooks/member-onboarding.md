# Controlled member onboarding and directory (Q02)

This release adds read-only directory search and versioned editing of existing memberships. It does not add invitations, send email, create accounts, link identities, or grant production access.

## Administrator checklist

1. Verify the account's immutable issuer and subject through the approved identity owner. Preserve an existing canonical `users.id`; never link by matching email.
2. Record the exact workspace, canonical user ID, least required roles, reason, approver and approved environment. Neon identity or token role cannot grant BuyerOS workspace authority.
3. Use the existing controlled administrator procedure for user/membership creation only after the specific target and grant have approval. Follow the production runbook and audit transaction; this UI has no create-member action.
4. Sign in as an authorized workspace administrator. In Settings, search by authorized display name, full user ID or membership ID. Compare the complete ID, particularly for duplicate names. The page holds 20 rows; API limits are 1..100 and query length <=200.
5. Make one existing-member change using its current version, reason and idempotency key. A 412 requires reading and comparing the latest version. An unknown write result must be reconciled before submitting a different action. Preserve at least one active administrator.
6. Confirm the intended account can read its own workspace and has only the approved actions. Check the audit event and that revoked/inactive memberships lose access on the next request. Do not treat a fixture identity as a production account rehearsal.

## Restricted owner directory

`GET /v1/workspaces/{workspace_id}/eligible-assignees?q=&offset=&limit=` is available only to current operator/workspace_admin memberships (the same caller permissions as `assignBuyerOwners`). Its projection is `{membership_id, display_name, user_id, version}`. Targets are current active workspace memberships, including viewer/reviewer roles, matching the existing submission rule. Submission and durable chunks recheck the shared eligibility predicate; a search result does not authorize a later write.

The admin membership directory contains role/active/version information. Neither projection returns email, issuer, subject, tokens, or identity-provider claims. Missing/blank display names fall back to the full canonical user ID. Search treats `%`, `_` and backslash literally; filters and totals use the same server query.

## Rollback

Revert the Q02 source/contract commit and regenerate the previous contract artifacts together. No database migration or data rollback is needed. Do not undo already audited role changes automatically; any compensating membership change needs current authority, version and a recorded reason. Delivery remains disabled (403).
