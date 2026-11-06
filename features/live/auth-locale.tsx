'use client';
import {useEffect,useState,useSyncExternalStore} from 'react';
const noBrowserChange=()=>()=>{};
const inBrowser=()=>true;
const onServer=()=>false;
const copy:Record<string,string>={
 'Verify email':'驗證電郵','Verification code':'驗證碼','Resend verification code':'重新發送驗證碼',
 'Email verified. You can now sign in.':'電郵已驗證，現在可以登入。',
 'Account created. Enter the six-digit verification code from your email.':'帳戶已建立，請輸入電郵中的六位數驗證碼。',
 'Enter the six-digit verification code from your email.':'請輸入電郵中的六位數驗證碼。',
 'That code is invalid or expired. Check the email and code, or request a new code.':'驗證碼無效或已過期。請檢查電郵地址及驗證碼，或索取新的驗證碼。',
 'If this account needs verification, a new code will arrive shortly. Check your spam folder too.':'如該帳戶需要驗證，你將很快收到新的驗證碼。請同時查看垃圾郵件。',
 'Forgot password?':'忘記密碼？','Create account':'建立帳戶','Resend verification email':'重新發送驗證電郵',
 'Reset password':'重設密碼','Send reset link':'發送重設連結','Save new password':'儲存新密碼','Send verification email':'發送驗證電郵',
 'Name':'姓名','New password':'新密碼','Confirm password':'確認密碼','Use 8–128 characters.':'請使用 8 至 128 個字元。',
 'Please wait…':'請稍候…','Checking reset link…':'正在檢查重設連結…','Back to sign in':'返回登入','Request a new reset link':'索取新的重設連結',
 'Passwords do not match.':'兩次輸入的密碼不相符。',
 'Too many attempts. Please wait and try again.':'嘗試次數過多，請稍後再試。',
 'This reset link may have expired or already been used. Request a new link.':'此重設連結可能已過期或已使用，請索取新連結。',
 'This reset link is missing or invalid. Request a new link.':'重設連結遺失或無效，請索取新連結。',
 'Could not create the account. If you already have an account, sign in or reset your password. Otherwise, try again or contact your administrator.':'未能建立帳戶。如已有帳戶，請登入或重設密碼；否則請重試或聯絡管理員。',
 'Could not send the email. Try again later or contact your administrator.':'未能發送電郵，請稍後再試或聯絡管理員。',
 'Password updated. Sign in with your new password.':'密碼已更新，請使用新密碼登入。',
 'Check your email to verify your account, then return to sign in.':'請查看電郵並驗證帳戶，然後返回登入。',
 'If this email has an eligible account, a password reset link will arrive shortly. Check your spam folder too.':'如該電郵有符合條件的帳戶，你將很快收到密碼重設連結。請同時查看垃圾郵件。',
 'If this account needs verification, a verification email will arrive shortly. Check your spam folder too.':'如該帳戶需要驗證，你將很快收到驗證電郵。請同時查看垃圾郵件。',
 'Use your invited work email. Creating an account does not grant workspace access; an administrator must invite you.':'請使用獲邀的工作電郵。建立帳戶不會自動獲得工作區權限，須由管理員邀請。',
 'Neon sign-in configuration is unavailable. Ask an administrator to restore sign-in.':'Neon 登入設定暫不可用。請要求管理員恢復登入。',
 'Sign-in provider configuration is unavailable. Ask an administrator to restore sign-in.':'登入服務設定暫不可用。請要求管理員恢復登入。',
 'Sign-in configuration unavailable. Ask an administrator to restore sign-in.':'登入設定暫不可用。請要求管理員恢復登入。',
 'Auth0 sign-in is disabled. An administrator needs to finish Neon sign-in setup before anyone can sign in.':'Auth0 登入已停用。管理員須先完成 Neon 登入設定，訪客才能登入。',
 'Sign-in failed. BuyerOS could not check for an existing session. Choose Sign in and enter your email and password.':'登入失敗。BuyerOS 未能檢查是否已有登入階段。請按登入，並輸入電郵及密碼。',

 'Support reference':'支援參考',
 'Sign in':'登入','Email':'電郵','Password':'密碼','Sign in with email':'使用電郵登入',
 'Sign in with Google':'使用 Google 登入','Start again':'重新開始','Language':'語言',
 'Signing in…':'正在登入…','Initializing sign-in…':'正在初始化登入…',
 'Neon sign-in is unavailable. Choose Start again, or ask an administrator if this continues.':'Neon 登入暫不可用。請選擇重新開始；若情況持續，請聯絡管理員。',
 'Enter the work email on your invitation and its password.':'輸入邀請上的工作電郵及其密碼。',
 'The invited work email.':'獲邀的工作電郵。',
 'The password for that account.':'該帳戶的密碼。',
 'or':'或',
 'Only for accounts created with Google.':'只適用於以 Google 建立的帳戶。',
 'Enter the work email on your invitation.':'請輸入邀請上的工作電郵。',
 'Enter a complete email address, such as name@company.com.':'請輸入完整電郵地址，例如 name@company.com。',
 'Enter the password for this BuyerOS account.':'請輸入此 BuyerOS 帳戶的密碼。',
 'This page is not linked to a sign-in yet. Choose Start again, then Sign in. You will enter the invited work email and its password.':'此頁尚未連接到登入流程。請選擇重新開始，然後按登入。下一頁會要求輸入邀請上的工作電郵及其密碼。',
 'Completing sign-in…':'正在完成登入…','Sign-in failed. Please start again.':'登入失敗，請重新開始。',
 'Live sign-in is disabled':'即時登入未啟用','Private workspace. Sign-in is required for every visitor.':'私人工作區，所有訪客均須登入。',
};
export function useAuthLocale(){
 // SSR/native interaction must not accept a preference before the browser
 // attaches React's change handler. This is presentation readiness only.
 const ready=useSyncExternalStore(noBrowserChange,inBrowser,onServer);
 const [locale,setLocale]=useState<'en'|'zh-HK'>('en');
 useEffect(()=>{try{const saved=localStorage.getItem('buyeros.locale');if(saved==='en'||saved==='zh-HK')queueMicrotask(()=>setLocale(saved));}catch{/* Optional locale storage. */}},[]);
 useEffect(()=>{document.documentElement.lang=locale;},[locale]);
 function change(value:'en'|'zh-HK'){setLocale(value);try{localStorage.setItem('buyeros.locale',value);}catch{/* Keep form state even without storage. */}}
 return {locale,t:(value:string)=>locale==='zh-HK'?(copy[value]??value):value,
   picker:<label>{locale==='zh-HK'?'語言':'Language'} <select aria-label={locale==='zh-HK'?'語言':'Language'} value={locale} disabled={!ready} onChange={event=>change(event.target.value as 'en'|'zh-HK')}><option value="en">English</option><option value="zh-HK">繁體中文</option></select></label>};
}
