# Conversation threads — Stage 3 boundary

Authority: Willy via Rio, 2026-10-29 continuous-plan after #40. This is a draft
implementation for review. The exact `NEXT_PUBLIC_CONVERSATION_HOME=true` flag
controls client and API registration and is also checked at request time.
Default OFF, Preview already true, Production unset. No environment edits.

All routes below are relative to
`/v1/workspaces/{workspace_id}/projects/{project_id}/conversation-threads`.
Each returns the standard live envelope, `Cache-Control: no-store`, current active
membership/project-view authorization, and 404 for unavailable thread authority.
They use explicit operation IDs and `_VIEWERS` operation roles, with the stricter
thread ACL below. Like `conversation-reply`, these flag-only routes are separate
from the retained proposed OpenAPI contract and use a handwritten LiveClient adapter.

| Method/path | Operation ID | Additional authority / payload |
| --- | --- | --- |
| GET root | listConversationThreads | Owned/shared summaries; offset 0–10000, limit 1–100 |
| POST root | createConversationThread | Explicit `confirmed:true`; template_id, title, messages, sources, runs |
| GET /{thread} | getConversationThread | Owner or current viewer/editor share |
| PATCH /{thread} | renameConversationThread | Owner; `{title}` |
| POST /{thread}/messages | appendConversationThreadMessage | Owner/editor; `{text}` |
| PUT /{thread}/sources | setConversationThreadSources | Owner/editor; `{sources:[{id,label}]}` |
| POST /{thread}/runs | appendConversationThreadRun | Owner/editor; `{id,label,status}`; existing ID updates status |
| DELETE /{thread} | deleteConversationThread | Owner; hard delete with cascading notes/shares |
| GET /{thread}/shares | listConversationThreadShares | Owner; includes inactive grants for revocation |
| GET /{thread}/share-recipients | searchConversationThreadRecipients | Owner; q ≤80, limit ≤25, offset ≤10000; member_id/display_name only |
| PUT /{thread}/shares/{member} | putConversationThreadShare | Owner; `{role:viewer|editor}`; active same-workspace member with project view |
| DELETE /{thread}/shares/{member} | revokeConversationThreadShare | Owner; immediate revocation |

All mutations of an existing thread require a strong `If-Match` version; browser
writes reuse the existing `X-BuyerOS-If-Match` transport carrier. Missing/malformed
preconditions are 400; stale versions are 409 `STALE_REVISION`. Imports, message/run
appends and share PUTs also require an 8–200 character `Idempotency-Key`. Replays
recheck current authority and return current authorized state, never stored note
snapshots. Idempotency records contain only request hashes and resource IDs.
Share changes increment both the thread version and the share's version. Thread
row locks serialize appends/share caps; project locks serialize the owned cap.

Roles are viewer/editor. There is no admin override. Owners alone can share,
revoke, delete and rename. Limits are 200 owned threads per actor/project and 25
shares per thread; title ≤80, each note ≤4000, ≤100 notes/sources/run refs. Import
accepts nonempty user notes only, rejects unknown fields at every level, and
requires the existing seven template IDs. Source IDs/labels and run IDs/statuses
match the device-store allowlists. No live AI/citation/document/fact bodies,
buyer fields, filenames or draft bodies are accepted as structured thread data.
User-entered note text is retained until owner deletion; privacy warnings tell
people not to put private details or source/draft bodies in notes. There is no
semantic content classifier. This adds no auto-upload, paid calls or provider.

Schema 0058 adds `conversation_threads`, `conversation_thread_messages`, and
`conversation_thread_shares`. Each has ENABLE/FORCE RLS and the NULLIF tenant
policy. Parent projects use `(workspace_id,project_id)` foreign keys; children
bind `(workspace_id,project_id,thread_id,owner_user_id)` to the parent. User IDs
have user FKs. Share CHECKs enforce the role, owner grantor and non-owner grantee.
Notes have DB text bounds; source/run JSONB has an immutable shape/enum/uniqueness
and size validator. JSONB keeps bounded references atomic with the thread version
without extra child writes. Threads/shares grant SELECT/INSERT/UPDATE/DELETE to
buyeros_api; immutable notes grant SELECT/INSERT. No PUBLIC or worker privileges
are added. Audit actions imported/shared/role_changed/revoked/deleted contain IDs
only, including the share ID for share operations; no titles or note text.

The migration re-points search/model/contact receipt fences to 0058 on upgrade and
0057 on downgrade. Empty downgrade drops only Stage 3 tables and the validation
helper. Populated downgrade refuses transactionally and keeps FORCE RLS/data.
Stage 2b admission, budgets, receipt transitions and the default
CONVERSATION_MODEL_UNAVAILABLE behavior are unchanged. The worker runtime reviewed
head allowlist gains 0058; no worker implementation or table grants change.

Must NOT: merge; env changes or Production flag; deploy/promote; CloudAgent;
new paid/provider/model calls; enrichment/contact/approval/send/export from chat;
PII/source/draft/live-AI-body persistence; connectors/OAuth; membership/auth/Neon
or delivery changes; public links/invites/notifications/presence; worker grants.
