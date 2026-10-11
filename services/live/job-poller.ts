import {LiveCancelled,LiveError} from './client';

type Clock={now:()=>number;setTimeout:(fn:()=>void,ms:number)=>ReturnType<typeof setTimeout>;clearTimeout:(id:ReturnType<typeof setTimeout>)=>void};
export type JobPollerOptions<T extends {status:string}>={
  fetchSummary:(signal:AbortSignal)=>Promise<T>;onValue:(value:T)=>void;onError:(error:unknown)=>void;
  signal:AbortSignal;isVisible:()=>boolean;
  visibilityTarget?:Pick<Document,'addEventListener'|'removeEventListener'>;
  isOnline?:()=>boolean;
  connectivityTarget?:Pick<EventTarget,'addEventListener'|'removeEventListener'>;
  clock?:Clock;
};
const terminal=new Set(['completed','failed','cancelled']);
/** One in-flight request per lifetime; pause hidden/offline. No result-page reads. */
export function startJobPoller<T extends {status:string}>({fetchSummary,onValue,onError,signal,isVisible,
  visibilityTarget=typeof document==='undefined'?undefined:document,
  isOnline=()=>typeof navigator==='undefined'||navigator.onLine!==false,
  connectivityTarget=typeof window==='undefined'?undefined:window,
  clock={now:Date.now,setTimeout:(fn,ms)=>setTimeout(fn,ms),clearTimeout:id=>clearTimeout(id)},
}:JobPollerOptions<T>):()=>void{
  let stopped=false,done=false,inFlight=false,failures=0,deadline=0;
  let timer:ReturnType<typeof setTimeout>|undefined,request:AbortController|undefined;
  const clear=()=>{if(timer!==undefined)clock.clearTimeout(timer);timer=undefined;};
  const canRead=()=>isVisible()&&isOnline();
  const stop=()=>{stopped=true;clear();request?.abort();signal.removeEventListener('abort',stop);visibilityTarget?.removeEventListener('visibilitychange',availability);connectivityTarget?.removeEventListener('offline',availability);connectivityTarget?.removeEventListener('online',availability);};
  function schedule(delay:number){clear();if(stopped||done||signal.aborted||!canRead())return;
    timer=clock.setTimeout(()=>{timer=undefined;void poll();},Math.max(0,delay));}
  function availability(){clear();if(stopped||done||signal.aborted)return;if(!canRead()){request?.abort();return;}if(!inFlight){if(deadline<=clock.now())void poll();else schedule(deadline-clock.now());}}
  async function poll(){
    if(stopped||done||inFlight||signal.aborted||!canRead())return;
    inFlight=true;const own=new AbortController();request=own;let timedOut=false,delay=2000;
    const timeout=clock.setTimeout(()=>{timedOut=true;own.abort(new DOMException('Job summary timed out','TimeoutError'));},10_000);
    try{
      const value=await fetchSummary(own.signal);
      if(stopped||signal.aborted)return;
      if(own.signal.aborted||!canRead()){delay=0;return;}
      failures=0;done=terminal.has(value.status);onValue(value);
    }catch(cause){
      if(stopped||signal.aborted)return;
      if(!canRead()||(own.signal.aborted&&!timedOut)){delay=0;return;}
      if(cause instanceof LiveCancelled&&!timedOut){stop();return;}
      const error=timedOut?new LiveError('Job summary timed out','NETWORK_ERROR',0,'',true):cause;
      onError(error);
      if(error instanceof LiveError&&error.status>=400&&error.status<500&&error.status!==429){done=true;return;}
      delay=Math.min(30_000,2000*2**Math.min(failures++,4));
      if(error instanceof LiveError&&error.status===429&&error.retryAfter){
        const raw=error.retryAfter.trim(),seconds=/^\d+$/.test(raw)?Number(raw):NaN;
        const wait=Number.isFinite(seconds)?seconds*1000:Date.parse(raw)-clock.now();
        if(Number.isFinite(wait))delay=Math.max(delay,wait);
      }
    }finally{
      clock.clearTimeout(timeout);inFlight=false;if(request===own)request=undefined;
      if(!stopped&&!done&&!signal.aborted){deadline=clock.now()+delay;if(delay===0&&canRead())void poll();else schedule(delay);}
    }
  }
  if(signal.aborted)return stop;
  signal.addEventListener('abort',stop,{once:true});visibilityTarget?.addEventListener('visibilitychange',availability);connectivityTarget?.addEventListener('offline',availability);connectivityTarget?.addEventListener('online',availability);
  void poll();return stop;
}
