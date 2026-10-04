# N00 / PR-05 / F20 / NA01 — partial local compatibility spike

Source `2f14645f34ba61ea032c1e826debff1c1defcec6`; base `27f1412369edb6ea8581aa15d3d2a7a0e84882d3`; isolated `codex/neon-auth-compatibility-local-20261004`. Two source commits b2e4d38/2f14645. **Full N00 gate not passed; real Neon NA01 not tested. No push/PR/deploy/cutover.**

## Implemented and reviewed

Pinned SDK0.5.0-beta as dev dependency; guarded loopback/source/readonly cache/owned-container build harness; official same-origin handler/server session/browser client in fixture overlays; public Vinext→Nitro fetch adapter in staged config only; sanitized runner + actual API readiness; separate FastAPI Ed25519/JWKS diagnostic; credential-free storage + isolated test discovery. Production Auth0/canonical IDs/memberships/RLS/owner/approval/audit/job actor/Cloudflare HMAC/delivery unchanged. No DB migration; sole0037 head.

## Exact final results

| Verification | Pass | Fail | Error | Skip | Output |
|---|---:|---:|---:|---:|---|
| Node guards/discovery/generated/Auth0 render/services |32|0|0|0|exit0;9502.4319ms |
| Strict pytest test_api_auth.py test_auth_tenant.py |34|0|0|0|exit0;5.68s;4deprecation warnings |
| Actual portable workerd output, whole3cases |2|1|0|0|exit1;25.9s |
| Actual Nitro/Vercel output+static bridge, whole3cases |2|1|0|0|exit1;23.8s |
| pnpm exec tsc --noEmit / focused eslint --max-warnings=0 |—|—|—|—|both exit0 |
| Clean pnpm build / node scripts/run-vercel.mjs build |—|—|—|—|both exit0 |

Both actual outputs pass login→Secure/HttpOnly/Lax host cookie + signed cache→client session→hard reload/server session→token→FastAPI EdDSA→no credential persistence→logout→reload/anonymous + cleared cookies. Six negative401 checks (missing bearer/issuer/audience/expiry/kid/algorithm) are one test case per target. Locale-only canonical existing prefs allowed; tokens/session/unknown keys/duplicate JSON refused by meaningful Node tests. Screenshots include unchanged portable fictional demo shell, not live staff workspace UAT.

**Callback fixture gate remains FAIL:** direct upstream302/HttpOnly cookie asserted; proxy returns Vercel200HTML or portable500, expected302. Assertions after the first failing callback status are unexecuted, not pass. Pinned SDK fetch follows redirects (server-b0OzGjXl.mjs1129 lacks redirect:manual); default Nitro SSR dispatch was a separate issue resolved for login/session/token by the public adapter. Portable subsequent500 root cause unproven. This synthetic302 transport is not real Neon OAuth/session-verifier protocol: do not infer a production SDK defect or actual callback semantics. No test converted to expected-failure/skip.

No required DB suite exists for this protocol-only change; no DB suite skipped, no shared/production/Neon DSN. Diagnostic is not production trust/identity/RLS. Real issuer/audience/JWKS/methods NULL/not observed. Real account/email/CSRF/state/refresh/key rotation/Safari/Firefox/Vercel ingress/bindings/protection/production/staff UAT/performance unverified. [Contract/ADR](../../../decisions/2026-10-03-neon-auth-contract.md) compares official same-origin+public adapter/custom proxy/supported-runtime gateway. No private/global-fetch patch/framework replacement. Reconcile callback contract before adoption; real isolated auth target/account needs concrete approval, expired approvals not reused.

## Conditions / provenance

LinuxNode22.23.2 image sha256:48e4b67d85f87bd551df43704e24d252f56cc5f8e9718841aace50f19948f0f9;4CPU/6GiB; pnpm11.25.0 frozen install37.3s; hostNode24.18.0/Python3.14.6/Playwright1.63 Chromium1120×800. Readonly seed052d6a686de9, own containerc30c54a5351c482cf7ebbf9b removed; clean outputs between targets;360s copy/300s install/300s each build bounds. No live SLA.

build-inputs records baseb2e4d38 + original/transformed hashes; all7compiled overlay files match final source. Three later harness/runner/discovery changes are not build dependencies; exact final runner/test hashes preserved. Genuine final output tarballs, screenshots, traces, JUnit and source patch retained. Local Vercel bridge is not actual platform verification. Public app catch-all/internal api binding unchanged; no new public service.

## Failures preserved / report integrity

See attempts-index for raw logs/XML/traces with short-name/source mappings. Retain missing exports, inventory exclusion, default SSR/staticHTML, wrong baseline filenames/0tests, npm timeout, Docker unavailable, cache180s failure, failed dead-container image snapshot, portable startup0tests, API readiness/pointer intercept, lint, concurrent type scan, LF/CRLF comparison false negatives, storage/discovery RED→GREEN and Windows long trace copy failure. No earlier producer record rewritten.

`--list` with default JUnit overwrote portable report with3listed/skipped/unexecuted cases. Preserved as portable-discovery-only.xml, excluded from executed counts; fresh whole portable suite restores3actual cases/0skip. Future listing uses --reporter=json/list. Freeze asserts nonzero case count and exact pass/fail/skip. Prior large archives stay ignored with SHA/path recorded; final two outputs included.

## Preservation / rollback / review

31frozen input hashes/4destructive guards exact; original plan,84operations (70original+14extensions), other worktrees preserved. Root671fed7clean/auditparent27f1412clean; unrelated Neona78859fe remains193dirtypaths/diffSHA32ad7260ed5da5c8f2b20dd2ff1a8b526548daf35e8e71efc4bd90c70863b2b0. No paid/provider/mail/account/member/schema/production action.

Reverse source.patch --check exit0; runtime/production rollback not rehearsed. Revert2f14645 thenb2e4d38 plus checkpoint metadata; no DB/data/role undo. Auth0 stays. Author review only; independent pending per no-agents. Full N00/NA01 incomplete; keep plan workspace open. Next uncompleted N00 callback contract + real roundtrip, then dependent N tasks. Q13 waitsN02; Q16/Q17 root evidence blocked. No eight-module/live acceptance claim.

Exact commands and review boundary are in the local PR description and COMMANDS.md.
