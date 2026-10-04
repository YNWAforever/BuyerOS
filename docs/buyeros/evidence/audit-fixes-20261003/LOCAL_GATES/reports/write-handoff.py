from pathlib import Path
import json,subprocess,hashlib,shutil
root=Path.cwd();area=root/'test-results/local-gates'
base='cbb67ddbb907b8b989b175588ba73ed205e2c2d8';source='d7ab5b6323402adf139d9b94e4e499f1631006b4'
evidence=root/'docs/buyeros/evidence/audit-fixes-20261003/LOCAL_GATES'
reports=evidence/'reports';reports.mkdir(parents=True,exist_ok=True)
for p in area.iterdir():
 if p.is_file() and p.suffix in ['.log','.json','.xml','.mjs','.py','.ps1','.patch','.txt']:shutil.copyfile(p,reports/p.name)
first=evidence/'first-build';first.mkdir(exist_ok=True)
for p in (area/'first-build').iterdir():
 if p.is_file() and p.suffix in ['.log','.json','.txt']:shutil.copyfile(p,first/p.name)
workspace=root/'.superpowers/sdd/2026-10-04-buyeros-local-verification-gates'
for p in workspace.iterdir():
 if p.is_file():shutil.copyfile(p,evidence/p.name)
attributes=root/'.gitattributes'
s=attributes.read_text(encoding='utf-8')
line='docs/buyeros/evidence/audit-fixes-20261003/LOCAL_GATES/** -text whitespace=cr-at-eol'
assert line not in s
attributes.write_text(s+'\n# Preserve local verification-gates raw producer evidence.\n'+line+'\n',encoding='utf-8')
results=f'''# Local verification gates — 2026-10-04

Reviewed test source `{source}`, base `{base}`. Application source remains `25694d3b938e704e883f9915cf0604bbdbac1daf`; no application/API/schema code changed. Local source commit only; no remote PR/push/deployment. Deployed SHA is null.

## What changed

`tests/e2e-fixture-cleanup.test.mjs` now imports each real Playwright configuration and invokes its configured teardown in a fresh isolated temporary directory. Twenty API fixture configurations each remove a uniquely named, newly owned Docker sentinel and marker. The audit wrapper also removes its labelled UI sentinel; wrong UI ownership and unrecognized database markers are refused and retained for explicit test cleanup. All fallback deletion checks this run's label. These are container-lifecycle tests: sentinel containers run sleep, not Postgres, and are not database integration or live auth/provider verification. Existing four destructive guards/teardown source remain unchanged.

The Vercel check needed a genuine build artifact. Existing `scripts/run-vercel.mjs build` was run with the Nitro `vercel` preset in a newly owned local Linux container, frozen pnpm dependencies and a safe secret-excluding source inventory. The emitted `__server.func/index.mjs` was tested directly, with no synthetic function or node-server substitute. Runtime/source/output hashes and reproduction helpers are in reports; no deployment configuration changed.

## Exact gates

| Command / environment | Result |
|---|---|
| Baseline `node --test tests/e2e-fixture-cleanup.test.mjs tests/vercel-render.test.mjs` | 0 pass / 2 fail / 0 skip: stale direct-filename check and missing emitted artifact |
| `node --test tests/e2e-fixture-cleanup.test.mjs` | 24 pass / 0 fail / 0 skip, 71429.0015 ms before final zero-case/finally hardening |
| Remove audit's `cleanupDatabase()` invocation, run same test, restore original bytes in finally | 22 pass / 2 fail / 0 skip; delegated database marker retained; final restore SHA verified. Parent and failed child both counted by Node |
| Each bounded local `corepack pnpm install --frozen-lockfile && timeout --signal=TERM --kill-after=10s 180s node scripts/run-vercel.mjs build` | Two local builds exit0; actual first Linux SSR3 pass; first Docker copy failed on Windows symlink privilege, retained. Second resolves symlinks in tar and extracts genuine artifact successfully |
| Linux `node --test tests/vercel-render.test.mjs` final | 3 pass / 0 fail / 0 skip,449.838376 ms |
| Windows same direct emitted-function test | 3 pass / 0 fail / 0 skip,658.5276 ms |
| **Final `node --test --test-reporter=spec --test-reporter-destination=stdout --test-reporter=junit --test-reporter-destination=test-results/local-gates/root-node-final.xml 'tests/*.test.mjs'`** | **69 pass / 0 fail / 0 cancelled / 0 skip / 0 todo;96210.0865 ms**. Includes cleanup and SSR, not additive independent counts |
| `node node_modules/typescript/bin/tsc --noEmit` | exit0 |
| `node node_modules/eslint/bin/eslint.js tests/e2e-fixture-cleanup.test.mjs --max-warnings=0` | exit0 |
| `node scripts/generate-api-types.mjs --check` | exit0 |
| `uv run --frozen --project services/api python scripts/generate-operation-routes.py --check` | exit0,84 operations =70 original +14 existing extensions;0 new |
| `uv run --frozen alembic heads` (services/api) | sole `0037_bulk_manifests`;0 migrations added/applied |
| `git apply --reverse --check docs/buyeros/evidence/audit-fixes-20261003/LOCAL_GATES/reports/test-rollback.patch` | applicability exit0; no runtime/production rollback rehearsal |

Node counts include the successful cleanup parent: JUnit contains68 leaf cases, including23 cleanup effects/negative leaves. It is not69 unique leaf scenarios. Exact individual results and raw XML/log retained. Host Windows Node24.18.0; local built runtime Node22.23.2/image48e4b67d...,4CPU/6GiB; Docker context desktop-linux. Existing source/lockfile frameworks remain unchanged. Root cleanup test now requires an available local Docker daemon and cached/pullable `node:22.23.2-bookworm-slim`; missing prerequisites fail, never skip. Linux CI already builds the emitted function before its rendering test.

## Failure history and provenance

First behavior-harness run misclassified Docker's lowercase `no such object` response; fixed case handling only, retained failing log. First build/render succeeded but recursive Docker copy lacked Windows symlink privilege; second local build used `tar -chzf` to export actual resolved files. Build warnings for unresolved optional nf3 traceInclude entries/plugin timing are retained and are not called a warning-free build. Mutation driver cp950 print failed after the expected red and exact restoration/proof had succeeded; verified that existing proof without rerunning the mutation. Artifact hash collector initially compared a relative path to an absolute root; corrected and rerun. These setup/diagnostic failures are not product REDs or hidden passes.

No paid provider/Auth0/Neon request, secret write, database/membership mutation, mail, service activation or deployment occurred. Owned sentinel/build containers were removed; only the label-verified existing dependency cache and ignored emitted output/source archives remain for review. Empty setup-error temporary directories were checked within the task prefix and removed.

## Preservation and review

U05's91, Q09 FINAL161 and KEYBOARD141 producer files still match their frozen manifests. Root remains clean at671fed7...; unrelated Neon worktree193 paths/raw diff SHA32ad7260... unchanged. Original98-case tracker and all operation rows unchanged; only Q11's follow-up evidence is added to TASKS. No new F-ID closure is claimed; U05/F04 remains its earlier local UI/strict-DB result, not newly run here. No UI/DB suite was rerun for this test-only delta, and no existing fixture result becomes live proof.

Author review of `{base}..{source}` and build/runtime/hash evidence found no Critical/Important or deferred Minor in this delta. Human forbids agents: independent review is still pending. Earlier U05 root Node42pass/2fail records remain immutable historical results; this new69pass gate resolves those two local prerequisites without rewriting history.

## Rulings I made

1. `continue` selects the recommended local gates follow-up after an optional pending scope question; no external work. If review-only was intended, the extra cost is local test execution/one test repair.
2. Human no-agents instruction overrides skill reviewer delegation; author review has less independence, so fresh review stays open.
3. Human tests-before-commit rule controls task-done: printed range cbb67dd..cbb67dd is precommit, not final reviewed/deployed SHA. Tested LF hash matches `{source}` Git blob; misreading it would attribute proof to the wrong tree.
4. Full product live acceptance, human staff/screen-reader UAT, provider/performance/Q16 evidence and Neon/Cloudflare cutover remain separate: calling this gate release acceptance would claim untested capabilities.

Deferred minors: none in this delta. No benchmark/p95/p99/goldset claim follows from suite duration. Q16 remains blocked on underlying evidence; N00 remains a separate compatibility scope. No new eligible task selected; this is a reviewable local candidate.

## Rollback and reproduction

The reverse patch restores only the prior test, retaining task/evidence/status records and all application/database data. It will reinstate the stale literal-filename gate and remove new lifecycle coverage; no user membership/role/identity restoration is involved. Applicability only was tested. For a clean Linux checkout, install frozen pnpm dependencies, run `node scripts/run-vercel.mjs build`, ensure the local Docker daemon/image is available, then run the final root command above. The Windows-owned builder is preserved in reports/build-linux.mjs; it requires the recorded label-matching cached volume and refuses existing emitted output. First/second input manifests identify their separate owned resources. The ignored27,344,314-byte faithful build archive SHA is `fb37cbacf5402efa738c65cb4f835c49360d2e266a87faff7f9d56a04a086380`;2611 emitted file hashes are retained, actual bundle stays ignored.
'''
(evidence/'RESULTS.md').write_text(results,encoding='utf-8')
review=root/'docs/buyeros/review/2026-10-03-audit-fixes'
(review/'LOCAL_GATES-review.md').write_text(f'''# Local verification gates — author review\n\nRange `{base}..{source}`; read the generated review package and actual emitted/runtime/hash proof after the final69pass suite. Human prohibits agents; independent review pending.\n\nConfigured effects (20 API fixtures plus audit UI/negative ownership/invalid marker), missing-delegation mutation, own-label fallback, bounded build inputs, real vercel preset entry, source equality and faithful archive extraction were checked. No product/API/schema code changes. No Critical/Important/Minor finding in this delta. Tests now have a documented Docker/image prerequisite and Node native TS loader; actual host24 and build22 versions reported.\n\nDeclined-to-judge scope is explicitly ruled in RESULTS/ledger: live acceptance, human UAT/screen-reader, provider/performance/Q16 and auth/jobs cutover. The whole repair programme still needs independent review and external/human gates.\n''',encoding='utf-8')
(review/'LOCAL_GATES-pr.md').write_text(f'''# Local PR description — verification gates\n\nNo GitHub PR created.\n\n**Title:** test: verify configured fixture cleanup with owned containers\n\n**Source commit:** `{source}`; base `{base}`.\n\n**Changes:** replace stale direct-filename cleanup assertion with actual configured teardown effects, ownership refusal and invalid marker behavior; preserve existing runtime and destructive guards. Existing Vercel output prerequisite satisfied with a genuine local build, without changing its rendering assertion.\n\n**Evidence:** [RESULTS](../../evidence/audit-fixes-20261003/LOCAL_GATES/RESULTS.md). Final rootNode69pass/0fail/skip (68JUnitleaves); cleanup24 including parent; actual SSR3 in each Linux/Windows run; types/lint/generated84 contract pass; no migration. Missing-delegation mutation fails and original exact bytes restored. Baseline/setup/copy failures retained.\n\n**Review/risks:** author only; independent review/human UAT/live activation gates remain open. Root check needs local Docker/image and prior actual Vercel build. No API/DB/UI acceptance rerun for this test-only delta.\n\n**Rollback:** reverse applicable one-test patch in evidence, retains runtime/data/status. Applicability only; reverting restores stale literal check. No push/deploy/production operation authorized or performed.\n''',encoding='utf-8')
statePath=root/'TASKS.json';state=json.loads(statePath.read_text())
original=json.loads(subprocess.check_output(['git','show',f'{base}:TASKS.json']))
q11=next(t for t in state['tasks'] if t['id']=='Q11')
q11['local_verification_gates_followup']={'status':'local-test-gates-verified','base_sha':base,'source_sha':source,'application_source_sha':'25694d3b938e704e883f9915cf0604bbdbac1daf','code_changes':'one test + focused plan; application/API/schema unchanged','checks':{'root_node':{'pass':69,'fail':0,'error':0,'skip':0,'junit_leaf_cases':68,'duration_ms':96210.0865},'cleanup_included':{'pass':24,'fail':0,'skip':0},'linux_emitted_ssr':{'pass':3,'fail':0,'skip':0},'windows_emitted_ssr':{'pass':3,'fail':0,'skip':0}},'contracts':'types/lint/generated84 pass;0 new operations','migrations':[],'head':'0037_bulk_manifests','evidence':'docs/buyeros/evidence/audit-fixes-20261003/LOCAL_GATES/RESULTS.md','rollback':'one-test reverse patch applicability passed; no runtime/production rehearsal','review':'author only; independent review pending','release_status':'not-deployed','limits':'Docker/image/build prerequisite; no fresh UI/DB/live/performance/human UAT; prior failures retained'}
state['selected_followups'].append('Q11 local verification gates')
state['reviewed_source_sha']=source
state['application_source_sha']='25694d3b938e704e883f9915cf0604bbdbac1daf'
state['deployed_sha']=None
assert state['next_eligible'] is None
assert len(state['tasks'])==25
for before,after in zip(original['tasks'],state['tasks']):
 if before['id']=='Q11':
  clean=dict(after);del clean['local_verification_gates_followup'];assert clean==before
 else:assert before==after
