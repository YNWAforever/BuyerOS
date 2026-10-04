"use client";
import {useState,useSyncExternalStore} from 'react';
import {createAuthClient} from '@neondatabase/auth/next';
import {validDiagnosticReceipt} from '@/scripts/neon-real-diagnostic.mjs';
const auth=createAuthClient(),subscribe=()=>()=>{};
export default function Client({fingerprint,subject}:{fingerprint:string;subject:string}){
 const [status,setStatus]=useState('ready'),[busy,setBusy]=useState(false),hydrated=useSyncExternalStore(subscribe,()=>true,()=>false);
 async function act(action:()=>Promise<string>){if(busy)return;setBusy(true);try{setStatus(await action());}catch{setStatus('request-unknown');}finally{setBusy(false);}}
 async function login(){const result=await auth.signIn.social({provider:'google',callbackURL:new URL('/compat/return',window.location.origin).href});return result.error?'login-error':'redirecting';}
 async function session(){const result=await auth.getSession();return result.error?'session-error':result.data?.user.id??'anonymous';}
 async function verify(){const result=await auth.token();if(result.error||!result.data?.token)return 'token-error';
  // JWT exists only in this operation; never render, log or persist it.
  const response=await fetch('/api/n00/verify',{method:'POST',headers:{Authorization:'Bearer '+result.data.token}});
  if(!response.ok)return response.status===401?'api-refused':'api-unavailable';
  return validDiagnosticReceipt(await response.json(),{fingerprint,subject})?'api-verified':'api-context-refused';
 }
 async function logout(){const result=await auth.signOut();return result.error?'logout-error':'signed-out';}
 return <section><button disabled={!hydrated||busy} onClick={()=>act(login)}>Continue with Google</button><button disabled={!hydrated||busy} onClick={()=>act(session)}>Session</button><button disabled={!hydrated||busy} onClick={()=>act(verify)}>Verify token</button><button disabled={!hydrated||busy} onClick={()=>act(logout)}>Logout</button><output data-testid="client-status">{status}</output></section>;
}
