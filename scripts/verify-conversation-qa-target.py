"""Verify Vercel candidate metadata before a separate job receives QA credentials.

Read-only management API requests. This does not replace protected runtime binding,
source attestation, real authenticated acceptance, or production release controls.
"""
import json
import os
import re
import sys
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def target_host(origin):
    url = urlsplit(origin)
    if (url.scheme != 'https' or '@' in url.netloc
            or url.port not in (None, 443) or url.path not in ('', '/')
            or url.query or url.fragment
            or not re.fullmatch(r'[a-z0-9-]+\.vercel\.app', url.hostname or '')
            or origin.rstrip('/') != 'https://' + url.hostname):
        raise ValueError('exact HTTPS Vercel origin required')
    return url.hostname


def verify_metadata(origin, source, project_id, team_id, repository, project, deployment):
    host = target_host(origin)
    if not re.fullmatch(r'[0-9a-f]{40}', source):
        raise ValueError('full reviewed source SHA required')
    if (not re.fullmatch(r'prj_[A-Za-z0-9]+', project_id)
            or not re.fullmatch(r'team_[A-Za-z0-9]+', team_id)
            or repository != 'YNWAforever/BuyerOS'):
        raise ValueError('trusted project/team/repository required')
    owner, repo = repository.split('/')
    if not isinstance(project, dict) or not isinstance(deployment, dict):
        raise ValueError('management metadata objects required')
    link = project.get('link') or {}
    if not isinstance(link, dict):
        raise ValueError('project repository metadata required')
    if (project.get('id') != project_id or project.get('accountId') != team_id
            or link.get('org') != owner or link.get('repo') != repo
            or not link.get('repoId')):
        raise ValueError('project repository binding mismatch')
    meta = deployment.get('meta') or {}
    if not isinstance(meta, dict):
        raise ValueError('deployment source metadata required')
    if (not isinstance(deployment.get('id'), str)
            or not re.fullmatch(r'dpl_[A-Za-z0-9_-]+', deployment['id'])
            or deployment.get('projectId') != project_id or deployment.get('ownerId') != team_id
            or deployment.get('readyState') != 'READY' or deployment.get('url') != host
            or meta.get('githubCommitSha') != source
            or meta.get('githubCommitOrg') != owner or meta.get('githubCommitRepo') != repo
            or str(meta.get('githubCommitRepoId')) != str(link['repoId'])):
        raise ValueError('ready immutable candidate/source binding mismatch')
    return {'source_sha': source, 'deployment_id': deployment['id'], 'origin': 'https://' + host}


def api_json(path, token):
    request = Request('https://api.vercel.com' + path,
                      headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'})
    with build_opener(NoRedirect()).open(request, timeout=20) as response:
        raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('bounded management response required')
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError('management response object required')
        return value


def main():
    try:
        origin, source = os.environ['QA_ORIGIN'], os.environ['QA_SHA']
        project_id, team_id = os.environ['VERCEL_PROJECT_ID'], os.environ['VERCEL_ORG_ID']
        repository, token = os.environ['GITHUB_REPOSITORY'], os.environ['VERCEL_TOKEN']
        host = target_host(origin)
        # Reject malformed configuration before making even a management request.
        if (not re.fullmatch(r'[0-9a-f]{40}', source)
                or not re.fullmatch(r'prj_[A-Za-z0-9]+', project_id)
                or not re.fullmatch(r'team_[A-Za-z0-9]+', team_id)
                or repository != 'YNWAforever/BuyerOS' or not token or any(c.isspace() for c in token)):
            raise ValueError('bounded trusted QA configuration required')
        project = api_json('/v9/projects/' + quote(project_id) + '?teamId=' + quote(team_id), token)
        deployment = api_json('/v13/deployments/' + host + '?teamId=' + quote(team_id), token)
        result = verify_metadata(origin, source, project_id, team_id, repository, project, deployment)
        print(json.dumps({'status': 'vercel_metadata_verified', **result}))
        return 0
    except (KeyError, ValueError, HTTPError, OSError):
        # Exception/request contents may contain private information. Never render them.
        print('BLOCKED: QA candidate metadata could not be verified', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
