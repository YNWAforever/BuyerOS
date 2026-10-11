export const flush=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
export function fixtureClock(){
 let time=Date.parse('2026-10-03T00:00:00Z'),id=0;const timers=new Map();
 const clock={now:()=>time,setTimeout:(fn,ms)=>{timers.set(++id,{at:time+ms,fn});return id;},clearTimeout:key=>timers.delete(key)};
 async function advance(ms){const target=time+ms;await flush();for(;;){const entries=[...timers].filter(([,v])=>v.at<=target).sort((a,b)=>a[1].at-b[1].at);if(!entries.length)break;const [key,value]=entries[0];timers.delete(key);time=value.at;value.fn();await flush();}time=target;await flush();}
 function latency(ms,value,signal){return new Promise((resolve,reject)=>{const timer=clock.setTimeout(()=>{signal?.removeEventListener('abort',abort);resolve(value);},ms);const abort=()=>{clock.clearTimeout(timer);reject(signal.reason??new DOMException('aborted','AbortError'));};if(signal?.aborted)abort();else signal?.addEventListener('abort',abort,{once:true});});}
 return {clock,advance,latency,timers};
}
