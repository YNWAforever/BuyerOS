"""C18 emitted migration/encrypted retained rollback; no deployed DB claim."""
import os,subprocess,sys
from pathlib import Path
import pytest

@pytest.mark.parametrize('mode,revisions',[('upgrade','0041_c61_model_receipts:0042_c61_contact_receipts'),('downgrade','0042_c61_contact_receipts:0041_c61_model_receipts')])
def test_contact_offline_encrypted_payload_retains_acceptance_metadata(mode,revisions):
    root=Path(__file__).resolve().parents[1]
    assert (root/'alembic/versions/0042_c61_contact_receipts.py').is_file(),'C18 encrypted receipt migration missing'
    env=os.environ.copy()
    for key in ['DATABASE_URL','BUYEROS_DATABASE_URL','BUYEROS_TEST_DATABASE_URL','BUYEROS_WORKER_DATABASE_URL']:env.pop(key,None)
    result=subprocess.run([sys.executable,'-m','alembic',mode,revisions,'--sql'],cwd=root,env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert 'contact_receipts' in result.stdout and 'buyeros_contact_receipts_writable' in result.stdout
    if mode=='upgrade':
        assert 'response_ciphertext bytea' in result.stdout and 'FORCE ROW LEVEL SECURITY' in result.stdout
        assert 'GRANT SELECT,INSERT ON public.contact_receipts TO buyeros_api' in result.stdout
        assert 'GRANT SELECT,UPDATE ON public.contact_receipts TO buyeros_worker' in result.stdout
    else:
        assert 'DROP TABLE' not in result.stdout and 'TRUNCATE' not in result.stdout and 'SELECT false' in result.stdout
