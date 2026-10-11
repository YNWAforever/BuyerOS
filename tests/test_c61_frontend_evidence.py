"""Synthetic provenance unit fixtures; never frontend/runtime release receipts."""
import copy,hashlib,importlib.util,json,unittest,xml.etree.ElementTree as E
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CHECKER=ROOT/'scripts/check-c61-evidence.py'
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=module('c61_base_unit_fixtures',ROOT/'tests/test_c61_evidence.py')
contracts=module('c61_frontend_contract',CHECKER)
class FullFrontendGateTests(unittest.TestCase):
 def setUp(self):
  self.f=base.EvidenceTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.checker=module('frontend_candidate',CHECKER)
  f=self.f;self.proof=f.manifest['proofs'][0];self.proof['environment']='built-fixture';self.proof['discovery_format']='named-json'
  self.receipt=json.loads((f.root/self.proof['provenance']['path']).read_text());self.receipt['environment']='built-fixture'
  self.groups=copy.deepcopy(contracts.FRONTEND_NODE_GROUPS);self.groups['audit']=['tests/audit-auth-render.test.mjs','tests/audit-workflows.test.mjs','tests/job-poller-checks.mjs']
  files=sorted({p for group in self.groups.values() for p in group}|{'tests/domain-checks.mjs','tests/live-adapter-checks.mjs','tests/live-auth-checks.mjs'})
  self.source=dict(schema='buyeros.frontend-source-inventory.v1',source_sha=base.SHA,source_tree=base.TREE,tracked_test_files=files)
  self.job=dict(schema='buyeros.full-frontend-job.v1',gate_id='frontend-full',cwd='.',fixture_scope='loopback-Neon-protocol',dependency_scope='fresh-owned-node_modules',shared_node_modules=False,source_unchanged=True,package_manifest=f.file_ref('package.json','{"private":true}'),lockfile=f.file_ref('pnpm-lock.yaml','synthetic frozen lock'),lockfile_after_sha256=hashlib.sha256(b'synthetic frozen lock').hexdigest(),source_inventory=f.file_ref('source-inventory.json',json.dumps(self.source)),Node_discovery_scope='exact-source-file-inventory-no-collect-only',browser_scope='unpatched-SDK-synthetic-loopback',steps=[])
  bare={'domain':['node','tests/domain-checks.mjs'],'live-adapter':['node','tests/live-adapter-checks.mjs'],'live-auth':['node','tests/live-auth-checks.mjs'],'Vercel-build':['node','scripts/run-vercel.mjs','build']}
  pnpm={'frozen-install':['install','--frozen-lockfile'],'types':['exec','tsc','--noEmit'],'lint':['lint'],'Sites-build':['build'],'Playwright-install':['exec','playwright','install','--with-deps','chromium'],'Playwright-discovery':['exec','playwright','test','--config','playwright.neon-runtime-built.config.ts','--list'],'Playwright-tests':['exec','playwright','test','--config','playwright.neon-runtime-built.config.ts']}
  all_cases=[]
  for i,sid in enumerate(contracts.FRONTEND_STEPS):
   if sid in self.groups:command=['node',*(['--conditions=react-server'] if sid=='neon-sdk' else []),'--test','--test-reporter=tap','--test-reporter-destination=stdout','--test-reporter=junit','--test-reporter-destination='+sid+'.xml',*self.groups[sid]]
   else:command=bare.get(sid) or ['pnpm',*pnpm[sid]]
   step=dict(step_id=sid,command=command,exit_code=0,started_at_utc=f'2026-10-08T00:00:{i*2:02d}+00:00',finished_at_utc=f'2026-10-08T00:00:{i*2+1:02d}+00:00',log=f.file_ref(sid+'.log','synthetic '+sid))
   if sid in self.groups:
    cases=[(sid,'test_'+sid.replace('-','_'))];step['junit']=self.junit(sid+'.xml',cases);all_cases+=cases
   elif sid=='Playwright-tests':
    cases=[('neon-session-production.spec.ts','session control'),('neon-security-production.spec.ts','security control')];step['junit']=self.junit(sid+'.xml',cases);all_cases+=cases
   elif sid=='Playwright-discovery':step['discovery']=f.file_ref('native-browser-list.txt','Listing tests:\n  neon-session-production.spec.ts:1:1 › session control\n  neon-security-production.spec.ts:2:1 › security control\nTotal: 2 tests in 2 files\n')
   elif sid in ('Sites-build','Vercel-build'):
    inventory=dict(schema='buyeros.frontend-build-inventory.v1',source_sha=base.SHA,source_tree=base.TREE,platform='Sites' if sid=='Sites-build' else 'Vercel',files={'server/index.mjs':dict(bytes=1,sha256='c'*64)})
    step['build_inventory']=f.file_ref(sid+'-output.json',json.dumps(inventory))
   self.job['steps'].append(step)
  names=sorted(c+'::'+n for c,n in all_cases);self.proof['junit']=self.junit('aggregate.xml',all_cases);self.proof['discovery']=f.file_ref('aggregate-names.json',json.dumps(dict(schema='buyeros.named-discovery.v1',exit_code=0,cases=names)))
  self.inventory=dict(schema='buyeros.required-test-inventory.v1',source_sha=base.SHA,source_tree=base.TREE,gate_id='frontend-full',environment='built-fixture',cases=names)
  self.job['required_inventory']=f.file_ref('full-inventory.json',json.dumps(self.inventory));self.receipt['full_job']=self.job;f.manifest['gates']=[dict(gate_id='frontend-full',proof_ids=['s1'])];self.flush()
 def junit(self,name,cases):
  root=E.Element('testsuite',tests=str(len(cases)))
  for c,n in cases:E.SubElement(root,'testcase',classname=c,name=n)
  return self.f.file_ref(name,E.tostring(root,encoding='utf-8'))
 def step(self,sid):return next(s for s in self.job['steps'] if s['step_id']==sid)
 def flush(self):self.proof['provenance']=self.f.file_ref('s1.json',json.dumps(self.receipt))
 def reject(self):
  self.flush();r=self.f.check();self.assertTrue(r['automated_evidence_valid'],r);self.assertNotIn('frontend-full',r['validated_automated_gates']);self.assertFalse(r['predeploy_ready'])
 def test_full_frontend_all_original_steps_and_positive_reports_remain_release_no_go(self):
  r=self.f.check();self.assertIn('frontend-full',r['validated_automated_gates'],r['blockers']);self.assertFalse(r['predeploy_ready']);self.assertFalse(r['release_accepted']);self.assertFalse(r['neon_only_accepted']);self.assertFalse(r['native_send_accepted'])
 def test_full_frontend_windows_native_pnpm_is_valid(self):
  for s in self.job['steps']:
   if s['command'][0]=='pnpm':s['command']=['cmd.exe','/d','/c',*s['command']]
  self.flush();self.assertIn('frontend-full',self.f.check()['validated_automated_gates'])
 def test_frontend_unscoped_subset_cannot_satisfy_full_job(self):del self.receipt['full_job'];self.reject()
 def test_frontend_missing_bare_script_cannot_pass(self):self.job['steps'].remove(self.step('live-auth'));self.reject()
 def test_frontend_wrong_original_step_order_cannot_pass(self):self.job['steps'][3],self.job['steps'][4]=self.job['steps'][4],self.job['steps'][3];self.reject()
 def test_frontend_node_keyword_filter_cannot_pass(self):self.step('audit')['command']+=['--test-name-pattern=owned'];self.reject()
 def test_frontend_omitted_audit_source_file_cannot_pass(self):self.step('audit')['command'].remove('tests/audit-workflows.test.mjs');self.reject()
 def test_frontend_empty_group_junit_cannot_pass(self):self.step('deployment')['junit']=self.f.file_ref('empty.xml','<testsuite tests="0"/>');self.reject()
 def test_frontend_skipped_group_cannot_pass(self):self.step('neon-built')['junit']=self.f.file_ref('skipped.xml','<testsuite tests="1"><testcase classname="neon-built" name="test_neon_built"><skipped/></testcase></testsuite>');self.reject()
 def test_frontend_duplicate_group_report_cannot_count_twice(self):self.step('deployment')['junit']=self.step('api-types')['junit'];self.reject()
 def test_frontend_empty_native_Playwright_discovery_cannot_pass(self):self.step('Playwright-discovery')['discovery']=self.f.file_ref('native-browser-list.txt','Total: 0 tests in 0 files\n');self.reject()
 def test_frontend_native_Playwright_name_mismatch_cannot_pass(self):self.step('Playwright-discovery')['discovery']=self.f.file_ref('native-browser-list.txt','neon-session-production.spec.ts:1:1 › wrong\nneon-security-production.spec.ts:2:1 › security control\nTotal: 2 tests in 2 files\n');self.reject()
 def test_frontend_wrong_Playwright_config_cannot_pass(self):self.step('Playwright-tests')['command'][5]='playwright.config.ts';self.reject()
 def test_frontend_shared_node_modules_cannot_pass(self):self.job['shared_node_modules']=True;self.reject()
 def test_frontend_changed_frozen_lockfile_cannot_pass(self):self.job['lockfile_after_sha256']='d'*64;self.reject()
 def test_frontend_boolean_native_exit_cannot_pass(self):self.step('types')['exit_code']=False;self.reject()
 def test_frontend_build_echo_cannot_pass(self):self.step('Sites-build')['command']=['node','-e','0'];self.reject()
 def test_frontend_empty_build_output_cannot_pass(self):self.step('Sites-build')['build_inventory']=self.f.file_ref('empty-build.json',json.dumps(dict(schema='buyeros.frontend-build-inventory.v1',source_sha=base.SHA,source_tree=base.TREE,platform='Sites',files={})));self.reject()
 def test_frontend_build_other_source_cannot_pass(self):self.step('Vercel-build')['build_inventory']=self.f.file_ref('other-build.json',json.dumps(dict(schema='buyeros.frontend-build-inventory.v1',source_sha='d'*40,source_tree=base.TREE,platform='Vercel',files={'entry':dict(bytes=1,sha256='c'*64)})));self.reject()
 def test_frontend_tampered_native_log_cannot_pass(self):(self.f.root/'audit.log').write_text('changed');self.reject()
 def test_frontend_step_time_outside_candidate_cannot_pass(self):self.step('lint')['finished_at_utc']='2026-10-08T00:02:00+00:00';self.reject()
 def test_frontend_source_change_cannot_pass(self):self.job['source_unchanged']=False;self.reject()
 def test_frontend_invented_Node_collect_only_claim_cannot_pass(self):self.job['Node_discovery_scope']='native-collect-only';self.reject()
 def test_frontend_synthetic_browser_cannot_be_called_real_Neon(self):self.job['browser_scope']='real-Neon';self.reject()
 def test_frontend_duplicate_full_inventory_cannot_pass(self):self.inventory['cases']*=2;self.job['required_inventory']=self.f.file_ref('full-inventory.json',json.dumps(self.inventory));self.reject()
if __name__=='__main__':unittest.main()
