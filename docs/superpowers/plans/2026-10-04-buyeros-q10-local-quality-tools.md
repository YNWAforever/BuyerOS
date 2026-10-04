# BuyerOS Q10 independent local quality tools

Spec: 2026-10-03 implementation plan Q10/Global Constraints/Review Focus and frozen audit F12/P09/P10/A03-A08; continue after LOCAL_GATES. Base6232e4e1f4127833b93c1343207894c79b638852.

## Global Constraints
Existing isolated branch; no agents/push/remote PR/deploy/paid provider/mail/production DB or auth/Cloudflare cutover. Preserve identities, role/RLS/holds, original inputs/cases and unrelated work. Existing destructive guards remain unchanged; required DB run strictly with inherited DSNs removed and owned Docker only. Fixture labels/results cannot become real accuracy. Q13/N02 and human/provider/full-release gates remain prerequisites; no security policy optimization in this slice.

## Review Focus
Benchmark includes failed requests and query/error denominator, truthful cold/warm/in-process context, non-owner role/pool isolation and frozen <=6 directory SQL budget. Capture failing scaling baseline without claiming remediation. Goldset cannot silently omit missing/duplicate/foreign predictions; holdout segregates by company; two independent declared labels require separate adjudication for disagreement; abstention/zero denominator/uncertainty and three correlated repeats stay explicit. Wrong company/workspace/unsupported evidence fails the offline quality gate. No provider/network/identity/write activation follows from tools.

## Task 1: Versioned statistics and offline goldset evaluator
Interfaces: existing benchmark-buyeros wrapper/results; tools-only metrics/evaluator; existing fit and unknown-hold settlement. Q10's Q13/human/provider prerequisites retain their blocked state.

- [ ] Write meaningful regression tests for inherited DSN refusal, full latency/error denominators, p99/small sample, Wilson/zero denominator, company isolation/labels/three runs and unsafe references. Run RED before implementation.
  Expected: existing wrapper incorrectly accepts non-test inherited DB variables under collect-only; missing new tools/metrics fail assertions, no DB/provider called by RED.
- [ ] Implement tools-only metrics/evaluator and strengthen wrapper guard/provenance without changing historical outputs or domain auth/roles/ledger. Run new and named fit/settlement tests.
  Expected: fixture hand-derived metrics pass, malformed/leaky inputs fail, declared labels never imply live/provider verification; strict0skip.

## Task 2: Owned workspace directory baseline and evidence
Interfaces: current GET/v1/workspaces under actual fixture JWT/runtime NOBYPASSRLS role; existing strict migrated fixture; metrics from task1. No schema change.

- [ ] Add bounded runner + opt-in persistent-loop DB benchmark for W1/10/100/1000, fixed visible memberships, actor count, actual query/bytes/latency/EXPLAIN and pool/revocation probes; run wrapper guards first and capture current baseline.
  Expected: current O(W) route violates frozen <=6 budget for large W; keep the CLI gate nonzero and F18/P09/P10 open. Capture itself has1real DB case pass0skip if valid; no fake connection result.
- [ ] Run regression/contract/root Node gates, inspect diff and author review, verify reverse patch and preservation; commit source then case/status/evidence locally.
  Expected: tools locally verified; Q10 remains partial/externally or dependency blocked for Q13, full fixed-load/UI/RUM/worker/human200-company goldset/WF03. Exact task checks and failures recorded, no product-live claim.
