from pathlib import Path
import subprocess,json,hashlib
proof=json.loads(Path('test-results/local-gates/tested-test-sha256.json').read_text())
blob=subprocess.check_output(['git','show','d7ab5b6323402adf139d9b94e4e499f1631006b4:tests/e2e-fixture-cleanup.test.mjs'])
assert hashlib.sha256(blob.replace(b'\r\n',b'\n')).hexdigest()==proof['lf_sha256']
Path('test-results/local-gates/tested-source-proof.json').write_text(json.dumps({'reviewed_source_sha':'d7ab5b6323402adf139d9b94e4e499f1631006b4','test_path':proof['path'],'tested_lf_sha256':proof['lf_sha256'],'matches_git_blob':True,'application_source_unchanged_from':'25694d3b938e704e883f9915cf0604bbdbac1daf','deployed_sha':None},indent=2)+'\n',encoding='utf-8')
patch=subprocess.check_output(['git','diff','--binary','cbb67ddbb907b8b989b175588ba73ed205e2c2d8','d7ab5b6323402adf139d9b94e4e499f1631006b4','--','tests/e2e-fixture-cleanup.test.mjs'])
Path('test-results/local-gates/test-rollback.patch').write_bytes(patch)
subprocess.run(['git','apply','--reverse','--check','test-results/local-gates/test-rollback.patch'],check=True)
print('tested source hash and reverse patch applicability passed')
