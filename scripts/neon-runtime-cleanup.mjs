/** Owned fixture cleanup only; never accepts production/shared paths. */
import {readFileSync,lstatSync,realpathSync,readdirSync,existsSync} from 'node:fs';
import {rm,unlink,rmdir} from 'node:fs/promises';
import {resolve,relative,isAbsolute,basename,join} from 'node:path';
import {tmpdir} from 'node:os';
const transient=new Set(['EPERM','EBUSY','ENOTEMPTY','EMFILE','ENFILE']);
export async function removeOwnedRuntimeRoot(input,owner,{remove=rm,now=Date.now,pause=ms=>new Promise(ok=>setTimeout(ok,ms)),timeoutMs=10000}={}){
 const root=resolve(input),part=relative(resolve(tmpdir()),root);
 function owned(){
  if(!part||part.startsWith('..')||isAbsolute(part)||!/^buyeros-n00-runtime-[a-zA-Z0-9_-]+$/.test(basename(root))||lstatSync(root).isSymbolicLink()||realpathSync(root)!==root)throw new Error('N00_PROBE_ROOT');
  const value=JSON.parse(readFileSync(join(root,'owner.json'),'utf8'));
  if(owner.fixture_only!==true||owner.private_root!==root||owner.pid!==process.pid||!/^[a-f0-9]{12}$/.test(owner.runId??'')||!['portable','vercel'].includes(owner.target)||!['valid','missing','mismatch','expired'].includes(owner.scenario)||Object.keys(value).length!==Object.keys(owner).length||Object.entries(owner).some(([key,v])=>value[key]!==v))throw new Error('N00_PROBE_OWNER');
 }
 owned();if(!Number.isFinite(timeoutMs)||timeoutMs<=0||timeoutMs>10000)throw new Error('N00_PROBE_ROOT_TIMEOUT');
 const names=readdirSync(root);
 if(names.some(name=>!['owner.json','wrangler.json','state','.wrangler'].includes(name)))throw new Error('N00_PROBE_ROOT_ENTRIES');
 function noLinks(path){const stat=lstatSync(path);if(stat.isSymbolicLink())throw new Error('N00_PROBE_ROOT_SYMLINK');if(stat.isDirectory())for(const name of readdirSync(path))noLinks(join(path,name));}
 for(const name of names)noLinks(join(root,name));
 const deadline=now()+timeoutMs,errors=[];
 // Preserve marker during partial removal, and dispose runtime secret first.
 for(const name of ['wrangler.json','state','.wrangler'].filter(name=>names.includes(name))){
  while(true){
   owned();if(now()>=deadline)throw new Error('N00_PROBE_ROOT_TIMEOUT');
   try{await remove(join(root,name),{recursive:true,force:true,maxRetries:0});break;}
   catch(error){if(!transient.has(error.code))throw error;errors.push({entry:name,code:error.code});await pause(200);}
  }
 }
 owned();if(readdirSync(root).some(name=>name!=='owner.json'))throw new Error('N00_PROBE_ROOT_ENTRIES');
 await unlink(join(root,'owner.json'));await rmdir(root);
 return {removed:!existsSync(root),marker_retained_until_children_removed:true,private_configuration_removed_first:true,transient_errors:errors};
}
