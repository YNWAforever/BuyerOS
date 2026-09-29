"""Provider callback replay detection (BO-020)."""


def event_key(provider: str, account: str, event_id: str) -> str:
    return f"{provider}:{account}:{event_id}"


def is_replay(seen_keys: set[str], key: str, digest: str) -> bool:
    return key in seen_keys


def digest_conflict(seen: dict[str, str], key: str, digest: str) -> bool:
    return key in seen and seen[key] != digest


# No live callback protocol is selected. Production stays unavailable until a
# named vendor's exact raw-body signature contract has been verified.
import hashlib
import hmac
import json
import re
import time
from decimal import Decimal

from ..api.errors import ApiError
from ..providers.base import SELECTED_LIVE_PROVIDERS


def verify_raw_callback(provider: str, raw_bytes: bytes, headers: dict,
                        *, verifier=None, environment: str = "production") -> dict:
    if verifier is None or getattr(verifier, "provider", None) != provider:
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "provider callback protocol is not configured")
    if getattr(verifier, "test_only", False):
        if environment != "test":
            raise ApiError(503, "PROVIDER_UNAVAILABLE", "fixture callback is test-only")
    elif provider not in SELECTED_LIVE_PROVIDERS:
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "provider callback protocol is not configured")
    if len(raw_bytes) > 65536:
        raise ApiError(413, "INVALID_REQUEST", "callback body exceeds limit")
    event = verifier.verify(raw_bytes, {str(k).lower(): str(v) for k, v in headers.items()})
    required = {"account_reference", "operation_reference", "event_id", "state",
                "observed_cost"}
    if not isinstance(event, dict) or set(event) != required:
        raise ApiError(422, "INVALID_REQUEST", "verified callback shape is invalid")
    for field, maximum in (("account_reference", 128), ("operation_reference", 255),
                           ("event_id", 128)):
        value = event[field]
        if not isinstance(value, str) or not value or len(value) > maximum:
            raise ApiError(422, "INVALID_REQUEST", "verified callback identity is invalid")
    if event["state"] not in {"accepted", "pending", "unknown", "succeeded", "not_found", "failed"}:
        raise ApiError(422, "INVALID_REQUEST", "verified callback state is invalid")
    cost = event["observed_cost"]
    if cost is not None:
        try:
            cost = Decimal(cost)
        except (ValueError, TypeError):
            raise ApiError(422, "INVALID_REQUEST", "verified callback cost is invalid") from None
    return {**event, "observed_cost": cost,
            "digest": hashlib.sha256(raw_bytes).hexdigest()}


class FixtureCallbackVerifier:
    """Explicit test-only HMAC protocol; never advertised as a vendor contract."""

    provider = "fixture"
    test_only = True

    def __init__(self, secret: bytes):
        if len(secret) < 32:
            raise ValueError("fixture HMAC secret must be at least 32 bytes")
        self.secret = secret

    def verify(self, raw_bytes: bytes, headers: dict) -> dict:
        stamp = headers.get("x-fixture-timestamp", "")
        signature = headers.get("x-fixture-signature", "")
        if not re.fullmatch(r"[0-9]{10}", stamp) or not re.fullmatch(r"[a-f0-9]{64}", signature):
            raise ApiError(401, "INVALID_SIGNATURE", "callback signature is invalid")
        if abs(time.time() - int(stamp)) > 300:
            raise ApiError(401, "INVALID_SIGNATURE", "callback timestamp is outside replay window")
        expected = hmac.new(self.secret, stamp.encode() + b"." + raw_bytes, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ApiError(401, "INVALID_SIGNATURE", "callback signature is invalid")
        try:
            parsed = json.loads(raw_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(422, "INVALID_REQUEST", "callback body is invalid") from None
        if not isinstance(parsed, dict):
            raise ApiError(422, "INVALID_REQUEST", "callback body is invalid")
        return parsed
