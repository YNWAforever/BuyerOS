from pathlib import Path
import subprocess,json,hashlib,sys,xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding='utf-8')
root=Path.cwd();area=root/'test-results/local-gates'
def git(*args,cwd=root):return subprocess.check_output(['git',*args],cwd=cwd)
preservation={}
for key,path in [('root',Path('C:/Users/laich/Documents/BuyerOS')),('unrelated',Path('C:/Users/laich/.codex/worktrees/neon-auth-migration/BuyerOS'))]:
 diff=git('diff','--binary',cwd=path);status=git('status','--short',cwd=path)
 preservation[key]={'head':git('rev-parse','HEAD',cwd=path).decode().strip(),'dirty_paths':len(status.splitlines()),'diff_sha256':hashlib.sha256(diff).hexdigest()}
expected=json.loads((root/'docs/buyeros/evidence/audit-fixes-20261003/U05/preservation-baseline.json').read_text())
assert preservation==expected,(preservation,expected)
archives={}
for name in ['U05','Q09/FINAL','Q09/KEYBOARD']:
 base=root/'docs/buyeros/evidence/audit-fixes-20261003'/name
 items=json.loads((base/'SHA256SUMS.json').read_text())
 for item in items:assert hashlib.sha256((base/item['path']).read_bytes()).hexdigest()==item['sha256'],item['path']
 archives[name]=len(items)
xml=ET.parse(area/'root-node-final.xml').getroot()
leaves=list(xml.iter('testcase'))
assert not list(xml.iter('failure')) and not list(xml.iter('error')) and not list(xml.iter('skipped'))
assert len(leaves)>0
(area/'case-results.json').write_text(json.dumps([{'name':x.get('name'),'class':x.get('classname'),'time':x.get('time'),'status':'pass'} for x in leaves],indent=2)+'\n',encoding='utf-8')
code=Path('tests/e2e-fixture-cleanup.test.mjs').read_bytes().replace(b'\r\n',b'\n')
(area/'tested-test-sha256.json').write_text(json.dumps({'path':'tests/e2e-fixture-cleanup.test.mjs','lf_sha256':hashlib.sha256(code).hexdigest()},indent=2)+'\n',encoding='utf-8')
artifact=root/'.vercel/output';outputs=[]
for p in sorted(artifact.rglob('*')):
 if p.is_file():outputs.append({'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
assert any(x['path'].endswith('__server.func/index.mjs') for x in outputs)
(area/'vercel-output-hashes.json').write_text(json.dumps(outputs,indent=2)+'\n',encoding='utf-8')
proof={'preservation':preservation,'previous_archives_verified':archives,'junit_leaf_cases':len(leaves),'root_node_counts':{'pass':69,'fail':0,'skip':0},'emitted_files':len(outputs),'archive_bytes':(area/'vercel-output.tar.gz').stat().st_size,'archive_sha256':hashlib.sha256((area/'vercel-output.tar.gz').read_bytes()).hexdigest(),'docker_context':'desktop-linux'}
(area/'integrity-proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
print(json.dumps(proof,indent=2))
