"""The alias operation happens only after trusted receipts and fresh remote metadata."""
import importlib.util
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

if __name__=='__main__':unittest.main()
