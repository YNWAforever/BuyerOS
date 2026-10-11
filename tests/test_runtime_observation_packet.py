"""Protected read scope and publication scope controls, owned packets only."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from test_workspace_runtime_observations import packet, TOKENS

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT/'scripts/runtime-observation-packet.py'
    assert path.exists(), 'protected runtime observation packet handler is absent'
    spec = importlib.util.spec_from_file_location('runtime_packet', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def schema_contract():
    target = {'database': 'owned', 'endpoint_sha256': '1'*64, 'metadata_receipt_sha256': '2'*64}
    return {'contract_version': 'buyeros.schema-contract.v1', 'source_sha': 'a'*40,
            'required_revisions': ['0039_c61_user_identities'], 'compatible_heads': ['0050_c61_delivery_authorizations'],
            'required_relations': {'public.user_identities': ['user_id']},
            'required_functions': ['public.buyeros_workspace_directory(uuid,bigint,integer)'],
            'required_privileges': [{'relation': 'public.user_identities', 'columns': ['user_id'], 'privilege': 'SELECT'}],
            'required_rls': ['public.memberships'], 'runtime_role_policy': {'role': 'buyeros_api', 'superuser': False, 'bypass_rls': False},
            'target': target, 'target_receipt': copy.deepcopy(target), 'evidence_mode': 'candidate_runtime', 'statement_timeout_ms': 5000}


class RuntimePacketTests(unittest.TestCase):
    def setUp(self):
        self.api, self.schema = packet(), schema_contract()
        self.environment = {
            'GITHUB_REF': 'refs/heads/main', 'GITHUB_SHA': 'a'*40,
            'BUYEROS_G0_TARGET_JSON': json.dumps(self.api), 'BUYEROS_SCHEMA_CONTRACT_JSON': json.dumps(self.schema),
            'BUYEROS_G0_ALLOWED_ORIGIN': self.api['origin'],
            'BUYEROS_RUNTIME_READ_SCOPE_SHA256': self.api['authorization_reference_sha256'],
            'BUYEROS_G0_CONTRACT_SHA256': digest(self.api), 'BUYEROS_SCHEMA_CONTRACT_SHA256': digest(self.schema),
            'PUBLISH_OBSERVATIONS': 'false',
            **{'BUYEROS_G0_'+key.upper()+'_TOKEN': token for key, token in TOKENS.items()}}
        self.environment['BUYEROS_RUNTIME_WORKFLOW_REQUEST_SHA256'] = digest({
            'source_sha': 'a'*40, 'api_contract_sha256': digest(self.api), 'schema_contract_sha256': digest(self.schema),
            'artifact_scope': 'public-workflow-status-v1'})

    def prepare(self):
        with tempfile.TemporaryDirectory() as parent:
            directory = Path(parent)/'private'
            result = load().prepare(directory, self.environment)
            self.assertEqual(result, {'source_sha': 'a'*40, 'publish': False})
            self.assertEqual(json.loads((directory/'api-contract.json').read_text()), self.api)
            for path in directory.iterdir():
                for token in TOKENS.values(): self.assertNotIn(token, path.read_text())

    def reject(self):
        with tempfile.TemporaryDirectory() as parent:
            directory = Path(parent)/'private'
            with self.assertRaises(ValueError): load().prepare(directory, self.environment)
            self.assertFalse(directory.exists())

    def test_reviewed_packets_prepare_without_secret_credentials(self): self.prepare()

    def test_pr_context_cannot_materialize_runtime_packet(self):
        self.environment['GITHUB_REF'] = 'refs/pull/13/merge'; self.reject()

    def test_stale_source_cannot_materialize_runtime_packet(self):
        self.environment['GITHUB_SHA'] = 'c'*40; self.reject()

    def test_fixture_schema_cannot_be_relabelled_runtime(self):
        self.schema['evidence_mode'] = 'owned_disposable_fixture'
        self.environment['BUYEROS_SCHEMA_CONTRACT_JSON'] = json.dumps(self.schema)
        self.environment['BUYEROS_SCHEMA_CONTRACT_SHA256'] = digest(self.schema)
        self.reject()

    def test_unbound_schema_target_is_rejected(self):
        self.schema['target_receipt'] = None
        self.environment['BUYEROS_SCHEMA_CONTRACT_JSON'] = json.dumps(self.schema)
        self.environment['BUYEROS_SCHEMA_CONTRACT_SHA256'] = digest(self.schema)
        self.reject()

    def test_different_branch_proof_is_rejected(self):
        self.schema['target_receipt']['endpoint_sha256'] = '3'*64
        self.environment['BUYEROS_SCHEMA_CONTRACT_JSON'] = json.dumps(self.schema)
        self.environment['BUYEROS_SCHEMA_CONTRACT_SHA256'] = digest(self.schema)
        self.reject()

    def test_reviewed_contract_digest_cannot_drift(self):
        self.environment['BUYEROS_G0_CONTRACT_SHA256'] = '3'*64; self.reject()

    def test_read_scope_reference_is_required(self):
        self.environment['BUYEROS_RUNTIME_READ_SCOPE_SHA256'] = ''; self.reject()

    def test_boolean_publication_request_is_not_export_authorization(self):
        self.environment['PUBLISH_OBSERVATIONS'] = 'true'; self.reject()

    def test_public_workflow_status_requires_its_own_exact_disclosure_scope(self):
        del self.environment['BUYEROS_RUNTIME_WORKFLOW_REQUEST_SHA256']
        self.reject()

    def test_other_publication_scope_cannot_authorize_workflow_status(self):
        self.environment['BUYEROS_RUNTIME_WORKFLOW_REQUEST_SHA256'] = digest({
            'source_sha': 'a'*40, 'api_contract_sha256': digest(self.api), 'schema_contract_sha256': digest(self.schema),
            'artifact_scope': 'public-redacted-observations-v1'})
        self.reject()

    def test_generic_publication_scope_is_not_exact_payload_authorization(self):
        self.environment.update(PUBLISH_OBSERVATIONS='true', BUYEROS_RUNTIME_PUBLICATION_SCOPE='public-redacted-observations-v1')
        self.environment['BUYEROS_RUNTIME_PUBLICATION_REQUEST_SHA256'] = '4'*64
        self.reject()

    def test_exact_reviewed_publication_payload_has_positive_control(self):
        module = load()
        request = module.publication_request('a'*40, digest(self.api), digest(self.schema))
        self.environment.update(PUBLISH_OBSERVATIONS='true', BUYEROS_RUNTIME_PUBLICATION_SCOPE='public-redacted-observations-v1',
                                BUYEROS_RUNTIME_PUBLICATION_REQUEST_SHA256=digest(request))
        with tempfile.TemporaryDirectory() as parent:
            result = module.prepare(Path(parent)/'private', self.environment)
        self.assertTrue(result['publish'])

    def test_successful_native_reads_still_cannot_replace_browser_mapping_and_rollback(self):
        with tempfile.TemporaryDirectory() as parent:
            directory = Path(parent)
            api = {'schema': 'buyeros.workspace-api-observations.v1', 'reviewed_source_sha': 'a'*40,
                   'all_checks_passed': True, 'checks': [{'passed': True} for _ in range(7)]}
            schema = {'schema': 'buyeros.schema-readiness.v1', 'source_sha': 'a'*40, 'evidence_mode': 'candidate_runtime',
                      'compatible': True, 'target_match': True, 'blockers': [], 'checks': [{'passed': True}]}
            (directory/'api-observations.json').write_text(json.dumps(api), encoding='utf-8')
            (directory/'schema-observations.json').write_text(json.dumps(schema), encoding='utf-8')
            result = load().summarize(directory, 'a'*40)
        self.assertTrue(result['all_read_checks_passed'])
        self.assertFalse(result['promotable'])
        self.assertIn('compatible_frontend_api_rollback_not_collected', result['acceptance_blockers'])

    def test_duplicate_json_keys_are_rejected(self):
        self.environment['BUYEROS_G0_TARGET_JSON'] = '{"source_sha":"a","source_sha":"b"}'
        self.reject()

    def test_missing_native_receipts_are_partial_not_promotable(self):
        with tempfile.TemporaryDirectory() as parent:
            result = load().summarize(Path(parent), 'a'*40)
        self.assertFalse(result['all_read_checks_passed'])
        self.assertFalse(result['promotable'])
        self.assertNotIn('manifest', result)


if __name__ == '__main__': unittest.main()
