"""Separate, non-promotable encrypted subprocess failure evidence."""
import base64
import json
import os
import re
import tempfile
from pathlib import Path

SCHEMA='buyeros.runtime-failure.encrypted.v1'
MAX_STDERR_BYTES=65536

HTTP_PROBE_FAILURES = {
    401: 'http_unauthorized', 403: 'http_forbidden', 404: 'http_not_found',
    502: 'http_unavailable', 503: 'http_unavailable', 504: 'http_unavailable',
}
TRANSIENT_PROBE_FAILURES = frozenset({
    'runtime_dns_failed', 'runtime_connection_failed', 'runtime_timeout', 'http_unavailable',
})
PROBE_FAILURES = TRANSIENT_PROBE_FAILURES | frozenset(HTTP_PROBE_FAILURES.values()) | frozenset({
    'runtime_transport_failed', 'runtime_redirect_refused', 'runtime_response_target_mismatch',
    'runtime_malformed_response', 'http_unexpected_status', 'binding_independent_target_mismatch',
    'binding_source_mismatch', 'binding_deployment_mismatch', 'binding_database_mismatch',
    'binding_schema_head_mismatch', 'configuration_fingerprint_mismatch', 'configuration_activation_mismatch',
})


class RuntimeProbeError(ValueError):
    """A fixed diagnostic category with optional private subprocess evidence."""

    def __init__(self, category, *, http_status=None, exit_code=None, stderr=None):
        if category not in PROBE_FAILURES:
            raise ValueError('unknown runtime probe failure category')
        super().__init__(category)
        self.category = category
        self.http_status = http_status if type(http_status) is int and 100 <= http_status <= 599 else None
        self.exit_code = exit_code if type(exit_code) is int else None
        self.stderr = bounded_stderr(stderr)

    @classmethod
    def for_http_status(cls, status):
        if type(status) is not int or not 100 <= status <= 599:
            return cls('runtime_malformed_response')
        if 300 <= status < 400:
            return cls('runtime_redirect_refused', http_status=status)
        return cls(HTTP_PROBE_FAILURES.get(status, 'http_unexpected_status'), http_status=status)


def bounded_stderr(value):
    # Never stringify an exception or arbitrary object. Preserve captured bytes.
    if type(value) is str:
        return value[:MAX_STDERR_BYTES].encode('utf-8',errors='replace')[:MAX_STDERR_BYTES]
    if type(value) is bytes:return value[:MAX_STDERR_BYTES]
    return b''


def encrypt_failure(failure,key_hex,source_sha,run_id):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if (type(key_hex) is not str or re.fullmatch(r'[0-9a-fA-F]{64}',key_hex) is None
            or type(source_sha) is not str or re.fullmatch(r'[0-9a-f]{40}',source_sha) is None
            or type(run_id) is not str or re.fullmatch(r'[1-9][0-9]{0,19}',run_id) is None):
        raise ValueError('private diagnostic binding unavailable')
    binding={'schema':SCHEMA,'source_sha':source_sha,'run_id':run_id}
    aad=json.dumps(binding,sort_keys=True,separators=(',',':')).encode('ascii')
    payload={'phase':failure['phase'],'category':failure['category'],'exit_code':failure['exit_code'],
             'stderr_base64':base64.b64encode(bounded_stderr(failure['stderr'])).decode('ascii')}
    nonce=os.urandom(12)
    ciphertext=AESGCM(bytes.fromhex(key_hex)).encrypt(nonce,
        json.dumps(payload,sort_keys=True,separators=(',',':')).encode('ascii'),aad)
    return {**binding,'nonce':base64.b64encode(nonce).decode('ascii'),
            'ciphertext':base64.b64encode(ciphertext).decode('ascii')}


def write_private_failure(path,failure,key_hex,source_sha,run_id):
    """Publish fully written ciphertext atomically, without replacing any file."""
    envelope=encrypt_failure(failure,key_hex,source_sha,run_id)
    temporary=None
    try:
        # Temporary files contain only ciphertext, never private plaintext.
        with tempfile.NamedTemporaryFile(mode='wb',dir=path.parent,prefix='.runtime-failure-',delete=False) as handle:
            temporary=Path(handle.name)
            handle.write(json.dumps(envelope,sort_keys=True,separators=(',',':')).encode('ascii')+b'\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary,path)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)
