import csv,io,json,hashlib,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
root=Path.cwd();out=root/'docs/buyeros/evidence/audit-fixes-20261003/Q12';base='c7136fbceb1567bca87215b57d142e8137b8968d'
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*a,cwd=root):return subprocess.check_output(['git','-C',str(cwd),*a],stderr=subprocess.DEVNULL)
def write(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
pre=json.loads((out/'q12-preflight-preservation.json').read_text(encoding='utf-8'));worktrees={}
for key,path in [('original',Path('C:/Users/laich/Documents/BuyerOS')),('neon',Path('C:/Users/laich/.codex/worktrees/neon-auth-migration/BuyerOS'))]:
 head=git('rev-parse','HEAD',cwd=path).decode().strip();status=git('status','--porcelain',cwd=path).decode();assert head==pre[key+'_head']
 entry={'path':str(path),'head':head,'status_lines':len(status.splitlines()),'read_only':True}
 if key=='original':assert not status.strip()
 else:
  diff=git('diff','--binary','HEAD',cwd=path);assert sha(diff)==pre['neon_diff_sha256'];assert entry['status_lines']==pre['neon_dirty_paths'];entry['raw_diff_sha256']=sha(diff)
 worktrees[key]=entry
write(out/'q12-unrelated-worktrees.json',worktrees)
reports={}
for name,n in [('q12-api-final.xml',85),('q12-ui-named-final.xml',4)]:
 p=out/name;suites=list(ET.parse(p).getroot().iter('testsuite'));totals={k:sum(int(x.attrib.get(k,'0')) for x in suites) for k in ['tests','failures','errors','skipped']};assert totals=={'tests':n,'failures':0,'errors':0,'skipped':0}
 command=[str(root/'services/api/.venv/Scripts/python.exe'),'scripts/check-required-tests.py','--junit',str(p)];r=subprocess.run(command,capture_output=True,text=True);assert r.returncode==0,r.stdout+r.stderr
 reports[name]={'totals':totals,'checker_command':command,'checker_exit':r.returncode,'checker_stdout':r.stdout,'suite_seconds':sum(float(x.attrib.get('time','0')) for x in suites)}
ops=list(csv.DictReader((root/'docs/buyeros/remaining/API_OPERATION_STATUS.csv').open(encoding='utf-8')));assert len(ops)==81 and len({x['operation_id'] for x in ops})==81
baseline=Path('C:/Users/laich/Downloads/BuyerOS_Codex_GPT6_Sol_Implementation_Pack_2026-09-27/API_OPERATION_COVERAGE.csv'); (out/'original-70-api-operation-coverage.csv').write_bytes(baseline.read_bytes()); historical=list(csv.DictReader(baseline.open(encoding='utf-8-sig')))
original_ids={x.get('operation_id') for x in historical};assert len(original_ids)==70 and None not in original_ids
current_ids={x['operation_id'] for x in ops};assert original_ids<=current_ids
coverage={'original':len(original_ids),'extensions':sorted(current_ids-original_ids),'total':len(ops),'original_missing':[],'release_live_coverage_not_asserted':True}
write(out/'q12-operation-coverage.json',coverage)
local=json.loads((out/'q12-local-checkpoint.json').read_text(encoding='utf-8'));local.update({'reports':reports,'unrelated_worktrees_preserved':True,'operation_coverage':coverage,'raw_artifact_byte_checks':'manifest then staged/committed verification; .gitattributes * -text'})
write(out/'q12-checkpoint-integrity.json',local)
manifest=[]
for p in sorted(out.rglob('*')):
 if p.is_file() and p.name!='SHA256SUMS.json':
  b=p.read_bytes();manifest.append({'path':p.relative_to(out).as_posix(),'bytes':len(b),'sha256':sha(b)})
write(out/'SHA256SUMS.json',manifest)
print(json.dumps({'reports':reports,'coverage':coverage,'manifest_files':len(manifest),'bytes':sum(x['bytes'] for x in manifest),'unrelated_preserved':True},ensure_ascii=False))

