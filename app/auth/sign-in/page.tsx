'use client';
import Link from 'next/link';
import {useState} from 'react';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
export default function NeonSignInPage(){
  const {auth,authBootstrap}=useWorkspaceSession();const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  if(authBootstrap.kind==='initializing')return <section className="panel" role="status">Initializing sign-in…</section>;
  if(auth?.provider!=='neon')return <section className="panel" role="alert">Neon sign-in is unavailable.</section>;
  async function submit(action:()=>Promise<void>){if(busy)return;setBusy(true);setError('');try{await action();}catch{setPassword('');setError('Sign-in failed. Check your details or start again.');}finally{setBusy(false);}}
  return <main className="main-shell"><section className="panel"><h1>Sign in</h1>
    <form onSubmit={event=>{event.preventDefault();void submit(()=>auth!.signInEmail!(email,password));}}>
      <label>Email <input type="email" autoComplete="username" value={email} required onChange={event=>setEmail(event.target.value)} disabled={busy}/></label>
      <label>Password <input type="password" autoComplete="current-password" value={password} required onChange={event=>setPassword(event.target.value)} disabled={busy}/></label>
      <button type="submit" disabled={busy}>Sign in with email</button>
    </form><button type="button" disabled={busy} onClick={()=>void submit(()=>auth!.signInGoogle!())}>Sign in with Google</button>
    {error&&<p role="alert">{error}</p>}<Link href="/app">Start again</Link>
  </section></main>;
}
