# PR-05 / N00 / F20 — local compatibility spike (gate open)

Branch codex/neon-auth-compatibility-local-20261004; source range27f1412369edb6ea8581aa15d3d2a7a0e84882d3..2f14645f34ba61ea032c1e826debff1c1defcec6; commitsb2e4d38/2f14645 plus separate metadata checkpoint. No remote PR/push.16source files in second commit; SDK/lock/guards/plan in first.

## Changes

Exact SDKdev pin; official same-origin server/client fixture overlay, public Nitro/Vinext fetch wiring in disposable source only, owned clean Docker builds, env isolation/readiness, local Ed25519/JWKS FastAPI diagnostic, actual builtUI cases, strict credential-free locale storage, discovery separation. No production handler/auth trust/identity/role/schema/provider/Cloudflare change.

## Evidence and unresolved gate

32Node/34API pass0skip,types/lint/generation pass; both clean builds0. Each actual portable/Vercel3cases2pass1fail0skip. Login→session→reload→token→signature→logout passes; synthetic302callback gets500/200. This is not real Neon OAuth/session-verifier evidence or proven productionSDK defect. No expected-failure/skip. FullN00/NA01 open; real isolated auth/independentreview and later N prerequisites unverified. No deploymentSHA. Do not merge auth cutover based on fixtures.

[Exact results/commands/trace/screenshots](../../evidence/audit-fixes-20261003/N00_LOCAL/RESULTS.md), [ADR](../../decisions/2026-10-03-neon-auth-contract.md). Original31inputs/98historicfields/97othercases/24tasks/84operations/4guards/otherworktrees preserved. Revert2f14645 thenb2e4d38 and checkpoint metadata; reversepatch applicability0, no DB undo/production rehearsal.

Next: reconcile supported actual callback contract, then request a concrete isolated target/account rehearsal; no production provisioning/deployment/identity linking/email implied. Same-author review only; no agents spawned.


## Callback follow-up source2fd84ef (2026-10-04)

Six files/111insertions/3deletions: fictional managed protocol upstream, official proxy.ts middleware/dynamic return overlay, two added built cases, discovery5, ADR. Actual new2cases pass both outputs; whole5each4pass1fail0skip; fullN00/NA01stillopen.32Node/types/lint/builds pass; API34carried previous source, not current rerun. No original case relaxed. [Exact evidence](../../evidence/audit-fixes-20261003/N00_CALLBACK/RESULTS.md). Reviewed SHA `2fd84ef49d289ea313a5abb21ec6e30bc2659a9d`; deployed null. Revert2fd84ef and metadata for this follow-up; N00_LOCAL record untouched. Next specifically approved fresh real isolated auth/account/method; no production/cutover implied.


## Real-preflight local preparation sourceef0b437 (2026-10-04)

4files351insertions; inert metadata validator,36guard tests, NULL template and bounded-runbook usage. Fresh68relatedNode pass0fail0skip/types0/lint0; current0037heads0/noDB; actual Node process exit/restart keeps reservation. Includes200total/20cleanup reserve,2build reservations,2hourTTL, exact ID cleanup planning and runtime/build env helpers. **No HTTP/deletion executor, actual SDK/browser counting or real-only built config proof yet; no real target/approval/identity/secret created.** Previous built/UI/API evidence carried, not rerun; full gate remains open. [Exact evidence](../../evidence/audit-fixes-20261003/N00_REAL_PREFLIGHT/RESULTS.md). Reviewed sourceef0b4373fa6e4e6ca5db603d949062bec688f14b, deployed null. Revert this source and metadata checkpoint; reverse applicability0 only. No remote PR/push.
