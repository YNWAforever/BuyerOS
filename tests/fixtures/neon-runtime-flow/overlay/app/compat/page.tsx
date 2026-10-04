import {getAuth,describeRuntime} from '../../lib/neon-real-runtime/server';
import Client from './client';
export const dynamic='force-dynamic';
async function sessionSnapshot(){
 try{const description=describeRuntime(),result=await getAuth().getSession();return {fingerprint:description.fingerprint,subject:result.error?'session-error':result.data?.user.id??'anonymous'};}
 catch{return null;}
}
export default async function Page(){
 const snapshot=await sessionSnapshot();
 if(!snapshot)return <main><h1>N00 configuration unavailable</h1><p>The runtime target must be explicitly configured before this experiment can run.</p></main>;
 return <main><h1>N00 session and token diagnostic</h1><p>Protocol experiment only. This subject is not a BuyerOS user ID or workspace role.</p><output data-testid="server-session">{snapshot.subject}</output><output data-testid="runtime-fingerprint">{snapshot.fingerprint}</output><Client fingerprint={snapshot.fingerprint} subject={snapshot.subject}/></main>;
}
