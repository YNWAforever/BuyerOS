# BuyerOS release and conversation handoff

Recorded 8 November 2026 (Asia/Singapore). This is a historical handoff, not a fresh release receipt. Recheck remote state before further deployment.

## Current release

- Application and release fixes are already merged through [PR #55](https://github.com/YNWAforever/BuyerOS/pull/55). Guided sales and reviewed Xverum integration landed in [PR #44](https://github.com/YNWAforever/BuyerOS/pull/44); auth repairs in #45/#46; release controls and tooling in #47–#54.
- Reviewed source: `e651fee8a7bd3c1eda61f3c8e1535108cabe6bd7`. All 15 jobs passed in [main CI 42454712232](https://github.com/YNWAforever/BuyerOS/actions/runs/42454712232).
- Production `buyer-os-nu.vercel.app` was read back pointing to `dpl_EpqYALMjYWBwkd2K93srD2qadgUV`, immutable host `buyer-ijom82knt-ynwaforevers-projects.vercel.app`, at that source.
- The user supplied a handoff from **Conversation studio layout not live** documenting a direct Vercel promotion of this deployment. That action occurred in another chat, outside the guarded GitHub promotion workflow. Do not describe it as a completed signed release.
- `autoAssignCustomDomains=false` is intentional release isolation, not a defect to repair. Its value remained false on readback.

## Verification and limits

| Evidence | Observed result | Boundary |
| --- | --- | --- |
| Exact-source schema preflight | 253 compatible checks | Does not replace post-promotion runtime acceptance |
| [Stage 42460395064](https://github.com/YNWAforever/BuyerOS/actions/runs/42460395064) | Stage/probe passed for `dpl_Epq…`; seven API account controls passed | Signing was not completed; run canceled after evidence expired |
| Authenticated QA browser check at 16:22 SGT | Candidate and then-current rollback: login, scoped workspace/project, secure cookies, reload, cross-tab UI logout; candidate displayed 17 skills, Documents, discussion navigation | Dedicated QA scope; no provider execution; UI logout is not proof of global server-session revocation |
| Deterministic first-project QA at 16:28 SGT | Discussion/task creation returned 201; one preparation returned 200; completed task, saved revision 1, Documents listing, reopening and reload verified | Empty-source synthetic task only; original creation-navigation check failed, then existing records were resumed. Buyer/research/draft native linkage, project-editor navigation and paid MCP execution were not tested |
| [Stage 42463204691](https://github.com/YNWAforever/BuyerOS/actions/runs/42463204691) | Stage/probe passed for `dpl_FEBESMRVBBD59XQzri5aiC9AKZf6`, same source | Later browser check had six 60-second read timeouts; canonical alias changed during verification. Run canceled, no acceptance receipt installed |
| Follow-up API-only saved-output readback | Rejected changed canonical deployment before authentication or application reads | No write replay; no successful post-promotion readback claim |

The output browser helper published its success report before closing the context. Its recorded workflow assertions passed, but that report alone does not establish a clean request drain. The separate session helper was corrected to drain pending requests and passed with zero failures before promotion. Keep these evidence scopes separate.

Raw local evidence and private QA helpers remain untracked in the originating checkout. This PR intentionally contains no account credentials, tokens, database URLs, raw runtime payloads or private QA record identifiers. Reuse existing QA records only after private reconciliation; do not recreate them to recover an uncertain write.

## Why users may still see the old interface

`features/live/sales-skills/capability.ts` maps every capability-fetch failure to `enabled:false`. `features/live/workspace-picker.tsx` combines that result with the conversation feature flag to select the shell. Thus a timeout can present the legacy shell instead of a distinct loading/error state. This mechanism is source-verified; the affected business user's exact failing request was not captured.

Do not revive the unproven claim that Vinext failed to inline the public flag. Vinext handles `NEXT_PUBLIC_*`, and authenticated QA displayed the enabled interface on this deployment. Anonymous HTML 200 responses and route 401 responses establish neither an authenticated UI nor working workflows.

## Read-timeout investigation

- The newer candidate check recorded six genuine 60-second GET timeouts for capability, usage and native sources during request draining. They were not classified as browser-shutdown cancellations.
- Database snapshots showed advisory-lock waiters and open transactions, then cleared. A later exact QA policy-lock lookup returned zero matches. Global counts do not identify the QA workload or establish the root cause.
- `SelectedSources` depends on an unstable translation function; rerenders can repeat parallel reads. Cleanup ignores stale results without aborting those reads. Capability refreshes on mount, focus and location events without deduplication.
- Sales read access takes policy and budget transaction locks before membership/rate checks. Native-source enumeration performs per-source validation while retaining locks. These are investigation leads, not authorization to remove policy/budget gates.
- Candidate and rollback browser workloads differed. Their timeout counts are not an equal-load performance comparison. Browser interception via `route.fetch` also complicates cancellation and latency attribution.

Next verification should capture the affected user's actual capability status, distinguish disabled/loading/error states, and correlate bounded request timing with exact workspace lock holders. Preserve tenant, membership, revocation and paid-admission checks in any repair.

## Remaining product work

The delivered surface is guided task cards/forms with persisted tasks and versioned outputs. It does **not** fulfill the complete requested Ads-Copilot-style continuous conversation experience.

Continue from the existing conversation design and guided-sales plan, preserving canonical buyer, research and draft workflows:

1. Make the persistent conversation and composer the primary working surface, with templates starting guided interviews in that thread.
2. Continue across turns with durable messages, selected sources, visible action proposals, inline tool results and citations.
3. Route allowed BuyerOS actions and approved MCP connections through existing authorization, budget, review and idempotency controls; never interpret chat text as permission to expand tool access.
4. Save/reopen canonical linked outputs and expose recovery for interrupted or uncertain work.
5. Verify the actual authenticated business workspace, responsive layout, reload continuity and each approved integration separately. Existing first-project QA is not full workflow or Xverum acceptance.

Reference documents: [conversation design](../superpowers/specs/2026-10-26-conversation-home-design.md), [guided-sales design](../superpowers/specs/2026-11-05-guided-sales-skills-xverum-design.md), [implementation plan](../superpowers/plans/2026-11-05-guided-sales-skills-xverum.md), [protected release procedure](protected-workspace-release.md).

## Continuation boundary

Both staging runs above are canceled and their receipts are stale. No waiting approval from this chat should be reused. Reconcile the current production target and reviewed rollback before the next release. Preserve the approved solo-owner manual signoff, all required CI checks and the protected promotion workflow. Do not fabricate fresh timestamps or treat this handoff as a runtime acceptance receipt.

Paid research/enrichment, delivery and worker activation remain separate from interface deployment. This handoff does not activate them. The next chat owns continuation; this PR neither deploys nor rolls production back.

## Continuation update — 12 November 2026

This handoff was picked up. The sections above remain the historical record of
8 November; this addendum only records what changed since, and is still not a
runtime acceptance receipt.

### Release state

- [PR #57](https://github.com/YNWAforever/BuyerOS/pull/57) (conversation studio
  and capability-state fix) merged 11 November.
- [PR #70](https://github.com/YNWAforever/BuyerOS/pull/70) (per-turn metrics and
  budget dashboard) and [PR #71](https://github.com/YNWAforever/BuyerOS/pull/71)
  (recorded provider-acceptance harness) merged 12 November. Main is
  `61a6483f1e967361cee96c0cbf8f18b74b975631`; [CI 43176420452](https://github.com/YNWAforever/BuyerOS/actions/runs/43176420452)
  passed all 15 required jobs.
- No candidate has been staged and nothing has been promoted from this chat. The
  protected staging/signoff path, authenticated QA environment and explicit owner
  approval are still required before any promotion.

### "Why users may still see the old interface" — client cause addressed

The source-verified mechanism described above is fixed on current main:

- `features/live/sales-skills/capability.ts` now exposes explicit
  `idle/loading/enabled/disabled/unavailable` states. Only a **server-answered**
  `disabled` may select the legacy shell; read failures render `unavailable`
  (with bounded retry guidance) or `checking`, never a false legacy fallback.
  Reads are single-flight per session identity, abort on scope change, coalesce
  focus/location refreshes and bound automatic retries.
- `features/live/workspace-picker.tsx` routes the decision through
  `salesCapabilityShell(...)`, so the picker and its panels share one state
  machine.
- This is source verification only; the original business user's failing request
  was never captured and is not claimed as reproduced or accepted.

### Read-timeout leads — client re-issue fixed, server causes still open

- `features/live/sales-skills/sources.tsx` now owns one read set per session
  identity (`useEffect` keyed on `[client,session,identity]`) with a local
  `AbortController`, a single shared abort signal for the parallel context,
  project, outputs and native-source reads, and abort-aware result handling.
  An unstable translation function or parent rerender can no longer re-issue the
  burst; `tests/core-sources-dedup.test.mjs` guards this.
- The server-side leads from 8 November (policy/budget locks taken before
  membership/rate checks, per-source native validation while holding locks) are
  **not** claimed fixed here. In any performance work, preserve tenant,
  membership, revocation and paid-admission checks.

### Remaining work

- Owner-gated: refresh the protected contract items for the current source,
  verify the recorded rollback deployment, stage a candidate, create
  `buyeros-conversation-qa` with the dedicated Neon account, run the
  authenticated QA workflow, then approve the protected signoff/promotion.
- Phase 1 remains open: reviewed live-model admission
  (`CONVERSATION_MODEL_UNAVAILABLE` is still the honest result), Xverum
  connection/OAuth/paid-admission/worker-runtime provisioning, and the Drive
  retention decision. Current turns are deterministic with explicit proposals;
  no paid activation has occurred.
