# N00 / F20 / NA01 — strict runtime preparation (full gate OPEN)

Reviewed source `790a1b29b971ce6e23221ac38cd5de4a61c50144`; base `535e12bc49588eadb4e4ce0c75f748489868e084`; isolated branch `codex/neon-auth-compatibility-local-20261004`. 12 source files,253 insertions/47 deletions. Local commit only; deployed SHA null. Author review only, independent review pending; no agents per user.

## Implemented

Shared target contract now lives in `scripts/neon-real-target.mjs` without filesystem/HTTP dependencies. Existing preflight/journal uses the same validation. The sanitized runtime environment carries the complete target manifest, while builds drop all N00/Neon configuration. Request-time configuration independently checks the exact manifest/fingerprint/base/issuer/audience/JWKS/EdDSA tuple, cookie secret format and two-hour expiry.

The lazy SDK boundary reads no environment and constructs no SDK on import/factory creation. Every request revalidates, caches only one exact target+secret context, refuses context replacement and expired cached use, and redacts constructor errors. Strict generic declaration preserves the pinned official SDK0.5.0-beta type; configuration/trust are immutable. Thin server-only handler and callback middleware preparation remains under a separate test overlay, outside BuyerOS public routes. This overlay has **not** been built or run. Unit constructors are instrumented fixtures, not live SDK/Neon verification.

Actual fixture runs exposed a Windows cleanup bound error. Native taskkill was cancelled at5s; null error code previously appeared as0. The sanitized-parent owned uv/workerd probe took8.5s. Bounded native15s/owned-stop18s/global20s and condition polling preserve exact OS ESRCH evidence. Failed command killed/signal fields remain observable. The first poll-only correction still failed and is retained. Final two runtimes prove owned children absent and journal removed. No test assertion was weakened.

## Fresh verification

| Gate | Pass | Fail | Skip | Exit / details |
|---|---:|---:|---:|---|
| New runtime unit RED | 0 | 30 | 0 | observed before implementation |
| New runtime unit GREEN | 30 | 0 | 0 | constructor boundary fixtures only |
| Related Node final | 110 | 0 | 0 | exit0;13491.6775ms |
| Strict SDK typing | — | — | — | RED TS2578/exit2 exposed any; final tsc exit0 |
| All authored-file lint | — | — | — | exit0;zero warnings |
| Generated domain contract check | — | — | — | exit0;84 existing operations unchanged |
| Portable built fixture final | 6 | 1 | 0 | exit1;55.428903999999996s;global errors0 |
| Nitro/Vercel built fixture final | 6 | 1 | 0 | exit1;19.568469s;global errors0 |
| NULL real-target guard | — | — | — | expected exit1/N00_REAL_TARGET_REQUIRED |
| Alembic heads, no DB environment | — | — | — | exit0;single0037_bulk_manifests;0migrations |

The sole strict UI failure remains original expected302 vs portable500/Vercel200. It is **not** declared an actual Neon defect, suppressed, skipped or converted to expected failure. Managed callback2 and counted SDK2 cases pass on each output. Initial two portable attempts additionally had1global teardown error each; JUnit reports errors0 and does not encode that global error, so CLI logs and SUMMARY explicitly preserve it. All four attempts are archived. A failed UI command is never counted as complete NA01.

Each final runtime reserved44 actual fixture auth requests, forwarded44, accepted41/rejected3, pending0/unknown0, external auth requests0. Two failed-attempt owned synthetic journals (44 settled requests each) were copied byte-for-byte and removed only after exact nonce/marker/temp containment/no-reparse/OS-PID checks. All four fixture ports are clear. Native tree timing probes used fresh owned loopback processes; no provider/resource/identity activity.

## Evidence and environment

[portable signed-in fixture screenshot](captures/0002-portable-signed-in.png); [portable managed-callback fixture screenshot](captures/0001-portable-managed-callback.png); [vercel signed-in fixture screenshot](captures/0004-vercel-signed-in.png); [vercel managed-callback fixture screenshot](captures/0003-vercel-managed-callback.png)

