'use client';
import {useEffect,useState,useSyncExternalStore} from 'react';
const noBrowserChange=()=>()=>{};
const inBrowser=()=>true;
const onServer=()=>false;
const copy:Record<string,string>={
 'Neon sign-in configuration is unavailable.':'Neon 登入設定暫不可用。',
 'Sign-in provider configuration is unavailable.':'登入服務設定暫不可用。',
 'Sign-in configuration unavailable.':'登入設定暫不可用。',

 'Support reference':'支援參考',
 'Sign in':'登入','Email':'電郵','Password':'密碼','Sign in with email':'使用電郵登入',
 'Sign in with Google':'使用 Google 登入','Start again':'重新開始','Language':'語言',
 'Signing in…':'正在登入…','Initializing sign-in…':'正在初始化登入…',
 'Neon sign-in is unavailable.':'Neon 登入暫不可用。',
 'Sign-in failed. Check your details or start again.':'登入失敗，請檢查資料或重新開始。',
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
