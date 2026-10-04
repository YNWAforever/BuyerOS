from pathlib import Path
p=Path('test-results/local-gates/collect-integrity.py')
s=p.read_text(encoding='utf-8').replace("artifact=Path('.vercel/output')","artifact=root/'.vercel/output'")
p.write_text(s,encoding='utf-8')
