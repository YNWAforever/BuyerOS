/** Exact-resource cleanup orchestration against the owned local model only.
 * No provider API paths, credentials, real identity or deletion executor accepted. */
import {cleanupTargets,RealRunJournal} from './neon-real-preflight.mjs';
import {assertFixtureExecutionBoundary} from './neon-execution-boundary.mjs';
function need(value,code){if(!value)throw new Error('N00_EXECUTION_'+code);}
export async function runFixtureCleanup({execution,journal,now=Date.now}){
 assertFixtureExecutionBoundary(execution,journal);need(journal instanceof RealRunJournal&&execution.report().fixture_only===true,'CLEANUP_BOUNDARY');need(execution.report().journal.target.fingerprint===journal.snapshot().target.fingerprint,'BOUND_TARGET');
 async function read(path){const result=await execution.dispatch({channel:'control',method:'GET',path,body:''});need(result.outcome==='accepted'&&result.status===200,'CLEANUP_READBACK');let value;try{value=JSON.parse(result.body);}catch{throw new Error('N00_EXECUTION_CLEANUP_READBACK');}return {value,evidenceRef:result.evidenceRef};}
 const fresh=await read('/fixture/control/target'),actions=cleanupTargets(journal.snapshot(),fresh.value,now()),target=journal.snapshot().target,absent=[],receipts=[fresh.evidenceRef];
 const result=(complete,blocked=null)=>({complete,blocked,absent,receipts,fixture_only:true,external_verified:false});
 for(const action of actions){const path='/fixture/control/'+action.kind+'/'+action.id;
  async function existence(){const readback=await read(path);receipts.push(readback.evidenceRef);const value=readback.value;need(value&&Object.keys(value).sort().join(',')==='authId,exists,id,kind,observedAt,orgId,projectId','CLEANUP_READBACK');need(value.kind===action.kind&&value.id===action.id&&value.projectId===target.projectId&&value.authId===target.authId&&value.orgId===target.orgId&&typeof value.exists==='boolean','CLEANUP_READBACK');const time=Date.parse(value.observedAt);need(Number.isFinite(time)&&new Date(time).toISOString()===value.observedAt&&time>=Date.parse(target.createdAt)&&time<=now()&&now()-time<=300000,'CLEANUP_READBACK');return value.exists;}
  if(!await existence()){absent.push(action.kind);continue;}
  const request={channel:'control',method:'DELETE',path,body:''};if(execution.holds(request))return result(false,'held-delete');
  const deletion=await execution.dispatch(request);receipts.push(deletion.evidenceRef);if(deletion.outcome==='unknown')return result(false,'unknown-delete');if(deletion.outcome!=='accepted'||![200,202,204].includes(deletion.status))return result(false,'rejected-delete');
  if(await existence())return result(false,'absence-not-confirmed');absent.push(action.kind);
 }
 return result(true);
}
