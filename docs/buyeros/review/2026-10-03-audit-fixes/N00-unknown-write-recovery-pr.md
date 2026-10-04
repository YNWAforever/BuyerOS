# N00 / F20 / NA01 — retain unknown auth transport holds

Branch: codex/n00-unknown-write-recovery. Base: 58b3cff65625c5abe55a0f8ab316b604989d8063. Source: 2b69e7cf8c0b0c738bfc34b3de44b1877468a0ca. Local commits only; no remote PR/push/deployment.

## Change

Six source and test files: 112 insertions, 22 deletions. Refused post-dispatch redirect remains unknown; state/verifier GETs are one-use writes. Intent bound to state/verifier, excluding renewed bearer and incidental query. Receipt fsync before journal settlement. Restart holds state changes when any unresolved reservation exists, without trusting legacy/corrupt receipts. Owned fault proves SDK/handler/browser502 then409 without extra upstream commit; wrong owner returns 403.

## Verification

Final checks: 214 related Node tests, 8 EdDSA tests, 6 portable UI tests and 6 Vercel UI tests pass, with zero failures, errors or skips. Includes 13 new Node cases and one UI case per output. Types, lint and generated contracts for 84 operations exit 0. Genuine earlier outputs reused:14overlayhashes unchanged,95portable/2220Vercelregularmembers match. No new build, database connection, migration, provider call, account, email or paid action. Alembic head is 0037. All owned run resources cleaned.

The earlier 27-file root MJS attempt remains RED: 269 pass, 5 fail, 0 skip. Failures: offerDocker30stimeout+parent,2intentcasesobservedbeforelastfix(nowGREEN214),missingnormalmainVercelentry. InitialRED/setup/discovery/lint/portable0teststartup failure retained. No assertions/timeouts/guards relaxed. Not final-source full-project acceptance.

## Release / rollback

N00/NA01 remainOPEN:original strict302 unclosed;realNeon/Google/fullnativeSDK-browser-CLI accounting/Managedidentitycleanup/absence/canonicalmappingRLS/real ingress/independentreview pending. Auth0/framework/canonicalusers/roles/actors/HMAC/delivery403 unchanged;peerQ13 separate. Author review only per no-agents instruction.

Revert followingmetadata checkpoint then source2b69e7c; reverse applicability0only,not applied/rehearsed; no DB/data undo. Legacy unknown journals remain held until trusted reconciliation. [Exact logs, screenshots, commands, source patch](../../evidence/audit-fixes-20261003/N00_UNKNOWN_WRITE_RECOVERY/RESULTS.md).
