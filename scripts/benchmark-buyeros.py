"""Run opt-in BuyerOS T29 read and broker-publish benchmarks on disposable services.

Example: python scripts/benchmark-buyeros.py --fixture-size 10000 --workspaces 100
The API fixture owns PostgreSQL 16; the 100-workspace worker stage also owns Valkey 8.
No Celery worker or provider is called.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "services" / "api"
CASE = API / "tests" / "benchmark_buyeros_case.py"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-size", type=int, choices=(1000, 10000), required=True)
    parser.add_argument("--workspaces", type=int, choices=(1, 10, 100), required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "t29-benchmark.json")
    args = parser.parse_args()
    if os.environ.get("BUYEROS_TEST_DATABASE_URL"):
        parser.error("unset BUYEROS_TEST_DATABASE_URL; this benchmark owns a disposable Docker database")
    python = API / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        parser.error(f"API virtual environment missing: {python}; run uv sync --frozen in services/api")
    env = dict(os.environ)
    env["BUYEROS_STRICT_INTEGRATION"] = "1"
    env["BUYEROS_BENCH_FIXTURE_SIZE"] = str(args.fixture_size)
    env["BUYEROS_BENCH_WORKSPACES"] = str(args.workspaces)
    env["BUYEROS_BENCH_OUTPUT"] = str(args.output.resolve())
    command = [str(python), "-m", "pytest", "-q", "-s", str(CASE), "--tb=short"]
    result = subprocess.call(command, cwd=API, env=env)
    if result or args.workspaces != 100:
        return result
    worker = ROOT / "services" / "worker"
    worker_python = worker / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not worker_python.is_file():
        parser.error(f"worker virtual environment missing: {worker_python}; run uv sync --frozen in services/worker")
    dispatcher_output = args.output.resolve().with_name(args.output.stem + "-dispatcher.json")
    env["BUYEROS_DISPATCH_BENCH_OUTPUT"] = str(dispatcher_output)
    worker_case = worker / "tests" / "benchmark_dispatcher_case.py"
    result = subprocess.call([str(worker_python), "-m", "pytest", "-q", "-s", str(worker_case), "--tb=short"],
                             cwd=worker, env=env)
    if result:
        return result
    output = args.output.resolve()
    combined = json.loads(output.read_text(encoding="utf-8"))
    combined["dispatcher"] = json.loads(dispatcher_output.read_text(encoding="utf-8"))
    output.write_text(json.dumps(combined, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())