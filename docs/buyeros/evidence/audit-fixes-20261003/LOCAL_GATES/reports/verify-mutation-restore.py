from pathlib import Path
import json,hashlib,sys
sys.stdout.reconfigure(encoding='utf-8')
proof=json.loads(Path('test-results/local-gates/cleanup-mutation-proof.json').read_text())
assert hashlib.sha256(Path('tests/e2e/audit-teardown.ts').read_bytes()).hexdigest()==proof['restored_sha256']
assert proof['exit']==1
log=Path('test-results/local-gates/cleanup-mutation-red.log').read_text(encoding='utf-8')
assert 'database marker retained: teardown did not run' in log
print(json.dumps(proof,ensure_ascii=True))
p=Path('test-results/local-gates/mutation-proof.py')
s=p.read_text(encoding='utf-8').replace('import subprocess,json,hashlib','import subprocess,json,hashlib,sys\nsys.stdout.reconfigure(encoding=\'utf-8\')')
p.write_text(s,encoding='utf-8')
