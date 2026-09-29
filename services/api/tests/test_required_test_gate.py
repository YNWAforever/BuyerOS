"""A required integration suite must fail CI when pytest silently skips it."""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
GATE = ROOT / "scripts" / "check-required-tests.py"


def _run_gate(tmp_path: Path, testcase: str) -> subprocess.CompletedProcess[str]:
    report = tmp_path / "tests.xml"
    report.write_text(
        f'<testsuite tests="1"><testcase classname="integration" name="db">{testcase}</testcase></testsuite>',
        encoding="utf-8",
    )
    return subprocess.run(
        [sys.executable, str(GATE), "--junit", str(report)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_required_suite_skip_fails_gate(tmp_path: Path):
    skipped = _run_gate(tmp_path, '<skipped message="database unavailable" />')
    assert skipped.returncode == 1, skipped.stdout + skipped.stderr
    assert "skipped=1" in skipped.stdout


def test_required_suite_passes_gate(tmp_path: Path):
    passed = _run_gate(tmp_path, "")
    assert passed.returncode == 0, passed.stdout + passed.stderr
    assert "passed=1" in passed.stdout


def test_required_suite_error_fails_gate(tmp_path: Path):
    errored = _run_gate(tmp_path, '<error message="fixture failed" />')
    assert errored.returncode == 1, errored.stdout + errored.stderr
    assert "errors=1" in errored.stdout
