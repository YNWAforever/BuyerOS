"""CI gate controls; these do not provide database or release acceptance."""
import os,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class PytestRequiredDiscoveryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.directory=Path(self.tmp.name)
  self.discovery='tests/test_scope.py::test_owned[::1]\ntests/test_hold.py::HoldTests::test_unknown[繁體]\n\n2 tests collected in 0.1s\n'
  self.xml='<testsuite tests="2" failures="0" errors="0" skipped="0"><testcase classname="tests.test_scope" name="test_owned[::1]"/><testcase classname="tests.test_hold.HoldTests" name="test_unknown[繁體]"/></testsuite>'
 def run_gate(self,discovery=None,xml=None,only=False,count=2,extra=(),stale=False):
  d=self.directory/'collection.txt';d.write_text(self.discovery if discovery is None else discovery,encoding='utf-8')
  j=self.directory/'fresh.xml';j.write_text(self.xml if xml is None else xml,encoding='utf-8')
  if stale:os.utime(j,(1,1))
  args=[sys.executable,str(ROOT/'scripts/check-required-tests.py'),'--pytest-discovery',str(d),'--expected-count',str(count)]
  args+=['--discovery-only'] if only else ['--junit',str(j)]
  return subprocess.run(args+list(extra),capture_output=True,text=True,encoding='utf-8')
 def test_actual_native_names_and_class_parameter_mapping_are_accepted(self):
  p=self.run_gate();self.assertEqual(p.returncode,0,p.stdout+p.stderr)
 def test_positive_native_discovery_is_checked_before_execution(self):
  p=self.run_gate(only=True);self.assertEqual(p.returncode,0,p.stdout+p.stderr)
 def test_empty_discovery_is_refused(self):self.assertNotEqual(self.run_gate('',only=True).returncode,0)
 def test_missing_native_summary_is_refused(self):self.assertNotEqual(self.run_gate(self.discovery.split('\n\n')[0],only=True).returncode,0)
 def test_duplicate_native_case_is_refused(self):self.assertNotEqual(self.run_gate(self.discovery.replace('tests/test_hold.py::HoldTests::test_unknown[繁體]','tests/test_scope.py::test_owned[::1]'),only=True).returncode,0)
 def test_filtered_discovery_cannot_shrink_full_count(self):self.assertNotEqual(self.run_gate(count=3,only=True).returncode,0)
 def test_native_summary_cannot_hide_missing_case(self):self.assertNotEqual(self.run_gate(self.discovery.replace('2 tests collected','3 tests collected'),only=True).returncode,0)
 def test_different_passing_execution_is_refused(self):self.assertNotEqual(self.run_gate(xml=self.xml.replace('test_unknown[繁體]','test_another[繁體]')).returncode,0)
 def test_subset_execution_is_refused(self):self.assertNotEqual(self.run_gate(xml='<testsuite tests="1"><testcase classname="tests.test_scope" name="test_owned[::1]"/></testsuite>').returncode,0)
 def test_duplicate_execution_is_refused(self):self.assertNotEqual(self.run_gate(xml=self.xml.replace('tests.test_hold.HoldTests','tests.test_scope').replace('test_unknown[繁體]','test_owned[::1]')).returncode,0)
 def test_skipped_execution_is_refused(self):self.assertNotEqual(self.run_gate(xml=self.xml.replace('name="test_unknown[繁體]"/>','name="test_unknown[繁體]"><skipped/></testcase>')).returncode,0)
 def test_error_execution_is_refused(self):self.assertNotEqual(self.run_gate(xml=self.xml.replace('name="test_unknown[繁體]"/>','name="test_unknown[繁體]"><error/></testcase>')).returncode,0)
 def test_failed_execution_is_refused(self):self.assertNotEqual(self.run_gate(xml=self.xml.replace('name="test_unknown[繁體]"/>','name="test_unknown[繁體]"><failure/></testcase>')).returncode,0)
 def test_stale_JUnit_cannot_be_current_execution(self):self.assertNotEqual(self.run_gate(stale=True).returncode,0)
 def test_two_discovery_sources_cannot_be_combined(self):self.assertNotEqual(self.run_gate(extra=('--playwright-discovery','missing.json')).returncode,0)
 def test_nonpositive_discovery_count_is_refused(self):self.assertNotEqual(self.run_gate(count=0,only=True).returncode,0)
 def test_pytest_cannot_use_Playwright_spec_files(self):self.assertNotEqual(self.run_gate(extra=('--expected-file','scope.spec.ts')).returncode,0)
 def test_discovery_only_cannot_claim_JUnit_execution(self):self.assertNotEqual(self.run_gate(only=True,extra=('--junit',str(self.directory/'fresh.xml'))).returncode,0)
 def assert_original_job(self,name,count,next_job):
  workflow=(ROOT/'.github/workflows/buyeros-ci.yml').read_text(encoding='utf-8');body=workflow.split('  '+name+':\n',1)[1].split('\n  '+next_job+':',1)[0]
  discover='uv run --frozen pytest tests --collect-only -q > artifacts/c61-full-discovery.txt'
  pre='python ../../scripts/check-required-tests.py --pytest-discovery artifacts/c61-full-discovery.txt --expected-count '+str(count)+' --discovery-only'
  original='uv run --frozen pytest tests -q --junitxml=artifacts/tests.xml'
  post='python scripts/check-required-tests.py --pytest-discovery services/'+name+'/artifacts/c61-full-discovery.txt --expected-count '+str(count)+' --junit services/'+name+'/artifacts/tests.xml'
  for command in [discover,pre,original,post]:self.assertIn(command,body)
  self.assertLess(body.index(discover),body.index(pre));self.assertLess(body.index(pre),body.index(original));self.assertLess(body.index(original),body.index(post))
  self.assertIn('services/'+name+'/artifacts/c61-full-discovery.txt',body)
 def test_original_API_requires_full_native_collection_and_exact_execution(self):self.assert_original_job('api',2563,'worker')
 def test_original_worker_requires_full_native_collection_and_exact_execution(self):self.assert_original_job('worker',468,'owned-worker-capacity')
 def test_original_CI_discovers_and_executes_all_gate_controls(self):
  workflow=(ROOT/'.github/workflows/buyeros-ci.yml').read_text(encoding='utf-8');body=workflow.split('      - name: Verify required full pytest discovery guards\n',1)[1].split('      - name: Discover C61 evidence checker assertions before running',1)[0]
  self.assertIn("pattern='test_pytest_required_discovery.py'",body);self.assertIn('assert len(names)==len(set(names))==21,',body);self.assertIn('assert result.testsRun==21 and result.wasSuccessful() and not result.skipped,',body)
