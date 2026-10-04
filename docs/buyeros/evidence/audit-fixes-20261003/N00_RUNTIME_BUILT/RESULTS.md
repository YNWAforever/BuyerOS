# N00 / F20 / NA01 — actual built runtime kernel (full gate OPEN)

Reviewed source `e683a89225863387367bda204f84aa168f6abefb`; base `1df7b4cb1b46a25b9019adf05bd4cd46cf2a7fa3`. Branch `codex/neon-auth-compatibility-local-20261004`. Local source commit:16 files,305 insertions/8 deletions. Deployed SHA null. Author review only; independent review pending; no agents.

## Implemented and scope

A separate fixed build profile overlays the pinned official SDK0.5.0-beta wrapper and a small runtime kernel UI/API into disposable source. The public BuyerOS application/auth routes, Auth0, canonical IDs/memberships/RLS/actors, Cloudflare HMAC and delivery403 are unchanged. Runtime-only fictional metadata and a fresh32-byte cookie secret are injected after clean builds. The probe requires fixture mode and fictional IDs/hosts/audience; it constructs the actual official SDK with the strict request-time wrapper, returns the exact trust/fingerprint descriptor, and exercises a denied global fetch. It does **not** invoke SDK session/token/handler/middleware or real Neon/Google.

Both emitted outputs actually execute the shared node:crypto configuration kernel. This closes the previously unbuilt constructor/configuration gap only. The underlying real-only handler/middleware overlay is compiled but its flows remain unexercised by these kernel cases. Global fetch evidence applies to this probe/Node bridge; full SDK/browser/CLI provider accounting is still open. The diagnostic API34 result is historical, not rerun here. No new domain operation or migration owner.

## Observed RED and repairs

10 guard/profile tests first execute1pass9fail0skip. Three named browser/HTTP cases on the retained old built Vercel fixture execute0pass3fail0skip. No zero-test run is called a RED feature pass. Six meaningful cleanup guards execute0pass6fail0skip before implementation, then6pass.

All three fresh build pairs succeed (six commands, each <=300s), but the first two Vercel kernel startups fail: Nitro's SSR adapter tries a non-callable default export. Restoring a bare re-export alone does not resolve it. The missing fixture `server.ts` dispatcher is then identified from the working older fixture and added; no emitted output or SDK package is patched. All three source/build snapshots are retained; the final8 overlay hashes match current source. Each archive's74portable/2197Vercel regular members matches the extracted output.

Two earlier workerd runs pass their3cases but each has1global cleanup error/exit1; they are **not** accepted clean runs. The second captures native `EPERM` during owned-root removal. The exact later rmSync repeat succeeds, and a later read-only Restart Manager snapshot shows0lock holders; this does not prove a persistent lock owner or underlying OS cause. Final cleanup uses async removal, retains its marker while state is removed, deletes private configuration first and retries only specified transient errors within10s. Native child kill15s, child stop18s, teardown35s. Actual final portable cleanup captures one `EBUSY` retry and succeeds. Six unit regressions cover partial removal/marker, foreign owner, unexpected entry, timeout, IO error and root junction. All fourteen recorded fixture roots are removed; final acceptance children are OS-absent at cleanup, and ports44890/44891/44892/44894/44900/44901 are clear.

The first final bookkeeping scan flags a recycled child PID11188, now a newer codebase-memory-mcp process; no unowned process is stopped. Start-time-aware readback resolves the check. The shell originally proceeded to the source commit after that bookkeeping error; all source tests and eight acceptance reports had already been verified. The raw failed bookkeeping record is retained. New checks stop on a failed script exit.

## Fresh verification

| Gate | Pass | Fail | Skip | Details |
|---|---:|---:|---:|---|
| Final related Node |126|0|0|exit0;12046.3406ms;10 kernel +6 cleanup new cases|
| Portable built kernel |6|0|0|3valid + missing/mismatch/expired; all CLI exits0/global errors0|
| Nitro/Vercel built kernel |6|0|0|same six cases; actual emitted handler via local bridge|
| Strict tsc / authored lint / generated contract |—|—|—|each exit0;zero lint warnings|
| Actual clean builds |—|—|—|all6commands exit0; final dispatcher profile used for acceptance|
| Alembic heads, no DB env |—|—|—|exit0;single0037_bulk_manifests;0migrations/DB connections|
| Required DB suites |—|—|—|not applicable to this configuration/constructor-only slice;0DB skips|

