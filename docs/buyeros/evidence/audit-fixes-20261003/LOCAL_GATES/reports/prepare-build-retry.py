from pathlib import Path
p=Path('test-results/local-gates/build-linux.mjs')
s=p.read_text(encoding='utf-8')
s=s.replace(" run('docker',['cp',`${name}:/src/.vercel`,root]);", " run('docker',['exec',name,'tar','-chzf','/tmp/vercel-output.tar.gz','.vercel'],{timeout:180_000});\n run('docker',['cp',`${name}:/tmp/vercel-output.tar.gz`,join(area,'vercel-output.tar.gz')],{timeout:180_000});\n run('C:/Windows/System32/tar.exe',['-xzf',join(area,'vercel-output.tar.gz'),'-C',root],{timeout:180_000});")
p.write_text(s,encoding='utf-8')
first=Path('test-results/local-gates/first-build')
first.mkdir(exist_ok=True)
for pattern in ['build-*','vercel-*']:
 for item in Path('test-results/local-gates').glob(pattern):
  if item.is_file() and item.name!='build-linux.mjs':
   (first/item.name).write_bytes(item.read_bytes())
