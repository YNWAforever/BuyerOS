"""Synthetic provenance controls, never runtime or release receipts."""
import copy,hashlib,importlib.util,json,unittest,xml.etree.ElementTree as E
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CHECKER=ROOT/'scripts/check-c61-evidence.py'
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=module('built_base_fixtures',ROOT/'tests/test_c61_evidence.py')
AUDIT_FILES=['audit-access-revocation.spec.ts','audit-auth-entry.spec.ts','audit-bulk-confirmation.spec.ts','audit-bulk-manifest.spec.ts','audit-candidate-review.spec.ts','audit-daily-journey.spec.ts','audit-daily-ux.spec.ts','audit-draft-dirty.spec.ts','audit-draft-reground.spec.ts','audit-job-scope.spec.ts','audit-keyboard-workbench.spec.ts','audit-keyboard.spec.ts','audit-maintenance-settings.spec.ts','audit-memberships.spec.ts','audit-native-run-progress.spec.ts','audit-operations.spec.ts','audit-research-intent.spec.ts','audit-template-copy.spec.ts','work-queue-counts.spec.ts']
CONFIGS={'audit':'playwright.audit-fixes.config.ts','react':'playwright.c61-react-regression.config.ts','unicode':'playwright.c61-unicode-joined.config.ts'}
REACT_COUNTS={'audit-candidate-review.spec.ts':3,'audit-bulk-manifest.spec.ts':2,'c61-eight-module-fixture.spec.ts':4,'c61-joined-authority-fixture.spec.ts':4,'c61-joined-bulk-fixture.spec.ts':4}
class FullBuiltGateTests(unittest.TestCase):
 def setUp(self):
  self.f=base.EvidenceTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.checker=module('built_candidate',CHECKER);f=self.f
  self.proof=f.manifest['proofs'][0];self.proof.update(environment='built-fixture',discovery_format='named-json')
  self.receipt=json.loads((f.root/self.proof['provenance']['path']).read_text());self.receipt['environment']='built-fixture'
  depnames=['package.json','pnpm-lock.yaml','services/api/pyproject.toml','services/api/uv.lock','services/worker/pyproject.toml','services/worker/uv.lock']
  deps={p:f.file_ref('input-'+str(i),p) for i,p in enumerate(depnames)}
  self.job=dict(schema='buyeros.full-built-job.v1',gate_id='built-ui',cwd='.',fixture_scope='owned-PG16-synthetic-Auth0-and-providers',proper_Git_source_inventory=True,source_unchanged=True,dependency_scope='fresh-owned-node_modules-and-venvs',browser_scope='native-JSON-list-equals-execution-no-live-claim',owner_scope='native-seven-metadata-unit-assertions-not-Linux-process-proof',dependency_inputs=deps,dependency_inputs_after_sha256={k:v['sha256'] for k,v in deps.items()},steps=[])
  self.reports={};allcases=[]
  self.addstep('pnpm-frozen-install',['pnpm','install','--frozen-lockfile'])
  self.addstep('Playwright-install',['pnpm','exec','playwright','install','--with-deps','chromium'])
  self.addstep('uv-sync-api',['uv','sync','--frozen','--project','services/api'])
  self.addstep('uv-sync-worker',['uv','sync','--frozen','--project','services/worker'])
  for group in CONFIGS:
   files=AUDIT_FILES if group=='audit' else list(REACT_COUNTS) if group=='react' else ['c61-'+group+'.spec.ts'];cases=[];suites=[]
   for file in files:
    count=REACT_COUNTS[file] if group=='react' else 3 if file in ('audit-candidate-review.spec.ts','audit-native-run-progress.spec.ts') else 4 if group=='unicode' else 1
    specs=[]
    for i in range(count):
     title='case '+str(i);definition='fixtures/staff-journey.ts' if file=='audit-keyboard.spec.ts' else file
     specs.append(dict(title=title,file=definition,id=group+file+str(i),tests=[dict(results=[])]));cases.append((file,title))
    suites.append(dict(title=file,file=file,specs=specs))
   self.reports[group]=dict(errors=[],suites=suites)
   command=['pnpm','exec','playwright','test','--config',CONFIGS[group]]
   self.addstep(group+'-discovery',command+['--list','--reporter=json'],json.dumps(self.reports[group]))
   step=self.addstep(group+'-tests',command);step['junit']=self.junit(group+'.xml',cases);allcases+=cases
  self.owners=['test_c61_built_owner.BuiltOwnerTests.test_owned_'+str(i) for i in range(7)]
  self.addstep('owner-discovery',['python','-X','utf8','-c',"import unittest; suite=unittest.defaultTestLoader.discover('tests',pattern='test_c61_built_owner.py'); print('native traversal')"],json.dumps(self.owners))
  ownerlog='\n'.join(n.rsplit('.',1)[1]+' ('+n+') ... ok' for n in self.owners)+'\n\nRan 7 tests in 0.01s\n\nOK\n'
  self.addstep('owner-tests',['python','-X','utf8','-m','unittest','discover','-s','tests','-p','test_c61_built_owner.py','-v'],ownerlog)
  # The native audit/React groups intentionally overlap; aggregate each identity once.
  allcases=list(dict.fromkeys(allcases))
  names=sorted(c+'::'+n for c,n in allcases)
  self.proof['junit']=self.junit('aggregate.xml',allcases);self.proof['discovery']=f.file_ref('aggregate.json',json.dumps(dict(schema='buyeros.named-discovery.v1',exit_code=0,cases=names)))
  self.inventory=dict(schema='buyeros.required-test-inventory.v1',source_sha=base.SHA,source_tree=base.TREE,environment='built-fixture',gate_id='built-ui',cases=names)
  self.job['required_inventory']=f.file_ref('inventory.json',json.dumps(self.inventory));self.receipt['full_job']=self.job;f.manifest['gates']=[dict(gate_id='built-ui',proof_ids=['s1'])];self.flush()
 def addstep(self,sid,command,body='synthetic native step'):
  i=len(self.job['steps']);step=dict(step_id=sid,command=command,exit_code=0,started_at_utc=f'2026-10-08T00:00:{i*2:02d}+00:00',finished_at_utc=f'2026-10-08T00:00:{i*2+1:02d}+00:00',log=self.f.file_ref(sid+'.log',body));self.job['steps'].append(step);return step
 def step(self,sid):return next(s for s in self.job['steps'] if s['step_id']==sid)
 def junit(self,name,cases):
  root=E.Element('testsuite',tests=str(len(cases)))
  for c,n in cases:E.SubElement(root,'testcase',classname=c,name=n)
  return self.f.file_ref(name,E.tostring(root,encoding='utf-8'))
 def report(self,group):self.step(group+'-discovery')['log']=self.f.file_ref(group+'-discovery.log',json.dumps(self.reports[group]))
 def flush(self):self.proof['provenance']=self.f.file_ref('s1.json',json.dumps(self.receipt))
 def reject(self):
  self.flush();r=self.f.check();self.assertTrue(r['automated_evidence_valid'],r);self.assertNotIn('built-ui',r['validated_automated_gates']);self.assertFalse(r['predeploy_ready'])
 def test_complete_native_JSON_registration_alias_and_owner_metadata_remain_release_no_go(self):
  r=self.f.check();self.assertIn('built-ui',r['validated_automated_gates'],r['blockers']);self.assertFalse(r['predeploy_ready']);self.assertFalse(r['release_accepted']);self.assertFalse(r['neon_only_accepted']);self.assertFalse(r['native_send_accepted'])
 def test_windows_native_commands_are_valid(self):
  for s in self.job['steps']:
   if s['command'][0]=='pnpm':s['command']=['cmd.exe','/d','/c',*s['command']]
  self.flush();self.assertIn('built-ui',self.f.check()['validated_automated_gates'])
 def test_missing_full_provenance_rejected(self):del self.receipt['full_job'];self.reject()
 def test_empty_native_discovery_rejected(self):self.reports['audit']['suites']=[];self.report('audit');self.reject()
 def test_collection_error_rejected(self):self.reports['audit']['errors']=[dict(message='collection failure')];self.report('audit');self.reject()
 def test_duplicate_native_id_rejected(self):self.reports['audit']['suites'][1]['specs'][0]['id']=self.reports['audit']['suites'][0]['specs'][0]['id'];self.report('audit');self.reject()
 def test_results_in_list_rejected(self):self.reports['audit']['suites'][0]['specs'][0]['tests'][0]['results']=[dict(status='passed')];self.report('audit');self.reject()
 def test_multiple_projects_for_one_spec_rejected(self):self.reports['audit']['suites'][0]['specs'][0]['tests']*=2;self.report('audit');self.reject()
 def test_missing_audit_family_rejected(self):self.reports['audit']['suites']=[s for s in self.reports['audit']['suites'] if s['file']!='audit-draft-dirty.spec.ts'];self.report('audit');self.reject()
 def test_candidate_family_subset_rejected(self):next(s for s in self.reports['audit']['suites'] if s['file']=='audit-candidate-review.spec.ts')['specs'].pop();self.report('audit');self.reject()
 def test_definition_file_cannot_replace_registration_identity(self):self.reports['audit']['suites'][11]['file']='fixtures/staff-journey.ts';self.report('audit');self.reject()
 def test_foreign_file_path_rejected(self):self.reports['audit']['suites'][0]['file']='../audit-access-revocation.spec.ts';self.report('audit');self.reject()
 def test_empty_group_JUnit_rejected(self):self.step('react-tests')['junit']=self.f.file_ref('empty.xml','<testsuite tests="0"/>');self.reject()
 def test_failed_group_JUnit_rejected(self):self.step('react-tests')['junit']=self.f.file_ref('failed.xml','<testsuite><testcase classname="x" name="y"><failure/></testcase></testsuite>');self.reject()
 def test_skipped_group_JUnit_rejected(self):self.step('unicode-tests')['junit']=self.f.file_ref('skip.xml','<testsuite><testcase classname="x" name="y"><skipped/></testcase></testsuite>');self.reject()
 def test_missing_step_rejected(self):self.job['steps'].remove(self.step('uv-sync-worker'));self.reject()
 def test_keyword_filtered_execution_rejected(self):self.step('audit-tests')['command']+=['--grep','owned'];self.reject()
 def test_old_text_discovery_rejected(self):self.step('audit-discovery')['command'].remove('--reporter=json');self.reject()
 def test_wrong_original_config_rejected(self):self.step('audit-tests')['command'][5]='playwright.config.ts';self.reject()
 def test_nonzero_native_exit_rejected(self):self.step('react-tests')['exit_code']=1;self.reject()
 def test_boolean_native_exit_rejected(self):self.step('react-tests')['exit_code']=False;self.reject()
 def test_source_change_rejected(self):self.job['source_unchanged']=False;self.reject()
 def test_shared_dependency_scope_rejected(self):self.job['dependency_scope']='shared';self.reject()
 def test_frozen_dependency_change_rejected(self):self.job['dependency_inputs_after_sha256']['pnpm-lock.yaml']='e'*64;self.reject()
 def test_browser_fixture_cannot_claim_real_auth(self):self.job['browser_scope']='real-Neon';self.reject()
 def test_owner_metadata_cannot_claim_Linux_process_proof(self):self.job['owner_scope']='Linux-process';self.reject()
 def test_owner_empty_discovery_rejected(self):self.step('owner-discovery')['log']=self.f.file_ref('owner-discovery.log','[]');self.reject()
 def test_owner_discovery_execution_mismatch_rejected(self):self.owners[0]='test_c61_built_owner.BuiltOwnerTests.test_other';self.step('owner-discovery')['log']=self.f.file_ref('owner-discovery.log',json.dumps(self.owners));self.reject()
 def test_owner_fake_success_log_rejected(self):self.step('owner-tests')['log']=self.f.file_ref('owner-tests.log','Ran 7 tests\nOK\n');self.reject()
 def test_time_outside_receipt_rejected(self):self.step('owner-tests')['finished_at_utc']='2026-10-08T00:02:00+00:00';self.reject()
 def test_discovery_after_its_execution_rejected(self):a=self.job['steps'];a[4],a[5]=a[5],a[4];self.reject()
 def test_duplicate_required_inventory_rejected(self):self.inventory['cases']*=2;self.job['required_inventory']=self.f.file_ref('inventory.json',json.dumps(self.inventory));self.reject()

 def test_windows_CRLF_native_owner_log_keeps_names_and_release_no_go(self):
  step=self.step('owner-tests');original=(self.f.root/step['log']['path']).read_bytes();self.assertIn(b' ... ok',original)
  windows=original.replace(b'\n',b'\r\n');step['log']=self.f.file_ref('owner-native-CRLF.log',windows);self.flush()
  result=self.f.check();self.assertTrue(result['automated_evidence_valid']);self.assertIn('built-ui',result['validated_automated_gates'],result['blockers']);self.assertFalse(result['predeploy_ready'])
  self.assertEqual((self.f.root/step['log']['path']).read_bytes(),windows)
 def test_CRLF_skipped_owner_row_cannot_be_hidden_by_OK_summary(self):
  step=self.step('owner-tests');original=(self.f.root/step['log']['path']).read_bytes();self.assertIn(b' ... ok',original)
  windows=original.replace(b' ... ok',b" ... skipped 'owned fixture'",1).replace(b'\n',b'\r\n');step['log']=self.f.file_ref('owner-skipped-CRLF.log',windows);self.reject()


 def test_explicit_frozen_built_python312_pin_preserves_all_release_refusals(self):
  for service in ['api','worker']:self.step('uv-sync-'+service)['command']=['uv','sync','--frozen','--python','3.12','--project','services/'+service]
  self.flush();r=self.f.check();self.assertIn('built-ui',r['validated_automated_gates'],r['blockers'])
  for flag in ['predeploy_ready','release_accepted','neon_only_accepted','native_send_accepted']:self.assertFalse(r[flag])
 def test_wrong_or_mutable_built_python_selectors_remain_refused(self):
  for service in ['api','worker']:
   for version in ['3.11','3.13','/external/python.exe','3.12-auto','3.12 --no-frozen']:
    with self.subTest(service=service,version=version):
     original=self.step('uv-sync-'+service)['command'];self.step('uv-sync-'+service)['command']=['uv','sync','--frozen','--python',version,'--project','services/'+service];self.reject();self.step('uv-sync-'+service)['command']=original

 def test_exact_package_native_Node_Playwright_entry_preserves_release_refusals(self):
  for group in CONFIGS:
   for kind in ['discovery','tests']:
    step=self.step(group+'-'+kind);original=step['command']
    self.assertEqual(original[:3],['pnpm','exec','playwright'])
    step['command']=['node','node_modules/@playwright/test/cli.js',*original[3:]]
  self.flush();result=self.f.check();self.assertIn('built-ui',result['validated_automated_gates'],result['blockers'])
  for flag in ['predeploy_ready','release_accepted','neon_only_accepted','native_send_accepted']:self.assertFalse(result[flag])
 def test_native_Node_browser_entry_refuses_external_scripts_filters_and_wrappers(self):
  for group in CONFIGS:
   for kind in ['discovery','tests']:
    step=self.step(group+'-'+kind);original=step['command'];args=original[3:]
    variants=[['node','node_modules/other/cli.js',*args],['node','../node_modules/@playwright/test/cli.js',*args],['node','/external/node_modules/@playwright/test/cli.js',*args],['node','node_modules/@playwright/test/cli.js','--grep','owned',*args],['node','node_modules/@playwright/test/cli.js',*args,'--project','reduced'],['node','--eval','fake',*args],['cmd.exe','/d','/c','node','node_modules/@playwright/test/cli.js',*args],['npx','playwright',*args],['node','node_modules/@playwright/test/cli.js',*args,'--pass-with-no-tests']]
    for command in variants:
     with self.subTest(group=group,kind=kind,command=command):
      step['command']=command;self.reject()
    step['command']=original

if __name__=='__main__':unittest.main()
