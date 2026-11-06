'use client';
import {useRef,useState,type FormEvent} from 'react';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {LiveBrand} from './shell';
import {useAuthLocale} from './auth-locale';
import {neonSignInDiagnostic} from '@/services/live/neon-auth';

export function VerifyEmailForm({initialEmail='',fromSignup=false}:{initialEmail?:string;fromSignup?:boolean}){
 const {auth,authBootstrap}=useWorkspaceSession(),{t,picker}=useAuthLocale();
 const [email,setEmail]=useState(initialEmail),[code,setCode]=useState(''),[done,setDone]=useState(false);
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[sent,setSent]=useState(false);
 const submitting=useRef(false),emailInput=useRef<HTMLInputElement>(null);
 const ready=auth?.provider==='neon'&&authBootstrap.kind==='ready';
 async function act(kind:'verify'|'resend',event?:FormEvent){
  event?.preventDefault();if(!ready||submitting.current||!emailInput.current?.reportValidity())return;
  submitting.current=true;setBusy(true);setError('');setSent(false);
  try{
   if(kind==='verify'){await auth!.verifyEmailCode!(email,code);setDone(true);}
   else {await auth!.sendVerificationEmail!(email);setSent(true);}
  }catch(cause){
   setError(neonSignInDiagnostic(cause).http_status===429?'Too many attempts. Please wait and try again.':kind==='verify'?'That code is invalid or expired. Check the email and code, or request a new code.':'Could not send the email. Try again later or contact your administrator.');
  }finally{setCode('');submitting.current=false;setBusy(false);}
 }
 return <main className="main-shell live-workspace live-signin">
  <header className="live-signin-top">{picker}</header>
  <section className="panel live-signin-card"><LiveBrand/><h1>{t('Verify email')}</h1>
   {done?<p role="status">{t('Email verified. You can now sign in.')}</p>:
    authBootstrap.kind==='initializing'?<p role="status">{t('Initializing sign-in…')}</p>:
    !ready?<p role="alert">{t('Neon sign-in is unavailable. Choose Start again, or ask an administrator if this continues.')}</p>:<>
     <p>{t(fromSignup?'Account created. Enter the six-digit verification code from your email.':'Enter the six-digit verification code from your email.')}</p>
     <form className="live-auth-form" aria-busy={busy} onSubmit={event=>void act('verify',event)}>
      <div className="live-auth-field"><label htmlFor="verify-email">{t('Email')}</label><input ref={emailInput} id="verify-email" type="email" autoComplete="email" value={email} maxLength={320} required disabled={busy} onChange={event=>{setEmail(event.target.value);setCode('');setError('');setSent(false);}}/></div>
      <div className="live-auth-field"><label htmlFor="verify-code">{t('Verification code')}</label><input id="verify-code" type="text" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} value={code} required disabled={busy} onChange={event=>setCode(event.target.value.replace(/\s/g,''))}/></div>
      <button className="live-primary" type="submit" disabled={busy}>{t(busy?'Please wait…':'Verify email')}</button>
      <button className="live-secondary" type="button" disabled={busy} onClick={()=>void act('resend')}>{t('Resend verification code')}</button>
     </form>
    </>}
   {sent&&<p role="status">{t('If this account needs verification, a new code will arrive shortly. Check your spam folder too.')}</p>}
   {error&&<p className="live-auth-alert" role="alert">{t(error)}</p>}
   <p><a href="/auth/sign-in">{t('Back to sign in')}</a></p>
  </section>
 </main>;
}