Final cases assert exact owner-bound fictional IDs/issuer/audience/JWKS/EdDSA/OKP/Ed25519 and sanitized actual response attachments. Missing/mismatch/expiry each yields503 with the exact code. Runtime values and the cookie secret are absent from emitted text:70portable/2368Vercel text files scanned per run,0matches. The secret is not retained in evidence; only its hash is. Explicit egress test reports blocked1/forwarded0; external auth requests0.

[Portable screenshot](captures/0050-runtime-kernel.png), [Vercel screenshot](captures/0193-runtime-kernel.png). These are kernel fixtures, not logged-in staff UAT. [Exact commands](COMMANDS.md), [structured results](SUMMARY.json), [raw capture map](CAPTURE_MAP.json), [source hashes](SOURCE_HASHES.json), [rollback](rollback.json), [author review](AUTHOR_REVIEW.md).222 byte-exact producer captures include earlier built profiles/startups, red logs, traces, successful/rejected HTTP bodies, private-root recovery and archive verification. The initial archive verifier hits the Windows266-character path limitation (observed error recorded in ARCHIVE_VERIFICATION_ATTEMPTS.json); extended-path verification then checks every member without ignoring any file.

## Environment and performance conditions

Windows PowerShell/Node24.18.0, Playwright1.63.0/Chromium, Wrangler4.137.0. Builders are owned Docker Node22.23.2-bookworm-slim,4CPUs/6GiB, read-only seedbuyeros-audit-ui-deps-052d6a686de9, frozen pnpm11.25.0/SDK0.5.0-beta and no auth runtime env. Build base is1df7b4 plus recorded pending-file snapshots; SOURCE_HASHES ties final tested bytes to the reviewed commit. No external hosted/real-auth build allowance is consumed. Windows filesystem cache/startup dominates initial Vercel command58.192747s; per-scenario command durations are in SUMMARY. These are functional test conditions, not provider or product latency/SLA measurements.

The pinned workerd configuration uses nodejs_compat/date2026-09-21. Runtime environment behavior is checked by actual responses, with the [Cloudflare process.env contract](https://developers.cloudflare.com/workers/runtime-apis/nodejs/process/) as the platform reference. Cleanup uses the documented [Node filesystem removal API](https://nodejs.org/api/fs.html#fspromisesrmpath-options); no provider operations or documentation bodies are republished.

## Preservation, rollback and next eligible

943prior manifest payloads are unchanged (31inputs +150/66/23/421/252 earlierN00). Older89portable/2214Vercel files match their archives; prior source/evidence and strict callback assertions remain unchanged. The original callback302 expectation still has historical500/200 failures and was not rerun/relaxed by this slice. Original98case fields/97other rows/24other tasks/84operations(70+14)/four destructive DB guards/generated contract/master plan are preserved. Root/audit-parent checkout and historical193dirty paths are checked separately. No production/provider/account/email/paid/identity/link/membership/push/PR/Cloudflare/deployment action.

Reverse-patch applicability exit0, not applied. Rollback: revert source `e683a89225863387367bda204f84aa168f6abefb` and its separate metadata checkpoint; no DB/resource undo or production rehearsal. F20/NA01/N00/Task2 remains local-partial, real-Neon-unverified. N00 is still first eligible. Next local work: real-only UI/session/token/FastAPI diagnostic and complete bounded SDK/browser/CLI/cleanup accounting. Real target/issuer/audience/JWKS and one human Google identity remain absent and require the exact pending new-isolated-target proposal, not old/expired approvals. N01/N02/Q13 and Q16/Q17 gates remain unchanged. No eight-module live acceptance claim.
