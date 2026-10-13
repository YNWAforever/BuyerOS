'use client';
import Link from 'next/link';
import {useState} from 'react';
import {ShieldCheck} from 'lucide-react';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {LiveBrand} from '@/features/live/shell';
export default function NeonSignInPage(){
  const {auth,authBootstrap}=useWorkspaceSession();const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const frame=(body:React.ReactNode)=><main className="main-shell live-workspace live-signin">
    <section className="panel live-signin-card"><LiveBrand/>{body}</section>
    <p className="live-signin-note"><ShieldCheck size={14} aria-hidden="true"/>Private workspace. Sign-in is required for every visitor.</p>
  </main>;
  if(authBootstrap.kind==='initializing')return frame(<h1 role="status">Initializing sign-in…</h1>);
  if(auth?.provider!=='neon')return frame(<p role="alert">Neon sign-in is unavailable.</p>);
  async function submit(action:()=>Promise<void>){if(busy)return;setBusy(true);setError('');try{await action();}catch{setPassword('');setError('Sign-in failed. Check your details or start again.');}finally{setBusy(false);}}
  return frame(<><h1>Sign in</h1><p>Sign in to access your workspaces.</p>
    <button type="button" className="live-primary" disabled={busy} onClick={()=>void submit(()=>auth!.signInGoogle!())}>Sign in with Google</button>
    <p className="live-signin-or">or</p>
    <form onSubmit={event=>{event.preventDefault();void submit(()=>auth!.signInEmail!(email,password));}}>
      <label>Email <input type="email" autoComplete="username" value={email} required onChange={event=>setEmail(event.target.value)} disabled={busy}/></label>
      <label>Password <input type="password" autoComplete="current-password" value={password} required onChange={event=>setPassword(event.target.value)} disabled={busy}/></label>
      <button type="submit" disabled={busy}>Sign in with email</button>
    </form>
    {error&&<p role="alert">{error}</p>}<Link className="live-signin-restart" href="/app">Start again</Link>
  </>);
}