Raw commands/results/traces/screenshots, unit/compiler RED, failed cleanups, recovery data, budget proofs and diagnostic timing reports are mapped byte-for-byte in [CAPTURE_MAP](CAPTURE_MAP.json). [Exact commands](COMMANDS.md), [structured results](SUMMARY.json), [tested and committed source hashes](SOURCE_HASHES.json), [preservation](PRESERVATION.json), [rollback](rollback.json). The full producer logs retain original bytes and whitespace.

Windows PowerShell; Node24.18.0; Playwright/Chromium1.63.0; pinned @neondatabase/auth0.5.0-beta. Existing built outputs only: original build base2606ed5/compiled overlay2fd84ef,9overlay hashes and every89portable/2214Vercel emitted archive file match. No new build. Runtime proof reports Git HEAD535e12 during pending changes; SOURCE_HASHES ties their tested bytes to final source790a1b2. Existing built SDK fixtures do not exercise the new real-only overlay or its node:crypto/runtime-env behavior.

Official references: [SDK handler/cookie configuration](https://neon.com/docs/auth/quick-start/nextjs-api-only), [OAuth setup](https://neon.com/docs/auth/guides/setup-oauth). These inform the thin pinned-SDK interface; compatibility is assessed by separate tests. Public documentation readback is separate from auth-check budgeting; document bodies are not republished.

## Preservation / case status

31 original audit inputs plus150/66/23/421 prior N00 payloads =691 unchanged payloads. Other24 tasks,97 cases and all98 historical15-field case records preserved. 84 operations (70original+14existing extensions), generated contract, master plan, four destructive DB guards and old fictional overlay remain unchanged. Root/audit-parent worktrees clean; unrelated historical193paths retain binary diff SHA25632ad7260ed5da5c8f2b20dd2ff1a8b526548daf35e8e71efc4bd90c70863b2b0.

F20/NA01 is local-spike-partial, real-Neon-unverified. No DB-dependent implementation or required DB suite applies to this protocol/configuration-only slice; no required DB suite was skipped, no Neon DSN reached destructive fixtures. Existing API34 evidence is historical, not a fresh API rerun. Production Auth0/canonical IDs/memberships/roles/RLS/actors/HMAC/delivery contract remains; no production source activation occurred.

## Remaining gates / next eligible

N00 remains first eligible; Task2 is not marked complete. Exact real target/issuer/audience/JWKS are NULL, no approval record/identity/secret created. New overlay needs actual builds with runtime-only fixture configuration, complete real-harness UI/diagnostic, and SDK/browser/CLI traffic accounting/owned cleanup executor. Then specifically authorized fresh empty Auth target and human Google rehearsal can verify the real contract. The pending [bounded runbook](../../../runbooks/neon-auth-n00-real-roundtrip-20261004.md) retains US$0/free-only/200checks/20cleanup reserve/2hour scope. Continue does not authorize new resources/accounts.

N01/N02 depend on N00; Q13 depends on N02. Q09 human/staff metrics remain NULL, Q10 SQL/accuracy/performance gates remain open, Q16 lacks driver/SQLSTATE/pool/compute cause evidence and Q17 is not guessed. No live provider/platform/staff journey/deployment acceptance claimed.

## Rulings and rollback

1. Extract one pure target validator and prepare request-lazy strict SDK overlay. Cost: unit/typing evidence cannot close the actual built/real Google gate.
2. Adjust only measured fixture cleanup timing and retain OS absence proof. Cost: local teardown can take20s; unknown/unremoved outcomes continue to fail closed.

Source reverse patch applicability exit0, check only, not applied. For this slice revert its metadata checkpoint first, then `790a1b29b971ce6e23221ac38cd5de4a61c50144`; no database migration/data/resource rollback is required. [Exact binary source patch](source.patch.gz) preserves the raw tested diff. Existing Auth0 path remains the operational rollback baseline. Independent review and full N00 acceptance remain open.
