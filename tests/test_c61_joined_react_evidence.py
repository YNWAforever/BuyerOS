"""Discovery metadata controls only; never a browser/runtime receipt."""
import importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class JoinedReactInventoryTests(unittest.TestCase):
 def setUp(self):
  s=importlib.util.spec_from_file_location('joined_react_checker',ROOT/'scripts/check-c61-evidence.py');self.checker=importlib.util.module_from_spec(s);s.loader.exec_module(self.checker)
 def report(self,joined=True,bulk=True):
  counts={'audit-candidate-review.spec.ts':3,'audit-bulk-manifest.spec.ts':2,'c61-eight-module-fixture.spec.ts':4}
  if joined:counts['c61-joined-authority-fixture.spec.ts']=4
  if bulk:counts['c61-joined-bulk-fixture.spec.ts']=4
  return {'errors':[],'suites':[dict(title=file,file=file,specs=[dict(id=file+str(i),title='case '+str(i),file='fixtures/staff-journey.ts' if file.startswith('c61-') else file,tests=[dict(results=[])]) for i in range(count)]) for file,count in counts.items()]}
 def test_complete_react17_includes_original9_authority4_and_joined_bulk4(self):
  try:names=self.checker._built_playwright_names(json.dumps(self.report()).encode(),'react')
  except ValueError:names=set()
  self.assertEqual(len(names),17,'all five exact registration families are required')
 def test_legacy_react9_cannot_omit_required_authority_cases(self):
  with self.assertRaises(ValueError):self.checker._built_playwright_names(json.dumps(self.report(False,False)).encode(),'react')
 def test_legacy_react13_cannot_omit_required_joined_bulk_cases(self):
  with self.assertRaises(ValueError):self.checker._built_playwright_names(json.dumps(self.report(bulk=False)).encode(),'react')
 def test_seventeen_other_cases_cannot_replace_joined_bulk_family(self):
  report=self.report();report['suites'][-1]['file']='another-family.spec.ts'
  with self.assertRaises(ValueError):self.checker._built_playwright_names(json.dumps(report).encode(),'react')
