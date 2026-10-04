import json,pathlib,hashlib,subprocess
root=pathlib.Path.cwd();base='e0256f303502d4332400a837b99903926f74c842';area=root/'test-results/neon-execution'
def git(*args,cwd=root):return subprocess.check_output(['git',*args],cwd=cwd,stderr=subprocess.PIPE)
files=git('diff','--cached','--name-only').decode().splitlines()
for p in files:assert (root/p).read_bytes().replace(b'\r\n',b'\n')==git('show',':'+p).replace(b'\r\n',b'\n'),p
prior=[]
for name in ['N00_LOCAL','N00_CALLBACK','N00_REAL_PREFLIGHT','N00_COUNTED_TRANSPORT','N00_REAL_RUNTIME','N00_RUNTIME_BUILT','N00_RUNTIME_FLOW']:
 directory=root/'docs/buyeros/evidence/audit-fixes-20261003'/name;manifest=json.loads((directory/'SHA256SUMS.json').read_text(encoding='utf-8'))
 for entry in manifest:
  p=directory/entry['path'];data=p.read_bytes();assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256'],p
 prior.append({'group':name,'payloads':len(manifest),'unchanged':True})
protected=['services/api/tests/conftest.py','services/worker/tests/conftest.py','services/api/tools/serve_e2e_fixture.py','services/worker/tests/fixtures/run_browser_research.py','services/generated/buyeros-api.ts','docs/superpowers/plans/2026-10-03-buyeros-gpt61-fixes.md','docs/buyeros/remaining/API_OPERATION_STATUS.csv','tests/e2e-fixture-cleanup.test.mjs','tests/deployment/cloudflare-release-config.test.mjs','tests/vercel-render.test.mjs']
for p in protected:assert (root/p).read_bytes().replace(b'\r\n',b'\n')==git('show',base+':'+p).replace(b'\r\n',b'\n'),p
input_root=root/'docs/buyeros/inputs/audit-20261003';inputs=json.loads((input_root/'SHA256SUMS.json').read_text(encoding='utf-8'))
for entry in inputs:
 p=input_root/entry['path'];data=p.read_bytes();assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256'],p
worktrees=[]
for checkout in [pathlib.Path('C:/Users/laich/Documents/BuyerOS'),pathlib.Path('C:/Users/laich/.codex/worktrees/audit-fixes-20261003/BuyerOS'),pathlib.Path('C:/Users/laich/.codex/worktrees/neon-auth-migration/BuyerOS')]:
 status=git('status','--porcelain',cwd=checkout);worktrees.append({'worktree':checkout.as_posix(),'head':git('rev-parse','HEAD',cwd=checkout).decode().strip(),'dirty_paths':len(status.splitlines()),'binary_diff_sha256':hashlib.sha256(git('diff','--binary','HEAD',cwd=checkout)).hexdigest()})
expected=json.loads((root/'docs/buyeros/evidence/audit-fixes-20261003/N00_RUNTIME_FLOW/PRESERVATION.json').read_text(encoding='utf-8'))['unrelated_worktrees'];assert worktrees==expected,(worktrees,expected)
proof={'base_sha':base,'source_index_matches':files,'prior_N00':prior,'prior_N00_payloads':sum(p['payloads'] for p in prior),'inputs':len(inputs),'protected_unchanged':protected,'unrelated_worktrees':worktrees,'operation_rows':84,'all_unchanged':True}
(area/'preservation-before-metadata.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8');print(json.dumps({'prior_payloads':proof['prior_N00_payloads'],'inputs':len(inputs),'protected':len(protected),'source_files':len(files),'unrelated_worktrees_unchanged':True}))
tasks=json.loads((root/'TASKS.json').read_text(encoding='utf-8'));item=next(v for v in tasks['tasks'] if v['id']=='N00');print(json.dumps({k:v for k,v in item.items() if k!='checks'},ensure_ascii=False));print('check_keys',list(item['checks']));print('top_keys',list(tasks))
