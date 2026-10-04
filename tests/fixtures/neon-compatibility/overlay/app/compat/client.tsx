"use client";
import {useState,useSyncExternalStore} from 'react';
import {createAuthClient} from '@neondatabase/auth/next';
const auth=createAuthClient();
const subscribe=()=>()=>{};
export default function Client(){const [status,setStatus]=useState('ready');const hydrated=useSyncExternalStore(subscribe,()=>true,()=>false);
 async function login(){const result=await auth.signIn.email({email:'n00@fixture.invalid',password:'fictional-password'});setStatus(result.error?'login-error':'signed-in');}
 async function session(){const result=await auth.getSession();setStatus(result.error?'session-error':result.data?.user.id??'anonymous');}
 async function token(){const result=await auth.token();if(result.error||!result.data?.token){setStatus('token-error');return;}
  // Bearer remains in this call; never persist to browser storage.
  const response=await fetch('http://127.0.0.1:44892/verify',{headers:{Authorization:`Bearer ${result.data.token}`}});setStatus(response.ok?'api-verified':'api-error');}
 async function logout(){const result=await auth.signOut();setStatus(result.error?'logout-error':'signed-out');}
 return <section data-hydrated={String(hydrated)}><button disabled={!hydrated} onClick={login}>Fixture login</button><button disabled={!hydrated} onClick={session}>Session</button><button disabled={!hydrated} onClick={token}>Verify token</button><button disabled={!hydrated} onClick={logout}>Logout</button><output data-testid="client-status">{status}</output></section>;}
