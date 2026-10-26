import copy,importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('t21_inventory_checker',ROOT/'scripts/check-c61-evidence.py')
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
def receipt(file='public-ui-audit.spec.mjs'):
 return {'errors':[],'suites':[{'file':file,'specs':[{'title':'synthetic guard-only control','id':'guard-1','file':file,'tests':[{'results':[]}]}]}]}
class PublicInventory(unittest.TestCase):
 def test_reviewed_mjs_format_is_supported_only_for_additional_ci_collection(self):
  self.assertEqual(checker._built_playwright_names(json.dumps(receipt()).encode(),'ci-required'),
                   {'public-ui-audit.spec.mjs::synthetic guard-only control'})
 def test_other_mjs_files_are_not_admitted(self):
  with self.assertRaises(ValueError):checker._built_playwright_names(json.dumps(receipt('other.spec.mjs')).encode(),'ci-required')
 def test_protected_audit_family_does_not_admit_mjs(self):
  with self.assertRaises(ValueError):checker._built_playwright_names(json.dumps(receipt()).encode(),'audit')
 def test_definition_traversal_is_rejected(self):
  value=receipt();value['suites'][0]['specs'][0]['file']='../public-ui-audit.spec.mjs'
  with self.assertRaises(ValueError):checker._built_playwright_names(json.dumps(value).encode(),'ci-required')
 def test_duplicate_native_ids_are_rejected(self):
  value=receipt();second=copy.deepcopy(value['suites'][0]['specs'][0]);second['title']='another synthetic control';value['suites'][0]['specs'].append(second)
  with self.assertRaises(ValueError):checker._built_playwright_names(json.dumps(value).encode(),'ci-required')
 def test_navigation_protocol_controls_are_executed_with_exact_twelve_case_report(self):
  import shlex
  workflow=(ROOT/'.github/workflows/buyeros-ci.yml').read_text()
  inventory_count=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_t21_public_inventory.py').countTestCases()
  inventory_commands=[shlex.split(line.strip()) for line in workflow.splitlines() if line.strip().startswith('python -c ') and "pattern='test_t21_public_inventory.py'" in line]
  self.assertEqual(len(inventory_commands),1)
  inventory_guard=inventory_commands[0][2]
  self.assertIn(f'assert s.countTestCases()=={inventory_count};',inventory_guard)
  self.assertIn(f'assert r.testsRun=={inventory_count} and r.wasSuccessful() and not r.skipped',inventory_guard)
  marker='      - name: Verify T21 traversal and synthetic protocol controls'+chr(10)
  self.assertEqual(workflow.count(marker),1)
  before,after=workflow.split(marker)
  self.assertIn('uv sync --frozen',before.split('  frontend:'+chr(10),1)[1])
  block=after.split(chr(10)+'      - ',1)[0]
  command=next(shlex.split(line.strip()) for line in block.splitlines() if line.strip().startswith('node --test '))
  self.assertEqual(command,['node','--test','--test-reporter=junit','--test-reporter-destination=artifacts/t21/navigation-unit.xml',
   'tests/t21-navigation.test.mjs','tests/t21-history-replay.test.mjs','tests/workbench-neon-fixture.test.mjs'])
  self.assertIn('python scripts/check-required-tests.py --junit artifacts/t21/navigation-unit.xml',block)
  self.assertIn('len(cases)==len(names)==12',block)
  self.assertIn('buyeros-t21-navigation-unit',after)
 def test_execution_results_cannot_replace_original_collection(self):
  value=receipt();value['suites'][0]['specs'][0]['tests'][0]['results']=[{'status':'passed'}]
  with self.assertRaises(ValueError):checker._built_playwright_names(json.dumps(value).encode(),'ci-required')
if __name__=='__main__':unittest.main()
