"""Installed code paths for child processes without inherited credentials."""
from importlib.metadata import distribution
import os
from pathlib import Path
import sys


def child_environment() -> dict[str, str]:
    # Hosted runtimes add vendor packages to the parent's sys.path. A fresh
    # interpreter cannot see that modification. Read only installed package
    # metadata and our code location, never caller input or inherited PYTHONPATH.
    roots = [Path(__file__).resolve().parents[2]]
    for package in ("psycopg", "sqlalchemy", "pypdf", "langgraph", "langgraph-checkpoint-postgres"):
        root = Path(distribution(package).locate_file("")).resolve()
        if not root.is_dir():
            raise ValueError("installed runtime package directory required")
        if root not in roots:
            roots.append(root)
    env = {"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHONPATH": os.pathsep.join(str(root) for root in roots)}
    if sys.platform == "win32":
        env["SystemRoot"] = os.environ.get("SystemRoot", r"C:\Windows")
    return env
