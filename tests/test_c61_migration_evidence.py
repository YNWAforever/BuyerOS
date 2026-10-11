"""Typed owned migration proof controls; synthetic files are never live receipts."""
import copy
import json
import unittest
import test_c61_evidence as base

REQUIRED = {
    'tests.test_identity_migration_db::test_fresh_0038_backfill_and_retained_rollback_preserve_canonical_history',
    'tests.test_identity_migration_db::test_identity_revision_preserves_runtime_off_and_rejects_unknown_future_head',
    'tests.test_identity_migration_db::test_supported_0038_upgrade_to_current_head_preserves_history_and_restricted_runtime',
    'tests.test_neon_cutover_db::test_identity_collision_stops_entire_cutover_batch[0]',
    'tests.test_neon_cutover_db::test_identity_collision_stops_entire_cutover_batch[1]',
    'tests.test_neon_cutover_db::test_later_denied_workspace_rolls_back_earlier_mapping',
    'tests.test_neon_cutover_db::test_unknown_batch_commit_has_one_transaction_and_only_readonly_recovery',
    'tests.test_neon_cutover_db::test_neon_cutover_rollback_preserves_new_users',
    'tests.test_neon_cutover_db::test_restore_replays_deletion_before_reopen',
    'tests.test_neon_cutover_db::test_atomic_manifest_scopes_multiple_workspaces_and_replays',
    'tests.test_delivery_admission_db::test_delivery_authority_schema_force_RLS_and_runtime_grants_are_real',
    'tests.test_delivery_admission_db::test_delivery_authority_force_RLS_owned_positive_foreign_denial_and_immutable_runtime_grants',
    'tests.test_delivery_admission_db::test_empty0050_downgrade_and_reupgrade_restore_exact_head_receipt_guards',
    'tests.test_delivery_admission_db::test_populated_authority_downgrade_refuses_and_retains_original_refs_and_full_hold',
}


class MigrationEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.h = base.FullBackendGateTests()
        self.h.setUp()
        self.addCleanup(self.h.doCleanups)
        self.h.full_job()
        self.f = self.h.fixture
        self.f.manifest['gates'] = [{'gate_id': 'migration-runtime', 'proof_ids': ['s1']}]
        self.install_names(REQUIRED)
        ids = ['11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222']
        snapshot = {
            'canonical_ids': ids, 'identities': {'count': 4, 'sha256': 'a' * 64},
            'historical_fks': {user: {'membership': 'b' * 64} for user in ids},
            'ledger_and_unknown': {name: {'count': 1, 'sha256': 'c' * 64} for name in ('budget_accounts', 'budget_reservations', 'provider_operations', 'cost_events')},
        }
        closed = {'statuses': {'migrated': 503, 'neon_only': 503, 'revoked': 503},
                  'codes': {'migrated': 'READ_DISABLED', 'neon_only': 'READ_DISABLED', 'revoked': 'READ_DISABLED'}}
        steps = ['current_receipt_privacy_schema_before_backup', 'older_backup', 'external_fixture_tombstone',
                 'restored_backup_still_closed', 'tombstone_replayed_twice_and_ledger_reconciled_reads_still_closed',
                 'old_epoch_cannot_resume_or_submit', 'local_reviewer_reopens_only_reads_with_compatible_neon_api_workers_unready']
        self.report = {'before': snapshot, 'after': copy.deepcopy(snapshot), 'closed_before': closed, 'closed_after': copy.deepcopy(closed),
                       'rollback_sha': 'd' * 40, 'archive_sha256': 'e' * 64,
                       'unknown_holds_preserved': True, 'tombstone_replayed': True, 'old_epoch_fenced': True,
                       'reopened': {'statuses': {'migrated': 200, 'neon_only': 200, 'revoked': 404},
                                    'codes': {'migrated': None, 'neon_only': None, 'revoked': 'NOT_FOUND'},
                                    'canonical_project_ids': {'migrated': ids[0], 'neon_only': ids[0]},
                                    'ready': False, 'auth_package_from_archive': True, 'approved_JWKS_fetches': 1, 'exception_metadata': {}},
                       'timeline': [{'step': step, 'utc': f'2026-10-08T00:00:{i + 1:02d}+00:00'} for i, step in enumerate(steps)]}
        self.report['timeline'][0]['schema'] = '0050_c61_delivery_authorizations'
        self.h.receipt['migration_runtime'] = {'schema': 'buyeros.migration-runtime-job.v1', 'gate_id': 'migration-runtime',
                                              'scope': 'owned-PG16-supported0038-current0050-and-retained-app-rollback',
                                              'from_head': '0038_c61_workspace_directory', 'to_head': '0050_c61_delivery_authorizations',
                                              'real_Neon_or_production_acceptance': False}
        self.flush()

    def install_names(self, names):
        names = sorted(names)
        xml = '<testsuite tests="' + str(len(names)) + '">' + ''.join(
            '<testcase classname="' + name.split('::')[0] + '" name="' + name.split('::')[1] + '"/>' for name in names) + '</testsuite>'
        discovery = '\n'.join(name.split('::')[0].replace('.', '/') + '.py::' + name.split('::')[1] for name in names) + f'\n{len(names)} tests collected in 0.01s\n'
        self.h.proof['junit'] = self.f.file_ref('s1.xml', xml)
        self.h.proof['discovery'] = self.f.file_ref('s1.txt', discovery)
        self.h.inventory['cases'] = names
        self.h.receipt['full_job']['required_inventory'] = self.f.file_ref('full-inventory.json', json.dumps(self.h.inventory))
        self.h.flush()

    def flush(self):
        self.h.receipt['migration_runtime']['retained_rollback_report'] = self.f.file_ref('cold-rollback.json', json.dumps(self.report))
        self.h.flush()

    def rejected(self):
        self.flush()
        result = self.f.check()
        self.assertNotIn('migration-runtime', result.get('validated_domain_gates', []), result)
        self.assertFalse(result['predeploy_ready'])
        self.assertTrue(any('migration-runtime:' in item for item in result['blockers']), result)

    def test_complete_owned_migration_proof_is_scoped_and_release_stays_no_go(self):
        result = self.f.check()
        self.assertIn('migration-runtime', result.get('validated_domain_gates', []), result)
        self.assertTrue(result['automated_evidence_valid'], result)
        self.assertTrue(all(result[key] is False for key in ('predeploy_ready', 'release_accepted', 'neon_only_accepted', 'native_send_accepted')))
        self.assertIn('real-auth: typed external evidence validator pending', result['blockers'])

    def test_bare_full_API_JUnit_cannot_replace_retained_migration_report(self):
        del self.h.receipt['migration_runtime']
        self.h.flush()
        result = self.f.check()
        self.assertNotIn('migration-runtime', result.get('validated_domain_gates', []), result)
        self.assertFalse(result['predeploy_ready'])

    def test_missing_current_supported_upgrade_assertion_is_not_migration_acceptance(self):
        self.install_names(REQUIRED - {'tests.test_identity_migration_db::test_supported_0038_upgrade_to_current_head_preserves_history_and_restricted_runtime'})
        self.rejected()

    def test_changed_UUID_FK_or_unknown_hold_cannot_pass(self):
        original = copy.deepcopy(self.report)
        for key in ('canonical_ids', 'historical_fks', 'ledger_and_unknown'):
            with self.subTest(key=key):
                self.report = copy.deepcopy(original)
                self.report['after'][key] = []
                self.rejected()

    def test_false_tombstone_hold_or_epoch_fence_is_not_a_rollback(self):
        for key in ('tombstone_replayed', 'unknown_holds_preserved', 'old_epoch_fenced'):
            with self.subTest(key=key):
                self.report[key] = False
                self.rejected()
                self.report[key] = True

    def test_historical_or_reordered_timeline_cannot_be_current(self):
        original = copy.deepcopy(self.report)
        self.report['timeline'][0]['utc'] = '2026-10-07T00:00:00+00:00'
        self.rejected()
        self.report = copy.deepcopy(original)
        self.report['timeline'][2], self.report['timeline'][3] = self.report['timeline'][3], self.report['timeline'][2]
        self.rejected()

    def test_reopened_runtime_readiness_and_revoked_identity_stay_refused(self):
        self.report['reopened']['ready'] = True
        self.rejected()
        self.report['reopened']['ready'] = False
        self.report['reopened']['statuses']['revoked'] = 200
        self.rejected()

    def test_fake_empty_history_or_zero_unknown_hold_cannot_pass(self):
        original = copy.deepcopy(self.report)
        self.report['before']['canonical_ids'] = []
        self.report['after']['canonical_ids'] = []
        self.rejected()
        self.report = copy.deepcopy(original)
        for key in ('before', 'after'):
            self.report[key]['ledger_and_unknown']['budget_reservations']['count'] = 0
        self.rejected()

    def test_owned_migration_proof_cannot_claim_real_Neon_or_production(self):
        self.h.receipt['migration_runtime']['real_Neon_or_production_acceptance'] = True
        self.rejected()

    def test_numeric_digest_or_boolean_count_cannot_fake_native_readback(self):
        original = copy.deepcopy(self.report)
        for kind in ('identity-digest', 'FK-digest', 'archive-digest', 'rollback-SHA', 'boolean-count'):
            with self.subTest(kind=kind):
                self.report = copy.deepcopy(original)
                if kind == 'identity-digest':
                    self.report['before']['identities']['sha256'] = int('1' * 64)
                elif kind == 'FK-digest':
                    for key in ('before', 'after'):
                        for rows in self.report[key]['historical_fks'].values():
                            rows['membership'] = int('1' * 64)
                elif kind == 'archive-digest':
                    self.report['archive_sha256'] = int('1' * 64)
                elif kind == 'rollback-SHA':
                    self.report['rollback_sha'] = int('1' * 40)
                else:
                    self.report['before']['identities']['count'] = True
                self.rejected()
