"""Pre-provision rejection: no database or Docker fixture is requested here."""
import importlib.util
from pathlib import Path

import pytest


def runner():
    path = Path(__file__).resolve().parents[1] / 'tools/run_sales_isolated.py'
    spec = importlib.util.spec_from_file_location('sales_runner', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('name,value', [
    ('BUYEROS_DATABASE_URL', 'postgresql://shared.invalid/prod'),
    ('BUYEROS_TEST_DATABASE_URL', 'postgresql://localhost/buyeros_test_shared'),
    ('DATABASE_URL', 'postgresql://shared.invalid/prod'),
    ('OPENAI_API_KEY', 'fixture-looking-but-inherited'),
    ('BUYEROS_XVERUM_TOKEN', 'inherited'),
    ('XVERUM_TOKEN', 'inherited'),
    ('AWS_SESSION_TOKEN', 'inherited'),
    ('GOOGLE_APPLICATION_CREDENTIALS', '/inherited/live.json'),
    ('NEXT_PUBLIC_CONVERSATION_HOME', 'true'),
    ('DOCKER_HOST', 'tcp://remote.invalid:2375'),
])
def test_sales_runner_rejects_shared_database(tmp_path, name, value):
    writes = []
    code = runner().execute(tmp_path / 'evidence', {name: value}, lambda: writes.append(1))
    assert code != 0
    assert writes == []
    assert not (tmp_path / 'evidence').exists()


def test_sales_runner_requires_explicit_allocator(tmp_path):
    assert runner().main(['--evidence', str(tmp_path / 'evidence')], env={}) != 0
    assert not (tmp_path / 'evidence').exists()


def test_sales_runner_accepts_clean_environment():
    runner().validate_environment({'PATH': '/bin', 'SYSTEMROOT': 'C:/Windows'})


def test_sales_runner_rejects_unowned_case(tmp_path):
    assert runner().main(['--allocate-owned', '--evidence', str(tmp_path / 'evidence'),
                          '--case', '/external/test_paid.py'], env={}) != 0
    assert not (tmp_path / 'evidence').exists()


def test_case_receipt_binds_actual_artifact_bytes(tmp_path):
    import hashlib
    import json
    module = runner()
    plugin = module.CaseReceipts(tmp_path, {'candidate_sha256': 'a'*64})
    plugin.cases = {'synthetic': {'id': 'synthetic', 'status': 'PASS'}}
    payload = b'<testsuite tests="1"/>'
    (tmp_path / 'pytest.xml').write_bytes(payload)
    plugin.bind_artifact()
    receipt = json.loads((tmp_path / 'cases.json').read_text())[0]
    assert receipt['artifact_sha256'] == hashlib.sha256(payload).hexdigest()
    assert receipt['artifact'] == 'pytest.xml'


def test_required_native_suite_cannot_silently_shrink(monkeypatch):
    module = runner()
    original = Path.is_file
    monkeypatch.setattr(Path, 'is_file', lambda path: False if path.name == 'test_settlement.py' else original(path))
    with pytest.raises(RuntimeError, match='cannot shrink'):
        module.selection()


@pytest.mark.parametrize('missing', ['test_sales_composition_db.py', 'test_xverum_mcp.py'])
@pytest.mark.parametrize('affected', [False, True])
def test_fix1_missing_focused_file_refused_before_any_writes(tmp_path, monkeypatch, missing, affected):
    module = runner()
    original = Path.is_file
    monkeypatch.setattr(Path, 'is_file', lambda path: False if path.name == missing else original(path))
    calls = []
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **k: calls.append(a))
    args = ['--allocate-owned', '--evidence', str(tmp_path / 'evidence')]
    if affected:
        args += ['--case', str(module.API / 'tests/test_sales_context.py')]
    assert module.main(args, env={}) != 0
    assert not (tmp_path / 'evidence').exists()
    assert calls == []


@pytest.mark.parametrize('explicit', [False, True])
def test_fix1_remote_effective_context_refused_before_receipts(tmp_path, monkeypatch, explicit):
    import subprocess
    module = runner()
    commands = []
    def command(argv, **kwargs):
        commands.append(argv)
        assert argv[:3] in (['docker', 'context', 'show'], ['docker', 'context', 'inspect'])
        return subprocess.CompletedProcess(argv, 0, 'remote-context\n' if argv[2] == 'show' else 'ssh://remote.invalid\n', '')
    monkeypatch.setattr(module.subprocess, 'run', command)
    writes = []
    env = {'DOCKER_CONTEXT': 'remote-context'} if explicit else {}
    assert module.execute(tmp_path / 'evidence', env, lambda *_: writes.append(1)) != 0
    assert not (tmp_path / 'evidence').exists() and writes == []
    assert commands


