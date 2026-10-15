"""Owned bundle inputs. These never represent hosted acceptance."""
import copy

API_CODES = [
    ('owned_workspace_roles_response', 200), ('owned_project_response', 200),
    ('empty_directory_response', 200), ('empty_account_project_not_found', 404),
    ('revoked_account_project_not_found', 404), ('foreign_tenant_project_not_found', 404),
    ('foreign_account_owned_project_response', 200),
]


def api_observation(source, checked_at):
    return {'schema':'buyeros.workspace-api-observations.v1', 'reviewed_source_sha':source,
            'contract_sha256':'4'*64, 'checked_at':checked_at, 'scope':'bounded_api_reads_only',
            'checks':[{'code':name, 'passed':True, 'observed_status':status, 'response_sha256':'9'*64}
                      for name, status in API_CODES], 'all_checks_passed':True, 'promotable':False,
            'acceptance_blockers':['browser_canary_not_collected']}


def compose_inputs(manifest, receipts):
    protected = copy.deepcopy(receipts)
    protected['items']['workspace_canary']['data'].update(
        api_observation_sha256='1'*64, schema_observation_sha256='2'*64,
        human_signoff=True, browser_canary_sha256='3'*64,
        reviewer_id=202, initiator_id=101, approval_run_id=456, approval_comment_sha256='5'*64)
    return dict(
        manifest=manifest,
        protected_receipts={'schema':'buyeros.workspace-release-receipts.v1',
                            'items':{name:protected['items'][name] for name in ('workspace_canary','rollback')}},
        schema_observation=copy.deepcopy(receipts['items']['schema']['data']),
        api_observation=api_observation(manifest['source_sha'], receipts['items']['schema']['checked_at']),
        binding_observation=copy.deepcopy(receipts['items']['deployment_binding']),
        schema_observation_sha256='2'*64, api_observation_sha256='1'*64,
        api_contract_sha256='4'*64, ci=copy.deepcopy(receipts['items']['ci']['data']),
        artifacts={'frontend':manifest['frontend_artifact'],'api':manifest['api_artifact']},
        source_sha=manifest['source_sha'])
