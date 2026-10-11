"""Offline upgrade/rollback payloads preserve erasure/acceptance metadata."""
import os,subprocess,sys
from pathlib import Path
import pytest

@pytest.mark.parametrize('mode,revisions',[('upgrade','0042_c61_contact_receipts:0043_c61_receipt_retention'),('downgrade','0043_c61_receipt_retention:0042_c61_contact_receipts')])
def test_receipt_privacy_payload_is_reviewable_and_conservative(mode,revisions):
    root=Path(__file__).resolve().parents[1];env=os.environ.copy()
    for key in ['DATABASE_URL','BUYEROS_DATABASE_URL','BUYEROS_TEST_DATABASE_URL','BUYEROS_WORKER_DATABASE_URL']:env.pop(key,None)
    result=subprocess.run([sys.executable,'-m','alembic',mode,revisions,'--sql'],cwd=root,env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr;sql=result.stdout
    assert 'DROP TABLE' not in sql and 'TRUNCATE' not in sql and 'BYPASSRLS' not in sql and 'GRANT UPDATE' not in sql
    if mode=='upgrade':
        assert 'buyeros_erase_provider_receipt' in sql and 'FORCE ROW LEVEL SECURITY' in sql
        assert 'provider_receipt.expired' in sql and 'pg_has_role(session_user' in sql
        assert "r.workspace_id=ws AND r.id=receipt AND r.redacted_at IS NULL" in sql
        assert 'buyeros_receipt_dependency_expired' in sql
    else:
        assert sql.count('SELECT false')==3
        assert 'redacted_at=NULL' not in sql and 'UPDATE public.provider_operations' not in sql
