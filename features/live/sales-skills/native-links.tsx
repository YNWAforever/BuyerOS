'use client';
import {useMemo,useState} from 'react';
import {useRouter} from 'next/navigation';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import type {SalesSchema as S} from '@/services/live/sales-transport';
import {SalesDocuments} from './documents';
import {liveZh} from '../locale';
export function NativeSalesLinks({surface,id,revision=1,locale='en'}:{surface:S['NativeRef']['surface'];id:string;revision?:number;locale?:'en'|'zh-HK'}){
 const {session,client}=useWorkspaceSession(),snapshot=useSessionSnapshot(),router=useRouter();
 const native=useMemo(()=>({surface,id,revision}),[surface,id,revision]);
 const [opened,setOpened]=useState(false);
 const t=(v:string)=>locale==='zh-HK'?(liveZh[v]??v):v;
 const navigate=(path:string)=>{void session.transition(async()=>{const url=new URL(path,location.origin);url.searchParams.set('workspace',snapshot.scope.workspace??'');url.searchParams.set('project',snapshot.scope.project??'');router.push(url.pathname+url.search+url.hash);});};
 // Once opened, retain the reader/editor when collapsed so local work survives.
 return <details onToggle={event=>{if(event.currentTarget.open)setOpened(true);}}><summary>{t('Linked outputs')}</summary>{opened&&<SalesDocuments key={snapshot.identity+id} {...{session,client,t,navigate,native}}/>}</details>;
}
