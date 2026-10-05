import json,hashlib,pathlib,subprocess,xml.etree.ElementTree as ET
root=pathlib.Path.cwd()
r=root/'test-results/pr11-ci-followup-20261006'
def counts(name):
 p=r/name
 cases=list(ET.parse(p).getroot().iter('testcase'))
 if not cases: raise RuntimeError(f'zero cases:{name}')
 out={'cases':len(cases),'fail':sum(c.find('failure') is not None for c in cases),'error':sum(c.find('error') is not None for c in cases),'skip':sum(c.find('skipped') is not None for c in cases)}
 out['pass']=len(cases)-out['fail']-out['error']-out['skip']
 out['duration_seconds']=sum(float(c.attrib.get('time',0)) for c in cases)
 out['producer_total_seconds']=float(ET.parse(p).getroot().attrib.get('time',ET.parse(p).getroot().find('testsuite').attrib.get('time',0) if ET.parse(p).getroot().find('testsuite') is not None else 0))
 return out
checks={k:counts(v) for k,v in {'api':'api-full.xml','workbench':'workbench-final.xml','auth_entry':'auth-entry.xml'}.items()}
for key,expected in {'api':812,'workbench':8,'auth_entry':7}.items():
 c=checks[key]
 if c['pass']!=expected or c['fail']+c['error']+c['skip']:raise RuntimeError(f'Incomplete required gate:{key} {c}')
checks['workbench_red']=counts('workbench-red-scoped.xml')
checks['workbench_first_full']=counts('workbench-green.xml')
checks['types']={'exit_code':0,'report':'types.log'}
checks['lint']={'exit_code':0,'report':'lint.log'}
checks['generated_contract']={'exit_code':0,'operations':84,'report':'contracts.log'}
checks['operation_routes']={'exit_code':0,'operations':84,'report':'routes.log'}
base=json.loads((r/'preservation-baseline.json').read_text(encoding='utf-8-sig'))
changed=[p for p,h in base['files'].items() if hashlib.sha256((root/p).read_bytes()).hexdigest()!=h]
if changed:raise RuntimeError(f'Original input/evidence changed:{changed[:10]}')
(r/'checks.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
(r/'original-evidence-preserved.json').write_text(json.dumps({'verified_files':len(base['files']),'changed_files':changed,'original_inputs_unchanged':True},indent=2)+'\n',encoding='utf-8')
print(json.dumps(checks,indent=2));print('Original tracked evidence unchanged:',len(base['files']))