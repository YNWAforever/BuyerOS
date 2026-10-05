from pathlib import Path
from datetime import datetime,timezone
import json,csv,hashlib,subprocess,shutil
root=Path.cwd();area=root/'test-results/n00-proxy-dispatch-deadline';group=root/'docs/buyeros/evidence/audit-fixes-20261003/N00_PROXY_DISPATCH_DEADLINE'
assert not group.exists();(group/'reports').mkdir(parents=True);(group/'screenshots').mkdir();(group/'runtime').mkdir()
sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert sha=='9e1ef78d4ae61429dee0d4b6fd62de9cbfdd7c92';stamp=datetime.now(timezone.utc).isoformat()
record=json.loads((area/'checks.json').read_text(encoding='utf-8-sig'));record.update(status='local-proxy-deadlines-verified;full-N00-open',source_sha=sha,base_sha='233848b263cfdefc49d6dc5f53df2d534afdba16',application_source_sha='5aaf6492ec10078e4f1a4fa5b17efd41c5673eba',branch='codex/n00-proxy-dispatch-deadline',checked_at=stamp,owner_role='Identity / QA',source_files=3,insertions=105,deletions=8,protocol_code_changes='absolute ingress body deadline, TTL recheck immediately before physical dispatch, remaining TTL clamps upstream timeout; unknown hold retained',new_operations=0,operation_count=84,original_operations=70,extensions=14,source_schema_head='0037_bulk_manifests',evidence='docs/buyeros/evidence/audit-fixes-20261003/N00_PROXY_DISPATCH_DEADLINE/RESULTS.md',rollback='Revert following metadata commit then9e1ef78 as one local harness/test unit;no DB/data undo;never erase admitted/unknown journal state.',next_eligible='N00 local native browser/CLI containment gap audit; full real-Neon/Google/Admincleanup/original302 requires separate evidence and fresh exact authorization;N01/N02 prerequisite unchanged')
(area/'checkpoint.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for p in area.iterdir():
 if p.is_file() and p.suffix in ['.log','.xml','.json','.txt','.py'] and p.name not in ['preservation-before.json','root-tasks-before.json','registry-before.json','cases-before.csv','operations-before.csv']:
  shutil.copyfile(p,group/'reports'/p.name)
shutil.copyfile(area/'source.patch',group/'source.patch')
for name in ['playwright.neon-runtime-flow.config.ts','scripts/neon-runtime-flow-teardown.mjs','tests/e2e/audit-neon-runtime-flow.spec.ts']:
 shutil.copyfile(root/name,group/'reports'/('runner-'+Path(name).name))
for run in record['built_reuse_ui']:
 target,nonce=run['target'],run['nonce'];folder=root/'test-results/neon-runtime-flow/runs'/f'{target}-valid-{nonce}';dest=group/'runtime'/target;dest.mkdir()
 # Exclude private configuration/owner runtime metadata; public producer receipts only.
 for p in folder.iterdir():
  if p.is_file() and (p.name.startswith('journal-') or p.name in ['budget.json','cleanup.json','child-cleanup.json','runtime-output.log','leak-check.json']):shutil.copyfile(p,dest/p.name)
 shutil.copyfile(root/'test-results/neon-runtime-flow'/f'{target}-{nonce}-ui.xml',group/'reports'/f'{target}-ui.xml')
 shots=list((root/'test-results/neon-runtime-flow'/f'{target}-{nonce}-ui').rglob('signed-in.png'));assert len(shots)==1;shutil.copyfile(shots[0],group/'screenshots'/f'{target}-fictional-session.png')
(group/'.gitattributes').write_text('* -text whitespace=cr-at-eol\nreports/** -text -diff\nruntime/** -text -diff\nscreenshots/** -text -diff\nsource.patch -text -diff -whitespace\n',encoding='utf-8')
text=f'''# N00 / F20 / NA01 — counted proxy ingress and physical dispatch deadline

Reviewed source `{sha}`, BASE233848b263cfdefc49d6dc5f53df2d534afdba16, branch codex/n00-proxy-dispatch-deadline, checked `{stamp}`. **Full N00/NA01/F20 OPEN; deployed SHA NULL.** Author review only, independent review pending. Local harness repair; Auth0/domain API/UI/schema/roles unchanged; no external/provider/account/email/push/deploy action.

## Reproduced issue and smallest fix

Native Node HTTP streamed-body RED observed: an already reserved request completed its body after target expiry and still returned200; continuous body trickle reset the idle timer and returned200; a physical write with100ms remaining TTL used the full1000ms timeout and returned200 after180ms. These failed expected403/408/503 respectively. Timely-body positive control passed.

Replace resettable ingress idle timeout with an absolute body collection deadline and bounded bytes. Recheck journal TTL immediately before physical dispatch; clamp its signal deadline to min(configured upstream timeout, remaining target TTL). Pre-dispatch body/expiry rejection records rejected with zero upstream hops; post-dispatch uncertainty retains unknown hold. Restart/renewed channel/query/token semantics and 200-total/20-cleanup reserve unchanged. Body timeout responds408 and closes the incomplete request connection. No code grants identity or workspace authority.

Three files/105insertions/8deletions: scripts/neon-counted-proxy.mjs, tests/neon-proxy-deadline.test.mjs, focused plan. [Source patch](source.patch); [author review](reports/source-review.json). The named four native HTTP tests exercise real owned servers and fresh persisted journals, no mocked backend fetch. Original302/body/status/timeouts and DB guards unchanged. No migration; read-only Alembic heads0037_bulk_manifests. Separate peerQ13 proposed0038 unmerged.

## Fresh results

|Check|Pass|Fail|Skip|Evidence|
|---|---:|---:|---:|---|
|First RED (timely control included)|1|2|0|reports/red.log/.xml|
|Complete RED (remainingTTL added)|1|3|0|reports/red-final.log/.xml|
|Focused deadline + original counted proxy|28|0|0|reports/focused-green.log/.xml|
|All29 rootMJS suites|304reported /303JUnit leaves|0|0|reports/root-green.log/.xml|
|STRICT owned EdDSA diagnostic|8|0|0|reports/crypto.log/.xml|
|Portable actual retained SDK output + fresh proxy/browser|6|0|0|reports/portable-ui.log/.xml|
|Vercel actual retained SDK output + fresh proxy/browser|6|0|0|reports/vercel-ui.log/.xml|

Root106071.156ms; focused7845.584ms; crypto1.61s/one existing asyncio deprecation warning; UIportable17.345563s/vercel8.442168s, zero JUnit/global errors. Types/scoped ESLint/generated types/routes exit0;84operations=70+14, no operation/ledger changes. Root reported count includes one nested parent. Focused28 is a subset of root304, not additional unique cases.

This protocol slice needs no domain DB suite: direct protocol/crypto DBconnections0, no required DB skip. Whole root runs its existing guarded disposable test subprocesses; its304 is Node counts, not a new API/SQL count. All required assertions ran; no0-test/skip was counted pass. No new auth integration, provider accuracy, production performance or full staff journey result inferred.

## Built-output provenance and accounting

No new build. SDK0.5.0-beta/framework pins unchanged. Reused actual compiled base2eb4b388a4d669a80bd3f205804d97e3f3a81267 from historical c756596406f41884f61a3b64c8549f569e34cfa4 checkpoint.14 compiled overlays unchanged; archiveSHA matches immutable N00_UNKNOWN_WRITE_RECOVERY reuse proof; every actual output byte compared to its frozen archive:95portable and2625Vercel files (2220 regular members +405 hard links). [Exact reuse evidence](reports/build-reuse.json); [verification script/log](reports/verify-build-reuse.py). Current proxy is a host-side script imported at runtime, not embedded in those compiled artifacts. Do not call this a fresh current-source build. Root SSR uses the retained normal main artifact from5aaf649; application/API/UI source unchanged in this follow-up.

Each UI run has38durable reservations,37physical owned-loopback Auth hops,35accepted/2rejected/1unknown/0pending,0external Auth requests. Locally_rejected2 includes the forwarded refused redirect and one held retry; it is not received minus forwarded. Expected sign-out unknown hold survives UI retry. Original ownership-guarded teardown proves private root/configuration/journal removal and actual OS child absence. [Portable receipts](runtime/portable/budget.json), [Vercel receipts](runtime/vercel/budget.json); cleanup.json and child-cleanup.json under each. Fresh fictional screenshots under screenshots/; this UI explicitly says its subject is not a BuyerOS user or role. No true Google/account/session/provider result.

## Exact executed commands

Cwd is the isolated worktree unless noted. Crypto/UI set PYTHONUTF8=1,BUYEROS_STRICT_INTEGRATION=1, unset DATABASE_URL/BUYEROS_TEST_DATABASE_URL. All targets loopback/fixture.invalid; real targets/credentials unused.

```powershell
# RED before implementation
node --test --test-reporter=spec --test-reporter-destination=test-results/n00-proxy-dispatch-deadline/red-final.log --test-reporter=junit --test-reporter-destination=test-results/n00-proxy-dispatch-deadline/red-final.xml tests/neon-proxy-deadline.test.mjs
# GREEN
node --test --test-concurrency=1 --test-reporter=spec --test-reporter-destination=test-results/n00-proxy-dispatch-deadline/focused-green.log --test-reporter=junit --test-reporter-destination=test-results/n00-proxy-dispatch-deadline/focused-green.xml tests/neon-proxy-deadline.test.mjs tests/neon-counted-proxy.test.mjs
$taskTests=@(Get-ChildItem -LiteralPath tests -Filter '*.test.mjs' -File | Sort-Object Name | ForEach-Object {{'tests/'+$_.Name}})
node --test --test-concurrency=1 --test-reporter=spec --test-reporter-destination=test-results/n00-proxy-dispatch-deadline/root-green.log --test-reporter=junit --test-reporter-destination=test-results/n00-proxy-dispatch-deadline/root-green.xml @taskTests
services/api/.venv/Scripts/python.exe -m pytest -q tests/fixtures/neon-runtime-flow/test_verify.py --junitxml=test-results/n00-proxy-dispatch-deadline/crypto.xml
node node_modules/typescript/bin/tsc --noEmit
node node_modules/eslint/bin/eslint.js scripts/neon-counted-proxy.mjs tests/neon-proxy-deadline.test.mjs --max-warnings=0
node scripts/generate-api-types.mjs --check
uv run --frozen --project services/api python scripts/generate-operation-routes.py --check
python test-results/n00-proxy-dispatch-deadline/verify-build-reuse.py
# Actual retained outputs; sequential, with ownership-bound nonces
$env:BUYEROS_N00_FLOW_PROFILE='runtime-flow-final'
$env:BUYEROS_N00_TARGET='portable'; $env:BUYEROS_N00_RUN_ID='2314a4a2e7e8'
node node_modules/@playwright/test/cli.js test --config playwright.neon-runtime-flow.config.ts tests/e2e/audit-neon-runtime-flow.spec.ts
$env:BUYEROS_N00_TARGET='vercel'; $env:BUYEROS_N00_RUN_ID='5d6402f65c01'
node node_modules/@playwright/test/cli.js test --config playwright.neon-runtime-flow.config.ts tests/e2e/audit-neon-runtime-flow.spec.ts
# Read-only, cwd services/api
.venv/Scripts/python.exe -m alembic heads
git diff --cached --check
git apply --reverse --check test-results/n00-proxy-dispatch-deadline/source.patch
```

Windows/Node24.18.0/Python3.14.6, Chromium1120x800. No timer/budget allowance increased. Native body trickle deadline100ms; TTL-crossing uses a controlled clock after durable admission; physical remainingTTL100ms vs response180ms; positive control verifies bytes/header/one-hop persistence. Existing40ms upstream timeout regressions remain intact. Timing is test-condition evidence, not a production latency benchmark. Retained compiled image was Node22.23.2 bookworm-slim; no Docker build this follow-up.

## Case/findings and remaining limits

NA01/F20 remain partial local diagnostic/rehearsal evidence. The three deadline failures are locally fixed; latest four native cases and both fresh built-output fixture flows pass. All other97 cases/24 audit task objects and legacy31 task objects retain their own evidence.84operation definitions/ledger unchanged.3433prior input/evidence files and three foreign worktrees, including193dirty paths and peerQ13, preserved; original pack unmodified.

Original strict302 callback assertion is unchanged and **not rerun this slice**; its prior failure remains carried/open. Real Neon/Google/Managed Admin cleanup/schema/absence, full native browser/CLI containment/accounting and independent/human review remain OPEN. Do not bypass N01/N02 prerequisites or link by email. F10/F18/F21/fullQ11 and live staff/recovery/provider gates are not closed by this change. Auth0, canonical users.id/memberships/owner/approval/audit/job actor/RLS and independent Cloudflare HMAC retained; delivery403.

Code implemented: local harness only. Fictional fixtures verified: four native HTTP tests and twelve SDK/browser cases. Actual local integration verified: owned HTTP, fsynced journal/restart, pinned SDK/built output/EdDSA diagnostic. External/live/deployed: none; deployedSHA NULL. Independent review: pending, no agents or forged owner approval.

## Rollback and next eligibility

Source reverse-apply applicability exit0; no actual production rollback run. Revert the following metadata commit then `{sha}`. No DB/business data undo or auth cutover. Existing admitted/unknown journals must remain intact and reconcile; never erase holds to re-enable a retry. Public release additionally needs the unchanged real/integration/owner gates; tests alone do not authorize it.

Next local work: remaining N00 native browser/CLI containment gap audit/preparation. Fresh real-target/Auth/one human Google identity/cleanup requires exact bounded authorization; prior projects/approvals are not reused. No automatic admin grant is proposed. The original real-roundtrip runbook is a historical, unapproved proposal whose target/quota/config/cleanup readbacks need refresh before external execution.
'''
(group/'RESULTS.md').write_text(text,encoding='utf-8')
(group/'PR_DESCRIPTION.md').write_text(f'''# Proposed PR — N00 proxy ingress and physical dispatch TTL

Branch codex/n00-proxy-dispatch-deadline; base233848b;source{sha}. No remote PR/push/deploy.

Fix counted fixture transport's resettable body deadline and admission-to-dispatch TTL gap; clamp physical request timeout to remaining TTL. Before dispatch stays rejected/zero-hop; after dispatch stays unknown/held across restart. No auth/domain/UI/schema/roles/provider change.

RED1pass/3fail observed; GREEN28focused,304reportedroot(303leaves),8STRICTcrypto,portable6/vercel6 actual retained-output browser fixtures,all0fail/error/skip;types/lint/generated84 exit0. No new build; immutable historical outputs/hash provenance clearly separated. Exact commands/raw evidence/counters in RESULTS.md.

Rollback followingmetadata then source{sha};no DB/data undo,retain admitted/unknown journals. FullN00/NA01/original302/realNeon/Google/Admincleanup/nativeallchannel/independentreview remainOPEN;no production acceptance implied.
''',encoding='utf-8')
# Only N00 and explicit current pointers. Preserve historical N00 subrecords.
p=root/'TASKS.json';d=json.loads(p.read_text(encoding='utf-8-sig'));t=next(t for t in d['tasks'] if t['id']=='N00');t.update(status='local-spike-partial',code_status='local counted proxy absolute ingress and dispatch TTL repaired;Auth0 retained',verification_status='304reportedroot(303leaves)/28focused/8crypto/6UIeach pass0fail/skip;retained compiled outputs;no new build/fullN00open',source_sha=sha,release_status='not-deployed');t['proxy_dispatch_deadline_20261005']=record;d['reviewed_source_sha']=sha;d['latest_local_verification_source_sha']=sha;d['next_eligible']=record['next_eligible'];d['selected_followups'].append('N00 local ingress and physical dispatch deadline');p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=root/'docs/buyeros/remaining/TASKS.json';d=json.loads(p.read_text(encoding='utf-8-sig'));d['prior_q11_capability_guidance_checkpoint_20261005']=d['latest_local_verification_checkpoint'];d['prior_native_sdk_cleanup_checkpoint_20261005']=d['latest_local_auth_checkpoint'];d['latest_local_verification_checkpoint']=record;d['latest_local_auth_checkpoint']=record;p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=root/'docs/buyeros/remaining/AUDIT_FIX_CASE_STATUS_20261003.csv';raw=p.read_bytes()
with p.open(encoding='utf-8-sig',newline='') as f:r=csv.DictReader(f);fields=r.fieldnames;rows=list(r)
r=next(r for r in rows if r['case_id']=='NA01');r.update(repair_status='partial-local-proxy-deadlines;fullN00open',reviewed_source_sha=sha,repair_source_sha=sha,code_status='absolute-body-deadline;recheck/clamp-dispatchTTL;post-dispatchunknownheld;fixture-only',verification_status='304reportedroot(303leaves)+28focused+8crypto+6UIeach0fail/skip;retainedbuild/no newbuild;original302/realNeonopen',release_status='not-deployed');r['repair_evidence']+=';'+record['evidence']
with p.open('w',encoding='utf-8-sig' if raw.startswith(b'\xef\xbb\xbf') else 'utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
p=root/'docs/buyeros/CURRENT_STATUS.md';old=p.read_text(encoding='utf-8-sig');header=f'''# Current N00 local proxy-deadline checkpoint — 2026-10-05

Reviewed source `{sha}` on codex/n00-proxy-dispatch-deadline. **Full N00/NA01/F20/Q11 remain OPEN.** [Red/green commands, actual fixture counters, screenshots and rollback](evidence/audit-fixes-20261003/N00_PROXY_DISPATCH_DEADLINE/RESULTS.md).

| Current field | Evidence / disposition |
| --- | --- |
| Local source | `{sha}`;local harness/test/plan3files105insertions/8deletions |
| Application/API/UI source | 5aaf6492ec10078e4f1a4fa5b17efd41c5673eba unchanged in this follow-up |
| Deployed source | Unknown / not checked;no new deployment;older deployment records historical |
| Schema/runtime role/selector/epoch | Source0037_bulk_manifests;0migration;production unknown;peer0038unmerged |
| Provider capabilities | Unconfigured/disabled;no real provider/price/quota/canary proof |
| Local evidence | 28focused/304reportedroot(303leaves)/8STRICTcrypto/portable6+vercel6 UI;0fail/error/skip |
| Build provenance | No new build;verified historical compiled base2eb4b38/c756596,14overlays/95portable+2625Vercel files;fresh current host proxy |
| Contracts / responsibility / checked at | Generated84=70+14/types/lint exit0;Identity/QA;`{stamp}` |
| Next eligible | N00 native browser/CLI containment gap audit/preparation;real auth separately gated |

Local HTTP/persistence/SDK diagnostic integration verified with fictional identity. Each built-output UI fixture has38reservations/37hops/1expectedunknown/0pending/0external;owned children/root/journal removed. Original302/realNeon/Google/Admincleanup/fullnativeaccounting/independent/human gatesOPEN;N01/N02 prerequisite unchanged. Auth0/canonical users/memberships/RLS/HMAC retained;delivery403;no full staff/live/pilot acceptance. Q11 guidance child and other24 tasks/97 cases/3433 prior artifacts preserved.

## Historical checkpoints below — original source/time scopes only

''';p.write_text(header+old,encoding='utf-8')
p=root/'docs/buyeros/REMAINING_DEVELOPMENT_STATUS.md';old=p.read_text(encoding='utf-8-sig').replace('> Current Q11 guidance checkpoint:','> Historical Q11 guidance checkpoint:',1);p.write_text(f'> Current N00 local deadline checkpoint: source `{sha}`;absolute body wait/dispatchTTL repaired. 28focused/304reportedroot/8crypto/6UIeach pass0fail/error/skip;actual retained SDK outputs hash-verified,no newbuild/no external/authcutover/migration/deploy. FullN00/NA01/Q11 open. [Current status](CURRENT_STATUS.md); [exact evidence](evidence/audit-fixes-20261003/N00_PROXY_DISPATCH_DEADLINE/RESULTS.md). Next local native browser/CLI containment gap audit.\n\n'+old,encoding='utf-8')
p=root/'docs/buyeros/RELEASE_READINESS.md';old=p.read_text(encoding='utf-8-sig');end=old.index('## Historical T30 record');p.write_text(f'# Current release readiness — 2026-10-05\n\n**NOT READY FOR LIVE PILOT.** [CURRENT_STATUS.md](CURRENT_STATUS.md) is the current table. Reviewed local harness source `{sha}` repairs N00 deadline gaps;304reportedroot/28focused/8crypto/6UIeach pass0fail/skip. Actual retained SDK output reuse is separate from new builds (none this slice);application/API/UI source5aaf649 unchanged. FullN00/original302/realAuth/provider/recovery/staff/human/independentreview/productionreadback gatesOPEN. Auth0/delivery403 retained;no deployment or migration.\n\n'+old[end:],encoding='utf-8')
print(f'Prepared local checkpoint {sha}; fullN00 remains open')
