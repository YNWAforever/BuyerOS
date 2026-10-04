# BuyerOS pilot human evaluation protocol — proposed, NOT RUN

This protocol is a review artifact. It does not approve a provider, external spend, real-company collection or deployment. The exact workspace, users, lawful purpose, regions, dates, retention, provider capabilities and financial caps remain unfilled in `PILOT_EXECUTION_RECORD.md`.

## Sampling and independent labels

After separate pilot authorization, select 30–50 real candidate companies from the approved market/time window using a recorded sampling method before reviewing fit results. Keep candidate identity, source, query/run and snapshot IDs in a restricted evaluation register. Two named human reviewers independently label buyer type, relevance to the approved offer/ICP, each material evidence claim as supported/unsupported/unknown, human acceptance, and contact validity only when an approved contact path exists. Preserve disagreements for a third adjudicator; report both pre-adjudication agreement and final adjudicated labels. Do not feed this labelled set into prompt tuning, query repair or threshold changes before the holdout result is sealed.

The browser's fixture Match verdict, accepted state or generated draft is never a ground-truth label. Evidence support requires an accessible source and a specific cited claim, with inference marked separately. Contact yield is not the count of returned strings: it requires current provider-marked-valid, purpose-eligible, unsuppressed business contacts. Manual outcomes are human-entered observations, not inbox synchronization or a causal sales claim.

## Proposed measures, pending owner approval

| Measure | Numerator / denominator | Proposed review threshold |
| --- | --- | --- |
| Accepted-candidate precision | Independently judged relevant accepted companies / all reviewed accepted companies | >=80%; report n and uncertainty |
| Structural citation coverage | Material claims with a source link or explicit unknown/inference marker / material claims sampled | 100% |
| Empirical factual support | Correct supported material claims / sampled material claims with checkable sources | >=95% |
| Reviewer agreement | Same independent relevance verdict / doubly reviewed companies | >=80% before adjudication |
| Contact yield | Accepted eligible companies with >=1 current valid eligible contact / accepted eligible companies actually researched | Measure first; no target promised |
| Cost per accepted company | Settled attributable USD / distinct accepted company IDs in the same scope/period | Report amount and denominator; zero denominator means unavailable |
| Human review time | Active minutes on completed company decisions / completed decisions | Establish baseline; proposed median <=3 minutes subject to evidence complexity |

Report active holds and unknown provider liability separately from settled spend. Store request IDs, provider receipts and price versions only in the restricted operational record after authorized calls. Never infer a free operation from timeout.

## Stopping and disposition

Stop new admission/dispatch on tenant leakage, unauthorized contact access, unsupported material claims passing review, broken reservation limits, unexplained charges, missing authoritative provider status, accidental delivery or the approved cap/time window. Retain unknown holds and reconcile; preserve read access and audit history when safe. A failed quality threshold is a no-go with labelled examples and a proposed bounded revision, not a reason to relabel the holdout. Mailbox/CRM/sending stay disconnected and `/deliver` stays 403.

No sample, reviewer assignment, provider receipt, quality score or cost figure has been collected in this session.

## Q10 local tools supplement — 2026-10-04

The older30–50/80% pilot proposal above is retained historical context. The
2026-10-03 repair plan's tentative full-Q10 goal is >=200 companies, two
independent human labels with adjudication, company-level holdout and three
runs; proposed match precision>=95% with recall/coverage/needs_review/CI and
zero wrong-company/cross-tenant/unsupported references. No owner approval,
reviewer assignment, actual goldset or provider receipt is fabricated here.

The new offline evaluator checks supplied label/prediction structure and
per-run metrics; declarations remain unauthenticated, outputs always say
live_verified=false/release_accepted=false. Its fictional8-company fixture
validates tool arithmetic only. Contact validity/company relationship,
factual truth and adversarial source behavior need separate actual evidence.
[Commands and boundaries](../runbooks/q10-local-quality-tools.md).
