"""Bound candidate/source verification without contacting a deployment or using credentials."""
import copy
import importlib.util
import io
import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

spec = importlib.util.spec_from_file_location('conversation_qa_target', Path(__file__).parents[1] / 'scripts' / 'verify-conversation-qa-target.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SOURCE = 'a' * 40
ORIGIN = 'https://buyer-candidate-team.vercel.app'
PROJECT = {'id': 'prj_test', 'accountId': 'team_test', 'link': {'org': 'YNWAforever', 'repo': 'BuyerOS', 'repoId': 123}}
DEPLOYMENT = {'id': 'dpl_test', 'projectId': 'prj_test', 'ownerId': 'team_test', 'readyState': 'READY', 'url': 'buyer-candidate-team.vercel.app',
              'meta': {'githubCommitSha': SOURCE, 'githubCommitOrg': 'YNWAforever', 'githubCommitRepo': 'BuyerOS', 'githubCommitRepoId': '123'}}


def verify(**kwargs):
    values = dict(origin=ORIGIN, source=SOURCE, project_id='prj_test', team_id='team_test', repository='YNWAforever/BuyerOS',
                  project=copy.deepcopy(PROJECT), deployment=copy.deepcopy(DEPLOYMENT))
    values.update(kwargs)
    return module.verify_metadata(**values)


def test_accepts_ready_exact_candidate_and_source():
    assert verify() == {'source_sha': SOURCE, 'deployment_id': 'dpl_test', 'origin': ORIGIN}
    assert verify(origin=ORIGIN + '/')['origin'] == ORIGIN


def test_rejects_untrusted_origins_and_does_not_redirect():
    for origin in ('http://buyer-candidate-team.vercel.app', 'https://example.com', ORIGIN + '/path', ORIGIN + '?x=1',
                   ORIGIN + '#fragment', 'https://user@buyer-candidate-team.vercel.app', ORIGIN + ':444', 'https://vercel.app'):
        with pytest.raises(ValueError):
            verify(origin=origin)
    assert module.NoRedirect().redirect_request(None, None, 302, None, None, 'https://other.example') is None


def test_rejects_unreviewed_source_and_scope():
    for kwargs in ({'source': 'short'}, {'source': 'A' * 40}, {'project_id': 'other'}, {'team_id': 'other'}, {'repository': 'other/repo'}):
        with pytest.raises(ValueError):
            verify(**kwargs)


def test_rejects_project_owner_and_repository_substitution():
    for key, value in (('id', 'prj_other'), ('accountId', 'team_other'), ('link', {'org': 'other', 'repo': 'BuyerOS', 'repoId': 123}),
                       ('link', {'org': 'YNWAforever', 'repo': 'BuyerOS', 'repoId': 456})):
        project = copy.deepcopy(PROJECT)
        project[key] = value
        with pytest.raises(ValueError):
            verify(project=project)


def test_rejects_wrong_candidate_state_origin_scope_and_source():
    for key, value in (('id', 'invalid'), ('projectId', 'prj_other'), ('ownerId', 'team_other'), ('readyState', 'BUILDING'),
                       ('url', 'buyer-other-team.vercel.app'), ('meta', {**DEPLOYMENT['meta'], 'githubCommitSha': 'b' * 40}),
                       ('meta', {**DEPLOYMENT['meta'], 'githubCommitRepoId': '456'}), ('meta', {**DEPLOYMENT['meta'], 'githubCommitRepo': 'other'})):
        deployment = copy.deepcopy(DEPLOYMENT)
        deployment[key] = value
        with pytest.raises(ValueError):
            verify(deployment=deployment)


def test_qa_credentials_follow_trusted_main_metadata_gate():
    workflow = yaml.safe_load((Path(__file__).parents[1] / '.github' / 'workflows' / 'buyeros-conversation-qa.yml').read_text())
    metadata = workflow['jobs']['verify-target']
    journey = workflow['jobs']['conversation-qa']
    assert metadata['environment'] == 'buyeros-runtime-readonly'
    assert journey['needs'] == 'verify-target'
    assert journey['environment'] == 'buyeros-conversation-qa'
    checkout = metadata['steps'][0]
    assert checkout['with']['ref'] == 'main'
    assert checkout['with']['persist-credentials'] is False
    assert metadata['steps'][1]['run'] == 'python scripts/verify-conversation-qa-target.py'
    for job in (metadata, journey):
        assert 'head.repo.full_name == github.repository' in job['if']


def test_private_failure_data_is_not_rendered():
    environment = {'QA_ORIGIN': ORIGIN, 'QA_SHA': SOURCE, 'VERCEL_PROJECT_ID': 'prj_test', 'VERCEL_ORG_ID': 'team_test',
                   'GITHUB_REPOSITORY': 'YNWAforever/BuyerOS', 'VERCEL_TOKEN': 'unit-only-private-token'}
    output = io.StringIO()
    with patch.dict(os.environ, environment, clear=True), patch.object(module, 'api_json', side_effect=OSError('private-failure-sentinel')) as api, patch('sys.stderr', output):
        assert module.main() == 1
    assert api.call_count == 1
    assert output.getvalue() == 'BLOCKED: QA candidate metadata could not be verified\n'
    assert 'private-failure-sentinel' not in output.getvalue()
    assert environment['VERCEL_TOKEN'] not in output.getvalue()


def read_workflow():
    return yaml.safe_load((Path(__file__).parents[1] / '.github' / 'workflows' / 'buyeros-conversation-qa.yml').read_text(encoding='utf-8'))


def workflow_dispatch_inputs(workflow):
    on_block = workflow.get('on', workflow.get(True))
    return on_block['workflow_dispatch']['inputs']


def journey_steps(workflow):
    return workflow['jobs']['conversation-qa']['steps']


def test_live_recall_is_manual_opt_in_and_never_label_triggered():
    workflow = read_workflow()
    inputs = workflow_dispatch_inputs(workflow)
    assert inputs['live_model_recall']['type'] == 'boolean'
    assert inputs['live_model_recall']['default'] is False
    assert inputs['qa_isolated_rehearsal']['type'] == 'boolean'
    assert inputs['qa_isolated_rehearsal']['default'] is False
    assert 'isolated_workspace_id' in inputs and 'isolated_project_id' in inputs
    assert 'default' not in inputs['isolated_workspace_id']
    assert inputs['authorized_spend_usd']['default'] == '1'
    assert 'model_source_label' in inputs
    journey = workflow['jobs']['conversation-qa']
    recall = journey['env']['QA_MODEL_RECALL_ENABLED']
    assert "github.event_name == 'workflow_dispatch'" in recall
    assert 'inputs.live_model_recall == true' in recall
    assert "'true' || 'false'" in recall
    assert 'vars.' not in recall and 'label' not in recall.lower()
    rehearsal = journey['env']['QA_ISOLATED_REHEARSAL_ENABLED']
    assert "github.event_name == 'workflow_dispatch'" in rehearsal
    assert 'inputs.qa_isolated_rehearsal == true' in rehearsal
    assert "'true' || 'false'" in rehearsal
    run = next(step for step in journey_steps(workflow) if step.get('name') == 'Run authorized live model recall')
    env = run['env']
    assert run['if'] == "${{ success() && env.QA_MODEL_RECALL_ENABLED == 'true' }}"
    assert env['BUYEROS_QA_MODEL_RECALL'] == '${{ env.QA_MODEL_RECALL_ENABLED }}'
    assert env['BUYEROS_QA_LIVE_RECALL_BUDGET_USD'] == '${{ env.QA_MODEL_BUDGET_USD }}'
    assert env['BUYEROS_QA_MODEL_SOURCE_LABEL'] == '${{ env.QA_MODEL_SOURCE_LABEL_REQUIRED }}'
    assert env['BUYEROS_QA_WORKSPACE_ID'] == '${{ env.QA_ISOLATED_WORKSPACE_REQUIRED }}'
    assert env['BUYEROS_QA_PROJECT_ID'] == '${{ env.QA_ISOLATED_PROJECT_REQUIRED }}'
    # Nonbillable standard and paid modes are separate Playwright invocations. A
    # label can only reach the standard-account step, never an isolated mode.
    base = next(step for step in journey_steps(workflow) if step.get('name') == 'Run nonbillable authenticated conversation QA')
    assert base['if'] == "${{ env.QA_MODEL_RECALL_ENABLED != 'true' && env.QA_ISOLATED_REHEARSAL_ENABLED != 'true' }}"
    assert 'BUYEROS_QA_MODEL_RECALL' not in (base.get('env') or {})
    assert '--grep-invert "authorized model recalls"' in base['run']
    rehearsal_step = next(step for step in journey_steps(workflow) if step.get('name') == 'Run isolated nonbillable QA rehearsal')
    assert rehearsal_step['if'] == "${{ success() && env.QA_ISOLATED_REHEARSAL_ENABLED == 'true' }}"
    assert '--grep-invert "authorized model recalls"' in rehearsal_step['run']
    assert '--grep "authorized model recalls"' in run['run']
    # Protected environment variables, not dispatch-input shape alone, authorize
    # the isolated mode; the validation step compares inputs before credentials.
    assert journey['env']['QA_ISOLATED_WORKSPACE_REQUIRED'] == '${{ vars.BUYEROS_MODEL_QA_WORKSPACE_ID }}'
    assert journey['env']['QA_ISOLATED_PROJECT_REQUIRED'] == '${{ vars.BUYEROS_MODEL_QA_PROJECT_ID }}'
    assert journey['env']['QA_MODEL_SOURCE_LABEL_REQUIRED'] == '${{ vars.BUYEROS_MODEL_QA_SOURCE_LABEL }}'
    validate = next(step for step in journey_steps(workflow) if step.get('name') == 'Validate QA target, reviewed source and live-recall opt-in')
    assert validate['env']['QA_ISOLATED_WORKSPACE_REQUIRED'] == '${{ env.QA_ISOLATED_WORKSPACE_REQUIRED }}'
    assert 'isolatedWorkspace !== requiredWorkspace' in validate['run']
    assert 'sourceLabelInput !== requiredLabel' in validate['run']
    assert 'mutually exclusive' in validate['run']
    # The recall opt-in must never be wired to a repository variable or a label.
    raw = (Path(__file__).parents[1] / '.github' / 'workflows' / 'buyeros-conversation-qa.yml').read_text(encoding='utf-8')
    assert 'BUYEROS_QA_MODEL_RECALL: ${{ vars.' not in raw
    assert '064d5168' not in raw and 'bd632836' not in raw
    on_block = workflow.get('on', workflow.get(True))
    assert on_block['pull_request']['types'] == ['labeled']


def test_qa_job_pins_reviewed_source_before_credentials():
    workflow = read_workflow()
    journey = workflow['jobs']['conversation-qa']
    checkout = journey_steps(workflow)[0]
    assert checkout['uses'] == 'actions/checkout@v4'
    assert checkout['with']['ref'] == '${{ inputs.expected_source_sha || github.event.pull_request.head.sha }}'
    assert checkout['with']['persist-credentials'] is False
    verify = journey_steps(workflow)[1]
    assert verify['name'] == 'Verify pinned reviewed source checkout'
    assert 'git rev-parse HEAD' in verify['run'] and 'QA_SHA' in verify['run']
    # ACCOUNT CREDENTIALS ARE SCOPED TO THEIR RESPECTIVE TEST STEP, NOT THE JOB
    # OR CHECKOUT. The paid recall step uses the isolated model-QA account and has
    # no production QA secret fallback.
    for env in (workflow.get('env') or {}, journey.get('env') or {}):
        assert not any(key.startswith('BUYEROS_NEON_') for key in env)
    base = next(step for step in journey_steps(workflow) if step.get('name') == 'Run nonbillable authenticated conversation QA')
    rehearsal_step = next(step for step in journey_steps(workflow) if step.get('name') == 'Run isolated nonbillable QA rehearsal')
    paid = next(step for step in journey_steps(workflow) if step.get('name') == 'Run authorized live model recall')
    assert base['env']['BUYEROS_NEON_REAL_EMAIL'] == '${{ secrets.BUYEROS_NEON_REAL_EMAIL }}'
    assert base['env']['BUYEROS_NEON_REAL_PASSWORD'] == '${{ secrets.BUYEROS_NEON_REAL_PASSWORD }}'
    for isolated in (rehearsal_step, paid):
        assert isolated['env']['BUYEROS_NEON_REAL_EMAIL'] == '${{ secrets.BUYEROS_MODEL_QA_EMAIL }}'
        assert isolated['env']['BUYEROS_NEON_REAL_PASSWORD'] == '${{ secrets.BUYEROS_MODEL_QA_PASSWORD }}'
        assert all('BUYEROS_NEON_REAL_EMAIL' not in str(value) and 'BUYEROS_NEON_REAL_PASSWORD' not in str(value)
                   for value in isolated['env'].values())
    assert 'BUYEROS_MODEL_QA' not in base['env']
    # Device traces can contain session/login request data, so they are not uploaded.
    upload = next(step for step in journey_steps(workflow) if step.get('uses') == 'actions/upload-artifact@v4')
    assert upload['with']['path'].splitlines() == [
        'artifacts/conversation-qa/results*.xml',
        'artifacts/conversation-qa/*.png',
    ]
    runbook = (Path(__file__).parents[1] / 'docs' / 'buyeros' / 'runbooks' / 'conversation-qa.md').read_text(encoding='utf-8')
    assert 'live_model_recall=true' in runbook
    assert 'qa_isolated_rehearsal=true' in runbook
    assert 'authorized_spend_usd=1' in runbook
    assert 'model_source_label' in runbook and 'product' in runbook
    assert 'BUYEROS_MODEL_QA_EMAIL' in runbook and 'BUYEROS_MODEL_QA_PASSWORD' in runbook
    assert 'BUYEROS_MODEL_QA_WORKSPACE_ID' in runbook and 'BUYEROS_MODEL_QA_PROJECT_ID' in runbook
    assert 'BUYEROS_MODEL_QA_SOURCE_LABEL' in runbook
    assert '064d5168-709b-57e7-a7c3-871c2f16c814' in runbook
    assert 'bd632836-3298-58de-aa85-59213cb28ab2' in runbook
    assert 'no fallback' in runbook.lower() or 'never falls back' in runbook.lower()
    assert 'never' in runbook.lower() and 'label' in runbook.lower()
    assert 'two independent saved discussions' in runbook.lower()


def test_recall_spec_has_two_manual_gates_and_fixed_billable_scope():
    spec = (Path(__file__).parents[1] / 'tests' / 'e2e' / 'conversation-real-qa.spec.ts').read_text(encoding='utf-8')
    assert "process.env.BUYEROS_QA_MODEL_RECALL!=='true'" in spec
    assert 'BUYEROS_QA_LIVE_RECALL_BUDGET_USD' in spec
    assert 'BUYEROS_QA_MODEL_SOURCE_LABEL' in spec
    assert 'authorized_spend_usd' not in spec  # workflow input name stays outside the browser test
    assert "['Alder','Birch']" in spec and "['Cedar','Willow']" in spec
    assert 'otherThreadNames' in spec
    assert 'two threads x three turns' in spec
    assert '/^POST \\/v1\\/.*\\/conversation-turns$/' in spec
    assert '/^PUT \\/v1\\/.*\\/conversation-threads\\/[0-9a-f-]{36}\\/sources$/' in spec
    assert 'no unrelated billable or approval mutation' in spec
