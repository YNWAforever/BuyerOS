"""Idempotent quote confirmation primitives (BO-018)."""

import hashlib
import json
from dataclasses import dataclass


class IdempotencyConflict(Exception):
    pass


class QuoteChanged(Exception):
    pass


class QuoteExpired(Exception):
    pass


@dataclass
class ConfirmResult:
    job_id: str
    reservation_id: str
    idempotent_replay: bool = False


def request_fingerprint(body: dict) -> str:
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def same_request(key_a: str, hash_a: str, key_b: str, hash_b: str, raise_on_conflict: bool = False) -> bool:
    if key_a != key_b:
        return False
    if hash_a == hash_b:
        return True
    if raise_on_conflict:
        raise IdempotencyConflict("same key with a different body")
    return False
