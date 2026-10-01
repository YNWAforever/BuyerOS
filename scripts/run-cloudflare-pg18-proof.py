"""Owned local PG18 compatibility only. Never supply a shared/remote DSN."""
import os
import sys
from pathlib import Path
if os.environ.get('BUYEROS_TEST_DATABASE_URL'):
    raise SystemExit('unset inherited DB; owned local cluster only')
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'services/api'))
os.chdir(root/'services/api')
os.environ['BUYEROS_STRICT_INTEGRATION']='1'
import tests.conftest as fixtures
assert fixtures.POSTGRES_IMAGE=='postgres:16'
fixtures.POSTGRES_IMAGE='postgres:18'
print('Owned PG18 compatibility: fresh loopback postgres:18; inherited DB rejected; no cloud credentials; fixtures clean their own containers')
import pytest
raise SystemExit(pytest.main(['tests/test_checkpoint_schema_privileges_db.py','tests/test_cloudflare_migration_db.py','tests/test_cloudflare_bridge_db.py','tests/test_cloudflare_runtime_control_db.py','tests/test_cloudflare_recovery_db.py','tests/test_cloudflare_platform_db.py','-q','--junitxml=../../artifacts/cloudflare/CF08-pg18.xml']))
