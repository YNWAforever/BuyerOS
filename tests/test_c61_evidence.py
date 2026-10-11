"""C61 automated provenance gate; synthetic files are never release receipts."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / 'scripts/check-c61-evidence.py'
TRACE = ROOT / 'docs/buyeros/evidence/c61/BuyerOS_C61_Case_Traceability_2026-10-06.csv'
NEW = ROOT / 'docs/buyeros/evidence/c61/BuyerOS_C61_New_Test_Cases_2026-10-06.csv'
SHA = 'a' * 40
TREE = 'b' * 40
START = '2026-10-08T00:00:00+00:00'
END = '2026-10-08T00:01:00+00:00'

def load_checker():
    import importlib.util
    spec = importlib.util.spec_from_file_location('c61_evidence_checker', CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.checker = load_checker()
        self.catalog = self.checker.load_catalog(ROOT)
        self.manifest = {
            'schema': 'buyeros.c61-evidence.v1', 'candidate_sha': SHA,
            'candidate_tree': TREE, 'window_start_utc': START, 'window_end_utc': END,
            'cases': [{'case_id': x, 'status': 'pending', 'proof_ids': []} for x in self.catalog],
            'proofs': [], 'gates': [], 'open_findings': ['F21'],
        }
        self.add_suite('s1')

    def file_ref(self, name, data):
        raw = data.encode() if isinstance(data, str) else data
        (self.root / name).write_bytes(raw)
        return {'path': name, 'sha256': hashlib.sha256(raw).hexdigest()}

    def add_suite(self, name, junit=None, discovery=None, environment='owned-fixture'):
        junit = junit if junit is not None else '<testsuites><testsuite tests="1"><testcase classname="tests.test_boundary" name="test_owned_and_foreign"/></testsuite></testsuites>'
        discovery = discovery if discovery is not None else 'tests/test_boundary.py::test_owned_and_foreign\n1 test collected in 0.01s\n'
        receipt = {'source_sha': SHA, 'source_sha_after': SHA, 'source_tree': TREE,
                   'started_at_utc': START, 'finished_at_utc': END, 'exit_code': 0,
                   'required_gate_exit_code': 0, 'environment': environment}
        proof = {'id': name, 'kind': 'junit', 'environment': environment,
                 'junit': self.file_ref(name+'.xml', junit),
                 'discovery': self.file_ref(name+'.txt', discovery), 'discovery_format': 'pytest',
                 'provenance': self.file_ref(name+'.json', json.dumps(receipt))}
        self.manifest['proofs'].append(proof)
        return proof

    def check(self, candidate=None):
        return self.checker.validate(self.root, self.manifest, self.catalog, candidate or (SHA, TREE))

    def rewrite_receipt(self, key, value):
        proof = self.manifest['proofs'][0]
        obj = json.loads((self.root / proof['provenance']['path']).read_text())
        obj[key] = value
        proof['provenance'] = self.file_ref('s1.json', json.dumps(obj))

    def assert_block(self, token):
        result = self.check()
        self.assertFalse(result['automated_evidence_valid'], result)
        self.assertFalse(result['predeploy_ready'])
        self.assertTrue(any(token in x for x in result['blockers']), result['blockers'])

    def test_current_positive_automated_control_remains_release_no_go(self):
        result = self.check()
        self.assertTrue(result['automated_evidence_valid'], result)
        self.assertEqual(result['validated_test_executions'], 1)
        self.assertEqual(result['unique_automated_cases'], 1)
        self.assertFalse(result['predeploy_ready'])
        self.assertFalse(result['release_accepted'])
        self.assertFalse(result['neon_only_accepted'])
        self.assertFalse(result['native_send_accepted'])
        self.assertIn('F21: historical workspace500 root cause remains open', result['blockers'])

    def test_catalog_preserves_all114_and16_with_approved_phase_mapping(self):
        self.assertEqual(len(self.catalog), 130)
        self.assertEqual(sum(x=='predeploy' for x in self.catalog.values()), 119)
        self.assertEqual(self.catalog['B14'], 'superseded')
        self.assertEqual(self.catalog['U01'], 'postdeploy')
        self.assertEqual(self.catalog['NA28'], 'neon-only')
        self.assertEqual(self.catalog['C61T-12'], 'native-send')

    def test_missing_case_cannot_shrink_denominator(self):
        self.manifest['cases'].pop(); self.assert_block('case catalog mismatch')

    def test_duplicate_case_is_not_coverage(self):
        self.manifest['cases'].append(copy.deepcopy(self.manifest['cases'][0])); self.assert_block('duplicate case')

    def test_unknown_case_is_rejected(self):
        self.manifest['cases'][0]['case_id']='invented'; self.assert_block('case catalog mismatch')

    def test_old_candidate_sha_is_rejected(self):
        self.manifest['candidate_sha']='c'*40; self.assert_block('candidate identity mismatch')

    def test_old_tree_is_rejected(self):
        self.manifest['candidate_tree']='c'*40; self.assert_block('candidate identity mismatch')

    def test_provenance_mixed_source_is_rejected(self):
        self.rewrite_receipt('source_sha','c'*40); self.assert_block('source identity mismatch')

    def test_concurrent_head_change_is_rejected(self):
        self.rewrite_receipt('source_sha_after','c'*40); self.assert_block('source identity mismatch')

    def test_provenance_tree_drift_is_rejected(self):
        self.rewrite_receipt('source_tree','c'*40); self.assert_block('source identity mismatch')

    def test_nonzero_child_exit_is_rejected(self):
        self.rewrite_receipt('exit_code',1); self.assert_block('nonzero execution')

    def test_boolean_child_exit_does_not_mean_zero(self):
        self.rewrite_receipt('exit_code',False); self.assert_block('nonzero execution')

    def test_skipped_required_case_is_rejected(self):
        self.manifest['proofs'][0]['junit']=self.file_ref('s1.xml','<testsuite><testcase classname="tests.test_boundary" name="test_owned_and_foreign"><skipped/></testcase></testsuite>'); self.assert_block('failed/error/skipped')

    def test_empty_junit_is_rejected(self):
        self.manifest['proofs'][0]['junit']=self.file_ref('s1.xml','<testsuite tests="42"/>'); self.assert_block('empty JUnit')

    def test_failed_required_case_is_rejected(self):
        self.manifest['proofs'][0]['junit']=self.file_ref('s1.xml','<testsuite><testcase classname="tests.test_boundary" name="test_owned_and_foreign"><failure>observed</failure></testcase></testsuite>'); self.assert_block('failed/error/skipped')

    def test_error_required_case_is_rejected(self):
        self.manifest['proofs'][0]['junit']=self.file_ref('s1.xml','<testsuite><testcase classname="tests.test_boundary" name="test_owned_and_foreign"><error/></testcase></testsuite>'); self.assert_block('failed/error/skipped')

    def test_duplicate_testcase_cannot_inflate_count(self):
        c='<testcase classname="tests.test_boundary" name="test_owned_and_foreign"/>'
        self.manifest['proofs'][0]['junit']=self.file_ref('s1.xml','<testsuite>'+c+c+'</testsuite>'); self.assert_block('duplicate JUnit case')

    def test_junit_header_count_cannot_lie(self):
        self.manifest['proofs'][0]['junit']=self.file_ref('s1.xml','<testsuite tests="7"><testcase classname="tests.test_boundary" name="test_owned_and_foreign"/></testsuite>'); self.assert_block('JUnit count mismatch')

    def test_xml_entities_are_rejected(self):
        self.manifest['proofs'][0]['junit']=self.file_ref('s1.xml','<!DOCTYPE testsuite [<!ENTITY e "anything">]><testsuite/>'); self.assert_block('XML declarations')

    def test_tampered_artifact_is_rejected(self):
        (self.root/'s1.xml').write_text('<testsuite/>'); self.assert_block('digest mismatch')

    def test_path_escape_is_rejected(self):
        self.manifest['proofs'][0]['junit']['path']='../outside.xml'; self.assert_block('artifact path escapes')

    def test_absolute_path_is_rejected(self):
        self.manifest['proofs'][0]['junit']['path']=str(self.root/'s1.xml'); self.assert_block('relative artifact path')

    def test_duplicate_report_bytes_under_second_filename_are_rejected(self):
        self.add_suite('s2'); self.assert_block('duplicate JUnit digest')

    def test_zero_discovery_is_rejected(self):
        self.manifest['proofs'][0]['discovery']=self.file_ref('s1.txt','no tests collected\n'); self.assert_block('positive discovery')

    def test_named_discovery_and_actual_cases_must_match(self):
        self.manifest['proofs'][0]['discovery']=self.file_ref('s1.txt','tests/test_boundary.py::test_wrong\n1 test collected in 0.01s'); self.assert_block('discovery/JUnit mismatch')

    def test_stale_execution_is_rejected(self):
        self.rewrite_receipt('started_at_utc','2026-10-07T00:00:00+00:00'); self.assert_block('outside candidate window')

    def test_naive_timestamps_are_rejected(self):
        self.rewrite_receipt('started_at_utc','2026-10-08T00:00:00'); self.assert_block('timezone required')

    def test_environment_relabel_is_rejected(self):
        self.manifest['proofs'][0]['environment']='preview-real'; self.assert_block('environment mismatch')

    def test_historical_baseline_cannot_supply_current_pass(self):
        self.manifest['proofs'][0]['environment']='historical'; self.assert_block('unsupported environment')

    def test_pass_without_proof_is_rejected(self):
        self.manifest['cases'][1]['status']='passed'; self.assert_block('pass requires valid proof')

    def test_postdeploy_fixture_cannot_be_promoted(self):
        row=next(x for x in self.manifest['cases'] if x['case_id']=='U01');row.update(status='passed',proof_ids=['s1']); self.assert_block('requires production-readback')

    def test_human_case_cannot_use_junit_or_fixture(self):
        row=next(x for x in self.manifest['cases'] if x['case_id']=='U10');row.update(status='passed',proof_ids=['s1']); self.assert_block('requires actual human observations')

    def test_unapproved_supersession_is_rejected(self):
        self.manifest['cases'][1].update(status='superseded',successors=['B15','O26-05']); self.assert_block('unapproved supersession')

    def test_approved_supersession_requires_both_verified_successors(self):
        row=next(x for x in self.manifest['cases'] if x['case_id']=='B14');row.update(status='superseded',successors=['B15','O26-05']); self.assert_block('successors not verified')

    def test_junit_cannot_close_real_provider_or_human_gate(self):
        self.manifest['gates']=[{'gate_id':'real-research','proof_ids':['s1']}]
        result=self.check();self.assertFalse(result['predeploy_ready']);self.assertTrue(any('typed external evidence validator pending' in x for x in result['blockers']))

    def test_risk_acceptance_cannot_close_workspace500(self):
        self.manifest['open_findings']=[];self.manifest['risk_acceptance']={'F21':'owner accepted'}
        result=self.check();self.assertFalse(result['predeploy_ready']);self.assertIn('F21: historical workspace500 root cause remains open',result['blockers'])

    def test_validator_can_use_positive_named_json_discovery(self):
        proof=self.manifest['proofs'][0];proof['discovery_format']='named-json';proof['discovery']=self.file_ref('s1.txt',json.dumps({'schema':'buyeros.named-discovery.v1','exit_code':0,'cases':['tests.test_boundary::test_owned_and_foreign']}))
        self.assertTrue(self.check()['automated_evidence_valid'])

    def test_structural_bundle_never_dispatches_provider_or_deploy(self):
        result=self.check();self.assertEqual(result['external_operations'],0);self.assertEqual(result['authority'],'read-only local evidence validation')

    def test_utf16_entities_cannot_bypass_declaration_guard(self):
        xml='<!DOCTYPE testsuite [<!ENTITY e "expanded">]><testsuite><testcase classname="tests.test_boundary" name="test_owned_and_foreign"><system-out>&e;</system-out></testcase></testsuite>'
        self.manifest['proofs'][0]['junit']=self.file_ref('s1.xml',xml.encode('utf-16'))
        self.assert_block('UTF-8 JUnit required')

    def test_case_pass_must_name_its_actual_assertions(self):
        row=next(x for x in self.manifest['cases'] if x['case_id']=='U02');row.update(status='passed',proof_ids=['s1'])
        self.assert_block('case assertion names required')

    def test_case_cannot_name_assertion_absent_from_its_proof(self):
        row=next(x for x in self.manifest['cases'] if x['case_id']=='U02');row.update(status='passed',proof_ids=['s1'],test_names=['tests.other::test_invented'])
        self.assert_block('case assertions absent')

    def test_case_owned_positive_control_can_reference_actual_named_proof(self):
        row=next(x for x in self.manifest['cases'] if x['case_id']=='U02');row.update(status='passed',proof_ids=['s1'],test_names=['tests.test_boundary::test_owned_and_foreign'])
        self.assertTrue(self.check()['automated_evidence_valid'])

    def copied_catalog(self):
        import shutil
        destination=self.root/'catalog'
        for relative in (self.checker.TRACE,self.checker.ORIGINAL,self.checker.NEW):
            target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/relative,target)
        return destination

    def test_rewriting_both_original_and_trace_cannot_redefine_history(self):
        import csv
        destination=self.copied_catalog()
        for relative in (self.checker.TRACE,self.checker.ORIGINAL):
            path=destination/relative
            with path.open(encoding='utf-8-sig',newline='') as f:reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
            rows[0]['actual']='invented rewritten history'
            with path.open('w',encoding='utf-8-sig',newline='') as f:writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
        with self.assertRaisesRegex(ValueError,'original audit digest'):self.checker.load_catalog(destination)

    def test_optimized_interpreter_cannot_disable_phase_guard(self):
        import csv
        destination=self.copied_catalog();path=destination/self.checker.TRACE
        with path.open(encoding='utf-8-sig',newline='') as f:reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
        rows[0]['release_stage']='release-A-predeploy;final-acceptance-in-declared-environment'
        with path.open('w',encoding='utf-8-sig',newline='') as f:writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
        code="import importlib.util,sys; s=importlib.util.spec_from_file_location('checker',sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.load_catalog(sys.argv[2])"
        result=subprocess.run([sys.executable,'-O','-c',code,str(CHECKER),str(destination)],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('unapproved original phase change',result.stderr)

class FullBackendGateTests(unittest.TestCase):
    def setUp(self):
        self.fixture = EvidenceTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.proof = self.fixture.manifest['proofs'][0]
        self.fixture.manifest['gates'] = [{'gate_id': 'api-full', 'proof_ids': ['s1']}]

    def full_job(self, gate='api-full'):
        service = 'api' if gate == 'api-full' else 'worker'
        inventory = {'schema': 'buyeros.required-test-inventory.v1', 'source_sha': SHA,
                     'source_tree': TREE, 'environment': 'owned-fixture', 'gate_id': gate,
                     'cases': ['tests.test_boundary::test_owned_and_foreign']}
        ref = self.fixture.file_ref('full-inventory.json', json.dumps(inventory))
        receipt = json.loads((self.fixture.root/self.proof['provenance']['path']).read_text())
        receipt['full_job'] = {'schema': 'buyeros.full-backend-job.v1', 'gate_id': gate,
                               'cwd': 'services/'+service, 'test_root': 'tests',
                               'strict_integration': True, 'fixture_scope': 'owned-loopback-PG16',
                               'discovery_command': ['python', '-m', 'pytest', 'tests', '-q', '--collect-only'],
                               'execution_command': ['python', '-m', 'pytest', 'tests', '-q', '--junitxml=out.xml'],
                               'required_inventory': ref}
        self.receipt = receipt
        self.inventory = inventory
        self.fixture.manifest['gates'][0]['gate_id'] = gate
        self.flush()

    def flush(self):
        self.proof['provenance'] = self.fixture.file_ref('s1.json', json.dumps(self.receipt))

    def reject_gate(self, token):
        result = self.fixture.check()
        self.assertTrue(result['automated_evidence_valid'], result)
        self.assertTrue(any('api-full: '+token in x for x in result['blockers']), result['blockers'])
        self.assertNotIn('api-full', result.get('validated_automated_gates', []))
        self.assertFalse(result['predeploy_ready'])

    def test_full_gate_rejects_unscoped_valid_subset(self):
        self.reject_gate('full backend job provenance required')

    def test_full_api_positive_control_requires_exact_inventory_and_stays_no_go(self):
        self.full_job()
        result = self.fixture.check()
        self.assertEqual(result.get('validated_automated_gates'), ['api-full'])
        self.assertFalse(result['predeploy_ready'])
        self.assertFalse(result['release_accepted'])

    def test_full_worker_positive_control_is_independent(self):
        self.full_job('worker-full')
        result = self.fixture.check()
        self.assertEqual(result.get('validated_automated_gates'), ['worker-full'])
        self.assertFalse(result['predeploy_ready'])

    def test_full_gate_rejects_other_service_full_job(self):
        self.full_job('worker-full')
        self.fixture.manifest['gates'][0]['gate_id'] = 'api-full'
        self.reject_gate('full job gate mismatch')

    def test_full_gate_rejects_wrong_working_directory(self):
        self.full_job(); self.receipt['full_job']['cwd'] = 'services/worker'; self.flush()
        self.reject_gate('full job service/root mismatch')

    def test_full_gate_rejects_module_only_execution(self):
        self.full_job(); self.receipt['full_job']['execution_command'][3] = 'tests/test_boundary.py'; self.flush()
        self.reject_gate('unfiltered full pytest command required')

    def test_full_gate_rejects_execution_keyword_filter(self):
        self.full_job(); self.receipt['full_job']['execution_command'] += ['-k', 'owned']; self.flush()
        self.reject_gate('unfiltered full pytest command required')

    def test_full_gate_rejects_discovery_marker_filter(self):
        self.full_job(); self.receipt['full_job']['discovery_command'] += ['-m', 'unit']; self.flush()
        self.reject_gate('unfiltered full pytest command required')

    def test_full_gate_rejects_collection_as_execution(self):
        self.full_job(); self.receipt['full_job']['execution_command'].append('--collect-only'); self.flush()
        self.reject_gate('unfiltered full pytest command required')

    def test_full_gate_requires_strict_owned_environment(self):
        self.full_job(); self.receipt['full_job']['strict_integration'] = 1; self.flush()
        self.reject_gate('strict owned backend fixture required')

    def test_full_gate_rejects_inventory_candidate_drift(self):
        self.full_job(); self.inventory['source_sha'] = 'c'*40
        self.receipt['full_job']['required_inventory'] = self.fixture.file_ref('full-inventory.json', json.dumps(self.inventory)); self.flush()
        self.reject_gate('full inventory source/gate/environment mismatch')

    def test_full_gate_rejects_missing_executed_inventory_case(self):
        self.full_job(); self.inventory['cases'].append('tests.other::test_missing')
        self.receipt['full_job']['required_inventory'] = self.fixture.file_ref('full-inventory.json', json.dumps(self.inventory)); self.flush()
        self.reject_gate('full inventory/discovery/JUnit mismatch')

    def test_full_gate_rejects_duplicate_inventory_names(self):
        self.full_job(); self.inventory['cases'] *= 2
        self.receipt['full_job']['required_inventory'] = self.fixture.file_ref('full-inventory.json', json.dumps(self.inventory)); self.flush()
        self.reject_gate('unique full inventory cases required')

    def test_built_ui_cannot_satisfy_full_api(self):
        self.full_job(); self.proof['environment'] = 'built-fixture'
        self.receipt['environment'] = 'built-fixture'; self.flush()
        self.reject_gate('strict owned backend fixture required')

    def test_pytest_ipv6_parameter_is_preserved_as_one_test_name(self):
        name = 'test_owned_and_foreign[https://[::1]/a]'
        self.proof['junit'] = self.fixture.file_ref('s1.xml', '<testsuite tests="1"><testcase classname="tests.test_boundary" name="'+name+'"/></testsuite>')
        self.proof['discovery'] = self.fixture.file_ref('s1.txt', 'tests/test_boundary.py::'+name+'\n1 test collected in 0.01s\n')
        self.fixture.manifest['gates'] = []
        self.assertTrue(self.fixture.check()['automated_evidence_valid'])



class FullRootFocusedTests(unittest.TestCase):
 def setUp(self):self.checker=load_checker()
 def test_full_execution_requires_explicit_tests_root(self):
  with self.assertRaisesRegex(ValueError,'unfiltered full pytest command required'):self.checker._full_pytest_command(['python','-m','pytest','-q','--junitxml=proof.xml'],False)
 def test_full_discovery_requires_explicit_tests_root(self):
  with self.assertRaisesRegex(ValueError,'unfiltered full pytest command required'):self.checker._full_pytest_command(['uv','run','--frozen','pytest','--collect-only','-q'],True)
 def test_full_execution_empty_args_is_not_full_inventory(self):
  with self.assertRaisesRegex(ValueError,'unfiltered full pytest command required'):self.checker._full_pytest_command(['pytest'],False)
 def test_explicit_full_roots_keep_python_and_frozen_uv_controls(self):
  self.checker._full_pytest_command(['python','-X','utf8','-m','pytest','tests','-q','--junitxml=proof.xml'],False)
  self.checker._full_pytest_command(['uv','run','--frozen','pytest','tests','-q','--collect-only'],True)
 def test_module_substitution_cannot_become_the_full_root(self):
  with self.assertRaisesRegex(ValueError,'unfiltered full pytest command required'):self.checker._full_pytest_command(['pytest','tests/test_boundary.py','--collect-only'],True)


class FullControllerJobTests(unittest.TestCase):
 def setUp(self):
  self.fixture=EvidenceTests();self.fixture.setUp();self.addCleanup(self.fixture.tmp.cleanup)
  f=self.fixture;proof=f.manifest['proofs'][0];self.proof=proof
  name='services/cloudflare-jobs/tests/handler.test.ts::test_exact_owned_handler'
  proof['junit']=f.file_ref('s1.xml','<testsuite tests="1"><testcase classname="services/cloudflare-jobs/tests/handler.test.ts" name="test_exact_owned_handler"/></testsuite>')
  proof['discovery']=f.file_ref('s1.discovery.json',json.dumps(dict(schema='buyeros.named-discovery.v1',exit_code=0,cases=[name])))
  proof['discovery_format']='named-json'
  inventory=f.file_ref('controller-inventory.json',json.dumps(dict(schema='buyeros.required-test-inventory.v1',source_sha=SHA,source_tree=TREE,gate_id='controller-full',environment='owned-fixture',cases=[name])))
  self.steps=[]
  commands=[('frozen-install',['pnpm','install','--frozen-lockfile']),('types',['pnpm','cloudflare:types']),('lint',['pnpm','cloudflare:lint']),('bindings',['pnpm','cloudflare:bindings']),('discovery',['pnpm','exec','vitest','list','--config','services/cloudflare-jobs/vitest.config.ts','--json','discovery.json']),('tests',['pnpm','cloudflare:test','--reporter=default','--reporter=junit','--outputFile.junit=tests.xml']),('dry-run',['pnpm','exec','wrangler','deploy','--dry-run','--config','services/cloudflare-jobs/wrangler.jsonc','--outdir','.sites-runtime/controller-dry-run'])]
  for index,(sid,command) in enumerate(commands):
   self.steps.append(dict(step_id=sid,command=command,exit_code=0,started_at_utc='2026-10-08T00:00:'+str(index*2).zfill(2)+'+00:00',finished_at_utc='2026-10-08T00:00:'+str(index*2+1).zfill(2)+'+00:00',log=f.file_ref(sid+'.log','synthetic unit fixture '+sid)))
  self.job=dict(schema='buyeros.full-controller-job.v1',gate_id='controller-full',cwd='.',fixture_scope='explicit-owned-Miniflare',dependency_scope='fresh-owned-node_modules',source_unchanged=True,shared_node_modules=False,package_manifest=f.file_ref('package.json','{"private":true}'),lockfile=f.file_ref('pnpm-lock.yaml','synthetic frozen lock fixture'),lockfile_after_sha256=hashlib.sha256(b'synthetic frozen lock fixture').hexdigest(),required_inventory=inventory,steps=self.steps)
  self.receipt=json.loads((f.root/proof['provenance']['path']).read_text());self.receipt['full_job']=self.job
  f.manifest['gates']=[dict(gate_id='controller-full',proof_ids=['s1'])];self.flush()
 def flush(self):self.proof['provenance']=self.fixture.file_ref('s1.json',json.dumps(self.receipt))
 def rejected(self):
  self.flush();result=self.fixture.check();self.assertTrue(result['automated_evidence_valid'],result);self.assertNotIn('controller-full',result['validated_automated_gates']);self.assertFalse(result['predeploy_ready'])
 def test_controller_complete_named_original_job_is_valid_and_stays_release_no_go(self):
  result=self.fixture.check();self.assertIn('controller-full',result['validated_automated_gates'],result['blockers']);self.assertFalse(result['predeploy_ready']);self.assertFalse(result['release_accepted']);self.assertFalse(result['neon_only_accepted']);self.assertFalse(result['native_send_accepted'])
 def test_controller_windows_exact_pnpm_argv_is_valid_without_shell_text(self):
  for step in self.steps:step['command']=['cmd.exe','/d','/c',*step['command']]
  self.flush();self.assertIn('controller-full',self.fixture.check()['validated_automated_gates'])
 def test_controller_missing_frozen_install_cannot_pass_with_unit_junit(self):
  self.steps.pop(0);self.rejected()
 def test_controller_ignore_scripts_or_unfrozen_install_is_not_original_job(self):
  self.steps[0]['command']+=['--ignore-scripts'];self.rejected()
 def test_controller_module_keyword_filter_is_not_full_execution(self):
  self.steps[5]['command']+=['-t','test_exact_owned_handler'];self.rejected()
 def test_controller_missing_bindings_check_does_not_pass(self):
  self.steps.pop(3);self.rejected()
 def test_controller_wrangler_publish_is_not_dry_run(self):
  self.steps[-1]['command'].remove('--dry-run');self.rejected()
 def test_controller_different_vitest_config_is_not_required_inventory(self):
  self.steps[4]['command'][5]='vitest.config.ts';self.rejected()
 def test_controller_shared_dependency_junction_is_not_fresh_install(self):
  self.job['shared_node_modules']=True;self.rejected()
 def test_controller_changed_lockfile_does_not_pass(self):
  self.job['lockfile_after_sha256']='c'*64;self.rejected()
 def test_controller_boolean_step_exit_is_not_native_zero(self):
  self.steps[2]['exit_code']=False;self.rejected()
 def test_controller_nonzero_original_step_cannot_pass(self):
  self.steps[1]['exit_code']=1;self.rejected()
 def test_controller_step_outside_proof_window_is_not_current(self):
  self.steps[3]['started_at_utc']='2026-10-07T00:00:00+00:00';self.rejected()
 def test_controller_duplicate_step_cannot_hide_missing_original_check(self):
  self.steps[3]=copy.deepcopy(self.steps[2]);self.rejected()
 def test_controller_source_drift_does_not_pass(self):
  self.job['source_unchanged']=False;self.rejected()
 def test_controller_unscoped_subset_junit_remains_refused(self):
  del self.receipt['full_job'];self.rejected()
 def test_controller_other_service_or_fixture_scope_is_refused(self):
  self.job['fixture_scope']='production';self.rejected()
 def test_controller_tampered_original_step_log_does_not_pass(self):
  (self.fixture.root/'lint.log').write_text('changed');self.rejected()


if __name__=='__main__':unittest.main()