statePath.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
prefix=f'> Latest Q11 local verification-gates follow-up: reviewed source `{source}`; root Node69pass/0fail/skip (68JUnitleaves), genuine Linux/Windows emitted SSR3 each, types/lint/generated84 pass. Resolves U05 historical two root-gate failures;0 runtime/schema/migration changes, no deployment. [Evidence](evidence/audit-fixes-20261003/LOCAL_GATES/RESULTS.md). Independent/human/live gates remain open.\n\n'
for p in [root/'docs/buyeros/CURRENT_STATUS.md',root/'docs/buyeros/REMAINING_DEVELOPMENT_STATUS.md']:
 p.write_text(prefix+p.read_text(encoding='utf-8'),encoding='utf-8')
p=review/'HANDOFF.md'
p.write_text(f'> Latest local checkpoint: root Node69pass/0fail/skip at test source `{source}`; actual vercel emitted SSR3 Linux/3Windows. U05 historical root2fail prerequisites now closed locally; no runtime/schema change or deployment. [Evidence](../../evidence/audit-fixes-20261003/LOCAL_GATES/RESULTS.md), [local PR](LOCAL_GATES-pr.md). Independent/human/live gates remain open.\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8')
plan=root/'docs/superpowers/plans/2026-10-04-buyeros-local-verification-gates.md'
plan.write_text(plan.read_text(encoding='utf-8').replace('- [ ] Run types/lint','- [x] Run types/lint'),encoding='utf-8')
metadata={'tasks_total':25,'other_task_objects_unchanged':24,'case_csv_unchanged':subprocess.check_output(['git','diff',base,'--','docs/buyeros/remaining/AUDIT_FIX_CASE_STATUS_20261003.csv'])==b'','operation_ledger_unchanged':subprocess.check_output(['git','diff',base,'--','docs/buyeros/remaining/API_OPERATION_STATUS.csv'])==b'','runtime_diff_empty':subprocess.check_output(['git','diff',base,'--','features','services','app','alembic'])==b''}
assert metadata['case_csv_unchanged'] and metadata['operation_ledger_unchanged'] and metadata['runtime_diff_empty']
(evidence/'tracker-preservation.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
manifest=[]
for p in sorted(evidence.rglob('*')):
 if p.is_file():manifest.append({'path':p.relative_to(evidence).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(evidence/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'evidence_payloads':len(manifest),'metadata':metadata}))
