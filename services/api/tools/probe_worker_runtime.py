"""Local native-runtime feasibility probe; never a customer executor.

Consumes a migrated, explicitly owned loopback test DB using a worker login.
Does not create roles/tables, migrate, call providers or claim hosted proof.
Run in the legacy worker environment until native ownership moves to API.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlsplit

LOCAL_REQUIRED_CHECKS = (
    "native_imports", "pdf_native", "pdf_isolation", "pdf_timeout",
    "postgres_checkpoint", "postgres_role",
)
HOSTED_REQUIRED_CHECKS = (
    "vercel_api_bundle", "vercel_app_90s", "vercel_api_90s", "preview_protection",
)
PACKAGES = ("psycopg", "sqlalchemy", "pypdf", "langgraph", "langgraph-checkpoint-postgres")


def require_disposable_database(dsn: str) -> None:
    parsed = urlsplit(dsn)
    if (parsed.scheme not in {"postgresql", "postgres"}
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or not re.fullmatch(r"buyeros_test_[a-zA-Z0-9_]+", parsed.path.lstrip("/"))
            or parsed.query or parsed.fragment):
        raise ValueError("probe requires an owned disposable loopback buyeros_test_* database")


@dataclass
class RuntimeProbeReport:
    environment: str
    source_sha: str
    records: list[dict]

    def _verified(self, required: tuple[str, ...]) -> bool:
        return all(any(row["check"] == key and row["state"] == "verified"
                       for row in self.records) for key in required)

    @property
    def local_feasible(self) -> bool:
        return self._verified(LOCAL_REQUIRED_CHECKS)

    @property
    def hosted_feasible(self) -> bool:
        return self.environment == "preview" and self.local_feasible and self._verified(HOSTED_REQUIRED_CHECKS)

    def to_dict(self) -> dict:
        return {"environment": self.environment, "source_sha": self.source_sha,
                "local_feasible": self.local_feasible, "hosted_feasible": self.hosted_feasible,
                "records": self.records,
                "counts": {state: sum(row["state"] == state for row in self.records)
                           for state in ("verified", "failed", "not_run")}}


def sample_pdf() -> bytes:
    """A reviewed fictional single-page PDF; no user or provider input."""
    stream = b"BT /F1 12 Tf 50 250 Td (Product: Sensor) Tj ET"
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    result = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    start = len(result)
    result.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        result.extend(f"{offset:010d} 00000 n \n".encode())
    result.extend(f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode())
    return bytes(result)


def execution_module(name: str):
    """Use the sole new owner after extraction; legacy package before CF03."""
    try:
        return importlib.import_module(f"buyeros_api.execution.{name}")
    except ModuleNotFoundError as exc:
        if exc.name not in {"buyeros_api.execution", f"buyeros_api.execution.{name}"}:
            raise
        return importlib.import_module(f"buyeros_worker.{name}")


def _pdf_probe(records: list[dict]) -> None:
    parser = execution_module("pdf_parser")
    from buyeros_api.services.ingestion_service import validate_upload
    body = sample_pdf()
    upload = validate_upload("probe.pdf", "application/pdf", body, hashlib.sha256(body).hexdigest())
    original = parser.subprocess.run
    observed = []

    def inspect_child(*args, **kwargs):
        from buyeros_api.execution.subprocess_runtime import child_environment
        allowed = {"PYTHONIOENCODING", "PYTHONDONTWRITEBYTECODE", "PYTHONPATH", "SystemRoot"}
        assert set(kwargs["env"]) <= allowed
        assert kwargs["env"] == child_environment()
        assert kwargs["timeout"] == 8
        assert Path(kwargs["cwd"]).is_dir()
        observed.append({"environment_keys": sorted(kwargs["env"]), "timeout_seconds": 8,
                         "temporary_workdir": True, "stdin_bytes_only": kwargs["input"] == body})
        return original(*args, **kwargs)

    parser.subprocess.run = inspect_child
    start, cpu = time.perf_counter(), time.process_time()
    try:
        facts = parser.parse_pdf_candidates(upload)
    finally:
        parser.subprocess.run = original
    assert [(row["field"], row["value"], row["approved"]) for row in facts] == [("product", "Sensor", False)]
    records.append({"check": "pdf_native", "state": "verified", "details": {
        "wall_seconds": time.perf_counter() - start, "parent_cpu_seconds": time.process_time() - cpu,
        "sample_sha256": hashlib.sha256(body).hexdigest(), "facts": len(facts)}})
    records.append({"check": "pdf_isolation", "state": "verified", "details": observed[0]})

    # Exercise the actual parent kill primitive with a sleeping child, retaining
    # the parser's unchanged 8s deadline. This is a timeout fixture, not a PDF bomb.
    def sleeping_child(_command, **kwargs):
        return original([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)

    parser.subprocess.run = sleeping_child
    start = time.perf_counter()
    try:
        try:
            parser.parse_pdf_candidates(upload)
        except parser.PdfParserTimeout:
            records.append({"check": "pdf_timeout", "state": "verified", "details": {
                "timeout_seconds": 8, "child_killed": True, "fixture": "sleeping child",
                "wall_seconds": time.perf_counter() - start}})
        else:
            raise AssertionError("parser timeout failed to kill child")
    finally:
        parser.subprocess.run = original


class ProbeState(TypedDict):
    probe_id: str
    completed: bool


async def _checkpoint_probe(dsn: str, records: list[dict]) -> None:
    import psycopg
    from langgraph.graph import END, START, StateGraph
    checkpoints = execution_module("checkpoints")
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        row = await (await conn.execute(
            "SELECT rolsuper, rolbypassrls, pg_has_role(current_user, 'buyeros_worker', 'MEMBER'), "
            "EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='buyeros_graph' AND c.relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user)) "
            "FROM pg_roles WHERE rolname=current_user"
        )).fetchone()
        assert row == (False, False, True, False), "non-owner NOBYPASSRLS worker-role membership required"
    records.append({"check": "postgres_role", "state": "verified", "details": {
        "superuser": False, "bypassrls": False, "checkpoint_owner": False,
        "worker_role_membership": True, "environment": "disposable fixture role"}})
    workspace, other = uuid.uuid4(), uuid.uuid4()
    config = {"configurable": {"thread_id": f"{workspace}:{uuid.uuid4()}:cf00:1", "checkpoint_ns": ""}}
    calls = {"first": 0, "second": 0}

    async def first(_state):
        calls["first"] += 1
        return {"completed": False}

    async def second(_state):
        calls["second"] += 1
        if calls["second"] == 1:
            raise RuntimeError("intentional fixture interruption")
        return {"completed": True}

    def graph(saver):
        builder = StateGraph(ProbeState)
        builder.add_node("first", first)
        builder.add_node("second", second)
        builder.add_edge(START, "first")
        builder.add_edge("first", "second")
        builder.add_edge("second", END)
        return builder.compile(checkpointer=saver)

    async with checkpoints.open_checkpoint_saver(dsn, workspace) as saver:
        try:
            await graph(saver).ainvoke({"probe_id": str(uuid.uuid4()), "completed": False}, config)
        except RuntimeError as exc:
            assert str(exc) == "intentional fixture interruption"
        else:
            raise AssertionError("fixture interruption missing")
    async with checkpoints.open_checkpoint_saver(dsn, other) as saver:
        assert await saver.aget_tuple(config) is None
    async with checkpoints.open_checkpoint_saver(dsn, workspace) as saver:
        assert (await graph(saver).ainvoke(None, config))["completed"]
        assert (await graph(saver).ainvoke(None, config))["completed"]
    assert calls == {"first": 1, "second": 2}
    records.append({"check": "postgres_checkpoint", "state": "verified", "details": {
        "committed_node_replayed": False, "interrupted_node_resumed": True,
        "cross_tenant_read_closed": True, "schema_created_at_runtime": False}})


def probe_runtime(output: Path) -> RuntimeProbeReport:
    dsn = os.environ.get("BUYEROS_TEST_DATABASE_URL")
    if dsn:
        require_disposable_database(dsn)  # before importing drivers or doing I/O
    root = Path(__file__).resolve().parents[3]
    source = os.environ.get("BUYEROS_PROBE_SOURCE_SHA")
    if source is None:
        source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise ValueError("probe source SHA must be an exact Git commit")
    records = []
    report = RuntimeProbeReport("local", source, records)
    imports = "import psycopg, sqlalchemy, pypdf, langgraph; import langgraph.checkpoint.postgres"
    start = time.perf_counter()
    try:
        subprocess.run([sys.executable, "-c", imports], check=True, capture_output=True, timeout=30)
        cold = time.perf_counter() - start
        start, cpu = time.perf_counter(), time.process_time()
        for module in ("psycopg", "sqlalchemy", "pypdf", "langgraph", "langgraph.checkpoint.postgres"):
            importlib.import_module(module)
        parent_cold = time.perf_counter() - start
        start, cpu = time.perf_counter(), time.process_time()
        for module in ("psycopg", "sqlalchemy", "pypdf", "langgraph", "langgraph.checkpoint.postgres"):
            importlib.import_module(module)
        records.append({"check": "native_imports", "state": "verified", "details": {
            "versions": {name: importlib.metadata.version(name) for name in PACKAGES},
            "cold_subprocess_wall_seconds": cold, "parent_cold_import_wall_seconds": parent_cold,
            "warm_import_wall_seconds": time.perf_counter() - start,
            "warm_parent_cpu_seconds": time.process_time() - cpu, "platform": sys.platform,
            "python": sys.version.split()[0]}})
    except Exception as exc:
        records.append({"check": "native_imports", "state": "failed", "details": {"error_type": type(exc).__name__}})
    try:
        _pdf_probe(records)
    except Exception as exc:
        records.append({"check": "pdf_native", "state": "failed", "details": {"error_type": type(exc).__name__}})
    if dsn:
        try:
            if sys.platform == "win32":
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            asyncio.run(_checkpoint_probe(dsn, records))
        except Exception as exc:
            records.append({"check": "postgres_checkpoint", "state": "failed", "details": {"error_type": type(exc).__name__}})
    else:
        for key in ("postgres_role", "postgres_checkpoint"):
            records.append({"check": key, "state": "not_run", "details": {"reason": "owned fixture DSN missing"}})
    records.append({"check": "installed_environment_size", "state": "verified", "details": {
        "bytes": sum(p.stat().st_size for p in Path(sys.prefix).rglob("*") if p.is_file()),
        "production_bundle_proof": False,
        "includes_development_dependencies": any(d.metadata["Name"] == "pytest"
                                                 for d in importlib.metadata.distributions())}})
    sources = [Path(__file__).resolve(), root / "services/api/pyproject.toml", root / "services/api/uv.lock",
               root / "services/worker/pyproject.toml", root / "services/worker/uv.lock"]
    for name in ("pdf_parser", "pdf_parser_child", "checkpoints"):
        # Importing the child has no side effects; its main only runs as __main__.
        sources.append(Path(execution_module(name).__file__))
    records.append({"check": "source_manifest", "state": "verified", "details": {
        "base_commit": source, "working_files_sha256": {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sources}, "base_commit_alone_is_not_working_diff_proof": True}})
    if sys.platform != "win32":
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF)
        children = resource.getrusage(resource.RUSAGE_CHILDREN)
        records.append({"check": "process_usage", "state": "verified", "details": {
            "parent_peak_rss_bytes": usage.ru_maxrss * 1024,
            "child_peak_rss_bytes": children.ru_maxrss * 1024,
            "parent_cpu_seconds": usage.ru_utime + usage.ru_stime,
            "child_cpu_seconds": children.ru_utime + children.ru_stime,
            "native_linux_caps": True}})
    else:
        records.append({"check": "process_usage", "state": "not_run", "details": {
            "reason": "Linux native memory/CPU caps require the container probe"}})
    for key in HOSTED_REQUIRED_CHECKS:
        records.append({"check": key, "state": "not_run", "details": {
            "reason": "protected disposable preview and account-specific budget authorization required"}})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = probe_runtime(args.output)
    except ValueError as exc:
        parser.error(str(exc))  # no DSN/credential in diagnostics
    print(json.dumps({"environment": report.environment, "local_feasible": report.local_feasible,
                      "hosted_feasible": report.hosted_feasible, "counts": report.to_dict()["counts"]}))
    return 0 if report.local_feasible else 1


if __name__ == "__main__":
    raise SystemExit(main())
