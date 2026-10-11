"""C61-33a pure evidence joining; fixture files are not live receipts."""
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


def evaluate(manifest,receipts,gate='workspace'):
    path=ROOT/'scripts/check-release-readiness.py'
    assert path.exists(), 'runtime/artifact promotion gate is not implemented'
    spec=importlib.util.spec_from_file_location('release_readiness',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.evaluate_release(manifest,receipts,gate)


def candidate():
    manifest={'schema':'buyeros.release-manifest.v1','source_sha':'a'*40,'tree_sha':'b'*40,
        'configuration_sha256':'c'*64,'db_target_sha256':'d'*64,
        'frontend_artifact':'frontend-a','api_artifact':'api-a','worker_artifact':None,
        'required_heads':['0050_c61_delivery_authorizations'],'ci_run_id':123,
        'required_ci_jobs':['frontend','api','worker','browser-smoke','browser-continuity','browser-zoom',
            'audit-fixes','owned-worker-capacity','cloudflare-controller','cloudflare-staff-acceptance',
            'c61-evidence-checker','release-readiness'],
        'candidate_deployment_id':'dpl_candidate','receipt_max_age_seconds':900,
        'rollback_artifacts':{'frontend':'frontend-compatible','api':'api-compatible'},
        'activation':{'auth':'auth0','providers':'disabled','worker':'disabled','delivery':'disabled'}}
    common={'source_sha':manifest['source_sha'],'tree_sha':manifest['tree_sha'],
        'configuration_sha256':manifest['configuration_sha256'],'db_target_sha256':manifest['db_target_sha256'],
        'deployment_id':manifest['candidate_deployment_id'],'checked_at':datetime.now(timezone.utc).isoformat(),
        'evidence_mode':'candidate_runtime'}
    def receipt(data): return dict(common,data=data)
    receipts={'schema':'buyeros.release-receipts.v1','items':{
        'ci':receipt({'run_id':123,'head_sha':'a'*40,'status':'completed','conclusion':'success',
                      'jobs':{name:'success' for name in manifest['required_ci_jobs']}}),
        'artifacts':receipt({'frontend':'frontend-a','api':'api-a','worker':None}),
        'schema':receipt({'schema':'buyeros.schema-readiness.v1','source_sha':'a'*40,'checked_at':common['checked_at'],
             'target_match':True,'compatible':True,'observed_heads':['0050_c61_delivery_authorizations'],
             'checks':[{'code':'target_unproven_or_mismatched','passed':True},{'code':'runtime_role_mismatch','passed':True},
                       {'code':'runtime_role_privileged','passed':True},{'code':'schema_head_unknown','passed':True},
                       {'code':'required_revision_unproven','passed':True},
                       {'code':'relation_missing:public.user_identities','passed':True},
                       {'code':'function_missing_or_denied:public.buyeros_workspace_directory(uuid,bigint,integer)','passed':True}],
             'blockers':[],'evidence_mode':'candidate_runtime'}),
        'workspace_canary':receipt({'workspace_status':200,'correct_roles':True,'correct_project':True,
              'empty_membership_verified':True,'revoked_denied':True,'foreign_tenant_denied':True,'reload_retry_verified':True}),
        'rollback':receipt({'frontend':'frontend-compatible','api':'api-compatible','compatible':True})}}
    return manifest,receipts


class ReleaseReadinessTests(unittest.TestCase):
    def setUp(self): self.manifest,self.receipts=candidate()
    def check_blocked(self):
        result=evaluate(self.manifest,self.receipts)
        self.assertEqual(result['status'],'blocked'); self.assertFalse(result['promotable'])
    def test_workspace_does_not_require_paid_provider_or_worker_activation(self):
        self.assertTrue(evaluate(self.manifest,self.receipts)['promotable'])
    def test_declared_true_without_receipt_is_blocked(self):
        self.receipts['items'].pop('schema');self.check_blocked()
    def test_missing_relation_blocks_promotion(self):
        self.receipts['items']['schema']['data']['compatible']=False
        self.receipts['items']['schema']['data']['blockers']=['relation_missing:public.user_identities'];self.check_blocked()
    def test_same_head_wrong_target_is_blocked(self):
        self.receipts['items']['schema']['data']['target_match']=False;self.check_blocked()
    def test_wrong_runtime_role_is_blocked(self):
        self.receipts['items']['schema']['data']['checks'][1]['passed']=False;self.check_blocked()
    def test_same_sha_wrong_configuration_is_blocked(self):
        self.receipts['items']['workspace_canary']['configuration_sha256']='e'*64;self.check_blocked()
    def test_stale_receipt_is_blocked(self):
        self.receipts['items']['schema']['checked_at']=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat();self.check_blocked()
    def test_future_receipt_is_blocked(self):
        self.receipts['items']['schema']['checked_at']=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat();self.check_blocked()
    def test_pending_ci_is_blocked(self):
        self.receipts['items']['ci']['data']['status']='in_progress';self.check_blocked()
    def test_failed_ci_is_blocked(self):
        self.receipts['items']['ci']['data']['jobs']['api']='failure';self.check_blocked()
    def test_missing_required_ci_job_is_blocked(self):
        self.receipts['items']['ci']['data']['jobs'].pop('api');self.check_blocked()
    def test_manifest_cannot_reduce_required_CI_to_one_green_job(self):
        self.manifest['required_ci_jobs']=['frontend']
        self.assertEqual(evaluate(self.manifest,self.receipts)['status'],'malformed')
    def test_wrong_ci_head_is_blocked(self):
        self.receipts['items']['ci']['data']['head_sha']='f'*40;self.check_blocked()
    def test_unknown_manifest_key_is_malformed(self):
        self.manifest['predeploy_ready']=True
        self.assertEqual(evaluate(self.manifest,self.receipts)['status'],'malformed')
    def test_unknown_gate_is_malformed(self):
        self.assertEqual(evaluate(self.manifest,self.receipts,'health_live')['status'],'malformed')
    def test_missing_rollback_artifact_is_blocked(self):
        self.manifest['rollback_artifacts']['api']=None;self.check_blocked()
    def test_fixture_receipt_cannot_promote(self):
        self.receipts['items']['schema']['evidence_mode']='owned_disposable_fixture';self.check_blocked()
    def test_empty_schema_check_list_cannot_promote(self):
        self.receipts['items']['schema']['data']['checks']=[];self.check_blocked()
    def test_wrong_deployment_receipt_is_blocked(self):
        self.receipts['items']['workspace_canary']['deployment_id']='dpl_old';self.check_blocked()
    def test_research_gate_requires_real_neon_quality_performance_and_uat(self):
        result=evaluate(self.manifest,self.receipts,'research_export')
        self.assertFalse(result['promotable'])
        self.assertIn('receipt_missing:neon',result['blockers'])
        self.assertIn('receipt_missing:quality',result['blockers'])
        self.assertIn('receipt_missing:staff_uat',result['blockers'])
    def test_native_send_has_independent_delivery_acceptance(self):
        result=evaluate(self.manifest,self.receipts,'native_send')
        self.assertFalse(result['promotable'])
        self.assertIn('receipt_missing:delivery',result['blockers'])


if __name__=='__main__': unittest.main()
