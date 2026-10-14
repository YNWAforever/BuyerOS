"""Native CI discovery contracts; synthetic controls are never runtime acceptance."""
import copy,json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
GATE=ROOT/'scripts/check-required-tests.py'
class PlaywrightRequiredDiscoveryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.directory=Path(self.tmp.name)
  self.report=dict(errors=[],suites=[dict(file='journey.spec.ts',specs=[dict(id='one',title='approved export',file='journey.spec.ts',tests=[dict(results=[])]),dict(id='two',title='unknown remains held',file='journey.spec.ts',tests=[dict(results=[])])])])
  self.xml='<testsuite tests="2" failures="0" errors="0" skipped="0"><testcase classname="journey.spec.ts" name="approved export"/><testcase classname="journey.spec.ts" name="unknown remains held"/></testsuite>'
 def run_gate(self,report=None,xml=None,only=False,count=2):
  discovery=self.directory/'list.json';discovery.write_text(json.dumps(self.report if report is None else report),encoding='utf-8')
  junit=self.directory/'fresh.xml';junit.write_text(self.xml if xml is None else xml,encoding='utf-8')
  command=[sys.executable,str(GATE),'--playwright-discovery',str(discovery),'--expected-count',str(count),'--expected-file','journey.spec.ts']
  command+=['--discovery-only'] if only else ['--junit',str(junit)]
  return subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
 def test_actual_named_discovery_and_fresh_execution_are_accepted(self):
  result=self.run_gate();self.assertEqual(result.returncode,0,result.stdout+result.stderr)
 def test_positive_discovery_is_checked_before_execution(self):
  result=self.run_gate(only=True);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
 def test_empty_native_discovery_is_refused(self):
  report=copy.deepcopy(self.report);report['suites']=[];self.assertNotEqual(self.run_gate(report,only=True).returncode,0)
 def test_duplicate_native_id_is_refused(self):
  report=copy.deepcopy(self.report);report['suites'][0]['specs'][1]['id']='one';self.assertNotEqual(self.run_gate(report,only=True).returncode,0)
 def test_duplicate_native_name_is_refused(self):
  report=copy.deepcopy(self.report);report['suites'][0]['specs'][1]['title']='approved export';self.assertNotEqual(self.run_gate(report,only=True).returncode,0)
 def test_native_discovery_errors_are_refused(self):
  report=copy.deepcopy(self.report);report['errors']=[dict(message='import failed')];self.assertNotEqual(self.run_gate(report,only=True).returncode,0)
 def test_wrong_original_spec_file_is_refused(self):
  report=copy.deepcopy(self.report);report['suites'][0]['file']='subset.spec.ts';self.assertNotEqual(self.run_gate(report,only=True).returncode,0)
 def test_filtered_discovery_cannot_shrink_required_count(self):
  report=copy.deepcopy(self.report);report['suites'][0]['specs'].pop();self.assertNotEqual(self.run_gate(report,only=True).returncode,0)
 def test_execution_name_must_equal_discovered_name(self):
  self.assertNotEqual(self.run_gate(xml=self.xml.replace('unknown remains held','another passing test')).returncode,0)
 def test_duplicate_JUnit_cannot_replace_missing_case(self):
  self.assertNotEqual(self.run_gate(xml=self.xml.replace('unknown remains held','approved export')).returncode,0)
 def test_skipped_required_case_is_refused(self):
  self.assertNotEqual(self.run_gate(xml=self.xml.replace('name="unknown remains held"/>','name="unknown remains held"><skipped/></testcase>')).returncode,0)
 def test_discovery_report_cannot_be_an_execution_report(self):
  report=copy.deepcopy(self.report);report['suites'][0]['specs'][0]['tests'][0]['results']=[dict(status='passed')];self.assertNotEqual(self.run_gate(report,only=True).returncode,0)

 def test_original_CFstaff_has_discovery_and_exact_execution_gates(self):
  workflow=(ROOT/'.github/workflows/buyeros-ci.yml').read_text(encoding='utf-8')
  body=workflow.split('  cloudflare-staff-acceptance:\n',1)[1].split('\n  browser-continuity:',1)[0]
  discovery='pnpm exec playwright test --config playwright.cloudflare.config.ts --list --reporter=json > artifacts/cloudflare/ci-staff-discovery.json'
  pre='python scripts/check-required-tests.py --playwright-discovery artifacts/cloudflare/ci-staff-discovery.json --expected-count 7 --expected-file cloudflare-journey.spec.ts --discovery-only'
  original='node scripts/run-cloudflare-acceptance.mjs'
  post='python scripts/check-required-tests.py --playwright-discovery artifacts/cloudflare/ci-staff-discovery.json --expected-count 7 --expected-file cloudflare-journey.spec.ts --junit artifacts/cloudflare/acceptance/journey.xml'
  for command in [discovery,pre,original,post]:self.assertIn(command,body)
  self.assertLess(body.index(discovery),body.index(pre));self.assertLess(body.index(pre),body.index(original));self.assertLess(body.index(original),body.index(post))
  guards=workflow.split('      - name: Verify required Playwright discovery guards\n',1)[1].split('      - name: Discover C61 evidence checker assertions before running',1)[0]
  self.assertIn('assert len(names)==len(set(names))==16,',guards)
  self.assertIn('assert result.testsRun==16 and result.wasSuccessful() and not result.skipped,',guards)

 def test_original_frontend_Neon_browser_binds_exact_native9_execution(self):
  workflow=(ROOT/'.github/workflows/buyeros-ci.yml').read_text(encoding='utf-8');body=workflow.split('  frontend:\n',1)[1].split('\n  cloudflare-controller:',1)[0]
  native='pnpm exec playwright test --config playwright.neon-runtime-built.config.ts --list --reporter=json > artifacts/c61/ci-neon-session-native-discovery.json'
  pre='python scripts/check-required-tests.py --playwright-discovery artifacts/c61/ci-neon-session-native-discovery.json --expected-count 9 --expected-file neon-session-production.spec.ts --expected-file neon-security-production.spec.ts --discovery-only'
  original='pnpm exec playwright test --config playwright.neon-runtime-built.config.ts\n'
  post='python scripts/check-required-tests.py --playwright-discovery artifacts/c61/ci-neon-session-native-discovery.json --expected-count 9 --expected-file neon-session-production.spec.ts --expected-file neon-security-production.spec.ts --junit test-results/neon-session.xml'
  for command in [native,pre,original,post]:self.assertIn(command,body)
  self.assertLess(body.index(native),body.index(pre));self.assertLess(body.index(pre),body.index(original));self.assertLess(body.index(original),body.index(post));self.assertIn('artifacts/c61/ci-neon-session-native-discovery.json\n',body)

 def test_original_audit_discovers_history_and_workspace_recovery_with_all133_cases(self):
  workflow=(ROOT/'.github/workflows/buyeros-ci.yml').read_text(encoding='utf-8')
  marker='--playwright-discovery artifacts/c61/playwright-discovery.json --expected-count 133 --expected-file audit-delivery-history.spec.ts'
  commands=[line for line in workflow.splitlines() if marker in line]
  self.assertEqual(len(commands),2,'native audit preflight and postgate must include all133 cases')
  retained_files=['audit-delivery-history.spec.ts','audit-access-revocation.spec.ts','audit-auth-entry.spec.ts','audit-bulk-confirmation.spec.ts','audit-bulk-manifest.spec.ts','audit-candidate-review.spec.ts','audit-daily-journey.spec.ts','audit-daily-ux.spec.ts','audit-draft-dirty.spec.ts','audit-draft-reground.spec.ts','audit-job-scope.spec.ts','audit-keyboard-workbench.spec.ts','audit-keyboard.spec.ts','audit-maintenance-settings.spec.ts','audit-memberships.spec.ts','audit-native-run-progress.spec.ts','audit-operations.spec.ts','audit-research-intent.spec.ts','audit-reviewed-list-order.spec.ts','audit-template-copy.spec.ts','work-queue-counts.spec.ts']
  for command in commands:
   for name in [*retained_files,'audit-workspace-recovery.spec.ts']:
    self.assertIn('--expected-file '+name,command)
  self.assertIn('--discovery-only',commands[0]);self.assertIn('--junit test-results/audit-fixes.xml',commands[1])
  config=(ROOT/'playwright.audit-fixes.config.ts').read_text(encoding='utf-8')
  self.assertIn("testMatch:['audit-*.spec.ts','work-queue-counts.spec.ts']",config)
  self.assertTrue((ROOT/'tests/e2e/audit-delivery-history.spec.ts').is_file())
  self.assertTrue((ROOT/'tests/e2e/audit-workspace-recovery.spec.ts').is_file())

 def test_joined_authority_is_in_original_react_job_and_exact_discovery(self):
  workflow=(ROOT/'.github/workflows/buyeros-ci.yml').read_text(encoding='utf-8')
  marker='--playwright-discovery artifacts/c61/ci-c61-react-built-discovery.json --expected-count 17 --expected-file audit-bulk-manifest.spec.ts --expected-file audit-candidate-review.spec.ts --expected-file c61-eight-module-fixture.spec.ts --expected-file c61-joined-authority-fixture.spec.ts --expected-file c61-joined-bulk-fixture.spec.ts'
  self.assertEqual(workflow.count(marker),2,'original React pre/post must retain all old cases and require all joined authority and bulk cases')
  config=(ROOT/'playwright.c61-react-regression.config.ts').read_text(encoding='utf-8')
  self.assertIn("'c61-joined-authority-fixture.spec.ts'",config)
  self.assertTrue((ROOT/'tests/e2e/c61-joined-authority-fixture.spec.ts').is_file())
  self.assertIn("'c61-joined-bulk-fixture.spec.ts'",config)
  self.assertTrue((ROOT/'tests/e2e/c61-joined-bulk-fixture.spec.ts').is_file())
  guards=workflow.split('      - name: Verify required Playwright discovery guards\n',1)[1].split('      - name: Discover C61 evidence checker assertions before running',1)[0]
  self.assertIn('assert len(names)==len(set(names))==16,',guards)
  self.assertIn('assert result.testsRun==16 and result.wasSuccessful() and not result.skipped,',guards)
