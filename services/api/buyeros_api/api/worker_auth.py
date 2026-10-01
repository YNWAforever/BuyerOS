"""Request-bound machine authentication; never grants a customer role."""
import hashlib
import hmac
import re
import uuid
from dataclasses import dataclass
from datetime import datetime

from buyeros_api.settings import get_settings
from .errors import ApiError

INTERNAL_PATHS = frozenset(f"/v1/internal/worker/{name}" for name in
                           ("claim", "step", "status", "publication", "maintenance"))
MAX_BODY_BYTES = 8192


@dataclass(frozen=True)
class MachinePrincipal:
    key_id: str
    nonce: uuid.UUID


def verify_worker_request(method: str, path: str, raw_body: bytes, headers,
                          now: datetime) -> MachinePrincipal:
    if len(raw_body) > MAX_BODY_BYTES:
        raise ApiError(413, "INVALID_REQUEST", "worker request too large")
    denied = ApiError(401, "UNAUTHORIZED", "worker authentication required")
    if method != "POST" or path not in INTERNAL_PATHS:
        raise denied
    settings = get_settings()
    key_id = headers.get("x-buyeros-worker-key-id", "")
    if key_id and key_id == settings.worker_current_key_id:
        secret = settings.worker_current_secret
    elif (key_id and key_id == settings.worker_previous_key_id
          and key_id != settings.worker_current_key_id):
        secret = settings.worker_previous_secret
    else:
        raise denied
    if secret is None or len(secret.get_secret_value().encode()) < 32:
        raise denied
    timestamp = headers.get("x-buyeros-worker-timestamp", "")
    nonce = headers.get("x-buyeros-worker-nonce", "")
    signature = headers.get("x-buyeros-worker-signature", "")
    if (not re.fullmatch(r"[0-9]{1,12}", timestamp)
            or not re.fullmatch(r"[0-9a-f]{64}", signature)
            or abs(now.timestamp() - int(timestamp)) > 60):
        raise denied
    try:
        parsed_nonce = uuid.UUID(nonce)
    except (TypeError, ValueError, AttributeError):
        raise denied from None
    if str(parsed_nonce) != nonce:
        raise denied
    message = f"POST\n{path}\n{timestamp}\n{nonce}\n{hashlib.sha256(raw_body).hexdigest()}".encode()
    expected = hmac.new(secret.get_secret_value().encode(), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise denied
    return MachinePrincipal(key_id, parsed_nonce)
