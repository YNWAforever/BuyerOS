# Conversation home Stage 4 — Connections (Google Drive)

Authority: Willy via Rio, 2026-10-30 Asia/Singapore: A Connections, A1 Google Drive only;
Fimmick OAuth ownership, approved-folder read access, Ask grounding allowed,
HK residency preference and minimal retention. Other connectors and variants B/C/D remain parked.

`NEXT_PUBLIC_CONVERSATION_HOME` must equal the exact string `true` on both client
and API. Default/unset is OFF, retaining #41 OFF. Preview is already true;
Production must remain unset until separate approval. No Vercel environments,
secrets, deployments, promotion, merge or review readiness changes belong to this PR.

## User flow and permissions

Connections / Available context now contains Google Drive. An active workspace
admin connects the project's independently provisioned Fimmick OAuth grant,
opens the folder picker, and approves up to 20 folder IDs. No typed URLs, file
names, OAuth tokens or account identity fields are accepted. Folders/items use
numbered generic labels and opaque IDs so users can match the approved IDs in
their administrator's configuration. Members can list and select approved item
IDs. Workspace thread selection also enforces the existing owner/editor ACL;
viewers cannot edit. Existing Offer permissions still control Ask.

Approval changes, disconnect, and reconnect rotate a generation UUID; previous
source references never revive. Selection/import and each Ask recheck the current
connection, current project and membership, generation, folder approval and live
Drive parent/access. A moved/inaccessible item is rejected. Disconnect revokes
BuyerOS access locally in the same transaction, even during a gateway outage.
It does not delete Drive data or revoke an OAuth grant used elsewhere; the grant
owner can independently revoke it in Fimmick's secret service. Existing in-flight
reads cannot be recalled; row locks order local approval/revocation and requests.
No background ingestion, polling, write/upload/share/delete, or public links.

Disconnected, unavailable gateway/credentials, empty approved folders, denied
access, unverified responses, stale versions, and uncertain saves have distinct
honest UI states. Reload rechecks status/items. Each positive local selection bypasses the metadata cache and rechecks available IDs; local removal needs no external read. Offline status preserves the administrator's local disconnect control. Sign-out and scope transitions
abort requests and clear metadata and pending action intents. en and zh-HK, native checkboxes,
fieldset legends, keyboard buttons, live notices and 320–1440 layouts are covered.

## MCP adapter and provisioning boundary

`services/drive_mcp.py` is the API's read-only MCP adapter. The server-only
`BUYEROS_DRIVE_MCP_URL` (HTTPS, no userinfo/query/fragment) and
`BUYEROS_DRIVE_MCP_TOKEN` must be provisioned separately, outside this PR. Neither
is configured by this work. No second provider or custom OAuth client is added.
When absent, Connections reports unavailable and connect is disabled. CI uses
an owned fixture; no live Google/OAuth/paid calls form part of local proof.

The Fimmick-owned gateway must hold and refresh each tenant/project's OAuth grant
in its secret store and perform the administrator's Google consent flow with
`https://www.googleapis.com/auth/drive.readonly`. It must bind the API's authenticated
service credential and workspace/project IDs to the correct delegated grant;
IDs are never sufficient authorization by themselves. Connect verifies that grant,
then attaches it to the project; BuyerOS never receives a Google refresh token.
A generic unscoped Drive MCP server cannot be substituted for this gateway contract.

