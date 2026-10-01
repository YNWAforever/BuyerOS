"""Temporary isolated-preview entrypoint; never imported by the release API.

The preparer copies this module beside a frozen, non-secret target manifest.
No schema/role creation, staff identities, providers, delivery or live jobs.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

PROBE_PATH = "/v1/internal/runtime-probe"
DURATION_SECONDS = 61
MAX_BODY_BYTES = 256
MAX_OUTPUT_BYTES = 8192
PRODUCTION_VERCEL = "prj_qLOzTdqNiKvoS5rBjy5zZ2GeZgMw"
PRODUCTION_NEON = "nameless-bar-15324691"
TARGET_KEYS = frozenset(("vercel_project_id", "vercel_project_name", "neon_project_id", "neon_project_name",
                         "neon_branch_id", "neon_host", "database", "worker_role", "api_role", "source_sha",
                         "session_started_at", "expires_at"))


class NativeProbeFailure(RuntimeError):
    """Closed error-class metadata only; no child traceback or exception message."""
    def __init__(self, error_type):
        allowed = {"ModuleNotFoundError", "ImportError", "FileNotFoundError", "PermissionError", "OSError",
                   "AssertionError", "OperationalError", "UndefinedTable", "InsufficientPrivilege",
                   "ValueError", "RuntimeError", "TypeError", "KeyError", "TimeoutExpired", "CalledProcessError"}
        self.native_error_type = error_type if isinstance(error_type, str) and error_type in allowed else "NativeProbeFailed"
        super().__init__("native preview probe failed")


def validate_target(target, now):
    """Validate exact resource identities supplied from operator readback."""
    try:
        start = datetime.fromisoformat(target["session_started_at"])
        expiry = datetime.fromisoformat(target["expires_at"])
        valid = (
            set(target) == TARGET_KEYS
            and target["vercel_project_name"] == "buyeros-cf-preview"
            and target["neon_project_name"] == "BuyerOS-CF-preview-20261001"
            and re.fullmatch(r"prj_[A-Za-z0-9_]+", target["vercel_project_id"])
            and target["vercel_project_id"] != PRODUCTION_VERCEL
            and re.fullmatch(r"[a-z][a-z0-9-]+-[0-9]+", target["neon_project_id"])
            and target["neon_project_id"] != PRODUCTION_NEON
            and re.fullmatch(r"br-[a-zA-Z0-9-]+", target["neon_branch_id"])
            and re.fullmatch(r"ep-[a-z0-9-]+\.(?:c-[0-9]+\.)?ap-southeast-1\.aws\.neon\.tech", target["neon_host"])
            and target["database"] == "buyeros_cf_preview"
            and target["worker_role"] == "buyeros_cf_preview_worker"
            and target["api_role"] == "buyeros_cf_preview_api"
            and re.fullmatch(r"[0-9a-f]{40}", target["source_sha"])
            and start.tzinfo is not None and expiry.tzinfo is not None
            and start <= now < expiry and 0 < (expiry - start).total_seconds() <= 7200
        )
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise ValueError("isolated preview target or session window invalid")


def validate_dsn(dsn, target, role):
    """No query override, owner login, shared DB or credentials in diagnostics."""
    try:
        parsed = urlsplit(dsn)
        query = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
        valid = (parsed.scheme == "postgresql" and parsed.hostname == target["neon_host"]
                 and parsed.port in {None, 5432} and unquote(parsed.username or "") == role
                 and bool(parsed.password) and parsed.path == "/" + target["database"]
                 and not parsed.fragment and len({key for key, _ in query}) == len(query)
                 and dict(query).get("sslmode") == "require"
                 and all((key, value) in {("sslmode", "require"), ("channel_binding", "require")}
                         for key, value in query))
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise ValueError("pinned TLS preview database and restricted role required")


def require_preview(target, env, now):
    validate_target(target, now)
    if (env.get("BUYEROS_PREVIEW_PROBE_ENABLED") != "true" or env.get("VERCEL_ENV") != "preview"
            or env.get("VERCEL_PROJECT_ID") != target["vercel_project_id"]
            or env.get("BUYEROS_PREVIEW_PROBE_SOURCE_SHA") != target["source_sha"]
            or not re.fullmatch(r"cf-preview-[A-Za-z0-9_-]{1,48}", env.get("BUYEROS_PREVIEW_PROBE_KEY_ID", ""))
            or not 32 <= len(env.get("BUYEROS_PREVIEW_PROBE_SECRET", "").encode()) <= 4096
            or any(env.get(key, "false").lower() not in {"false", "0"} for key in (
                "BUYEROS_PAID_ADMISSION_ENABLED", "BUYEROS_R2_ENABLED", "BUYEROS_CLOUDFLARE_EXECUTION_ENABLED",
                "BUYEROS_CELERY_EXECUTION_ENABLED"))
            or any(env.get(key) for key in ("BUYEROS_DATABASE_MIGRATION_URL", "BUYEROS_RUNTIME_ADMIN_DATABASE_URL"))):
        raise ValueError("preview diagnostic disabled or unsafe runtime configuration")
    for key, role in (("BUYEROS_DATABASE_URL", target["api_role"]),
                      ("BUYEROS_EXECUTION_DATABASE_URL", target["worker_role"]),
                      ("BUYEROS_CHECKPOINT_DATABASE_URL", target["worker_role"])):
        validate_dsn(env.get(key, ""), target, role)
    return env["BUYEROS_CHECKPOINT_DATABASE_URL"]


def verify_probe_request(body, headers, env, now):
    from buyeros_api.api.errors import ApiError
    from buyeros_api.api.worker_auth import MachinePrincipal
    denied = ApiError(401, "UNAUTHORIZED", "preview machine authentication required")
    stamp = headers.get("x-buyeros-worker-timestamp", "")
    nonce = headers.get("x-buyeros-worker-nonce", "")
    signature = headers.get("x-buyeros-worker-signature", "")
    if (headers.get("x-buyeros-worker-key-id") != env.get("BUYEROS_PREVIEW_PROBE_KEY_ID")
            or not re.fullmatch(r"[0-9]{1,12}", stamp)
            or not re.fullmatch(r"[0-9a-f]{64}", signature)
            or abs(now.timestamp() - int(stamp)) > 60):
        raise denied
    try:
        parsed_nonce = uuid.UUID(nonce)
    except (TypeError, ValueError, AttributeError):
        raise denied from None
    message = f"POST\n{PROBE_PATH}\n{stamp}\n{nonce}\n{hashlib.sha256(body).hexdigest()}".encode()
    expected = hmac.new(env["BUYEROS_PREVIEW_PROBE_SECRET"].encode(), message, hashlib.sha256).hexdigest()
    if str(parsed_nonce) != nonce or not hmac.compare_digest(signature, expected):
        raise denied
    return MachinePrincipal(env["BUYEROS_PREVIEW_PROBE_KEY_ID"], parsed_nonce)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def native_checks(dsn):
    """Only called in a separate child so the PDF probe cannot patch an API process."""
    import importlib
    import importlib.metadata
    from tools.probe_worker_runtime import PACKAGES, _pdf_probe, _checkpoint_probe, sample_pdf
    records = []
    modules = ("psycopg", "sqlalchemy", "pypdf", "langgraph", "langgraph.checkpoint.postgres")
    start = time.perf_counter()
    for name in modules:
        importlib.import_module(name)
    cold = time.perf_counter() - start
    start = time.perf_counter()
    for name in modules:
        importlib.import_module(name)
    records.append({"check": "native_imports", "state": "verified", "details": {
        "versions": {name: importlib.metadata.version(name) for name in PACKAGES},
        "cold_import_seconds": cold, "warm_import_seconds": time.perf_counter() - start,
        "python": sys.version.split()[0], "platform": sys.platform,
        "development_dependencies_present": any(d.metadata["Name"] == "pytest"
                                                 for d in importlib.metadata.distributions())}})
    _pdf_probe(records)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_checkpoint_probe(dsn, records))
    # Execute the actual production child, then observe the limits it installed.
    if sys.platform != "linux":
        records.append({"check": "linux_caps", "state": "not_run", "details": {"platform": sys.platform}})
    else:
        import resource
        command = ("from buyeros_api.execution.pdf_parser_child import main; import resource,json; "
                   "assert main()==0; print(); print(json.dumps([resource.getrlimit(x) for x in "
                   "(resource.RLIMIT_AS,resource.RLIMIT_CPU,resource.RLIMIT_FSIZE)]))")
        process = subprocess.run([sys.executable, "-B", "-c", command], input=sample_pdf(),
                                 capture_output=True, check=True, timeout=8,
                                 env={"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
        limits = json.loads(process.stdout.splitlines()[-1])
        assert limits == [[536870912] * 2, [6] * 2, [1048576] * 2]
        parent, child = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
        records.append({"check": "linux_caps", "state": "verified", "details": {
            "limits": limits, "parent_peak_rss_bytes": parent.ru_maxrss * 1024,
            "child_peak_rss_bytes": child.ru_maxrss * 1024,
            "parent_cpu_seconds": parent.ru_utime + parent.ru_stime,
            "child_cpu_seconds": child.ru_utime + child.ru_stime}})
    return {"records": records, "hosted_feasible": False,
            "hosted_feasible_reason": "deployment protection, bundle and two-hop duration evidence collected separately"}


def run_native_probe(dsn, service_root, target):
    """DSN on stdin only; no inherited credentials, console traceback or shell."""
    validate_dsn(dsn, target, target["worker_role"])
    env = {"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    if sys.platform == "win32":
        env["SystemRoot"] = os.environ.get("SystemRoot", r"C:\Windows")
    with tempfile.TemporaryFile() as output:
        process = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--native-child"],
                                 input=json.dumps({"dsn": dsn, "target": target}).encode(), stdout=output,
                                 stderr=subprocess.DEVNULL, timeout=45, cwd=service_root, env=env,
                                 creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        output.seek(0)
        raw = output.read(MAX_OUTPUT_BYTES + 1)
    if len(raw) > MAX_OUTPUT_BYTES:
        raise ValueError("preview diagnostic output exceeded its bound")
    result = json.loads(raw)
    if process.returncode:
        raise NativeProbeFailure(result.get("error_type"))
    return result


def create_preview_app(target):
    from fastapi import Request
    from fastapi.responses import JSONResponse
    from buyeros_api.api.app import create_app
    from buyeros_api.api.errors import ApiError
    app = create_app()

    async def diagnostic(request: Request):
        env, now = dict(os.environ), datetime.now(timezone.utc)
        try:
            dsn = require_preview(target, env, now)
        except ValueError:
            return JSONResponse({"code": "NOT_FOUND"}, status_code=404, headers={"Cache-Control": "private, no-store"})
        if request.scope.get("query_string") or request.scope.get("raw_path", b"") != PROBE_PATH.encode():
            raise ApiError(401, "UNAUTHORIZED", "exact preview path required")
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > MAX_BODY_BYTES:
                raise ApiError(413, "INVALID_REQUEST", "preview request too large")
        principal = verify_probe_request(bytes(raw), request.headers, env, now)
        try:
            body = json.loads(raw, object_pairs_hook=_unique_object)
            if body not in ({"operation": "native"}, {"operation": "duration"}):
                raise ValueError("fixed operation required")
        except (TypeError, ValueError):
            raise ApiError(422, "INVALID_REQUEST", "fixed preview operation required") from None
        from buyeros_api.services.worker_execution import consume_machine_nonce, create_execution_engine
        engine = create_execution_engine()
        try:
            await consume_machine_nonce(engine, principal, now)
        finally:
            await engine.dispose()
        start = time.perf_counter()
        try:
            if body["operation"] == "duration":
                await asyncio.sleep(DURATION_SECONDS)
                result = {"slept_seconds": DURATION_SECONDS, "hosted_feasible": False}
            else:
                result = await asyncio.to_thread(run_native_probe, dsn, Path(__file__).resolve().parents[2], target)
        except Exception as exc:
            failure = {"code": "PROBE_FAILED", "error_type": type(exc).__name__}
            if isinstance(exc, NativeProbeFailure):
                failure["native_error_type"] = exc.native_error_type
            return JSONResponse(failure, status_code=503,
                                headers={"Cache-Control": "private, no-store"})
        return JSONResponse(result | {"source_sha": target["source_sha"], "wall_seconds": time.perf_counter() - start},
                            headers={"Cache-Control": "private, no-store"})

    # Local import + postponed annotations need an actual Request object for FastAPI.
    diagnostic.__annotations__["request"] = Request
    app.add_api_route(PROBE_PATH, diagnostic, methods=["POST"], include_in_schema=False)
    return app


def main_child():
    try:
        # The source-controlled child receives only the bounded parent envelope.
        data = json.loads(sys.stdin.buffer.read(16385))
        manifest = Path(__file__).with_name("preview_target.json")
        if not manifest.is_file() or data["target"] != json.loads(manifest.read_text(encoding="utf-8")):
            raise ValueError("source-bound compiled preview target required")
        validate_target(data["target"], datetime.now(timezone.utc))
        validate_dsn(data["dsn"], data["target"], data["target"]["worker_role"])
        sys.path.insert(0, os.getcwd())
        result = native_checks(data["dsn"])
        status = 0
    except Exception as exc:
        result, status = {"error_type": type(exc).__name__}, 1
    print(json.dumps(result))
    return status


if __name__ == "__main__":
    if sys.argv[1:] != ["--native-child"]:
        raise SystemExit("only the guarded diagnostic invokes this child")
    raise SystemExit(main_child())
