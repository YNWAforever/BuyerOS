# PR-05 / N00 / F20 — local compatibility spike (gate open)

Branch codex/neon-auth-compatibility-local-20261004; source range27f1412369edb6ea8581aa15d3d2a7a0e84882d3..2f14645f34ba61ea032c1e826debff1c1defcec6; commitsb2e4d38/2f14645 plus separate metadata checkpoint. No remote PR/push.16source files in second commit; SDK/lock/guards/plan in first.

## Changes

Exact SDKdev pin; official same-origin server/client fixture overlay, public Nitro/Vinext fetch wiring in disposable source only, owned clean Docker builds, env isolation/readiness, local Ed25519/JWKS FastAPI diagnostic, actual builtUI cases, strict credential-free locale storage, discovery separation. No production handler/auth trust/identity/role/schema/provider/Cloudflare change.

## Evidence and unresolved gate

32Node/34API pass0skip,types/lint/generation pass; both clean builds0. Each actual portable/Vercel3cases2pass1fail0skip. Login→session→reload→token→signature→logout passes; synthetic302callback gets500/200. This is not real Neon OAuth/session-verifier evidence or proven productionSDK defect. No expected-failure/skip. FullN00/NA01 open; real isolated auth/independentreview and later N prerequisites unverified. No deploymentSHA. Do not merge auth cutover based on fixtures.

[Exact results/commands/trace/screenshots](../../evidence/audit-fixes-20261003/N00_LOCAL/RESULTS.md), [ADR](../../decisions/2026-10-03-neon-auth-contract.md). Original31inputs/98historicfields/97othercases/24tasks/84operations/4guards/otherworktrees preserved. Revert2f14645 thenb2e4d38 and checkpoint metadata; reversepatch applicability0, no DB undo/production rehearsal.

Next: reconcile supported actual callback contract, then request a concrete isolated target/account rehearsal; no production provisioning/deployment/identity linking/email implied. Same-author review only; no agents spawned.
