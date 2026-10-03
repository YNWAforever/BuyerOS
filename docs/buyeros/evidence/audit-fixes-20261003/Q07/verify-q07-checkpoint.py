import csv,hashlib,io,json,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
import yaml
r=Path.cwd();e=r/'docs/buyeros/evidence/audit-fixes-20261003/Q07';source='a2696e1a317342a64c9b9b29b0585ae8ddff54bf';base='c09eec2872b1fa73719c0894c14d01c23a13bbdc'
def git(*args):return subprocess.check_output(['git',*args],cwd=r)
def rows(p):
 with Path(p).open(encoding='utf-8-sig',newline='') as f:
  rd=csv.DictReader(f);return rd.fieldnames,list(rd)
h=lambda b:hashlib.sha256(b).hexdigest();norm=lambda b:b.replace(b'\r\n',b'\n')
assert git('rev-parse','HEAD').decode().strip()==source
reports={}
for filename,expected in [('q07-api-final.xml',47),('q07-worker-final.xml',11),('q07-ui-final.xml',12)]:
 suites=ET.parse(e/filename).getroot().findall('testsuite');assert suites
 totals={k:sum(int(s.get(k,'0')) for s in suites) for k in ['tests','failures','errors','skipped']};assert totals==dict(tests=expected,failures=0,errors=0,skipped=0)
 command=['services/api/.venv/Scripts/python.exe','scripts/check-required-tests.py','--junit',str(e/filename)];run=subprocess.run(command,cwd=r,capture_output=True,text=True,check=True)
 reports[filename]={'totals':totals,'suite_seconds':sum(float(s.get('time','0')) for s in suites),'checker_command':command,'checker_stdout':run.stdout,'checker_exit':run.returncode}
inputs=r/'docs/buyeros/inputs/audit-20261003';manifest=json.loads((inputs/'SHA256SUMS.json').read_text(encoding='utf-8-sig'));assert len(manifest)==31
for v in manifest:
 b=(inputs/v['path']).read_bytes();assert len(b)==v['bytes'] and h(b)==v['sha256'],v['path']
f,original=rows(inputs/'BuyerOS_Test_Cases_2026-10-03.csv');_,current=rows(r/'docs/buyeros/remaining/AUDIT_FIX_CASE_STATUS_20261003.csv');assert len(original)==len(current)==98;assert original==[{k:v[k] for k in f} for v in current]
before=list(csv.DictReader(io.StringIO(git('show',base+':docs/buyeros/remaining/AUDIT_FIX_CASE_STATUS_20261003.csv').decode('utf-8-sig'))));changed_cases=[v['case_id'] for a,v in zip(before,current) if a!=v];assert set(changed_cases)=={'A02','A07'}
assert (r/'docs/superpowers/plans/2026-10-03-buyeros-gpt61-fixes.md').read_bytes()==Path('C:/Users/laich/Downloads/2026-10-03-buyeros-gpt61-fixes.md').read_bytes()
assert not git('diff','--','docs/buyeros/remaining/TASKS.json')
_,ops=rows(r/'docs/buyeros/remaining/API_OPERATION_STATUS.csv');oldops=list(csv.DictReader(io.StringIO(git('show',base+':docs/buyeros/remaining/API_OPERATION_STATUS.csv').decode('utf-8-sig'))));assert len(oldops)==len(ops)==80
changed_ops=[]
for a,v in zip(oldops,ops):
 for k in ['operation_id','method','path','primary_task','baseline_status','current_code','deployed']:assert a[k]==v[k],(v['operation_id'],k)
 if a!=v:changed_ops.append(v['operation_id'])
assert set(changed_ops)=={'generateDraft','getDraft','editDraft','requestDraftReview','approveDraft','exportDraft','downloadExport'}
spec=yaml.safe_load((r/'docs/buyeros/contracts/openapi.proposed.yaml').read_text(encoding='utf-8'));operations={item['operationId'] for value in spec['paths'].values() for method,item in value.items() if method in {'get','post','patch','put','delete','options','head'}}
assert operations=={v['operation_id'] for v in ops} and len(operations)==80
oldtasks=json.loads(git('show',base+':TASKS.json'));tasks=json.loads((r/'TASKS.json').read_text(encoding='utf-8-sig'));assert len(tasks['tasks'])==25
for a,v in zip(oldtasks['tasks'],tasks['tasks']):
 if v['id']!='Q07':assert a==v,v['id']
assert tasks['scope']==oldtasks['scope']+['Q07'] and tasks['next_eligible']=='Q12'
tested=json.loads((e/'q07-tested-source.json').read_text());paths=git('diff','--name-only',base,source).decode().splitlines();assert len(paths)==7 and set(paths)=={v['path'] for v in tested['files']}
source_proof=[]
for v in tested['files']:
 b=(r/v['path']).read_bytes();blob=git('show',source+':'+v['path']);assert h(b)==v['sha256'];assert h(blob)==v['staged_blob_sha256'];assert norm(b)==norm(blob)
 source_proof.append({'path':v['path'],'tested_working_sha256':h(b),'committed_blob_sha256':h(blob),'byte_equal':b==blob,'newline_normalized_equal':True})
assert not git('diff','--name-only',base,source,'--','services/api/alembic/versions','docs/buyeros/contracts/openapi.proposed.yaml','services/generated/api-types.ts')
assert '0036_checkpoint_schema_grants (head)' in (e/'q07-alembic-heads.log').read_text(encoding='utf-8-sig')
subprocess.run(['git','apply','--reverse','--check',str(e/'Q07.patch')],cwd=r,check=True);subprocess.run(['git','apply','--check',str(e/'generation-pause-rollback.patch')],cwd=r,check=True)
cleanup=json.loads((e/'q07-fixture-cleanup.json').read_text());assert cleanup['ui_marker_absent'] and cleanup['db_marker_absent'] and cleanup['removed'] and cleanup['owner']=='052d6a686de9'
assert 'ledger: Task 1: complete' in (e/'q07-task-done.log').read_text(encoding='utf-8-sig')
# Every relative local Markdown link in Q07 RESULTS resolves.
import re
for target in re.findall(r'\]\(([^)]+)\)',(e/'RESULTS.md').read_text(encoding='utf-8')):
 if not target.startswith('http'):assert (e/target).exists(),target
proof={'base_sha':base,'reviewed_source_sha':source,'deployed_sha':None,'reports':reports,'product_source':source_proof,'input_files_verified':31,'original_case_rows_and_columns_preserved':98,'changed_case_ids':changed_cases,'operations':80,'original_operations':70,'extensions':10,'changed_existing_operation_ids':changed_ops,'new_operation_ids':[],'other_task_records_preserved':24,'new_migrations':0,'migration_source_head':'0036_checkpoint_schema_grants','source_reverse_patch_check_exit':0,'recommended_rollback':'generation-pause-rollback.patch; no full revert','rollback_patch_check_exit':0,'rollback_browser_rehearsal':'not-run','cleanup':cleanup,'independent_review':'pending'}
(e/'q07-checkpoint-integrity.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8',newline='\n')
entries=[]
for p in sorted(e.iterdir(),key=lambda p:p.name):
 if p.is_file() and p.name!='SHA256SUMS.json':
  b=p.read_bytes();entries.append({'path':p.name,'bytes':len(b),'sha256':h(b)})
(e/'SHA256SUMS.json').write_text(json.dumps(entries,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'reports':{k:v['totals'] for k,v in reports.items()},'artifacts':len(entries),'source_files':7,'original_inputs':31,'original_cases':98,'changed_cases':changed_cases,'operations':80,'source':source}))
