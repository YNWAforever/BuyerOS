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


## Counted fixture transport source261a9e5 (2026-10-04)

8files287insertions/12deletions. Persistent governor fronts a newly owned loopback backend; bounded requests/manual redirects/no automatic retry/unknown-write freeze/concurrent barrier plus exact-nonce stop and actual OS child absence proof. No real provider hostname accepted.80relatedNodepass0skip;types/lint/contracts0; each actual built7cases6pass1fail0error0skip;2newcountedSDKcasespass each. Unchanged strict302teststillfails500/200; fullN00/NA01 **open**. Each44HTTPrequests/0pending/0unknown, allownedjournalscleaned. Reused89/2214emittedfiles and9overlayhashes verified; no new build. [Exact evidence](../../evidence/audit-fixes-20261003/N00_COUNTED_TRANSPORT/RESULTS.md). SourceSHA `261a9e51d9d038c68be1d0d67002fcbe6e1eff6c`; deployednull. Reversecheck0only; revert this source plus metadata, no DB/resource undo. Authorreviewonly/independentpending; no remotePR/push. Real-onlyconfig/accounting and specifically approved real emptyAuth/humanGoogleidentity remain pending.


## Runtime preparation source790a1b2 (2026-10-04)

12files253insertions/47deletions; shared target kernel/request-lazy exact-context runtime/strict SDK type boundary/separate server-only overlay.30newunit RED→GREEN, compiler any-return RED→GREEN; final110relatedNodepass0skip/types/lint/contracts0. Measured native cleanup correction validated both outputs; wholeUIeach6pass1originalcallbackfail0skip0globalerror, prior two globalcleanup failures retained. New real-only SDK overlay not built/run; constructor tests are instrumented fixtures. No auth or public domain route cutover. [Exact evidence](../../evidence/audit-fixes-20261003/N00_REAL_RUNTIME/RESULTS.md). Source `790a1b29b971ce6e23221ac38cd5de4a61c50144` /base535e12 /deployednull; reverse applicability0only, revert source plus metadata. Authorreviewonly/independentpending; fullN00/NA01 **open**; no remotePR/push. Nextcomplete real-harness runtime-only builds/UI/diagnostic/accounting, then specifically approved fresh isolated real target/test identity.


## 2026-10-05 N00 built runtime kernel checkpoint (e683a89)

Reviewed source `e683a89225863387367bda204f84aa168f6abefb`;16files305insertions/8deletions; local only, deployednull. OfficialSDK0.5.0-beta constructor/exact runtime env/trust/node:crypto execute on both actual emitted outputs. Final each6cases6pass0fail0skip0globalerror;126relatedNodepass0skip/types0/lint0/contracts0. Six actual clean build commands0 across3preserved profiles; missing dispatcher fixed in source. Two Vercel startup0-test errors and two portable cleanup globalerrors retained; marker-preserving async secret-first cleanup passes (actualEBUSY retry);14roots removed.222byte-exact captures/943priorpayloads preserved; final8overlayhashes/74portable2197Vercelregular members and old89/2214regular members match.84operations/4guards/24other tasks/97cases/all98historicalfields unchanged.0037singlehead/0migrations/noDBsuite or DBskip.

Configuration/constructor kernel is fixture verified; session/token/handler/middleware, true Neon/Google, full SDK/browser/CLI accounting and independent review remain unverified. Original strict callback302failure500/200 carried, not rerun/relaxed. No production/Auth0/identity/membership/email/paid/Cloudflare/push/PR/deployment change. N00/NA01/Task2 **OPEN**. [Commands/results/screenshots/rollback](../../evidence/audit-fixes-20261003/N00_RUNTIME_BUILT/RESULTS.md). Reverse applicability0only; revert source plus metadata, no DB/resource undo. NexteligibleN00real-only UI/session/token/API diagnostic/accounting; new isolated Auth/human Google approval remains pending. N01/N02/Q13/Q16/Q17 gates unchanged.


## 2026-10-05 N00 built session/token checkpoint (c756596)

Reviewed source c756596406f41884f61a3b64c8549f569e34cfa4;27files518insertions/1deletion. Official pinned SDK login/session/token/handler/managed callback/logout and independent owned EdDSA FastAPI execute on both actual built outputs with fictional target/transport:each5pass0fail0skip0globalerror.144serialNode/8crypto pass;types/lint/contracts0;fourcleanbuildcommands0. Receipt binds server session subject/fingerprint;bearer stays in memory. Both30fixtureAuthHTTP/0pending0unknown;owned roots/journals/children removed. Body timeout,two0-test startups,parallel40ms regression and initial type/lint failures retained;original status/body/deadline assertions unchanged. No DB/migration/external action. True Neon/Google/full SDK-browser-CLI accounting/external cleanup/independent review and original strict302 gate remain open;N00/NA01/Task2 OPEN. Evidence: docs/buyeros/evidence/audit-fixes-20261003/N00_RUNTIME_FLOW/RESULTS.md. Reverse applicability0only;revert source plus following metadata;no DB/resource undo. NexteligibleN00accounting/cleanup preparation;fresh real-target/account approval pending;Auth0 retained/deployednull.

## 2026-10-05 N00 local execution-boundary checkpoint (b8a1084)

Reviewed source b8a10848b62090ff19544918961e54df3ebfa921;10files277insertions/0deletions. Owned loopback gateway durably counts SDK/browser/fixed Node fixture CLI/control HTTP; cross-channel write holds/manual redirects/limits/TTL; exact-resource cleanup model uses fresh matching readback and confirmed absence. Real provider/CLI/human Google containment and external cleanup API adapters remain unimplemented/unverified. Final related165pass0fail0skip(new21included),Chromium3pass0skip0globalerror/3ownedcleanup receipts,crypto8pass1existingwarning;types/lint/contracts0;0037singlehead/no migrations/DBconnections/skips. Attempted full30-fileNode234tests229pass5fail0skip: two missing mainVerceloutput gates,admin/mvp Docker30stimeouts and parent failure; unchanged tests/no weakened assertions. Full suite RED disclosed. Prior c756596 actual builtUI historicalcarried,not rerun.1401priorN00payloads+31inputs/84operations(70+14)/guards/24other tasks/97other cases/all98historicfields/legacyT registry/unrelated worktrees preserved. Reverse applicability0only;revert following metadata then source;no DB/resource undo. Evidence: docs/buyeros/evidence/audit-fixes-20261003/N00_EXECUTION_BOUNDARY/RESULTS.md. N00/NA01/Task2 OPEN;original302/realNeon/humanGoogle/fresh approval/independent review gates open. Auth0 retained/deployednull;no agents/external mutation/push/deploy. Nexteligible N00 transport coverage/provider cleanup adapters.
