"""Separate, non-promotable encrypted subprocess failure evidence."""
import base64
import json
import os
import re
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SCHEMA='buyeros.runtime-failure.encrypted.v1'
MAX_STDERR_BYTES=65536


def bounded_stderr(value):
    # Never stringify an exception or arbitrary object. Preserve captured bytes.
    if type(value) is str:
        return value[:MAX_STDERR_BYTES].encode('utf-8',errors='replace')[:MAX_STDERR_BYTES]
    if type(value) is bytes:return value[:MAX_STDERR_BYTES]
    return b''


def encrypt_failure(failure,key_hex,source_sha,run_id):
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
