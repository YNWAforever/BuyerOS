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
