"""Offline measurement primitives. Failed requests stay in every denominator."""
import hashlib
import json
import math
import subprocess
from pathlib import Path

DATABASE_VARIABLES = ("BUYEROS_TEST_DATABASE_URL", "BUYEROS_DATABASE_URL", "DATABASE_URL", "BUYEROS_WORKER_DATABASE_URL")


def proportion(numerator: int, denominator: int) -> dict:
    """Two-sided Wilson 95% interval; zero denominator is unavailable, not zero."""
    if type(numerator) is not int or type(denominator) is not int or not 0 <= numerator <= denominator:
        raise ValueError("invalid proportion counts")
    if denominator == 0:
        return dict(numerator=0, denominator=0, estimate=None, ci95=None)
    p, n, z = numerator / denominator, denominator, 1.959963984540054
    divisor = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / divisor
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / divisor
    return dict(numerator=numerator, denominator=n, estimate=p, ci95=[max(0.0, centre-half), min(1.0, centre+half)])


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    low = math.floor(index)
    return round(ordered[low] + (ordered[math.ceil(index)] - ordered[low]) * (index - low), 3)


def summarize_requests(samples: list[dict]) -> dict:
    if not samples:
        raise ValueError("empty observations cannot pass a benchmark")
    for row in samples:
        for key in ("latency_ms", "sql_ms"):
            value = row[key]
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(f"invalid {key}")
        for key in ("queries", "bytes"):
            if type(row[key]) is not int or row[key] < 0:
                raise ValueError(f"invalid {key}")
        status = row["status"]
        if status is not None and (type(status) is not int or not 100 <= status <= 599):
            raise ValueError("invalid status")
        if type(row["invalid_context"]) is not bool:
            raise ValueError("invalid context flag")
    n = len(samples)
    latency = [r["latency_ms"] for r in samples]
    queries, sizes = [r["queries"] for r in samples], [r["bytes"] for r in samples]
    non_2xx = sum(r["status"] is not None and not 200 <= r["status"] < 300 for r in samples)
    failed = sum(r["status"] is None or not 200 <= r["status"] < 300 or r["invalid_context"] for r in samples)
    return {
        "requests": n,
        "latency_ms": {"p50": _percentile(latency, .5), "p95": _percentile(latency, .95), "p99": _percentile(latency, .99), "max": max(latency), "p99_stable": n >= 100},
        "errors": {"denominator": n, "http_5xx": sum(r["status"] is not None and r["status"] >= 500 for r in samples), "http_non_2xx": non_2xx, "transport": sum(r["status"] is None for r in samples), "invalid_context": sum(r["invalid_context"] for r in samples), "failed_requests": failed, "rate": failed/n},
        "queries": {"total": sum(queries), "min": min(queries), "max": max(queries), "mean": sum(queries)/n},
        "bytes": {"total": sum(sizes), "min": min(sizes), "max": max(sizes)},
        "sql_ms": {"total": sum(r["sql_ms"] for r in samples), "p95": _percentile([r["sql_ms"] for r in samples], .95)},
    }


def provenance(root: Path, paths: list[Path]) -> dict:
    """Dirty state and exact tool bytes accompany the repository commit."""
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip())
    return {"source_sha": sha, "source_dirty": dirty, "tool_hashes": {str(p.relative_to(root)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}


def write_new_report(path: Path, report: dict, protected: tuple[Path, ...] = ()) -> None:
    path = path.resolve()
    if path in [p.resolve() for p in protected]:
        raise ValueError("output aliases an input")
    payload = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as output:
        output.write(payload)
