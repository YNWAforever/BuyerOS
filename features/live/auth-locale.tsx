'use client';
import {useEffect,useState,useSyncExternalStore} from 'react';
const noBrowserChange=()=>()=>{};
const inBrowser=()=>true;
const onServer=()=>false;
const copy:Record<string,string>={
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
