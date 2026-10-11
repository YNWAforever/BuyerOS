"""Metadata-only Linux built fixture ownership. No SQL, provider IO or cleanup."""
import hashlib,json,os,re
from pathlib import Path

def validate_owned_built_process(root,rows,listener_inodes,source_sha):
 root=Path(root).resolve();entry=root/'.output/server/index.mjs'
 if not re.fullmatch(r'[0-9a-f]{40}',source_sha):raise RuntimeError('owned built source SHA missing')
 owners=[]
 for row in rows:
  argv=row.get('argv',[]);env=row.get('env',{})
  if len(argv)!=2 or Path(argv[0]).name!='node':continue
  if Path(row.get('cwd','')).resolve()!=root:continue
  if (root/argv[1]).resolve()!=entry.resolve():continue
  if env.get('HOST')!='127.0.0.1' or env.get('PORT')!='5173' or env.get('C61_SOURCE_SHA')!=source_sha:continue
  if not set(row.get('socket_inodes',())).intersection(listener_inodes):continue
  if type(row.get('pid')) is not int or row['pid']<=0:continue
  owners.append({'pid':row['pid'],'source_sha':source_sha,'host':'127.0.0.1','port':5173,'entrypoint':'.output/server/index.mjs'})
 if len(owners)!=1:raise RuntimeError('exactly one owned built loopback process required')
 return owners[0]

def hash_built_output(output):
 output=Path(output).resolve();rows=[]
 def walk(directory):
  for path in sorted(directory.iterdir(),key=lambda p:p.name):
   name=path.relative_to(output).as_posix()
   if path.is_symlink():rows.append([name,'symlink',os.readlink(path)])
   elif path.is_dir():walk(path)
   elif path.is_file():rows.append([name,path.stat().st_size,hashlib.sha256(path.read_bytes()).hexdigest()])
 if output.is_dir():walk(output)
 entry=next((row for row in rows if row[0]=='server/index.mjs' and row[1]!='symlink'),None)
 if not entry:raise RuntimeError('missing regular built entrypoint')
 return {'files':len(rows),'manifest_sha256':hashlib.sha256(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),'entrypoint_sha256':entry[2]}

def read_owned_linux_built_artifact(root,source_sha,proc=Path('/proc')):
 proc=Path(proc);inodes=set()
 # HOST=127.0.0.1 is required; a public/all-interface listener cannot satisfy it.
 for line in (proc/'net/tcp').read_text().splitlines()[1:]:
  fields=line.split()
  if len(fields)>9 and fields[1]=='0100007F:1435' and fields[3]=='0A':inodes.add(fields[9])
 rows=[]
 for directory in proc.iterdir():
  if not directory.name.isdigit():continue
  try:
   argv=[x.decode('utf-8') for x in (directory/'cmdline').read_bytes().split(b'\0') if x]
   if len(argv)!=2 or Path(argv[0]).name!='node':continue
   cwd=os.readlink(directory/'cwd');env={}
   for item in (directory/'environ').read_bytes().split(b'\0'):
    key,sep,value=item.partition(b'=')
    if sep and key in (b'HOST',b'PORT',b'C61_SOURCE_SHA'):env[key.decode()]=value.decode()
   sockets=set()
   for fd in (directory/'fd').iterdir():
    try:
     match=re.fullmatch(r'socket:\[(\d+)\]',os.readlink(fd))
     if match:sockets.add(match[1])
    except OSError:continue
   rows.append({'pid':int(directory.name),'cwd':cwd,'argv':argv,'env':env,'socket_inodes':sockets})
  except (OSError,UnicodeError):continue
 owner=validate_owned_built_process(root,rows,inodes,source_sha)
 return {**hash_built_output(Path(root)/'.output'),'serving_process':owner,'runtime':'built','mode':'http','platform':'linux-local-owned'}
