from pathlib import Path,PurePosixPath
import tarfile,hashlib,json,os
root=Path.cwd();area=root/'test-results/n00-proxy-dispatch-deadline';build=root/'test-results/neon-runtime-flow-final'
proof=json.loads((root/'docs/buyeros/evidence/audit-fixes-20261003/N00_UNKNOWN_WRITE_RECOVERY/captures/0036-proof-BUILD_REUSE.json').read_text(encoding='utf-8-sig'))
result={'fixture_only':True,'new_builds':0,'compiled_base':proof['reuse_compiled_base'],'recorded_source':'c756596406f41884f61a3b64c8549f569e34cfa4','unchanged_overlays':0,'outputs':[]}
inputs=json.loads((build/'build-inputs.json').read_text(encoding='utf-8-sig'))
for p in proof['compiled_overlays_unchanged']:
 entries=[x for x in inputs['files'] if x['path']==p];assert len(entries)==1,p
 raw=(root/p).read_bytes();assert hashlib.sha256(raw).hexdigest() in [entries[0]['sha256'],entries[0].get('stagedSha256')],p
 result['unchanged_overlays']+=1
for item in proof['outputs']:
 target=item['target'];archive=build/(target+'.tar.gz');digest=hashlib.sha256(archive.read_bytes()).hexdigest();assert digest==item['archive_sha256'],target
 files=[]
 with tarfile.open(archive,'r:gz') as tar:
  for member in tar.getmembers():
   if not (member.isfile() or member.islnk()):continue
   name=PurePosixPath(member.name);assert not name.is_absolute() and '..' not in name.parts and ':' not in member.name and '\\' not in member.name
   if member.islnk():
    link=PurePosixPath(member.linkname);assert not link.is_absolute() and '..' not in link.parts and ':' not in member.linkname
   content=tar.extractfile(member).read();full=build/target/Path(*name.parts)
   disk=Path('\\\\?\\'+str(full)).read_bytes() if os.name=='nt' else full.read_bytes();assert disk==content,member.name
   files.append({'path':member.name,'sha256':hashlib.sha256(content).hexdigest()})
 result['outputs'].append({'target':target,'archive_sha256':digest,'files_verified':len(files),'files':files})
(area/'build-reuse.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print({**result,'outputs':[{k:v for k,v in x.items() if k!='files'} for x in result['outputs']]})
