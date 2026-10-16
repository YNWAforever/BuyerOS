'use client';
import Link from 'next/link';
import {useRouter} from 'next/navigation';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import type {ReactNode} from 'react';

/** Keep ordinary clicks inside the same session transition as the workspace navigation. */
export function LeadLink({href,children,onNavigate}:{href:string;children:ReactNode;onNavigate?:(path:string)=>void}){
  const router=useRouter(),{session}=useWorkspaceSession();
  return <Link href={href} prefetch={false} onClick={event=>{
    if(event.defaultPrevented||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
    event.preventDefault();
    if(onNavigate)onNavigate(href);
    else void session.transition(async()=>router.push(href)).catch(()=>{});
  }}>{children}</Link>;
}
