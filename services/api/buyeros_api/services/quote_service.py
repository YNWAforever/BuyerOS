"""Immutable quote snapshot and eligibility (BO-017)."""

import hashlib
import json


def quote_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def eligible(gates: dict) -> tuple[bool, list[str]]:
    """Server-side eligibility; a quote holds no money and dispatches nothing."""
    reasons: list[str] = []
    if not gates.get("accepted"):
        reasons.append("buyer not accepted")
    if gates.get("policy") != "permitted":
        reasons.append(f"policy is {gates.get('policy')}")
    if gates.get("suppressed"):
        reasons.append("suppressed")
    if not gates.get("role_supported", True):
        reasons.append("unsupported role/contact type")
    return (not reasons), reasons
