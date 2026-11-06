'use client';
import {useEffect,useRef,useState,type FormEvent} from 'react';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {LiveBrand} from './shell';
import {useAuthLocale} from './auth-locale';
import {neonSignInDiagnostic} from '@/services/live/neon-auth';

type Mode='register'|'forgot'|'reset'|'verify';
const titles:Record<Mode,string>={register:'Create account',forgot:'Forgot password?',reset:'Reset password',verify:'Resend verification email'};
const actions:Record<Mode,string>={register:'Create account',forgot:'Send reset link',reset:'Save new password',verify:'Send verification email'};
export function AuthAccountForm({mode}:{mode:Mode}){
 const {auth,authBootstrap}=useWorkspaceSession(),{t,picker}=useAuthLocale();
 const [name,setName]=useState(''),[email,setEmail]=useState(''),[password,setPassword]=useState(''),[confirm,setConfirm]=useState('');
 const [busy,setBusy]=useState(false),[done,setDone]=useState(false),[error,setError]=useState('');
 const [resetToken,setResetToken]=useState<string|null>(null),submitting=useRef(false),resetRead=useRef(false);
 useEffect(()=>{
  if(mode!=='reset'||resetRead.current)return;
  resetRead.current=true;
  const url=new URL(window.location.href),tokens=url.searchParams.getAll('token');
  const token=!url.searchParams.has('error')&&(tokens.length === 1)&&tokens[0].length<=4096&&!/[\s\u0000-\u001f\u007f]/.test(tokens[0])?tokens[0]:'';
  // Keep the bearer reset token only in this mounted form, out of history and referrers.
  window.history.replaceState(window.history.state,'',url.pathname);
  queueMicrotask(()=>setResetToken(token));
 },[mode]);
 const ready=auth?.provider==='neon'&&authBootstrap.kind==='ready';
 const hasPassword=mode==='register'||mode==='reset';
 async function submit(event:FormEvent){
  event.preventDefault();if(!ready||submitting.current)return;
  if(hasPassword&&password!==confirm){setError('Passwords do not match.');return;}
  submitting.current=true;setBusy(true);setError('');
  try{
   if(mode==='register'){
    const result=await auth!.signUpEmail!(name,email,password);
    if(result==='signed-in')return;
   }else if(mode==='forgot')await auth!.requestPasswordReset!(email);
   else if(mode==='verify')await auth!.sendVerificationEmail!(email);
   else await auth!.resetPassword!(resetToken??'',password);
   setDone(true);
  }catch(cause){
   const status=neonSignInDiagnostic(cause).http_status;
   setError(status===429?'Too many attempts. Please wait and try again.':mode==='reset'?'This reset link may have expired or already been used. Request a new link.':mode==='register'?'Could not create the account. If you already have an account, sign in or reset your password. Otherwise, try again or contact your administrator.':'Could not send the email. Try again later or contact your administrator.');
  }finally{submitting.current=false;setBusy(false);setPassword('');setConfirm('');}
 }
 const confirmation=mode==='reset'?'Password updated. Sign in with your new password.':mode==='register'?'Check your email to verify your account, then return to sign in.':mode==='forgot'?'If this email has an eligible account, a password reset link will arrive shortly. Check your spam folder too.':'If this account needs verification, a verification email will arrive shortly. Check your spam folder too.';
 return <main className="main-shell live-workspace live-signin">
  <header className="live-signin-top">{picker}</header>
  <section className="panel live-signin-card"><LiveBrand/><h1>{t(titles[mode])}</h1>
   {done?<><p role="status">{t(confirmation)}</p>{mode==='register'&&<p><a href="/auth/verify-email">{t('Resend verification email')}</a></p>}</>:
    authBootstrap.kind==='initializing'?<p role="status">{t('Initializing sign-in…')}</p>:!ready?<p role="alert">{t('Neon sign-in is unavailable. Choose Start again, or ask an administrator if this continues.')}</p>:
    mode==='reset'&&resetToken===null?<p role="status">{t('Checking reset link…')}</p>:
    mode==='reset'&&!resetToken?<p role="alert">{t('This reset link is missing or invalid. Request a new link.')}</p>:<>
    {mode==='register'&&<p>{t('Use your invited work email. Creating an account does not grant workspace access; an administrator must invite you.')}</p>}
    <form className="live-auth-form" aria-busy={busy} onSubmit={event=>void submit(event)}>
     {mode==='register'&&<div className="live-auth-field"><label htmlFor="account-name">{t('Name')}</label><input id="account-name" autoComplete="name" value={name} onChange={e=>setName(e.target.value)} maxLength={200} required disabled={busy}/></div>}
     {mode!=='reset'&&<div className="live-auth-field"><label htmlFor="account-email">{t('Email')}</label><input id="account-email" type="email" autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} maxLength={320} required disabled={busy}/></div>}
     {hasPassword&&<>
      <div className="live-auth-field"><label htmlFor="account-password">{t('New password')}</label><input id="account-password" type="password" autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)} minLength={8} maxLength={128} aria-describedby="password-length" required disabled={busy}/><p id="password-length" className="live-auth-hint">{t('Use 8–128 characters.')}</p></div>
      <div className="live-auth-field"><label htmlFor="account-confirm">{t('Confirm password')}</label><input id="account-confirm" type="password" autoComplete="new-password" value={confirm} onChange={e=>setConfirm(e.target.value)} minLength={8} maxLength={128} required disabled={busy}/></div>
     </>}
     <button className="live-primary" type="submit" disabled={busy}>{t(busy?'Please wait…':actions[mode])}</button>
    </form></>}
   {error&&<p role="alert" className="live-auth-alert">{t(error)}</p>}
   {mode==='reset'&&!done&&<p><a href="/auth/forgot-password">{t('Request a new reset link')}</a></p>}
   {mode==='register'&&error&&<p><a href="/auth/forgot-password">{t('Forgot password?')}</a></p>}
   <p><a href="/auth/sign-in">{t('Back to sign in')}</a></p>
  </section>
 </main>;
}
