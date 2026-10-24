'use client';
import {useRef,useState} from 'react';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {neonSignInDiagnostic} from '@/services/live/neon-auth';
import {LiveBrand} from '@/features/live/shell';
import {useAuthLocale} from '@/features/live/auth-locale';

export default function NeonSignInPage(){
 const {auth,authBootstrap}=useWorkspaceSession(),{t,picker}=useAuthLocale();
 const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(false);
 const submitting=useRef(false);
 const [support,setSupport]=useState<ReturnType<typeof neonSignInDiagnostic>|null>(null);
 async function submit(action:()=>Promise<void>){
   if(submitting.current)return;submitting.current=true;setBusy(true);setError(false);setSupport(null);
   try{await action();}catch(cause){setPassword('');setError(true);setSupport(neonSignInDiagnostic(cause));}
   finally{submitting.current=false;setBusy(false);}
 }
 const ready=auth?.provider==='neon'&&authBootstrap.kind==='ready';
 return <main className="main-shell live-workspace live-signin">
   <header className="live-signin-top">{picker}</header>
   <section className="panel live-signin-card"><LiveBrand/><h1>{t('Sign in')}</h1>
   {authBootstrap.kind==='initializing'?<p role="status">{t('Initializing sign-in…')}</p>:!ready?<p role="alert">{t('Neon sign-in is unavailable.')}</p>:<>
     <form className="live-auth-form" aria-busy={busy} onSubmit={event=>{event.preventDefault();void submit(()=>auth!.signInEmail!(email,password));}}>
       <label>{t('Email')}<input type="email" autoComplete="username" value={email} required onChange={event=>setEmail(event.target.value)} disabled={busy}/></label>
       <label>{t('Password')}<input type="password" autoComplete="current-password" value={password} required onChange={event=>setPassword(event.target.value)} disabled={busy}/></label>
       <button className="live-primary" type="submit" disabled={busy}>{t('Sign in with email')}</button>
     </form>
     <button className="live-secondary live-auth-google" type="button" disabled={busy} onClick={()=>void submit(()=>auth!.signInGoogle!())}>{t('Sign in with Google')}</button>
     {busy&&<p role="status">{t('Signing in…')}</p>}
     {error&&<p role="alert">{t('Sign-in failed. Check your details or start again.')}</p>}
     {support&&<p data-testid="auth-support-reference">{t('Support reference')}: {support.category}{support.http_status?` · HTTP ${support.http_status}`:''}{support.request_id?` · ${support.request_id}`:''}</p>}
   </>}
   {/* A full navigation abandons the old return transaction; signIn always creates a fresh one. */}
   {/* eslint-disable-next-line @next/next/no-html-link-for-pages -- Native reset is intentional: the emitted vinext Link recovery fails pointer and Enter regressions. */}
   <a className="live-auth-restart" href="/app">{t('Start again')}</a>
   </section><p className="live-signin-note">{t('Private workspace. Sign-in is required for every visitor.')}</p>
 </main>;
}
