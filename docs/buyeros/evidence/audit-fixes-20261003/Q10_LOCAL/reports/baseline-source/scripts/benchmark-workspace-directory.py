"""Capture the current directory baseline on an owned PostgreSQL 16 fixture.

Exit 1 means the frozen <=6 SQL budget failed; a successful capture is not a
release gate pass. No live auth/provider/network load is verified.
"""
import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "services/api"
sys.path.insert(0, str(API))
from tools.quality_metrics import DATABASE_VARIABLES


def cleanup_owned(marker: Path, nonce: str) -> None:
    if not marker.exists():
        return
    owned = json.loads(marker.read_text(encoding="utf-8"))
    if owned["nonce"] != nonce or not owned["name"].startswith("buyeros-test-"):
        raise ValueError("refusing unrecognized directory fixture marker")
    inspected = subprocess.run(["docker", "inspect", owned["name"]], capture_output=True, text=True, timeout=15)
    if inspected.returncode:
        if "no such" in inspected.stderr.lower():
            return
        raise RuntimeError("cannot verify owned fixture for cleanup")
    identity = json.loads(inspected.stdout)[0]
    if identity["Id"] != owned["container_id"]:
        raise ValueError("refusing replacement container")
    subprocess.run(["docker", "rm", "-f", owned["name"]], check=True, timeout=20, capture_output=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, choices=range(30, 101), default=30)
    parser.add_argument("--actors", type=int, choices=(1, 10, 25), default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for variable in DATABASE_VARIABLES:
        if os.environ.get(variable):
            parser.error(f"unset inherited database {variable}; owned Docker only")
    output = args.output.resolve()
    marker, junit = output.with_suffix(".owner.json"), output.with_suffix(".xml")
    if any(p.exists() for p in (output, marker, junit)):
        parser.error("output/evidence must be new")
    python = API / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        parser.error("API virtual environment missing; run uv sync --frozen")
    nonce = uuid.uuid4().hex
    env = dict(os.environ, BUYEROS_STRICT_INTEGRATION="1", BUYEROS_DIRECTORY_OUTPUT=str(output),
               BUYEROS_DIRECTORY_OWNER=str(marker), BUYEROS_DIRECTORY_NONCE=nonce,
               BUYEROS_DIRECTORY_SAMPLES=str(args.samples), BUYEROS_DIRECTORY_ACTORS=str(args.actors))
    # Collection/extra-selection flags cannot turn a required DB capture into 0 tests.
    env.pop("PYTEST_ADDOPTS", None)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [str(python), "-m", "pytest", "-q", "-s", "tests/benchmark_workspace_directory_case.py", "--tb=short", f"--junitxml={junit}"]
    try:
        result = subprocess.run(command, cwd=API, env=env, timeout=900)
    except subprocess.TimeoutExpired:
        print("Directory capture exceeded its 15-minute local bound", file=sys.stderr)
        return 1
    finally:
        cleanup_owned(marker, nonce)
    if result.returncode:
        return result.returncode
    if not output.is_file():
        parser.error("no observed report; collection is not verification")
    report = json.loads(output.read_text(encoding="utf-8"))
    if report.get("run_id") != nonce or report.get("schema") != "buyeros.workspace-directory-benchmark.v1" or len(report.get("matrix", [])) != 4:
        parser.error("invalid or stale benchmark report")
    passed = report["directory_gate"]["passed"]
    print(f"Capture verified; frozen directory SQL gate passed={passed}; live_verified=false")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
