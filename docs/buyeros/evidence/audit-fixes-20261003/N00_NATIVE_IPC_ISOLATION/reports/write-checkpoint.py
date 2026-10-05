from pathlib import Path
import json,csv,subprocess,hashlib,shutil,datetime,xml.etree.ElementTree as E
P=Path('test-results/n00-native-ipc-isolation')
GROUP=Path('docs/buyeros/evidence/audit-fixes-20261003/N00_NATIVE_IPC_ISOLATION')
SHA=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip()
BASE='a06e134d807850c6fe8f4324a877d187e1ed5387'
assert SHA=='779138aa5335eb829a97a80bbc80430a32201c1a'
load=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
counts=load(P/'final-checks.json');obs=load(P/'final-native-observations.json')
assert counts['root-green']['pass']==307 and counts['root-green']['fail']==counts['root-green']['skip']==0
assert len(obs)==1 and obs[0]['cleanup']['complete'] and obs[0]['direct_http_requests']==0
clock=datetime.datetime.now(datetime.timezone.utc).isoformat()
NEXT='N00 explicit counted APIRequestContext adapter and parent/browser/control-plane OS isolation composition; no real execution until full containment, cleanup and fresh exact authorization'
check={'status':'local-fixed-native-worker-verified;full-N00-open','source_sha':SHA,'base_sha':BASE,'branch':'codex/n00-native-ipc-isolation','checked_at':clock,'evidence':str(GROUP/'RESULTS.md').replace('\\','/'),'application_source_sha':'5aaf6492ec10078e4f1a4fa5b17efd41c5673eba','runtime_proxy_source_sha':'9e1ef78d4ae61429dee0d4b6fd62de9cbfdd7c92','dedicated_browser_source_sha':'362b60dd42d034e229b9fa5f51a47d6ffcd4ec04','checks':counts,'static_gates':load(P/'static-final.json')|load(P/'integration-gates.json'),'native_observation':obs[0],'new_node_cases':3,'new_build':False,'fixture_only':True,'canonical_db_connection':False,'real_Neon_verified':False,'parent_os_contained':False,'browser_os_contained':False,'arbitrary_provider_cli_contained':False,'external_requests':0,'full_N00_open':True,'original302_rerun':False,'schema_head':'0037_bulk_manifests','migrations':0,'operation_count':84,'original_operations':70,'extensions':14,'independent_review':'pending','deployed_sha':None,'next_eligible':NEXT,'rollback':'Revert following metadata commit then source779138a; no DB/data rollback, retain admitted/unknown journal holds.'}
save(P/'checkpoint.json',check)
root=load('TASKS.json');n=next(t for t in root['tasks'] if t['id']=='N00')
n['prior_browser_native_summary_20261005']={k:n[k] for k in ['code_status','verification_status','release_status','base_sha','source_sha','evidence','rollback','next_action']}
n.update({'code_status':'fixed fictional native worker counted IPC and network-none isolation; Auth0/application unchanged','verification_status':'308 reported root/307 JUnit leaves, native3 included; Chromium5/strict crypto8;0fail-error-skip; full containment/Neon/original302 OPEN','base_sha':BASE,'source_sha':SHA,'evidence':check['evidence'],'rollback':check['rollback'],'next_action':NEXT,'full_gate_passed':False})
n['checks']['native_ipc_isolation']=check
n['native_ipc_isolation_20261005']=check
for limit in ['OS containment covers fixed Linux child only; parent/broker/browser/APIRequestContext/arbitrary provider CLI remain OPEN','Cached local image only; no real SDK/browser/provider CLI provisioned into container','Independent review and true Neon/Google/managed cleanup/original302 remain OPEN']:
 if limit not in n['limits']:n['limits'].append(limit)
root.update({'reviewed_source_sha':SHA,'latest_local_verification_source_sha':SHA,'next_eligible':NEXT})
root['selected_followups'].append('N00 counted native IPC and disposable fixed worker OS isolation (local-only)')
root['future_eligible']=[NEXT if s.startswith('N00 full real-transport coverage') else s for s in root['future_eligible']]
save('TASKS.json',root)
registry=load('docs/buyeros/remaining/TASKS.json')
for field in ['auth','verification']:registry['prior_native_browser_'+field+'_checkpoint_20261005']=registry['latest_local_'+field+'_checkpoint']
registry['latest_local_auth_checkpoint']=check;registry['latest_local_verification_checkpoint']=check
save('docs/buyeros/remaining/TASKS.json',registry)
casepath=Path('docs/buyeros/remaining/AUDIT_FIX_CASE_STATUS_20261003.csv')
with casepath.open(encoding='utf-8-sig',newline='') as f:
 reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