def test_fix1_verified_context_is_passed_to_action(tmp_path, monkeypatch):
    import subprocess
    module = runner()
    def command(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, 'unix:///var/run/docker.sock\n', '')
    monkeypatch.setattr(module.subprocess, 'run', command)
    identities = []
    assert module.execute(tmp_path / 'evidence', {'DOCKER_CONTEXT': 'local'},
                          lambda identity: identities.append(identity) or 0) == 0
    assert identities == [{'context': 'local', 'endpoint': 'unix:///var/run/docker.sock'}]


def fake_owned_docker(module, monkeypatch, *, fail_create=False):
    """Only mocks: never create a real colliding name or contact a Docker daemon."""
    import json
    import subprocess
    commands, records, created = [], [], {}
    identity = {'context': 'local', 'endpoint': 'unix:///var/run/docker.sock'}
    monkeypatch.setattr(module, 'resolve_docker_context', lambda env: identity)
    def command(argv, **kwargs):
        commands.append(argv)
        assert argv[:3] == ['docker', '--context', 'local']
        args = argv[3:]
        if args[:2] == ['image', 'inspect']:
            value = 'sha256:' + 'd'*64
        elif args[0] == 'run':
            if fail_create:
                return subprocess.CompletedProcess(argv, 1, '', 'mock name collision')
            name = args[args.index('--name')+1]
            cid = str(len(records)+1)*64
            created[cid] = {'Id': cid, 'Name': '/' + name, 'Image': 'sha256:'+'d'*64,
                            'Config': {'Labels': {'buyeros.policy.run': name}}, 'Mounts': []}
            value = cid
        elif args[0] == 'inspect':
            if args[1] not in created:
                return subprocess.CompletedProcess(argv, 1, '', 'No such object')
            value = json.dumps([created[args[1]]])
        elif args[0] == 'rm':
            assert len(args[-1]) == 64
            del created[args[-1]]
            value = args[-1]
        else:
            raise AssertionError(argv)
        return subprocess.CompletedProcess(argv, 0, value, '')
    docker = module.OwnedDocker(identity, records.append, env={}, command=command)
    return docker, commands, records, created


def test_fix1_failed_creation_never_removes_unowned_name(monkeypatch):
    module = runner()
    docker, commands, records, _ = fake_owned_docker(module, monkeypatch, fail_create=True)
    assert docker('run', '-d', '--name', 'collision', '--label', 'buyeros.policy.run=collision', 'postgres:16').returncode == 1
    with pytest.raises(ValueError, match='unverified'):
        docker('rm', '-f', 'collision')
    assert not records and not any(command[3] == 'rm' for command in commands)


def test_fix1_creation_id_recorded_before_startup_and_timeout_removal(monkeypatch):
    module = runner()
    docker, commands, records, created = fake_owned_docker(module, monkeypatch)
    result = docker('run', '-d', '--name', 'owned', '--label', 'buyeros.policy.run=owned', 'postgres:16')
    assert records[0]['container_id'] == result.stdout == '1'*64
    # No ready SQL/fixture receipt yet: simulate allocator startup timeout cleanup.
    docker('rm', '-f', 'owned')
    assert commands[-1][-1] == result.stdout and not created


def test_fix1_owned_cleanup_refuses_identity_drift(monkeypatch):
    module = runner()
    docker, commands, _, created = fake_owned_docker(module, monkeypatch)
    result = docker('run', '-d', '--name', 'owned', '--label', 'buyeros.policy.run=owned', 'postgres:16')
    created[result.stdout]['Config']['Labels']['buyeros.policy.run'] = 'foreign'
    with pytest.raises(ValueError, match='identity'):
        docker('rm', '-f', 'owned')
    assert not any(command[3] == 'rm' for command in commands)


@pytest.mark.parametrize('fail_create', [True, False])
def test_fix1_original_allocator_failure_branches_are_exact_owned(monkeypatch, fail_create):
    from types import SimpleNamespace
    from tests import conftest, policy_activation_target
    module = runner()
    docker, commands, records, created = fake_owned_docker(module, monkeypatch, fail_create=fail_create)
    monkeypatch.setattr(conftest, '_docker', docker)
    monkeypatch.setattr(policy_activation_target, 'local_docker_context',
                        lambda: ('local', 'unix:///var/run/docker.sock'))
    clock = iter(range(0, 1000, 121))
    monkeypatch.setattr(conftest, 'time', SimpleNamespace(time=lambda: next(clock), sleep=lambda _: None))
    def unavailable(_):
        raise RuntimeError('mock startup timeout')
    monkeypatch.setattr(conftest, '_unavailable', unavailable)
    with pytest.raises(ValueError if fail_create else RuntimeError,
                       match='unverified' if fail_create else 'mock startup timeout'):
        conftest._start_container()
    removals = [command for command in commands if command[3] == 'rm']
    if fail_create:
        assert not removals and not records
    else:
        assert len(records) == len(removals) == 2
        assert {command[-1] for command in removals} == {row['container_id'] for row in records}
        assert not created