The adapter implements initialization and session headers, then a fixed `tools/call`
allowlist using MCP 2025-06-18 [Streamable HTTP](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
and [structured tool results](https://modelcontextprotocol.io/specification/2025-06-18/server/tools).
JSON and bounded SSE responses are supported. No tool discovery or model-directed
tool execution is exposed. Redirects and environment proxy inheritance are disabled;
one 12-second deadline and a 64 KiB decoded-response cap cover each call. Source resolution has a 20-second total deadline. Upstream
bodies/errors, credentials, names and text are never logged or returned in errors.

Required tool `structuredContent` contracts (unknown metadata keys fail closed):

| Tool | Arguments beyond workspace_id/project_id | Result |
| --- | --- | --- |
| `buyeros_drive_status` | none | exact workspace_id/project_id, oauth_owner=`fimmick`, scope as above, connected=true, residency_preference=`HK`, retention_seconds=0 |
| `buyeros_drive_list_folders` | limit=100 | folder_ids: unique opaque IDs, maximum 100 |
| `buyeros_drive_list_items` | folder_ids, limit=100 | items: unique `{id,folder_id}`, maximum 100 |
| `buyeros_drive_read_item` | folder_ids, item_id, max_bytes=12000 | `{id,folder_id,text}` with bounded plain text |

The gateway must resolve current direct folder parents, reject shortcuts, public
links, trash and inaccessible files, and confine every item read to the supplied
approved folders; the API independently verifies returned parent IDs. Descendant
folders require their own explicit approval. Listings are bounded to 100 entries;
this release does not claim exhaustive Drive search or recursive discovery.
HK is a residency **preference**, not a claim that Google's infrastructure or a
future gateway has been independently residency-certified. The gateway must honor
the preference and zero content-retention contract before it can pass status.

## Data and Ask boundaries

Persisted data is connection UUID, project/workspace/admin UUIDs, connected state,
version, generation, approved folder IDs with `Google Drive folder` labels, and
created/updated timestamps. Selected discussion sources are
`drive:<generation UUID>:<opaque file ID>` plus `Google Drive item`. IDs are
bounded to `[A-Za-z0-9_-]{1,128}`; source references remain under 200 characters.
Authorization configuration remains until explicitly changed/disconnected; it is
not a content/metadata cache. Server content/metadata cache TTL is **zero**.
Browser metadata reads use scope-owned memory with a 30-second TTL and explicit reload invalidation; only selected IDs/generic labels may
join existing discussion persistence. No Drive file bodies, filenames, buyer PII,
Google tokens or gateway credentials go into DB, logs or browser storage.

Ask resolves only selected approved items, at most 20 selected sources and 12,000
UTF-8 bytes total. Text is untrusted evidence in request memory; it does not add
tools or instructions. Fixture grounding exercises the full source check and
citation path. Drive-derived replies remain ephemeral even for fixture replies.
Citation buttons stay within BuyerOS Connections; no Drive/public URLs are stored.

The current paid model receipt persists its basis/excerpts. Consequently Drive
Grounding has `paid_eligible=False` and cannot enter that receipt path. The
unselected `ROUTE.route_id=None` / `REGISTRATION=None` defaults and
`CONVERSATION_MODEL_UNAVAILABLE` remain unchanged. No paid model is activated.
If a future separately reviewed registration is installed, existing policy
admission rejects Drive before any reservation/receipt; enabling it would require
a content-free receipt design. Research-from-chat still confirms an existing
approved ICP through startRun; Drive content is not copied into research jobs or
receipts. This Stage does not expand research/provider admission.

## Routes, concurrency, schema

All six routes share
`/v1/workspaces/{workspace_id}/projects/{project_id}/conversation-connections/google-drive`:

| Method/suffix | Operation ID | Roles |
| --- | --- | --- |
| GET | getConversationDrive | existing project viewers |
| POST | connectConversationDrive | workspace_admin |
| DELETE | disconnectConversationDrive | workspace_admin |
| GET /folders | listConversationDriveFolders | workspace_admin |
| PUT /folders | approveConversationDriveFolders | workspace_admin |
| GET /items | listConversationDriveItems | existing project viewers |

Every request re-resolves membership/project, applies live_read_enabled and tenant
scope; admin denial/foreign project IDs are no-leak 404. The runtime flag returns
404 before auth/body validation when OFF. Responses, including errors, are no-store.
Bodies forbid unknown fields and use StrictStr IDs. All three mutations require
Idempotency-Key and `X-BuyerOS-If-Match` (or direct If-Match), including connect
against initial virtual version 1. Stale versions return 409 STALE_REVISION.
Project/connection locks serialize first creation and subsequent updates; replay
returns current authorization and cannot restore a revoked grant. Audit records
contain entity/actor IDs only. Thread source replacement is now idempotent,
revalidates Drive before replay, and audits the thread ID without copying content.

Alembic **0059_conversation_connections**, down_revision **0058_conversation_threads**,
adds one table with ENABLE+FORCE tenant RLS, composite workspace/project FK,
buyeros_api-only CRUD grants, strict JSON folder/label/cap CHECKs, no seeds and
no content/credential columns. The thread-source validator admits only generic
Drive references. All three receipt fences point to 0059. Downgrade refuses
populated connections or Drive references and restores 0058's validator/fences
only on an empty safe downgrade. Current-head assertions, readiness and C61
owned readback move to 0059. The only worker-related edit is appending 0059 to
the API recovery service's reviewed schema allowlist; worker behavior is unchanged.

Must NOT: Drive writes; other vendors/connectors; public/cross-workspace shares;
email invites; auth/Neon membership widening; paid activation; enrichment/contact/
approve/send/export from chat; Vercel environment edits; deploy/promote; undraft;
merge; CloudAgent. Production NEXT_PUBLIC_CONVERSATION_HOME remains unset.
