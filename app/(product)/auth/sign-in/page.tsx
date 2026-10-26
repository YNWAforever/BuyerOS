'use client';
import {useRef,useState,useSyncExternalStore,type FormEvent} from 'react';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {neonSignInDiagnostic} from '@/services/live/neon-auth';
import {describeSignInFailure,signInFailureMessage,type SignInReason} from '@/services/live/sign-in-failure';
import {LiveBrand} from '@/features/live/shell';
import {useAuthLocale} from '@/features/live/auth-locale';

const emailMissing = 'Enter the work email on your invitation.';
const emailFormat = 'Enter a complete email address, such as name@company.com.';
const passwordMissing = 'Enter the password for this BuyerOS account.';
function signInIsLinked(): boolean {
  try {
    if (new URLSearchParams(window.location.search).get('state')) return true;
    const raw = sessionStorage.getItem('buyeros-neon-return');
    if (!raw || raw.length > 4096) return false;
    const value = JSON.parse(raw) as {state?: unknown};
    return typeof value.state === 'string' && value.state.length > 0;
  } catch { return false; }
}

export default function NeonSignInPage(){
 const {auth,authBootstrap}=useWorkspaceSession(),{t,picker,locale}=useAuthLocale();
 const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[busy,setBusy]=useState(false);
 const [failure,setFailure]=useState<SignInReason|null>(null),[fieldError,setFieldError]=useState<string|null>(null);
 const submitting=useRef(false);
 const [support,setSupport]=useState<ReturnType<typeof neonSignInDiagnostic>|null>(null);
 const linked=useSyncExternalStore(()=>()=>{},signInIsLinked,()=>true);
 async function submit(action:()=>Promise<void>,context:'email'|'google'='email'){
   if(submitting.current)return;submitting.current=true;setBusy(true);setFailure(null);setFieldError(null);setSupport(null);
   try{await action();}catch(cause){setPassword('');setFailure(describeSignInFailure(cause,context));setSupport(neonSignInDiagnostic(cause));}
   finally{submitting.current=false;setBusy(false);}
 }
 function prepareValidity(){
   const apply=(id:string,missing:string,bad:string)=>{
     const field=document.getElementById(id);
     if(!(field instanceof HTMLInputElement))return;
     field.setCustomValidity('');
     if(field.validity.valueMissing)field.setCustomValidity(t(missing));
     else if(!field.validity.valid)field.setCustomValidity(t(bad));
     else field.setCustomValidity('');
   };
   apply('sign-in-email',emailMissing,emailFormat);
   apply('sign-in-password',passwordMissing,passwordMissing);
 }
 function invalid(event:FormEvent<HTMLInputElement>,missing:string,bad:string){
   const field=event.currentTarget,first=field.form?.querySelector<HTMLInputElement>(':invalid');
   if(first&&first!==field)return;
   setFieldError(field.validity.valueMissing?missing:bad);setFailure(null);
 }
 const ready=auth?.provider==='neon'&&authBootstrap.kind==='ready';
 const alertText=failure?signInFailureMessage(failure,locale):fieldError?t(fieldError):'';
 return <main className="main-shell live-workspace live-signin">
   <header className="live-signin-top">{picker}</header>
   <section className="panel live-signin-card"><LiveBrand/><h1>{t('Sign in')}</h1>
   {authBootstrap.kind==='initializing'?<p role="status">{t('Initializing sign-in…')}</p>:!ready?<p role="alert">{t('Neon sign-in is unavailable. Choose Start again, or ask an administrator if this continues.')}</p>:<>
     <p className="live-auth-lead">{t('Enter the work email on your invitation and its password.')}</p>
     {!linked&&<p className="live-auth-hint">{t('This page is not linked to a sign-in yet. Choose Start again, then Sign in. You will enter the invited work email and its password.')}</p>}
     <form className="live-auth-form" aria-busy={busy} aria-describedby={alertText?'sign-in-error':undefined} onKeyDown={event=>{if(event.key==='Enter')prepareValidity();}} onSubmit={event=>{event.preventDefault();setFieldError(null);void submit(()=>auth!.signInEmail!(email,password));}}>
       <div className="live-auth-field">
         <label htmlFor="sign-in-email">{t('Email')}</label>
         <input id="sign-in-email" type="email" autoComplete="username" placeholder="name@company.com" aria-describedby="sign-in-email-hint" aria-invalid={fieldError===emailMissing||fieldError===emailFormat} value={email} required disabled={busy} onChange={event=>{event.currentTarget.setCustomValidity('');setEmail(event.target.value);if(fieldError===emailMissing||fieldError===emailFormat)setFieldError(null);}} onInvalid={event=>invalid(event,emailMissing,emailFormat)}/>
         <p id="sign-in-email-hint" className="live-auth-hint">{t('The invited work email.')}</p>
       </div>
       <div className="live-auth-field">
         <label htmlFor="sign-in-password">{t('Password')}</label>
         <input id="sign-in-password" type="password" autoComplete="current-password" aria-describedby="sign-in-password-hint" aria-invalid={fieldError===passwordMissing} value={password} required disabled={busy} onChange={event=>{event.currentTarget.setCustomValidity('');setPassword(event.target.value);if(fieldError===passwordMissing)setFieldError(null);}} onInvalid={event=>invalid(event,passwordMissing,passwordMissing)}/>
         <p id="sign-in-password-hint" className="live-auth-hint">{t('The password for that account.')}</p>
       </div>
       <button className="live-primary" type="submit" disabled={busy} onMouseDown={prepareValidity} onKeyDown={event=>{if(event.key==='Enter'||event.key===' ')prepareValidity();}}>{t('Sign in with email')}</button>
     </form>
     <div className="live-auth-secondary">
       <p className="live-auth-or">{t('or')}</p>
       <p className="live-auth-hint">{t('Only for accounts created with Google.')}</p>
       <button className="live-secondary live-auth-google" type="button" disabled={busy} onClick={()=>void submit(()=>auth!.signInGoogle!(),'google')}>{t('Sign in with Google')}</button>
     </div>
     {busy&&<p role="status">{t('Signing in…')}</p>}
     {alertText&&<p id="sign-in-error" className="live-auth-alert" role="alert">{alertText}</p>}
     {support&&<p className="live-auth-support" data-testid="auth-support-reference">{t('Support reference')}: {support.category}{support.http_status?` · HTTP ${support.http_status}`:''}{support.request_id?` · ${support.request_id}`:''}</p>}
   </>}
   {/* A full navigation abandons the old return transaction; signIn always creates a fresh one. */}
   {/* eslint-disable-next-line @next/next/no-html-link-for-pages -- Native reset is intentional: the emitted vinext Link recovery fails pointer and Enter regressions. */}
   <a className="live-auth-restart" href="/app">{t('Start again')}</a>
   </section><p className="live-signin-note">{t('Private workspace. Sign-in is required for every visitor.')}</p>
 </main>;
}
