"""The alias operation happens only after trusted receipts and fresh remote metadata."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from test_release_readiness import candidate

ROOT=Path(__file__).resolve().parents[1]

def load():
    path=ROOT/'scripts/promote-candidate.py'
    assert path.exists(), 'promotion entry point is absent'
    spec=importlib.util.spec_from_file_location('candidate_promotion',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

class CandidatePromotionTests(unittest.TestCase):
    def setUp(self):
        self.manifest,self.receipts=candidate();self.calls=[]
        self.metadata={'source_sha':self.manifest['source_sha'],'deployment_id':'dpl_candidate',
            'project_match':True,'team_match':True,'repository_match':True,
            'target':'production','ready_state':'READY','auto_main_disabled':True,'protected_main':True,
            'protected_environment':True,'ci_completed':True,'ci_head':self.manifest['source_sha'],
            'ci_run_id':123,'jobs':{key:'success' for key in self.manifest['required_ci_jobs']}}
    def promote(self,verified=True,execute=True):
        return load().promote(self.manifest,self.receipts,'workspace',attestation_verified=verified,
            metadata=self.metadata,execute=execute,promote_alias=lambda deployment:self.calls.append(deployment))
    def test_missing_identity_relation_never_changes_alias(self):
        schema=self.receipts['items']['schema']['data'];schema['compatible']=False
        schema['blockers']=['relation_missing:public.user_identities']
        self.assertFalse(self.promote()['promoted']);self.assertEqual(self.calls,[])
    def test_mutable_true_receipts_without_attestation_never_change_alias(self):
        self.assertFalse(self.promote(False)['promoted']);self.assertEqual(self.calls,[])
    def test_good_attested_candidate_calls_bound_alias_once(self):
        self.assertTrue(self.promote()['promoted']);self.assertEqual(self.calls,['dpl_candidate'])
    def test_preflight_does_not_change_alias(self):
        self.assertFalse(self.promote(execute=False)['promoted']);self.assertEqual(self.calls,[])
    def test_ready_preview_cannot_replace_staged_production_artifact(self):
        self.metadata['target']='preview';self.assertFalse(self.promote()['promoted']);self.assertEqual(self.calls,[])
    def test_wrong_remote_source_never_changes_alias(self):
        self.metadata['source_sha']='e'*40;self.assertFalse(self.promote()['promoted']);self.assertEqual(self.calls,[])
    def test_auto_main_bypass_never_changes_alias(self):
        self.metadata['auto_main_disabled']=False;self.assertFalse(self.promote()['promoted']);self.assertEqual(self.calls,[])
    def test_unprotected_main_never_changes_alias(self):
        self.metadata['protected_main']=False;self.assertFalse(self.promote()['promoted']);self.assertEqual(self.calls,[])
    def test_missing_environment_reviewer_never_changes_alias(self):
        self.metadata['protected_environment']=False;self.assertFalse(self.promote()['promoted']);self.assertEqual(self.calls,[])
    def test_fresh_failed_CI_never_changes_alias(self):
        self.metadata['jobs']['api']='failure';self.assertFalse(self.promote()['promoted']);self.assertEqual(self.calls,[])
    def test_foreign_project_never_changes_alias(self):
        self.metadata['project_match']=False;self.assertFalse(self.promote()['promoted']);self.assertEqual(self.calls,[])
    def test_foreign_team_never_changes_alias(self):
        self.metadata['team_match']=False;self.assertFalse(self.promote()['promoted']);self.assertEqual(self.calls,[])
    def test_foreign_repository_never_changes_alias(self):
        self.metadata['repository_match']=False;self.assertFalse(self.promote()['promoted']);self.assertEqual(self.calls,[])


    def test_workspace_bundle_requires_complete_current_runtime_receipts(self):
        module = load()
        bundle = module.build_workspace_bundle(self.manifest, self.receipts, source_sha=self.manifest['source_sha'])
        self.assertEqual(set(bundle), {'schema', 'manifest', 'receipts'})
        self.assertEqual(bundle['schema'], 'buyeros.attested-runtime-bundle.v1')
        self.assertEqual(bundle['manifest'], self.manifest)
        self.assertEqual(bundle['receipts'], self.receipts)
        self.assertEqual(self.calls, [])

    def test_partial_observation_summary_cannot_become_runtime_bundle(self):
        module = load()
        partial = {'schema': 'buyeros.runtime-observations.v1', 'reviewed_source_sha': self.manifest['source_sha'],
                   'all_read_checks_passed': True, 'promotable': False}
        with self.assertRaisesRegex(ValueError, 'workspace release receipts'):
            module.build_workspace_bundle(self.manifest, partial, source_sha=self.manifest['source_sha'])
        self.assertEqual(self.calls, [])

    def test_workspace_bundle_rejects_non_workspace_gates(self):
        module = load()
        with self.assertRaisesRegex(ValueError, 'workspace gate only'):
            module.build_workspace_bundle(self.manifest, self.receipts, source_sha=self.manifest['source_sha'], gate='research_export')
        with self.assertRaisesRegex(ValueError, 'workspace gate only'):
            module.build_workspace_bundle(self.manifest, self.receipts, source_sha=self.manifest['source_sha'], gate='native_send')
        self.assertEqual(self.calls, [])

    def test_workspace_receipts_join_current_native_reads_and_protected_canary(self):
        from runtime_bundle_fixtures import compose_inputs
        module = load()
        receipts = module.compose_workspace_receipts(**compose_inputs(self.manifest, self.receipts))
        bundle = module.build_workspace_bundle(self.manifest, receipts, source_sha=self.manifest['source_sha'])
        self.assertEqual(bundle['receipts'], receipts)

    def test_workspace_receipts_reject_unbound_live_read_hashes(self):
        from runtime_bundle_fixtures import compose_inputs
        inputs = compose_inputs(self.manifest, self.receipts)
        inputs['protected_receipts']['items']['workspace_canary']['data']['api_observation_sha256']='f'*64
        with self.assertRaisesRegex(ValueError, 'bind current read observations'):
            load().compose_workspace_receipts(**inputs)

    def test_workspace_bundle_rejects_stale_or_missing_receipts(self):
        module = load()
        stale = copy.deepcopy(self.receipts)
        stale['items']['schema']['checked_at'] = '2020-01-01T00:00:00+00:00'
        with self.assertRaisesRegex(ValueError, 'workspace release receipts'):
            module.build_workspace_bundle(self.manifest, stale, source_sha=self.manifest['source_sha'])
        missing = copy.deepcopy(self.receipts)
        missing['items'].pop('rollback')
        with self.assertRaisesRegex(ValueError, 'workspace release receipts'):
            module.build_workspace_bundle(self.manifest, missing, source_sha=self.manifest['source_sha'])

    def test_encrypted_bundle_round_trips_without_exposing_receipts(self):
        module = load()
        key = 'a'*64
        bundle = module.build_workspace_bundle(self.manifest, self.receipts, source_sha=self.manifest['source_sha'])
        envelope = module.encrypt_workspace_bundle(bundle, key)
        serialized = json.dumps(envelope)
        self.assertNotIn('buyeros.release-receipts.v1', serialized)
        self.assertNotIn('workspace_canary', serialized)
        self.assertEqual(module.decrypt_workspace_bundle(envelope, key), bundle)

    def test_encrypted_bundle_rejects_wrong_key_and_tampering(self):
        module = load()
        key = 'a'*64
        bundle = module.build_workspace_bundle(self.manifest, self.receipts, source_sha=self.manifest['source_sha'])
        envelope = module.encrypt_workspace_bundle(bundle, key)
        with self.assertRaisesRegex(ValueError, 'authentication failed'):
            module.decrypt_workspace_bundle(envelope, 'b'*64)
        tampered = copy.deepcopy(envelope)
        tampered['ciphertext'] = tampered['ciphertext'][:-4] + 'AAAA'
        with self.assertRaisesRegex(ValueError, 'authentication failed'):
            module.decrypt_workspace_bundle(tampered, key)
    def test_workspace_bundle_rejects_paid_provider_worker_or_delivery_activation(self):
        module = load()
        for activation in ({'providers': 'active'}, {'worker': 'active'}, {'delivery': 'active'}):
            manifest = copy.deepcopy(self.manifest)
            manifest['activation'].update(activation)
            with self.subTest(activation=activation), self.assertRaisesRegex(ValueError, 'workspace release receipts'):
                module.build_workspace_bundle(manifest, self.receipts, source_sha=manifest['source_sha'])
        self.assertEqual(self.calls, [])

if __name__=='__main__':unittest.main()
