from pathlib import Path
import json,base64,hashlib,xml.etree.ElementTree as ET
root=Path('test-results'); report=root/'q09-keyboard-proof-full.json'; junit=root/'q09-keyboard-proof-full.xml'
x=json.loads(report.read_text(encoding='utf-8')); stats=x['stats']
assert stats['expected']==12 and stats['unexpected']==stats['flaky']==stats['skipped']==0
assert x['errors']==[]
y=ET.parse(junit).getroot();assert int(y.attrib['tests'])==12 and all(int(y.attrib[k])==0 for k in ('failures','errors','skipped'))
dst=root/'q09-keyboard-decoded-proof';dst.mkdir(exist_ok=False)
cases=[]; proofs=[]
def walk(suite):
 for spec in suite.get('specs',[]):
  assert spec['ok']; test=spec['tests'][0];assert test['status']=='expected';assert len(test['results'])==1
  result=test['results'][0];assert result['status']=='passed' and result['errors']==[]
  cases.append({'title':spec['title'],'file':spec['file'],'line':spec['line'],'pass':1,'fail':0,'error':0,'skip':0,'runtime_ms':result['duration']})
  for a in result['attachments']:
   if a['name'] not in ['operator-keyboard-input','reviewer-keyboard-input','keyboard-task3-proof','keyboard-task5-viewer','keyboard-task5-proof']:continue
   raw=base64.b64decode(a['body'],validate=True);v=json.loads(raw);inp=v.get('input',v)
   assert inp['mode']=='keyboard' and inp['trustedPointerEvents']==[] and len(inp['actions'])>0
   assert all(c['focusVisible'] and float(c['outline'].split('px ')[0])>=2 for c in inp['actions'])
   if a['name']=='keyboard-task3-proof':
    assert [r['offset'] for r in v['resultReads']]==[0,20,40,60,80,100];assert all(r['status']==200 for r in v['resultReads'])
    assert [v['result'][k] for k in ['processed','updated','unchanged','conflicts','blocked']]==[101,98,2,1,0]
    assert len(v['after']['buyers'])==101
   leaf=hashlib.sha256((spec['title']+a['name']).encode()).hexdigest()[:12]+'-'+a['name']+'.json'
   with (dst/leaf).open('xb') as f:f.write(raw)
   proofs.append({'case':spec['title'],'name':a['name'],'path':leaf,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'native_actions':len(inp['actions']),'trusted_pointer_events':0})
 for child in suite.get('suites',[]):walk(child)
for suite in x['suites']:walk(suite)
assert len(cases)==12 and len(proofs)==14
out={'fixture_only':True,'stats':stats,'junit':y.attrib,'cases':cases,'proofs':proofs,'total_native_actions':sum(p['native_actions'] for p in proofs),'keyboard_proof_bodies':len(proofs),'human_screen_reader':None,'human_staff_UAT':None,'deployed_sha':None}
with (root/'q09-keyboard-proof-summary.json').open('x',encoding='utf-8') as f:f.write(json.dumps(out,indent=2));f.write(chr(10))
print(json.dumps({'cases':len(cases),'proofs':len(proofs),'native_actions':out['total_native_actions'],'stats':stats}))
