from pathlib import Path,PurePosixPath
import tarfile,json,hashlib,shutil,os
root=Path.cwd().resolve(); area=root/'test-results/q11-current-source-gates'; archive=area/'vercel-output.tar.gz'
staging=area/'export-staging'; output=root/'.vercel/output'
assert not staging.exists() and not output.exists(),'refuse overwrite'
assert staging.resolve().is_relative_to(root) and output.resolve().is_relative_to(root),'outside workspace'
def safe(name):
    p=PurePosixPath(name)
    assert not p.is_absolute() and '\\' not in name and ':' not in name and '\0' not in name,'invalid member path'
    assert '..' not in p.parts and (str(p)=='.vercel' or str(p)=='.vercel/output' or str(p).startswith('.vercel/output/')),'outside output'
    return p
with tarfile.open(archive,'r:gz') as tf:
    members=tf.getmembers(); assert len(members)<=6000,'too many members'
    lookup={m.name:m for m in members}; assert len(lookup)==len(members),'duplicate path'
    total=0; links=[]
    def regular(m):
        seen=set()
        while m.islnk():
            assert m.name not in seen,'hardlink cycle';seen.add(m.name);safe(m.linkname)
            assert m.linkname in lookup,'missing target';m=lookup[m.linkname]
        assert m.isfile(),'target must be regular'
        return m
    for m in members:
        safe(m.name); assert m.isdir() or m.isfile() or m.islnk(),'special member refused'
        if not m.isdir():
            src=regular(m);total+=src.size
            if m.islnk():links.append({'path':m.name,'target':src.name})
    assert total<=250*1024*1024,'unbounded payload'
    staging.mkdir()
    for m in members:
        target=staging.joinpath(*safe(m.name).parts)
        assert target.resolve().is_relative_to(staging),'escaped staging'
        if m.isdir():target.mkdir(parents=True,exist_ok=True);continue
        target.parent.mkdir(parents=True,exist_ok=True)
        with tf.extractfile(regular(m)) as source,target.open('xb') as dest:shutil.copyfileobj(source,dest)
        os.chmod(target,0o644)
output.parent.mkdir(exist_ok=True)
os.rename(staging/'.vercel/output',output)
outputs=[{'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(output.rglob('*')) if p.is_file()]
assert all(not p.is_symlink() for p in output.rglob('*'))
record={'archive':{'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()},'files':outputs,'safe_export':{'members':len(members),'hardlinks_flattened':len(links),'symlinks':0,'total_bytes':total,'overwrite':False}}
(area/'build-output.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
(area/'safe-hardlinks.json').write_text(json.dumps(links,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'exported_files':len(outputs),**record['safe_export'],'archive':record['archive']}))
