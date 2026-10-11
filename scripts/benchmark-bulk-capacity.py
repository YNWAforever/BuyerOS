"""Finite 50/500/10000 owned PG16 capture; refuses inherited DB targets."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "services/api"
sys.path.insert(0, str(API))
from tools.quality_metrics import DATABASE_VARIABLES, provenance
from tests.bulk_capacity_driver import captures_complete


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for key in DATABASE_VARIABLES:
        if os.environ.get(key):
            parser.error("unset inherited database " + key + "; owned fixture only")
    folder = args.output_dir.resolve()
    if folder.exists():
        parser.error("output directory must be new; retain previous evidence")
    python = API / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        parser.error("frozen API virtual environment required")
    folder.mkdir(parents=True)
    env = dict(os.environ)
    env.pop("PYTEST_ADDOPTS", None)
    env.update(PYTHONUTF8="1", BUYEROS_STRICT_INTEGRATION="1", BUYEROS_BULK_CAPACITY_OUTPUT=str(folder))
    discovery = folder / "discovery.txt"
    junit = folder / "tests.xml"
    case = "tests/benchmark_bulk_capacity_case.py"
    command = [str(python), "-X", "utf8", "-m", "pytest", case]
    collected = subprocess.run(command + ["--collect-only", "-q"], cwd=API, env=env, capture_output=True, timeout=60)
    discovery.write_bytes(collected.stdout)
    if collected.returncode:
        sys.stderr.buffer.write(collected.stderr)
        return collected.returncode
    gate = [str(python), str(ROOT / "scripts/check-required-tests.py"), "--pytest-discovery", str(discovery), "--expected-count", "3"]
    checked = subprocess.run(gate + ["--discovery-only"], cwd=ROOT, env=env, timeout=60)
    if checked.returncode:
        return checked.returncode
    tested = subprocess.run(command + ["-q", "--tb=short", "--junitxml=" + junit.as_posix()], cwd=API, env=env, timeout=600)
    if tested.returncode:
        return tested.returncode
    checked = subprocess.run(gate + ["--junit", str(junit)], cwd=ROOT, env=env, timeout=60)
    if checked.returncode:
        return checked.returncode
    captures = [json.loads((folder / f"capture-{count}.json").read_text(encoding="utf-8")) for count in [50, 500, 10000]]
    if not captures_complete(captures):
        print("Incomplete bulk resource measurements; raw evidence retained", file=sys.stderr)
        return 1
    paths = [Path(__file__), API / case, API / "tests/bulk_capacity_driver.py",
             ROOT / "services/worker/tests/worker_capacity_driver.py", API / "tests/conftest.py",
             API / "tests/test_bulk_manifest_db.py", API / "tests/test_buyer_review_db.py",
             API / "buyeros_api/services/bulk_service.py", API / "buyeros_api/services/bulk_manifest.py",
             API / "buyeros_api/api/routes/bulk_manifests.py", API / "buyeros_api/api/deps.py"]
    report = dict(schema="buyeros.bulk-capacity.v1", evidence_mode="owned_disposable_pg16_inprocess_api",
                  live_verified=False, release_accepted=False, budget_adopted=False, captures=captures,
                  provenance=provenance(ROOT, paths))
    with (folder / "report.json").open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2, allow_nan=False)
        output.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