assert len(rows)==98
r=next(r for r in rows if r['case_id']=='NA01')
r.update({'repair_status':'partial-local; full N00 open','repair_evidence':r['repair_evidence']+'; '+check['evidence'],'reviewed_source_sha':SHA,'repair_source_sha':SHA,'code_status':'counted fixed-native IPC/network-none child implemented; Auth0 retained','verification_status':'root308reported307leaves/native3/Chromium5/crypto8 pass0fail-error-skip;parent-browser-APIRequestContext-arbitraryCLI/realNeon OPEN;original302 not rerun','release_status':'not-deployed; full N00 and real-Neon gates open'})
with casepath.open('w',encoding='utf-8',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(rows)
current=f'''# Current N00 counted native IPC checkpoint — 2026-10-05

Author-reviewed local source `{SHA}` on `codex/n00-native-ipc-isolation`. **Full N00 / NA01 / F20 remains OPEN.** [Commands, exact raw outputs, probes, screenshot and rollback](evidence/audit-fixes-20261003/N00_NATIVE_IPC_ISOLATION/RESULTS.md).

| Current field | Verified scope |
| --- | --- |
| Code | Fixed fixture native worker uses private counted IPC into the existing journal owner; actual child uses network none |
| RED → GREEN | Missing IPC: 0pass/2fail; behavioral native isolation: 2pass/1fail with 3 direct HTTP; final new3 pass, 0 direct HTTP |
| Fresh root | 308 reported tests /307 JUnit leaf cases pass, 0fail/error/skip; 466803.7974ms |
| Fresh other gates | Chromium5/EdDSA8 pass, zero failures/errors/skips; types/lint/generated contracts/routes84 exit0 |
| Local integration | Owned positive control: 3 HTTP requests plus native TCP; isolated child rawHTTP/fetch/TCP/subprocess all refused, counted IPC works, unknown hold survives restart |
| Ownership / cleanup | Exact own labels/IDs inspected before removal, absence confirmed; all this slice's owned Docker resources absent |
| OS isolation limits | Parent/broker/browser/APIRequestContext/arbitrary provider CLI/control-plane OPEN; no real provider runtime in the fixed worker |
| Application / schema | Application5aaf649, proxy9e1ef78, browser362b60d unchanged; head0037_bulk_manifests; migrations0; peer0038 unmerged |
| Builds / deployment | No new build or deployment; retained app SSR output is historical source5aaf649; deployedSHA unproven |
| Review / next | Author self-review only; independent pending. Next: counted APIRequestContext and parent/browser/control-plane isolation composition |

Auth0/canonical users/memberships/roles/RLS/historical actors/Cloudflare HMAC retained; delivery403. Original302 unchanged/not rerun; true Neon/Google/managed cleanup/full staff acceptance unverified. Other tasks/cases, original evidence and foreign worktrees preserved. No accounts, email, production DB/schema, paid provider, external mutation, push or deployment.

## Historical checkpoints below — original source and scope only

'''
p=Path('docs/buyeros/CURRENT_STATUS.md');p.write_text(current+p.read_text(encoding='utf-8-sig'),encoding='utf-8')
p=Path('docs/buyeros/REMAINING_DEVELOPMENT_STATUS.md');old=p.read_text(encoding='utf-8-sig');notice=f'''> Latest local checkpoint (2026-10-05): `{SHA}`. Counted fixed-native IPC and actual network-none child verified; root308 reported/307leaves, Chromium5, crypto8 all pass0fail/error/skip. Positive control3HTTP+TCP, isolated native4probes refused/0directHTTP; unknown intent retains hold after restart. No new build/deploy/auth cutover; full N00/NA01/parent/browser/APIRequestContext/arbitraryCLI remain OPEN. [Evidence and rollback](evidence/audit-fixes-20261003/N00_NATIVE_IPC_ISOLATION/RESULTS.md). Older notices retain their historical scope.

'''
checkpoint=f'''\n\n## 2026-10-05 N00 counted native IPC and fixed-worker isolation ({SHA[:7]})

{current.split('## Historical checkpoints below')[0]}
'''
p.write_text(notice+old+checkpoint,encoding='utf-8')
p=Path('docs/buyeros/RELEASE_READINESS.md');old=p.read_text(encoding='utf-8-sig');p.write_text(f'''# Current release decision — NOT READY (2026-10-05)

Local harness source `{SHA}`: fixed-native counted IPC and network-none child verified; root308 reported/307leaves, Chromium5, crypto8 pass0fail/error/skip; types/lint/generated84 exit0. Actual own sink/control exercises native3HTTP+TCP; isolated child's4native paths refuse/0directHTTP; owned containers/networks removed with absence confirmed. Parent/broker/browser/APIRequestContext/arbitrary provider CLI/control-plane are outside this child's OS boundary and remain OPEN. Full N00/original302/realNeon/Google/Admincleanup/independent review/live staff gates OPEN. Auth0/canonical actors/RLS/HMAC/delivery403 retained. No new build, migration, push, external provider action or deployment; production source not asserted. [Evidence/rollback](evidence/audit-fixes-20261003/N00_NATIVE_IPC_ISOLATION/RESULTS.md). Historical release records below retain their original scope.

## Historical release decisions below

'''+old,encoding='utf-8')
progress=Path('.superpowers/sdd/2026-10-05-n00-native-ipc-isolation/progress.md');progress.write_text(progress.read_text(encoding='utf-8-sig')+f'''\nTask1/Task2 bounded local slices complete: final whole root308reported/307leaf pass0fail/error/skip, Chromium5/crypto8 pass; types/lint/contracts/routes0. Fixed child networknone/native probes0direct; positivecontrol3HTTP+TCP; unknown hold survives new container/journal. Sourcecommit {SHA}; author review only, independent pending. Full original N00 Task2/NA01/F20 remain OPEN; parent/browser/APIRequestContext/arbitraryCLI/control-plane/trueNeon/cleanup/original302 need their separate evidence. Metadata checkpoint in progress.\n''',encoding='utf-8')
GROUP.mkdir(parents=True,exist_ok=False);(GROUP/'reports').mkdir();(GROUP/'screenshots').mkdir()
exclude={'preservation-before.json','root-tasks-before.json','registry-before.json','cases-before.csv','operations-before.csv','accounting-fixture.png','source.patch'}
for f in P.iterdir():
 if f.is_file() and f.name not in exclude:shutil.copyfile(f,GROUP/'reports'/f.name)
shutil.copyfile(P/'accounting-fixture.png',GROUP/'screenshots'/'accounting-fixture.png');shutil.copyfile(P/'source.patch',GROUP/'source.patch');shutil.copyfile(progress,GROUP/'progress.md')
(GROUP/'.gitattributes').write_text('* -text whitespace=cr-at-eol\nreports/** -text -diff\nscreenshots/** -text -diff\nsource.patch -text -diff -whitespace\n',encoding='utf-8')
(GROUP/'PR_DESCRIPTION.md').write_text(f'''# N00 counted native IPC and fixed worker isolation — local proposal

## Scope

Base `{BASE}`; source `{SHA}`. Existing isolated `codex/n00-native-ipc-isolation`, five source/plan files, 136 added lines. No remote PR/push/deployment. Metadata/evidence is a following local commit.

- Fixed fixture Linux worker sends bounded request tuples over private pipes; existing execution boundary and RealRunJournal own budget/intent/unknown holds.
- Explicit local Docker endpoint and immutable cached image, pull never. Own internal positive-control sink; actual worker network none, read-only/nonroot/cap-drop/no mounts or public ports.
- Exact owned label/ID cleanup and absence; single bounded readonly inspect retry after observed blank-stderr killed timeout. Writes are not retried.
- Three meaningful new tests, RED observed, final root308 reported/307leaves pass; Chromium5/crypto8 pass; types/lint/contracts84/routes exit0. Original assertion/DB guards preserved.

## Open release gates

Full N00/NA01/F20 remain OPEN. Fixed child only; parent/broker/browser/APIRequestContext/arbitrary provider CLI/control-plane containment and true Neon/Google/admincleanup/original302/independent review remain open. Auth0 remains current. No accounts/email/identity links/membership grants/production changes/provider activation/migrations/deployments.

## Review focus

Single budget owner, canonical tuple+fingerprint, stream/request limits, local context/image only, environment allowlist, exact resource ownership and absence on failures, unknown accepted writes held across restart. Author self-review recorded; independent review pending. Fresh raw failed attempts and final reports retained. Reviewer must not interpret fixture routes/screenshot as live/staff acceptance.

## Rollback

Revert following metadata commit then `{SHA}`. Source reverse patch applicability checked only, not a runtime rollback rehearsal. No schema/data rollback. Preserve admitted/unknown journal entries and reconcile accepted outcomes before any retry. See RESULTS.md for commands, environment, pass/fail/error/skip and cleanup evidence.
''',encoding='utf-8')
print(json.dumps({'source':SHA,'group':str(GROUP),'reports':len(list((GROUP/'reports').iterdir())),'metadata_files':6},indent=2))
