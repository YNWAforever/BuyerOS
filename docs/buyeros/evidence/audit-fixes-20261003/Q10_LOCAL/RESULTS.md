# Q10 independent local quality tools — 2026-10-04

Reviewed source `ad4f4394819664484eb4b928bdd56c43e055fd3d`; base `6232e4e1f4127833b93c1343207894c79b638852`. Commits7eb0ed5 (offline metrics/guard),
fd97c90 (owned directory capture), ad4f439 (verified actor bound). Application
source remains25694d3b938e704e883f9915cf0604bbdbac1daf; deployedSHA=null.
Full Q10 is **partial**, F12/F18 remain open. No external/provider/production action.

## Implemented and fixture verified

Versioned research evaluator validates supplied dual labels/adjudication,
company holdout/three exact repeats, scope and declared source references.
Precision/recall/coverage/abstention have Wilson95% per-run intervals and null
zero denominators. Fixture8companies/holdout6/three runs has TP2/FP1/TN1/FN1/
needs_review2; precision/recall2/3, coverage4/6, abstention2/6. This validates
arithmetic/structural refusal, not real labels, source truth or provider accuracy.
Every score, including perfect fixtures, remains live_verified/release_accepted=false.
Existing T29 wrapper retains keys and adds source-byte provenance, four-DSN
refusal and existing API/dispatcher report protection.

## Actual owned DB integration and failed performance gate

`--samples30 --actors1` calls actual FastAPI/fixture JWT verifier against owned
PG16 migrated0037, non-owner buyeros_api/superuser=false/bypass_rls=false.
One visible membership/actor; unrelated W varies. Frozen <=6 queries and
independence from unrelated W were chosen before capture and remain failed.

| W | Warm n | SQL per request | p50 ms | p95 ms | p99 ms (unstable) | Failed requests |
|---|---|---|---|---|---|---|
| 1 | 30 | 4 | 7.396 | 8.772 | 9.365 | 0 |
| 10 | 30 | 22 | 28.643 | 35.749 | 38.307 | 0 |
| 100 | 30 | 202 | 182.175 | 270.364 | 320.903 | 0 |
| 1000 | 30 | 2002 | 1905.56 | 2822.957 | 2935.981 | 0 |

Loopback/in-process observations, not geographic/live API or10-minute stairs.
Default local Docker resources; no CPU/memory/RTT caps, background OS load not controlled.
First-after-seed4, primers12, warm120 and pool/revocation5 requests are all
retained; p99 n30 is unstable. SQL time covers successful cursor completions.
Runtime-role EXPLAIN buffers/plans retained. BackendPID90 reused three times;
transaction-local workspace setting cleared; nonmember saw none and active
membership revocation was seen by the next request. Current O(W) route/RLS
remediation is deferred to Q13/N02, not hidden by a passing capture assertion.
Capture1pass/0fail/error/skip98.60s, but wrapper **exit1** for failed SQL gate.
Owned container908860eb... removed and ID marker retained; no shared DSN used.

## Exact verification

- Initial tools RED30fail/0skip; TEST DSN already refused but wording assertion
  was too narrow; three other DSNs genuinely accepted under collect-only.
- Predecessors19pass/0fail/skip6.90s. Task1 final38pass/0fail/skip and completion
  repeat38pass5.24s. Directory guard RED6fail, GREEN6pass0skip.
- Review p99/dispatcher RED2fail (safe collect-only), related GREEN61pass.
  Final actor bound RED1fail with process dispatch disabled; final suite
  **62pass/0fail/error/skip26.54s**,7 retained deprecation warnings.
  This combines60 unit/auth/tool checks and2 actual workspace DB cases.
- Final task-done predecessor/final61pass repeat96.30s retained separately;
  differing duration is not assigned an unproven Docker/pool/cold-start cause.
- Whole Node **69pass/0fail/cancel/skip/todo**,64864.1869ms;68 XML leaves plus
  parent count. Includes actual owned cleanup sentinels and previously built
  emitted SSR. No new app build/UI suite/screenshot; earlier UI evidence retained.
- TypeScript noEmit, generated API types, generated84 routes and Python compile
  exit0.84=70original+14existing extensions;0new operations.
- Alembic source single0037 head;0migrations added, existing migrations applied
  only to owned disposable integration DBs.0production migration/DB identity change.
- Exact commands/env/counts/raw failures in commands.json/reports. No0tests or
  skip is counted as pass. Original import-error1 and wrong-cwd edit repeat
  30fail/4pass logs retained as setup failures; cp950 UTF8/runbook and root
  Alembic relative-path errors recorded in ledger, corrected without test weakening.

## Source attribution and preservation

Baseline HEAD7eb0ed5+dirty overlay is preserved byte-for-byte and matched to
five observed benchmark tool/route hashes plus evaluator input-tool hashes; later sample-flag/actor admission fixes do not
change this already measured actor1/n30 path. Report provenance never rewritten
as final HEAD. Three source commits and final rollback.patch are separate.
31 original input hashes,98historical case fields,91other case rows,24other
TASKS objects, all84operation rows,4destructive guards and prior U05(91),
Q09FINAL(161),Q09KEYBOARD(141),LOCAL_GATES(59) producer bytes verified.
Root671fed7... remains clean; unrelated Neon193paths/diffSHA32ad7260... unchanged.

## Review, rollback and open gates

Author review only: human prohibited agents. Final review-package/ledger is
archived; observed Important findings fixed; no deferred Minor. Independent
review remains pending. Source reverse patch applicability exit0; no production
rollback rehearsal. Revert only these local Q10 source/docs commits after
review; runtime endpoints/auth/RLS/identity/roles/holds/approval/worker/delivery
and schema did not change. Sending remains disabled by unchanged source.

F12/A03–A06/A08 actual quality remains NOT TESTED; fictional metrics cannot
close those cases. F18/P09/P10 local scaling is **FAILED**; pool/revocation
subchecks pass. Full-Q10 gates: Q13/N02 directory resolution, genuine>=200-company
human labels and approved provider/source/contact evidence, full API/UI/RUM/
worker load, UAT and independent review. Q16 underlying evidence remains
blocked; no Neon cold-start/pool cause or Q17 fix inferred. Neon auth/cutover
and Cloudflare cutover remain separate and untouched.

## Rulings and costs

Recommended local Q10 tools selected after optional scope question: if N00 was
intended, cost is extra local tools work/delayed compatibility work. Only independent
slice implemented; fullQ10 acceptance stays open. No agents: independent review
cost remains. New output required to preserve evidence: callers choose new filenames.
Frozen<=6 gate stays failed and Q13/N02 deferred: performance remains unresolved.
p99 flag is a conservative1000-sample heuristic, no stability guarantee. Only
verifiedactor1 admitted:10/25actor harness deferred. Label declarations never
become authenticated/human/live evidence: accuracy/contact acceptance remains open.
Local branch preserved; no finishing/merge/live assertion while required fullQ10
performance/external gates remain unresolved.

Curated source/status whitespace checks exit0. Initial staged raw producer check
reported186 preserved patch/log whitespace findings; diagnostic capture may
repeat those lines. Raw bytes are retained under explicitcr-at-eol/-text
attributes; they are not normalized or counted as test failures/passes.