def test_fix1_context_drift_prevents_allocation(monkeypatch):
    module = runner()
    docker, commands, _, _ = fake_owned_docker(module, monkeypatch)
    monkeypatch.setattr(module, 'resolve_docker_context',
                        lambda env: {'context': 'local', 'endpoint': 'ssh://changed.invalid'})
    with pytest.raises(ValueError, match='identity changed'):
        docker('run', '-d', '--name', 'owned', '--label', 'buyeros.policy.run=owned', 'postgres:16')
    assert commands == []


def test_fix1_all_loaded_fixture_aliases_are_guarded(tmp_path, monkeypatch):
    from types import ModuleType
    module = runner()
    aliases = []
    for name in ('pure_mock_conftest', 'another_pure_mock_conftest'):
        alias = ModuleType(name)
        alias.__file__ = str(module.API / 'tests/conftest.py')
        alias._docker = object()
        monkeypatch.setitem(module.sys.modules, name, alias)
        aliases.append(alias)
    receipt = module.CaseReceipts(tmp_path, {})
    receipt.docker = object()
    receipt.bind_allocators(aliases)
    assert all(alias._docker is receipt.docker for alias in aliases)


@pytest.mark.parametrize('remote',[False,True])
def test_final_explicit_cold_image_preparation_precedes_allocation(monkeypatch,remote):
    import subprocess
    module=runner();commands=[];cached=False
    identity={'context':'local','endpoint':'ssh://remote' if remote else 'unix:///var/run/docker.sock'}
    monkeypatch.setattr(module,'resolve_docker_context',lambda env:identity)
    def command(args,**kwargs):
        nonlocal cached
        commands.append(args[3:])
        if args[3:5]==['image','inspect']:
            return subprocess.CompletedProcess(args,0 if cached else 1,'sha256:'+'a'*64 if cached else '', '')
        if args[3:]==['pull','postgres:16']:
            cached=True
            return subprocess.CompletedProcess(args,0,'','')
        raise AssertionError(args)
    if remote:
        with pytest.raises(ValueError,match='local'):module.prepare_image({},command=command)
        assert commands==[]
    else:
        docker=module.OwnedDocker(identity,lambda row:None,env={},command=command)
        with pytest.raises(ValueError,match='Local allocation image is unverified'):
            docker('run','-d','--name','cold','--label','buyeros.policy.run=cold','postgres:16')
        assert commands==[['image','inspect','postgres:16','--format','{{.Id}}']]
        commands.clear()
        assert module.prepare_image({},command=command)['image_id']=='sha256:'+'a'*64
        assert commands==[['image','inspect','postgres:16','--format','{{.Id}}'],['pull','postgres:16'],['image','inspect','postgres:16','--format','{{.Id}}']]
    workflow=(module.ROOT/'.github/workflows/buyeros-ci.yml').read_text().split('  guided-sales-isolated:',1)[1]
    assert workflow.index('--prepare-local-image')<workflow.index('--allocate-owned')
    assert workflow.count('--prepare-local-image') == 1


@pytest.mark.parametrize('executable,override,expected', [
    ('/usr/local/bin/pnpm', None, ['/usr/local/bin/pnpm']),
    ('C:/Tools/pnpm.cmd', None, ['C:/Tools/pnpm.cmd']),
    ('/usr/local/bin/pnpm', '/explicit/pnpm.cjs', ['node', '/explicit/pnpm.cjs']),
])
def test_final_browser_uses_installed_pnpm_or_explicit_override(monkeypatch, tmp_path, executable, override, expected):
    import shutil
    import subprocess

    spec = importlib.util.spec_from_file_location('final_browser_probe', Path(__file__).with_name('sales_final_browser.py'))
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    monkeypatch.setenv('SALES_TEST_EVIDENCE_DIR', str(tmp_path))
    monkeypatch.delenv('SALES_PNPM_CJS', raising=False)
    if override:
        monkeypatch.setenv('SALES_PNPM_CJS', override)
    monkeypatch.setattr(shutil, 'which', lambda name: executable if name == 'pnpm' else None)
    commands = []

    class Server:
        server_port = 12345
        def __init__(self, *args): pass
        def serve_forever(self): pass
        def shutdown(self): pass
        def server_close(self): pass

    def run(argv, **kwargs):
        commands.append(argv)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(bridge, 'ThreadingHTTPServer', Server)
    monkeypatch.setattr(bridge.subprocess, 'run', run)
    bridge.run_browser(object(), {'phase': 'native'}, {'Authorization': 'Bearer fixture'})
    assert commands == [[*expected, 'exec', 'playwright', 'test', '--config', 'playwright.sales-skills.config.ts', '--grep', 'final owned native']]
