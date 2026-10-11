"""Immutable test-only retained compatible source; excluded from production payloads."""
import hashlib,io,subprocess,tarfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[3]
ROLLBACK_SHA='0f2ac905c852403c3a30a966df18272acc723bf1'
ARCHIVE_SHA256='a93cc06c2d3b8e252d4c8d9ffa9841f99661d27cac7f673043418f55308a4cd2'
ARCHIVE_PATH=Path(__file__).with_name("retained_archives")/"0f2ac905-buyeros-api.tar"

def retained_rollback_archive():
    body=ARCHIVE_PATH.read_bytes()
    if hashlib.sha256(body).hexdigest()!=ARCHIVE_SHA256:raise ValueError('retained archive digest mismatch')
    try:
        with tarfile.open(fileobj=io.BytesIO(body)) as tar:
            if tar.pax_headers.get('comment')!=ROLLBACK_SHA:raise ValueError('retained archive source mismatch')
            members=tar.getmembers();names=set()
            for member in members:
                name=member.name.rstrip('/');parts=PurePosixPath(name).parts
                allowed=name.startswith('services/api/buyeros_api/') or name=='services/api/buyeros_api' or member.isdir() and name in {'services','services/api'}
                if not allowed or '..' in parts or '\\' in name or not (member.isdir() or member.isfile()):raise ValueError('retained archive package member refused')
                if member.isfile():names.add(name)
            required={'services/api/buyeros_api/__init__.py','services/api/buyeros_api/api/auth.py','services/api/buyeros_api/settings.py'}
            if not required<=names:raise ValueError('retained archive package is incomplete')
    except tarfile.TarError as error:raise ValueError('retained archive is malformed') from error
    return body
