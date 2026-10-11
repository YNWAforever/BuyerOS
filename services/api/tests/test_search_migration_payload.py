"""Reviewable SQL payloads; offline rollback conservatively retains all rows."""
import os,subprocess,sys
from pathlib import Path
import pytest

@pytest.mark.parametrize('mode,revisions',[('upgrade','0039_c61_user_identities:0040_c61_search_receipts'),('downgrade','0040_c61_search_receipts:0039_c61_user_identities')])
def test_search_offline_payload_is_reviewable_and_retains_receipts(mode,revisions):
    env=os.environ.copy()
    for key in ['DATABASE_URL','BUYEROS_DATABASE_URL','BUYEROS_TEST_DATABASE_URL','BUYEROS_WORKER_DATABASE_URL']:env.pop(key,None)
    result=subprocess.run([sys.executable,'-m','alembic',mode,revisions,'--sql'],cwd=Path(__file__).resolve().parents[1],env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert 'search_receipts' in result.stdout and 'buyeros_search_receipts_writable' in result.stdout
    if mode=='downgrade':
        assert 'DROP TABLE' not in result.stdout and 'TRUNCATE' not in result.stdout and 'DELETE FROM search_receipts' not in result.stdout
        assert 'SELECT false' in result.stdout
