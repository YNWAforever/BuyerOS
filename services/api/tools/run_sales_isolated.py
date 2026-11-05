"""Nonbillable acceptance, extending run_core_isolated's owned allocator.

Only --allocate-owned authorizes fresh local fixtures. No external DSN, existing
container, model endpoint, credential or activation target can be supplied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

API = Path(__file__).resolve().parents[1]
ROOT = API.parents[1]
LOCAL_ENGINES = {'npipe:////./pipe/dockerDesktopLinuxEngine', 'unix:///var/run/docker.sock'}
FOCUSED_TESTS = (
    'test_sales_composition_db.py', 'test_sales_context.py', 'test_sales_core_journey_db.py',
    'test_sales_documents.py', 'test_sales_drafting_db.py', 'test_sales_execution_db.py',
    'test_sales_intake_postgres.py', 'test_sales_intake.py', 'test_sales_model.py',
    'test_sales_native_lifecycle_db.py', 'test_sales_outputs_db.py', 'test_sales_privacy_db.py',
    'test_sales_provider_retention_db.py', 'test_sales_registry.py', 'test_sales_reporting_db.py',
    'test_sales_research.py', 'test_sales_retention_db.py', 'test_sales_tasks_api.py',
    'test_sales_tasks_db.py', 'test_sales_ui_access_db.py', 'test_xverum_connections.py',
    'test_xverum_credits_db.py', 'test_xverum_dispatch_db.py',
    'test_xverum_enrichment_boundaries_db.py', 'test_xverum_enrichment_db.py',
    'test_xverum_enrichment_locking_db.py', 'test_xverum_mcp.py', 'test_xverum_quotes_db.py',
)
NATIVE_TESTS = (
    'test_schema_readiness_db.py', 'test_schema_recovery_db.py',
    'test_exports_authorization_db.py', 'test_buyer_source_checks_db.py',
    'test_conversation_threads_api.py', 'test_conversation_threads_db.py',
    'test_run_model_admission_db.py', 'test_draft_approval_context_db.py',
    'test_conversation_connections_db.py', 'test_retention_authorization_db.py', 'test_settlement.py',
)


def validate_environment(env):
    for key, value in env.items():
        name = key.upper()
        if not value:
            continue
        if (name.startswith('BUYEROS_') or name == 'NEXT_PUBLIC_CONVERSATION_HOME'
                or re.search(r'(DATABASE_URL|DSN|API_KEY|TOKEN|SECRET|PASSWORD|CREDENTIALS|SECRET_ACCESS_KEY)$', name)
                or re.match(r'(XVERUM|OPENAI|ANTHROPIC|OPENCODE|NEON|SUPABASE)_', name)
                or name in {'PGHOST', 'PGSERVICE', 'PGPASSWORD', 'PGDATABASE', 'PGPORT', 'PGUSER'}):
            raise ValueError('inherited application target or credential refused: ' + key)
        if name == 'DOCKER_HOST' and value not in {
            'npipe:////./pipe/dockerDesktopLinuxEngine', 'unix:///var/run/docker.sock'
        }:
            raise ValueError('remote Docker refused')


def resolve_docker_context(env):
    """Read only. Resolve explicit/default context and reject overrides/drift."""
    def read(args):
        result = subprocess.run(['docker', *args], env=dict(env), capture_output=True,
                                text=True, encoding='utf-8', timeout=15)
        if result.returncode:
            raise ValueError('Docker context cannot be verified')
        return result.stdout.strip()
    context = env.get('DOCKER_CONTEXT') or read(['context', 'show'])
    if not context or context.startswith('-'):
        raise ValueError('Docker context identity missing')
    endpoint = read(['context', 'inspect', context, '--format', '{{.Endpoints.docker.Host}}'])
    if endpoint not in LOCAL_ENGINES:
        raise ValueError('Remote effective Docker context refused')
    if not env.get('DOCKER_CONTEXT') and env.get('DOCKER_HOST') not in {None, '', endpoint}:
        raise ValueError('Docker host override differs from verified context')
    return {'context': context, 'endpoint': endpoint}


def prepare_image(env, *, command=None):
    """Explicit prerequisite only: verify the effective local engine before pull.

    Allocation never pulls implicitly and still pins the inspected immutable ID.
    """
    validate_environment(env)
    identity=resolve_docker_context(env)
    if identity['endpoint'] not in LOCAL_ENGINES:
        raise ValueError('verified local engine required')
    docker=OwnedDocker(identity, lambda row: None, env=env, command=command)
    docker.verify_context()
    image=docker.raw('image','inspect','postgres:16','--format','{{.Id}}')
    if image.returncode:
        docker.verify_context()
        pulled=docker.raw('pull','postgres:16')
        if pulled.returncode: raise ValueError('Local image preparation failed')
        image=docker.raw('image','inspect','postgres:16','--format','{{.Id}}')
    docker.verify_context()
    if image.returncode or not re.fullmatch(r'sha256:[0-9a-f]{64}',image.stdout.strip()):
        raise ValueError('Prepared local image is unverified')
    return {**identity,'image_id':image.stdout.strip()}


def execute(evidence, env, action):
    # This ordering is a safety contract: rejection precedes even receipt writes.
    try:
        validate_environment(env)
        selection()  # Complete inventory even when only affected cases will run.
        docker_identity = resolve_docker_context(env)
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 2
    evidence.mkdir(parents=True, exist_ok=False)
    return action(docker_identity)


def source_identity():
    names = subprocess.check_output(
        ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT
    ).decode().split('\0')
    files = {}
    for name in sorted(set(names)):
        path = ROOT / name
        if not name or name.startswith(('.superpowers/', 'outputs/', 'test-results/')) or not path.is_file():
            continue
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'candidate_sha256': digest, 'files': files}


def selection():
    required = [API / 'tests' / name for name in (*FOCUSED_TESTS, *NATIVE_TESTS)]
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        raise RuntimeError('Required regression file missing; suite cannot shrink: ' + ', '.join(missing))
    return [str(p) for p in required]


class OwnedDocker:
    """Record successful creation before readiness; never delete by name alone."""
    def __init__(self, identity, record, *, env=None, command=None):
        self.identity, self.record = identity, record
        self.env = dict(os.environ if env is None else env)
        self.env.pop('DOCKER_HOST', None)
        self.env['DOCKER_CONTEXT'] = identity['context']
        self.command = command or subprocess.run
        self.created = {}

    def verify_context(self):
        if resolve_docker_context(self.env) != self.identity:
            raise ValueError('Docker context identity changed')

    def raw(self, *args):
        return self.command(['docker', '--context', self.identity['context'], *args],
                            env=self.env, capture_output=True, text=True, timeout=30)

    def owned(self, target):
        row = next((row for cid, row in self.created.items()
                    if target in {cid, row['name']}), None)
        if row is None:
            raise ValueError('Refusing unverified container removal/access')
        return row

    def inspect_owned(self, row):
        result = self.raw('inspect', row['container_id'])
        if result.returncode:
            if 'no such object' in result.stderr.lower() or 'no such container' in result.stderr.lower():
                return False
            raise ValueError('Owned container identity cannot be inspected')
        raw = json.loads(result.stdout)[0]
        if (raw.get('Id') != row['container_id'] or raw.get('Name') != '/' + row['name']
                or raw.get('Image') != row['image_id']
                or raw.get('Config', {}).get('Labels', {}).get('buyeros.policy.run') != row['name']
                or any(m.get('Type') == 'bind' for m in raw.get('Mounts', []))):
            raise ValueError('Owned container identity drift; removal refused')
        return True

    def __call__(self, *args):
        if args[0] == 'run':
            self.verify_context()
            name = args[args.index('--name') + 1]
            if 'buyeros.policy.run=' + name not in args or any(r['name'] == name for r in self.created.values()):
                raise ValueError('Fresh labelled allocation required')
            image = self.raw('image', 'inspect', args[-1], '--format', '{{.Id}}')
            image_id = image.stdout.strip()
            if image.returncode or not re.fullmatch(r'sha256:[0-9a-f]{64}', image_id):
                raise ValueError('Local allocation image is unverified')
            result = self.raw(*args[:-1], image_id)
            if result.returncode == 0:
                cid = result.stdout.strip()
                if not re.fullmatch(r'[0-9a-f]{64}', cid):
                    raise ValueError('Successful creation did not return an exact container ID')
                row = {'container_id': cid, 'name': name, 'image_id': image_id, **self.identity}
                self.created[cid] = row  # Before inspection, readiness, SQL or return to allocator.
                self.record(dict(row))
            return result
        if args[0] == 'rm':
            if any(flag not in {'-f', '-v', '--force', '--volumes'} for flag in args[1:-1]):
                raise ValueError('Only one exact owned removal is permitted')
            row = self.owned(args[-1])  # Failed create/collision has no ownership.
            self.verify_context()
            if not self.inspect_owned(row):
                return subprocess.CompletedProcess(args, 0, '', '')
            return self.raw(*args[:-1], row['container_id'])
        if args[0] in {'exec', 'port'}:
            row = self.owned(args[1])
            return self.raw(args[0], row['container_id'], *args[2:])
        raise ValueError('Unsupported allocator Docker command')

    def cleanup(self):
        rows = []
        for cid, row in self.created.items():
            self.verify_context()
            if self.inspect_owned(row):
                result = self('rm', '-f', '-v', cid)
                if result.returncode:
                    raise RuntimeError('Exact owned cleanup failed')
            removed = not self.inspect_owned(row)
            rows.append({'container_id': cid, 'creation_record': 'allocations.json',
                         'removed_verified': removed})
        return rows


class CaseReceipts:
    def __init__(self, evidence, identity, docker_identity=None):
        self.evidence, self.identity = evidence, identity
        self.cases = {}
        self.targets = {}
        self.docker_identity = docker_identity
        self.allocations = []

    def record_creation(self, row):
        self.allocations.append(row)
        (self.evidence / 'allocations.json').write_text(json.dumps(self.allocations, indent=2), encoding='utf-8')

    def pytest_collection_finish(self, session):
        self.bind_allocators()
        self.cases = {item.nodeid: {'id': item.nodeid, 'status': 'NOT_RUN',
                      'classification': 'owned-synthetic-fixture', 'seconds': 0,
                      'candidate_sha256': self.identity['candidate_sha256']} for item in session.items}
        self.save()

    def pytest_runtest_logreport(self, report):
        row = self.cases.setdefault(report.nodeid, {'id': report.nodeid, 'status': 'NOT_RUN',
                                  'classification': 'owned-synthetic-fixture', 'seconds': 0,
                                  'candidate_sha256': self.identity['candidate_sha256']})
        row['seconds'] += report.duration
        if report.failed:
            row['status'] = 'FAIL'
        elif report.skipped and row['status'] != 'FAIL':
            row['status'] = 'BLOCKED'
        elif report.when == 'call' and report.passed and row['status'] == 'NOT_RUN':
            row['status'] = 'PASS'
        self.save()

    def save(self):
        # No test arguments, captured output, conversations or personal payloads.
        (self.evidence / 'cases.json').write_text(json.dumps(list(self.cases.values()), indent=2), encoding='utf-8')

    def bind_artifact(self):
        artifact = self.evidence / 'pytest.xml'
        if artifact.is_file():
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            for row in self.cases.values():
                row['artifact'] = 'pytest.xml'
                row['artifact_sha256'] = digest
            self.save()

    def bind_allocators(self, modules=None):
        # Pytest can load this same conftest under a second package name.
        # Patch the defining globals used by every imported fixture function.
        expected = (API / 'tests/conftest.py').resolve()
        for module in tuple(sys.modules.values()) if modules is None else modules:
            path = getattr(module, '__file__', None)
            if path and Path(path).resolve() == expected and hasattr(module, '_docker'):
                module._docker = self.docker

    def pytest_sessionstart(self, session):
        self.docker = OwnedDocker(self.docker_identity, self.record_creation)
        self.bind_allocators()

    def cleanup(self):
        rows = self.docker.cleanup() if hasattr(self, 'docker') else []
        tracked = True
        # Receipts do not authorize adoption/removal. Creation records above do.
        for receipt in sorted((self.evidence / 'allocator').rglob('*.target.json')):
            meta = json.loads(receipt.read_text(encoding='utf-8-sig'))
            cid = meta['container_id']
            if meta['docker_context'] != self.docker_identity['context']:
                raise ValueError('Fixture receipt context differs from preflight')
            command = ['docker', '--context', meta['docker_context'], 'inspect', cid]
            result = subprocess.run(command, capture_output=True, text=True)
            removed = result.returncode != 0 and 'no such' in result.stderr.lower()
            existing = next((row for row in rows if row['container_id'] == cid), None)
            if existing is not None:
                existing.update(receipt=str(receipt.relative_to(self.evidence)), removed_verified=removed)
            else:
                tracked = False
                rows.append({'container_id': cid, 'receipt': str(receipt.relative_to(self.evidence)),
                             'removed_verified': removed, 'creation_record_missing': True})
        (self.evidence / 'cleanup.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
        return tracked and bool(rows) and all(row['removed_verified'] for row in rows)


def run(evidence, docker_identity, cases=()):
    sys.path.insert(0, str(API))
    import pytest
    os.environ.pop('DOCKER_HOST', None)
    os.environ['DOCKER_CONTEXT'] = docker_identity['context']
    identity = source_identity()
    (evidence / 'source.json').write_text(json.dumps(identity, indent=2), encoding='utf-8')
    os.environ.update(BUYEROS_STRICT_INTEGRATION='1', BUYEROS_POLICY_FIXTURE_EVIDENCE=str(evidence / 'allocator'),
                      SALES_TEST_EVIDENCE_DIR=str(evidence / 'browser'), PYTHONIOENCODING='utf-8')
    selected = list(cases) or selection()
    args = [*selected, '-q', '-p', 'no:cacheprovider', '--tb=short', '--junitxml=' + str(evidence / 'pytest.xml')]
    (evidence / 'command.json').write_text(json.dumps({'argv': [sys.executable, '-m', 'pytest', *args],
        'allocator': 'fresh-owned', 'docker_identity': docker_identity,
        'mode': 'affected' if cases else 'full-required',
        'provider': 'synthetic', 'activation': False}, indent=2), encoding='utf-8')
    plugin = CaseReceipts(evidence, identity, docker_identity)
    started = time.monotonic()
    try:
        result = int(pytest.main(args, plugins=[plugin]))
    finally:
        cleaned = plugin.cleanup()
        plugin.bind_artifact()
        unchanged = source_identity()['candidate_sha256'] == identity['candidate_sha256']
        (evidence / 'summary.json').write_text(json.dumps({
            'counts': {s: sum(r['status'] == s for r in plugin.cases.values()) for s in ['PASS','FAIL','BLOCKED','NOT_RUN']},
            'elapsed_seconds': time.monotonic() - started, 'cleanup_verified': cleaned,
            'source_unchanged': unchanged, 'candidate_sha256': identity['candidate_sha256'],
            'live': 'BLOCKED', 'phase_complete': False,
            'correction_rate': None, 'time_to_first_output': None, 'actual_live_cost': None,
            'telemetry_note': 'fixture test timings are not user completion latency or live spend'
        }, indent=2), encoding='utf-8')
    return result or (0 if cleaned and unchanged and all(r['status'] == 'PASS' for r in plugin.cases.values()) else 1)


def main(argv=None, env=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allocate-owned', action='store_true')
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--prepare-local-image', action='store_true')
    parser.add_argument('--case', action='append', default=[], help='Affected case or file from the fixed suite only')
    args = parser.parse_args(argv)
    if args.prepare_local_image:
        if args.allocate_owned or args.evidence or args.case:
            parser.error('image preparation is a separate prerequisite')
        print(json.dumps(prepare_image(os.environ if env is None else env)))
        return 0
    if not args.evidence: parser.error('--evidence required for allocation')
    if not args.allocate_owned:
        print('Explicit --allocate-owned required; no inherited resource accepted', file=sys.stderr)
        return 2
    evidence = args.evidence.resolve()
    try:
        permitted = {Path(p).resolve() for p in selection()}
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 2
    for case in args.case:
        if Path(case.split('::')[0]).resolve() not in permitted:
            print('Case outside fixed nonbillable suite refused', file=sys.stderr)
            return 2
    return execute(evidence, os.environ if env is None else env,
                   lambda docker_identity: run(evidence, docker_identity, args.case))


if __name__ == '__main__':
    raise SystemExit(main())
