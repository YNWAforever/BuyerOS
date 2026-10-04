## Task 2: Owned workspace directory baseline and evidence
Interfaces: current GET/v1/workspaces under actual fixture JWT/runtime NOBYPASSRLS role; existing strict migrated fixture; metrics from task1. No schema change.

- [ ] Add bounded runner + opt-in persistent-loop DB benchmark for W1/10/100/1000, fixed visible memberships, actor count, actual query/bytes/latency/EXPLAIN and pool/revocation probes; run wrapper guards first and capture current baseline.
  Expected: current O(W) route violates frozen <=6 budget for large W; keep the CLI gate nonzero and F18/P09/P10 open. Capture itself has1real DB case pass0skip if valid; no fake connection result.
- [ ] Run regression/contract/root Node gates, inspect diff and author review, verify reverse patch and preservation; commit source then case/status/evidence locally.
  Expected: tools locally verified; Q10 remains partial/externally or dependency blocked for Q13, full fixed-load/UI/RUM/worker/human200-company goldset/WF03. Exact task checks and failures recorded, no product-live claim.
