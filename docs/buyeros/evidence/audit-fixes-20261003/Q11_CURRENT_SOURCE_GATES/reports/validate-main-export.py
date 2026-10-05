from pathlib import Path,PurePosixPath
import tarfile,json,hashlib,shutil
root=Path.cwd().resolve();area=root/'test-results/q11-current-source-gates';archive=area/'vercel-output.tar.gz'
assert not (root/'.vercel/output').exists(),'refuse existing output'
assert (root/'.vercel/output').resolve().is_relative_to(root),'outside workspace'
# Preserve failed Windows staging rather than recursively deleting it.
src=area/'export-staging';dst=area/'export-attempt-1';assert src.resolve().is_relative_to(root) and dst.resolve().is_relative_to(root) and not dst.exists();src.rename(dst)
shutil.copy2(area/'export-main.py',area/'export-main-first.py')
(area/'export-attempt-1.json').write_text(json.dumps({'exit':1,'phase':'Windows staging','cause':'Win32 long path exceeded legacy path limit in deeply nested package.json; no main output written','staging_retained':'export-attempt-1','correction':'Validate archive and internal hard links before using native Windows tar directly into the shorter guarded main path; verify every emitted file hash'},indent=2)+'\n',encoding='utf-8')
def safe(name):
 p=PurePosixPath(name);assert not p.is_absolute() and '..' not in p.parts and '\\' not in name and ':' not in name and '\0' not in name
 assert str(p)=='.vercel' or str(p)=='.vercel/output' or str(p).startswith('.vercel/output/')
with tarfile.open(archive,'r:gz') as tf:
 members=tf.getmembers();lookup={m.name:m for m in members};assert len(lookup)==len(members) and len(members)<=6000
 def regular(m):
  seen=set()
  while m.islnk():
   assert m.name not in seen;seen.add(m.name);safe(m.linkname);assert m.linkname in lookup;m=lookup[m.linkname]
  assert m.isfile();return m
 for m in members:
  safe(m.name);assert m.isdir() or m.isfile() or m.islnk()
  if not m.isdir():regular(m)
 digest={}
 for m in members:
  if m.isfile():
   with tf.extractfile(m) as f:digest[m.name]=hashlib.sha256(f.read()).hexdigest()
 files=[{'path':m.name,'bytes':regular(m).size,'sha256':digest[regular(m).name]} for m in members if not m.isdir()]
 assert sum(x['bytes'] for x in files)<=250*1024*1024
 record={'archive':{'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()},'files':files,'safe_export':{'members':len(members),'hardlinks_validated_internal_regular':sum(m.islnk() for m in members),'symlinks':0,'target_absent':True,'target_inside_workspace':True}}
 (area/'build-output-expected.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');print(json.dumps(record['safe_export']))
