from pathlib import Path
import subprocess,json,hashlib,sys
sys.stdout.reconfigure(encoding='utf-8')
root=Path.cwd()
target=root/'tests/e2e/audit-teardown.ts'
original=target.read_bytes()
assert original.count(b'  cleanupDatabase();')==1
try:
    target.write_bytes(original.replace(b'  cleanupDatabase();',b'  // Deliberately removed only for the local regression mutation proof.'))
    result=subprocess.run(['node','--test','tests/e2e-fixture-cleanup.test.mjs'],capture_output=True,cwd=root)
    (root/'test-results/local-gates/cleanup-mutation-red.log').write_bytes(result.stdout+result.stderr)
    text=(result.stdout+result.stderr).decode('utf-8','replace')
    assert result.returncode!=0 and 'database marker retained: teardown did not run' in text, text[-5000:]
finally:
    target.write_bytes(original)
assert target.read_bytes()==original
(root/'test-results/local-gates/cleanup-mutation-proof.json').write_text(json.dumps({'mutation':'remove audit cleanupDatabase() invocation','expected_failure':'database marker retained: teardown did not run','exit':result.returncode,'restored_sha256':hashlib.sha256(original).hexdigest()},indent=2)+'\n',encoding='utf-8')
print(text[-4000:])
