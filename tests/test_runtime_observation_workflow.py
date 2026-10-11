"""Execute observed workflow shell redirection with owned CLI stand-ins, no runtime calls."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


class RuntimeWorkflowPrivacyTests(unittest.TestCase):
    def private_console(self, step_id):
        workflow = yaml.load((ROOT/'.github/workflows/buyeros-runtime-acceptance.yml').read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
        steps = workflow['jobs']['collect-observations']['steps']
        step = next(step for step in steps if step.get('id') == step_id)
        with tempfile.TemporaryDirectory() as parent:
            directory = Path(parent)
            (directory/'buyeros-private-observations').mkdir()
            fake = directory/'owned-cli.py'
            fake.write_text('import sys\nprint("PRIVATE_RUNTIME_STATUS_stdout")\nprint("PRIVATE_RUNTIME_STATUS_stderr", file=sys.stderr)\n', encoding='utf-8')
            command = step['run'].replace('services/api/.venv/bin/python', shlex.quote(Path(sys.executable).as_posix())+' '+shlex.quote(fake.as_posix()), 1)
            # Windows' System32 bash is WSL and does not share these native
            # paths/environment; use the same Git Bash as the syntax checks.
            bash = str(Path(os.environ.get('ProgramFiles', 'C:/Program Files'))/'Git/bin/bash.exe') if os.name == 'nt' else shutil.which('bash')
            self.assertTrue(bash and Path(bash).is_file(), 'native bash required, no skipped privacy controls')
            result = subprocess.run([bash, '-c', command],
                                    cwd=directory, env=dict(os.environ, RUNNER_TEMP=directory.as_posix(), GITHUB_SHA='a'*40),
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('PRIVATE_RUNTIME_STATUS', result.stdout+result.stderr)
            private_logs = list((directory/'buyeros-private-observations').glob('*.log'))
            self.assertTrue(any('PRIVATE_RUNTIME_STATUS_stdout' in path.read_text() and
                                'PRIVATE_RUNTIME_STATUS_stderr' in path.read_text() for path in private_logs))

    def test_schema_status_stays_out_of_public_console(self): self.private_console('schema')
    def test_api_status_stays_out_of_public_console(self): self.private_console('api')
    def test_summary_status_stays_out_of_public_console(self): self.private_console('summary')


if __name__ == '__main__': unittest.main()
