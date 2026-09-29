"""Run opt-in T29 mutation and run-admission timing on disposable PostgreSQL.

No external provider, paid request, worker, broker or production database is used.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "services" / "api"
CASE = API / "tests" / "benchmark_mutation_case.py"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "t29-mutations.json")
    args = parser.parse_args()
    if os.environ.get("BUYEROS_TEST_DATABASE_URL"):
        parser.error("unset BUYEROS_TEST_DATABASE_URL; this benchmark owns a disposable Docker database")
    python = API / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        parser.error(f"API virtual environment missing: {python}; run uv sync --frozen in services/api")
    env = dict(os.environ)
    env["BUYEROS_STRICT_INTEGRATION"] = "1"
    env["BUYEROS_MUTATION_BENCH_OUTPUT"] = str(args.output.resolve())
    return subprocess.call([str(python), "-m", "pytest", "-q", "-s", str(CASE), "--tb=short"],
                           cwd=API, env=env)


if __name__ == "__main__":
    sys.exit(main())
