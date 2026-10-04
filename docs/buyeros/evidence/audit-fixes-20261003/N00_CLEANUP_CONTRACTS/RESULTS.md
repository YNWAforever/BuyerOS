# N00/F20/NA01 — exact Neon cleanup contract preparation

Source370a558492ef2c6617379c8923f2ce17c81da66f; base158e05f0b31e4c59776d39c6c2926f6ab8bf3fcd; branchcodex/n00-cleanup-contracts. Four source/type/test paths,97insertions,0deletions. [Patch](source.patch), [source hashes](SOURCE_HASHES.json), [counts](COUNTS.json). No remote PR/push/deployment.

## Implemented

A pure provider-schema adapter validates official GET project/Auth payload fields against the journal's exact new-empty target: projectID/org/name/region/platform/creation time and Better Auth integrationID/branch/Neon ownership/explicit baseURL/JWKS. Fresh receipt timestamp/GET/exact URL/status200 required; all denied/redirect/error/404/stale/future/wrong-path/credential-bearing readbacks fail closed. Output is an unarmed exact GET/DELETE descriptor proposal with delete_data=false for auth schema preservation. No network, ambient credentials, CLI or deletion executor. Schema/HTTP parsing alone does not authenticate supplied metadata or grant permission.

A bound identity blocks Auth/project deletion descriptors until a Managed Better Auth removal/absence contract is verified. Pending/unknown journal requests also block every deletion descriptor. No unknown operation is resent or reservation erased. Cleanup planning after TTL requires fresh readbacks and retains the original target/expiry. Declared output can never claim external_verified/execution_enabled/authority=true.

## Official contract evidence and limitation

Public schema867639bytes SHA54dfd27c22f64fb31f100497885cb2465a512028aa3ca5e17ac574d554fb20e5 fetched without credentials. Endpoint/schema provenance in PROVIDER_CONTRACT.json; the full downloaded public schema remains ignored local input, not copied as product evidence. Official [GET Auth](https://api-docs.neon.tech/reference/getneonauth), [disable Auth](https://api-docs.neon.tech/reference/disableneonauth), [project deletion](https://api-docs.neon.tech/reference/deleteproject) and [user deletion](https://api-docs.neon.tech/reference/deletebranchneonauthuser) checked.

User deletion is described against users_sync and has no exact GET in this schema; this is insufficient proof of Managed Better Auth identity deletion/absence. No legacy endpoint is assumed compatible. Project deletion is recoverable for7days; it cannot establish immediate permanent identity erasure. No higher privilege, API credential, SQL deletion or email flow was invented to resolve this gate.

## Fresh verification

| Run | Pass | Fail | Error | Skip | Exit/time |
|---|---:|---:|---:|---:|---|
| Initial RED |0|32|0|0|1 /633.0962ms; missing required adapter functionality |
| First adapter GREEN |32|0|0|0|0 /1238.8187ms |
| Reconciliation RED |34|2|0|0|1 /2036.2317ms; pending/unknown lacked descriptor gate |
| Final14-file related Node |201|0|0|0|0 /45791.6769ms; includes36new cases |

Groups overlap; do not sum unique tests. Actual owned loopback HTTP integration returned provider-shaped project/Auth payloads over2durably reserved/accepted control requests; no DELETE, no external provider. Fictional body/schema values are fixtures. Exact cleanup of owned server/journal asserted by existing fixture after each use. Types --noEmit including negative activation/type checks0; scoped ESLint --max-warnings=0, generated API types --check and operation routes --check0,84operations=70+14 unchanged. Source diff check/reverse applicability0only; no rollback applied.

Commands: node --test --test-concurrency=1 with TAP/stdout and JUnit; new36 in tests/neon-cleanup-contracts.test.mjs plus the13related files recorded in COMMANDS.json. Node24.18.0, Windows PowerShell, Python3.14.6 for metadata only. No new app build, business DB connection/schema/migration or necessary DB suite applies to this pure contract/owned-HTTP slice; DBskip0. No new Chromium/staff screenshot because no UI changed. Prior actual builtSDK/browser/crypto evidence is carried, not rerun or relabeled live.

## Preserved gates / next eligible

N00/NA01/Task2 OPEN. Historical full30-file suite229pass5fail0skip remainsRED/carried (missing main Vercel output and admin/MVP Docker timeout/parent); no full-root rerun here. Original strict302 failure500/200, real Neon/human Google, full SDK/native/built/browser/arbitraryCLI transport accounting, provider authentication/exact absence/permanent identity cleanup and independent review remainopen. Auth0/canonicalusers/memberships/actors/RLS/HMAC/delivery403 unchanged. No accounts, membership/link/grant, email, paid provider, production DB, Cloudflare or deployment action. No forged owner/reviewer approval and no agents.

Next local N00 work is authoritative Managed Better Auth identity-cleanup/absence discovery and actual transport preparation; full original compatibility gate precedes N01/N02. A fresh exact-target/human-account/execution approval is still absent; expired preview authority is not reused. This adapter does not enable external activation.

Separately completed Q13 current-auth sourcefa198ae533be3dc93eda73bc45331c2d80eb9540/evidence55f81338e5d12948279b6f095787aa03e6038242 remains on codex/q13-workspace-discovery. Its109strict/91migration/69reportedNode and fixed5SQL evidence is a separate branch, not merged here. Here sourcehead0037; peer proposed0038. Reconcile one migration owner/current solehead before N01—never reuse0038 from a baseline plan. N02/fullQ13/true accuracy/load/human/live gates remain separate.

## Rollback and preservation

Revert following metadata then source370a558; pure tooling only, no DB/resource undo. Prior2665evidencefiles/31inputs/other24taskobjects/97othercases/all98historical15fields preserved, original destructive fixtures and old boundary/orchestrator unchanged. Root/dirtyNeon/Q13worktrees verified untouched. [Preservation](PRESERVATION.json). Review is author-only, independent security review pending. No eight-module live acceptance claim.
