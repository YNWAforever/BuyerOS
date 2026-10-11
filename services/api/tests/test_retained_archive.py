"""Source-only review must retain the exact compatible archive without unpublished Git history."""
import hashlib,io,tarfile
from pathlib import Path
import pytest
from tests import retained_archive as m

def pinned():return m.ARCHIVE_PATH.read_bytes()
def use(monkeypatch,tmp_path,body):
 p=tmp_path/'retained.tar';p.write_bytes(body);monkeypatch.setattr(m,'ARCHIVE_PATH',p);return p
def forbid_git(monkeypatch):
 def forbidden(*args,**kwargs):pytest.fail('retained source must be available without unpublished Git objects')
 monkeypatch.setattr(m.subprocess,'check_output',forbidden)
def package(entries):
 b=io.BytesIO()
 with tarfile.open(fileobj=b,mode='w',format=tarfile.PAX_FORMAT,pax_headers={'comment':m.ROLLBACK_SHA}) as tar:
  for name,kind in entries:
   info=tarfile.TarInfo(name)
   if kind=='symlink':info.type=tarfile.SYMTYPE;info.linkname='/outside'
   else:
    info.size=1
    if kind=='pax':info.name='placeholder';info.pax_headers={'path':name}
   tar.addfile(info,io.BytesIO(b'x') if kind!='symlink' else None)
 return b.getvalue()
def accept_hash(monkeypatch,body):monkeypatch.setattr(m,'ARCHIVE_SHA256',hashlib.sha256(body).hexdigest())

def test_retained_archive_matches_original_compatible_source():
 body=m.retained_rollback_archive();assert body==pinned();assert hashlib.sha256(body).hexdigest()==m.ARCHIVE_SHA256
def test_retained_archive_is_available_without_unpublished_Git(monkeypatch):
 expected=pinned();forbid_git(monkeypatch);assert m.retained_rollback_archive()==expected
def test_retained_archive_missing_file_refuses_without_Git_fallback(monkeypatch,tmp_path):
 monkeypatch.setattr(m,'ARCHIVE_PATH',tmp_path/'missing.tar')
 with pytest.raises(FileNotFoundError):m.retained_rollback_archive()
def test_retained_archive_empty_file_refuses(monkeypatch,tmp_path):
 use(monkeypatch,tmp_path,b'')
 with pytest.raises(ValueError,match='digest'):m.retained_rollback_archive()
def test_retained_archive_tampered_bytes_refuse(monkeypatch,tmp_path):
 body=bytearray(pinned());body[-1]^=1;use(monkeypatch,tmp_path,bytes(body))
 with pytest.raises(ValueError,match='digest'):m.retained_rollback_archive()
def test_retained_archive_source_label_cannot_be_rewritten(monkeypatch):
 monkeypatch.setattr(m,'ROLLBACK_SHA','a'*40)
 with pytest.raises(ValueError,match='source'):m.retained_rollback_archive()
def test_retained_archive_malformed_tar_refuses_even_with_matching_metadata(monkeypatch,tmp_path):
 body=b'not an archive';use(monkeypatch,tmp_path,body);accept_hash(monkeypatch,body)
 with pytest.raises(ValueError,match='archive'):m.retained_rollback_archive()
def test_retained_archive_unsafe_or_incomplete_package_refuses(monkeypatch,tmp_path):
 for entries in [[('../escape', 'file')], [('services/api/buyeros_api/api/auth.py', 'symlink')], [('services/api/buyeros_api/settings.py', 'file')], [('services/api/buyeros_api/..\\escape.py', 'pax'), ('services/api/buyeros_api/__init__.py', 'file'), ('services/api/buyeros_api/api/auth.py', 'file'), ('services/api/buyeros_api/settings.py', 'file')]]:
  body=package(entries);use(monkeypatch,tmp_path,body);accept_hash(monkeypatch,body)
  with pytest.raises(ValueError,match='package'):m.retained_rollback_archive()
