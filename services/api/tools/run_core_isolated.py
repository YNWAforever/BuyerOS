"""Bounded browser acceptance; allocate/prove a fresh target before application SQL.

Run with services/api/.venv/bin/python services/api/tools/run_core_isolated.py
from the repository root. Extra arguments are passed to Playwright (e.g. --grep).
This runner never selects an inherited application/test database or secret.
"""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import uuid

API = Path(__file__).resolve().parents[1]
ROOT = API.parents[1]
sys.path.insert(0, str(API))


def archive_dead_lock(evidence: Path) -> None:
    lock = ROOT / '.vinext/dev/lock.json'
    if not lock.exists():
        return
    if lock.is_symlink():
        raise RuntimeError('Refusing symlink dev lock')
    value = json.loads(lock.read_text())
    if value.get('cwd') != str(ROOT):
        raise RuntimeError('Dev lock belongs to a different checkout')
    pid = value['pid']
    if not isinstance(pid, int) or pid <= 0:
        raise RuntimeError('Unknown dev-lock PID')
    stat = Path(f'/proc/{pid}/stat')
    if stat.exists() and stat.read_text().rsplit(')', 1)[1].split()[0] != 'Z':
        raise RuntimeError('An existing process owns the dev lock; do not interrupt it')
    assert_ports_free(int(value['port']))
    lock.rename(evidence / f'stale-dev-lock-{time.time_ns()}.json')


def assert_ports_free(*ports: int) -> None:
    for port in ports:
        for host in ('127.0.0.1', '::1'):
            try:
                connection = socket.create_connection((host, port), timeout=0.5)
            except ConnectionRefusedError:
                continue
            except OSError as error:
                # IPv6 may be unavailable in the managed Linux container.
                import errno
                if host == '::1' and error.errno in {errno.EAFNOSUPPORT, errno.ENETUNREACH}:
                    continue
                raise
            else:
                connection.close()
                raise RuntimeError(f'Port {port} is already in use; leave its owner untouched')


def main() -> int:
    # Remove inherited application selectors, retaining platform proxy/CA settings.
    for name in list(os.environ):
        if name.startswith('BUYEROS_'):
            os.environ.pop(name)
    os.environ['BUYEROS_STRICT_INTEGRATION'] = '1'
    evidence = ROOT / 'outputs' / ('core-isolated-' + uuid.uuid4().hex[:12])
    evidence.mkdir(parents=True, exist_ok=False)
    source_paths = ('features/live/drafts.tsx', 'tests/e2e/core-isolated.spec.ts',
                    'playwright.core-isolated.config.ts', 'services/api/tools/run_core_isolated.py',
                    'services/api/tests/test_core_flow_scope_db.py',
                    'services/worker/tests/fixtures/run_browser_research.py')
    fingerprints = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source_paths}
    (evidence / 'tested-files.json').write_text(json.dumps({
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'sha256': fingerprints}, indent=2))
    retained_logs = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                     for path in ('test-results/t30-browser-worker.log', 'test-results/t30-browser-draft-worker.log')
                     if (ROOT / path).is_file()}
    marker = ROOT / 'test-results/e2e-db-container.txt'
    if marker.exists():
        raise RuntimeError('Existing fixture marker must be investigated; refusing to adopt it')
    assert_ports_free(8000, 5173)
    archive_dead_lock(evidence)
    from tests.conftest import _start_container
    from tests.policy_activation_target import fixture_receipt, inspect_target

    os.environ['BUYEROS_POLICY_FIXTURE_EVIDENCE'] = str(evidence / 'allocator')
    name, dsn = _start_container()  # Full identity gate precedes its first SQL probe.
    receipt = fixture_receipt(dsn)
    metadata = json.loads(receipt.read_text())
    os.environ['BUYEROS_TEST_DATABASE_URL'] = dsn
    os.environ['BUYEROS_POLICY_TARGET_RECEIPT'] = str(receipt)
    inspect_target(receipt)
    print(json.dumps({'evidence': str(evidence), 'target': metadata}), flush=True)
    marker.parent.mkdir(exist_ok=True)
    marker.write_text(name)
    child = os.environ.copy()
    # Worker fixture helpers re-register proof in their own fresh evidence dirs.
    child.pop('BUYEROS_POLICY_FIXTURE_EVIDENCE', None)
    child.update(COREPACK_HOME='/workspace/.cache/corepack', UV_CACHE_DIR='/workspace/.cache/uv',
                 BUYEROS_CORE_CHROMIUM=shutil.which('chromium') or '',
                 BUYEROS_CORE_JUNIT=str(evidence / 'browser.xml'),
                 BUYEROS_CORE_OUTPUT_DIR=str(evidence / 'browser'),
                 BUYEROS_E2E_WORKER_LOG_DIR=str(evidence / 'worker-logs'))
    command = ['corepack', 'pnpm', 'exec', 'playwright', 'test',
               '--config', 'playwright.core-isolated.config.ts', *sys.argv[1:]]
    try:
        with (evidence / 'browser.log').open('x') as output:
            result = subprocess.run(command, cwd=ROOT, env=child, stdout=output, stderr=subprocess.STDOUT)
        print('\n'.join((evidence / 'browser.log').read_text().splitlines()[-35:]), flush=True)
        changed = [path for path, digest in fingerprints.items()
                   if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest]
        if changed:
            raise RuntimeError('Tested source changed during execution; rerun required: ' + ', '.join(changed))
        if any(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest for path, digest in retained_logs.items()):
            raise RuntimeError('Earlier worker evidence changed during this run')
        (evidence / 'preserved-worker-evidence.json').write_text(json.dumps(retained_logs, indent=2))
        return result.returncode
    finally:
        # No name-based broad cleanup: independently revalidate the exact allocation.
        inspect_target(receipt)
        removed = subprocess.run(['docker', 'rm', '-f', '-v', metadata['container_id']],
                                 capture_output=True, text=True, timeout=30)
        if removed.returncode:
            raise RuntimeError('Exact owned target cleanup failed')
        (evidence / 'cleanup.json').write_text(json.dumps({'container_id': metadata['container_id'], 'removed': True}))
        if marker.exists() and marker.read_text().strip() == name:
            marker.unlink()
        archive_dead_lock(evidence)


if __name__ == '__main__':
    raise SystemExit(main())
