"""Run the actual CI metadata guards against native discovery and output."""
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CIEvidenceGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (ROOT / '.github/workflows/buyeros-ci.yml').read_text(encoding='utf-8')
        cls.directory = tempfile.TemporaryDirectory(prefix='buyeros-ci-native-')
        cls.addClassCleanup(cls.directory.cleanup)
        cls.fixture = Path(cls.directory.name)
        owner_suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern='test_c61_built_owner.py')
        pending = [owner_suite]
        names = []
        while pending:
            item = pending.pop()
            if isinstance(item, unittest.TestCase):
                names.append(item.id())
            else:
                pending.extend(item)
        if len(names) != len(set(names)) or len(names) != 7:
            raise AssertionError('original owner inventory must contain seven distinct native cases')
        cls.owner_names = sorted(names)
        execution = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                                    '-p', 'test_c61_built_owner.py', '-v'], cwd=ROOT, capture_output=True, text=True)
        if execution.returncode:
            raise AssertionError(execution.stderr)
        cls.native_owner_log = execution.stdout + execution.stderr
        commands = [line.strip() for line in cls.workflow.splitlines()
                    if line.strip().startswith('python -c ') and 'ci-built-owner.log' in line]
        if len(commands) != 1:
            raise AssertionError('original CI owner postgate must have one command')
        # The workflow executes this command through a POSIX shell. Preserve
        # its quoting before invoking Python, including the regex backslashes.
        cls.owner_argv = shlex.split(commands[0])
        if cls.owner_argv[:2] != ['python', '-c'] or len(cls.owner_argv) != 3:
            raise AssertionError('unexpected owner postgate command')

    def owner_guard(self, native_log):
        discovery = self.fixture / 'owner-discovery.json'
        log = self.fixture / 'owner.log'
        discovery.write_text(json.dumps(self.owner_names), encoding='utf-8')
        log.write_text(native_log, encoding='utf-8')
        script = self.owner_argv[2].replace('artifacts/c61/ci-built-owner-discovery.json', discovery.as_posix())
        script = script.replace('artifacts/c61/ci-built-owner.log', log.as_posix())
        return subprocess.run([sys.executable, '-c', script], cwd=ROOT, capture_output=True, text=True)

    def test_full_native_evidence_discovery_runs_the_actual_CI_guard(self):
        marker = '      - name: Discover C61 evidence checker assertions before running\n'
        self.assertEqual(self.workflow.count(marker), 1)
        block = self.workflow.split(marker, 1)[1].split('\n      - ', 1)[0]
        script = block.split("          python - <<'PY'\n", 1)[1].rsplit('\n          PY', 1)[0]
        script = textwrap.dedent(script)
        destination = self.fixture / 'actual-evidence-discovery.json'
        script = script.replace('artifacts/c61/ci-evidence-checker-discovery.json', destination.as_posix())
        result = subprocess.run([sys.executable, '-c', script], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(destination.read_text(encoding='utf-8'))
        self.assertGreater(report['count'], 0)
        self.assertEqual(report['count'], len(set(report['unique_names'])))
        self.assertIn('test_c61_ci_evidence.CIEvidenceGuardTests.test_owner_actual_native_log_runs_the_POSIX_CI_guard',
                      report['unique_names'])

    def test_owner_actual_native_log_runs_the_POSIX_CI_guard(self):
        result = self.owner_guard(self.native_owner_log)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_owner_empty_log_is_rejected(self):
        self.assertNotEqual(self.owner_guard('').returncode, 0)

    def test_owner_skipped_native_case_is_rejected(self):
        lines = self.native_owner_log.splitlines()
        first = next(i for i, line in enumerate(lines) if line.startswith('test_') and line.endswith(' ... ok'))
        lines[first] = lines[first].replace(' ... ok', " ... skipped 'fixture interruption'")
        self.assertNotEqual(self.owner_guard('\n'.join(lines)+'\n').returncode, 0)


if __name__ == '__main__':
    unittest.main()
