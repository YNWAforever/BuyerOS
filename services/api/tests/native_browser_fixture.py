"""Generate only fictional decks for compiled browser acceptance."""
import sys
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.pptx_fixtures import pptx_bytes

if sys.argv[1:] == ['reset']:
    import os
    import psycopg
    from tests.conftest import _require_disposable_test_dsn
    dsn=os.environ.get('BUYEROS_TEST_DATABASE_URL')
    if not dsn:
        import json,re
        from tests.conftest import _docker,POSTGRES_IMAGE,DB_NAME,DB_USER,DB_PASSWORD
        marker=Path(__file__).resolve().parents[3]/'test-results/e2e-db-container.txt'
        name=marker.read_text().strip()
        if not re.fullmatch(r'buyeros-test-[a-f0-9]{8}',name):raise RuntimeError('not an owned fixture container')
        result=_docker('inspect',name)
        if result.returncode:raise RuntimeError('fixture inspection failed')
        info=json.loads(result.stdout)[0]
        if info['Name']!='/'+name or info['Config']['Image']!=POSTGRES_IMAGE or f'POSTGRES_DB={DB_NAME}' not in info['Config']['Env']:
            raise RuntimeError('not the declared fictional database')
        port=_docker('port',name,'5432')
        if port.returncode:raise RuntimeError('fixture port inspection failed')
        host,number=port.stdout.strip().splitlines()[0].rsplit(':',1)
        if host!='127.0.0.1' or not number.isdecimal():raise RuntimeError('fixture must use loopback')
        dsn=f'postgresql://{DB_USER}:{DB_PASSWORD}@{host}:{number}/{DB_NAME}'
    _require_disposable_test_dsn(dsn)
    with psycopg.connect(dsn) as db:
        if db.execute("SELECT issuer,subject FROM users WHERE id='e0000000-0000-4000-8000-000000000002'").fetchone()!=('urn:buyeros:e2e','tester'):
            raise RuntimeError('reset requires the known fictional identity')
        workspace='e0000000-0000-4000-8000-000000000001'
        db.execute('DELETE FROM api_rate_windows WHERE workspace_id=%s',(workspace,))
        db.execute("UPDATE workspace_preferences SET locale='en' WHERE workspace_id=%s",(workspace,))
    print('fictional native initial counters isolated')
    raise SystemExit(0)

root = Path(sys.argv[1]).resolve()
expected = Path(__file__).resolve().parents[3] / 'test-results' / 'native-attachments'
if root != expected.resolve():
    raise RuntimeError('fixture output must stay in its owned test-results directory')
root.mkdir(parents=True, exist_ok=True)
(root / 'native-large.pptx').write_bytes(pptx_bytes(('Product: Native fixture rice', 'Literal <markup> 中文 source'),
    extra={'ppt/media/image.bin': b'x' * (4*1024*1024 + 1000)}, compression=zipfile.ZIP_STORED))
(root / 'native-image.pptx').write_bytes(pptx_bytes(('', '')))
print('fictional native fixtures generated')
