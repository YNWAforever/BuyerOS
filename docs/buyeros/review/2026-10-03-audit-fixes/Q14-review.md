# Q14 author review — 1aab3ddc0519bb6da8d1483efaf173eb5a87037e

Inline author review only; independent review pending. No agent/owner approval fabricated.

| Focus | Ruling |
|---|---|
| Domain/API ownership |Existing listAsyncJobs project_id filter/actor restriction used;84 generated operations unchanged;0schema/API/rolechanges |
| Shared scope/count/list/link |One generated-query-based builder, selected project explicit, workspace labelled; U15 A0/B5/ws5 actual DB/API |
| Authority |Runtime RLS/current membership; reviewer5/operator3/admin8/viewer0, other actor/tenant404; fixture-only canonical actor mapping |
| Scope/status/page race |Per-generation/view/status/page cache key and abort; counts+list held A-B-A; resetpage and old results; Q03 late result/schema regressions |
| Navigation/recovery |Read router query, explicit URL writes only, no implicit workspace persistence; current project resolution waits; refresh+reauth and503 read retry |
| UI |en/zh390labels/full IDs/20row real pagination; overflow assertion and visual screenshot inspection |
| Rollback |8file reverse patch applicability0; no durable data/API/auth change, restores prior count bug; runtime rehearsal not run |
| Integrity/limits |31inputs/98originalfields/3guards/193unrelatedpaths unchanged; fixture/dev only, no production/full UAT/performance claim |

Final strict API18/UI10/Node16 pass,0fail/error/skip, generated/type/lint0.8 committed normalized source hashes match tested source. Meaningful RED and first2/4UI failures retained, no timeout/guard/assertion weakened.
