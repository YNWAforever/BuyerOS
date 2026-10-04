## Task 1: Versioned statistics and offline goldset evaluator
Interfaces: existing benchmark-buyeros wrapper/results; tools-only metrics/evaluator; existing fit and unknown-hold settlement. Q10's Q13/human/provider prerequisites retain their blocked state.

- [ ] Write meaningful regression tests for inherited DSN refusal, full latency/error denominators, p99/small sample, Wilson/zero denominator, company isolation/labels/three runs and unsafe references. Run RED before implementation.
  Expected: existing wrapper incorrectly accepts non-test inherited DB variables under collect-only; missing new tools/metrics fail assertions, no DB/provider called by RED.
- [ ] Implement tools-only metrics/evaluator and strengthen wrapper guard/provenance without changing historical outputs or domain auth/roles/ledger. Run new and named fit/settlement tests.
  Expected: fixture hand-derived metrics pass, malformed/leaky inputs fail, declared labels never imply live/provider verification; strict0skip.

