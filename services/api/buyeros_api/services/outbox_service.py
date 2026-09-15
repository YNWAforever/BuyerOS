"""Deterministic outbox intent ids (BO-011)."""

import hashlib
import json


def build_intent(event_type: str, payload: dict, logical_index: int) -> str:
    raw = event_type + "|" + json.dumps(payload, sort_keys=True, separators=(",", ":")) + "|" + str(logical_index)
    return "job:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
