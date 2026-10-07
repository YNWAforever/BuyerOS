'use client';
import {useEffect,useRef,useState} from 'react';
import type {components} from '@/services/generated/buyeros-api';
import type {Offer} from '@/features/discovery/wizard';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {ActionIntent} from '@/services/live/action-intent';
import {LiveOfferDocuments} from './offer-documents';
import {LiveCancelled,LiveError,describeLiveError} from '@/services/live/client';
import {emptyLiveOffer,offerFromProject,toIcpSaveRequest,toProjectCreate,validateLiveOffer} from '@/services/live/profile';
import {readLatestProfile} from '@/services/live/profile-read';
import {ProfileStepError,saveProfile} from '@/services/live/writes';

type Project=components['schemas']['Project'];
type Fact=components['schemas']['OfferFact'];
type EditBase={id:string;version:number;offer_revision:number;latestIcpVersionId:string|null};
const labels=['Your offer','Target buyers','Buyer requirements','Review and save'];

export function LiveOfferWizard({mode,projectId,onSaved,t}: {
  mode:'create'|'edit';projectId?:string;
  onSaved:(info:{projectId:string;icpVersionId:string})=>void;t:(text:string)=>string;
}) {
  const {session,client}=useWorkspaceSession();
  const [offer,setOffer]=useState<Offer>(emptyLiveOffer);
  const [selectedDocuments,setSelectedDocuments]=useState<string[]>([]);
  const [documentFacts,setDocumentFacts]=useState<Partial<Record<'product'|'value_proposition',Fact>>>({});
  const [base,setBase]=useState<EditBase|null>(null);
  const [loading,setLoading]=useState(mode==='edit');
  const [step,setStep]=useState(0);
  const [busy,setBusy]=useState(false);
  const [dirty,setDirty]=useState(false);
  const [error,setError]=useState('');
  const [partial,setPartial]=useState('');
  const intent=useRef(new ActionIntent<void>());
  const busyRef=useRef(false);
  const errorRef=useRef<HTMLParagraphElement>(null);
  useEffect(()=>{if(error)errorRef.current?.focus();},[error]);
  useEffect(()=>{
    if(!dirty)return;
    const warn=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue='';};
    window.addEventListener('beforeunload',warn);
    return()=>window.removeEventListener('beforeunload',warn);
  },[dirty]);
  useEffect(()=>{
    if(mode==='create'||!projectId)return;
    let active=true;
    const own=new AbortController();
    const scope=session.current(),identity=session.identity();
    const signal=AbortSignal.any([own.signal,session.controller().signal]);
    const path=`/v1/workspaces/${encodeURIComponent(scope.workspace??'')}/projects/${encodeURIComponent(projectId)}`;
    void (async()=>{
      try{
        const token=session.token();
        const project=await client.request<Project>({path,token,scope:identity,signal});
        const latest=await readLatestProfile(client,session,projectId,signal);
        if(!active||!session.isCurrent(identity))return;
        setOffer(offerFromProject(project,latest));
        setSelectedDocuments(latest?.offer_document_ids??[]);
        setDocumentFacts(Object.fromEntries((latest?.offer_facts??[])
          .filter(fact=>fact.provenance==='document_excerpt'&&fact.source_document_id)
          .map(fact=>[fact.field,fact])) as Partial<Record<'product'|'value_proposition',Fact>>);
        setBase({id:project.id,version:project.version,offer_revision:project.offer_revision,latestIcpVersionId:latest?.id??null});
        setError('');setDirty(false);setLoading(false);
      }catch(cause){if(!active||cause instanceof LiveCancelled)return;setError(cause instanceof LiveError?describeLiveError(cause):cause instanceof Error?cause.message:'Could not load offer');setLoading(false);}
    })();
    return()=>{active=false;own.abort();};
  },[mode,projectId,session,client]);
  const update=(key:keyof Offer,value:string|boolean|string[])=>{
    setDirty(true);
    if(key==='product'||key==='value')setDocumentFacts(previous=>{const next={...previous};delete next[key==='product'?'product':'value_proposition'];return next;});
    setOffer(previous=>({...previous,[key]:value,confirmed:key==='confirmed'?Boolean(value):false}));
  };
  const chooseDocument=(id:string,selected:boolean)=>{
    setDirty(true);setSelectedDocuments(previous=>selected?[...new Set([...previous,id])]:previous.filter(item=>item!==id));
    if(!selected)setDocumentFacts(previous=>Object.fromEntries(Object.entries(previous).filter(([,fact])=>fact?.source_document_id!==id)) as typeof previous);
  };
  const applyCandidate=(fact:Fact)=>{
    if(fact.field!=='product'&&fact.field!=='value_proposition'||!fact.source_document_id)return;
    setSelectedDocuments(previous=>[...new Set([...previous,fact.source_document_id!])]);
    setDocumentFacts(previous=>({...previous,[fact.field]:fact}));
    setOffer(previous=>({...previous,[fact.field==='product'?'product':'value']:fact.value,confirmed:false}));
    setDirty(true);
  };
  function next(){
    try{
      if(step===0&&(offer.company.trim().length<2||offer.product.trim().length<2||offer.value.trim().length<5))throw new Error('Enter company, product and value proposition.');
      if(step===1){toProjectCreate(offer);if(!offer.buyerTypes?.length)throw new Error('Choose at least one buyer type.');}
      if(step===2&&(!offer.must.trim()||!offer.confirmed))throw new Error('Enter must-have requirements and confirm them.');
      setError('');setStep(current=>Math.min(3,current+1));
    }catch(cause){setError(cause instanceof Error?cause.message:'Complete required fields');}
  }
  async function save(){
    if(busyRef.current)return;
    busyRef.current=true;setBusy(true);setError('');setPartial('');
    try{
      validateLiveOffer(offer);
      const scope=session.current(),identity=session.identity();
      const fingerprint=JSON.stringify({mode,actor:scope.actor,workspace:scope.workspace,project:mode==='edit'?projectId:null,
        expectedProjectVersion:base?.version,parentIcpVersionId:base?.latestIcpVersionId,projectBody:toProjectCreate(offer),icpBody:toIcpSaveRequest(offer),
        documentIds:selectedDocuments,documentFacts:Object.values(documentFacts)});
      await intent.current.run(fingerprint,async idempotencyKey=>{
        const input={client,session,offer,idempotencyKey,documentIds:selectedDocuments,documentFacts:Object.values(documentFacts).filter((fact):fact is Fact=>Boolean(fact))};
        const out=mode==='edit'
          ? await saveProfile({...input,mode:'edit',projectId:base!.id,expectedProjectVersion:base!.version,basisOfferRevision:base!.offer_revision,parentIcpVersionId:base!.latestIcpVersionId??undefined})
          : await saveProfile({...input,mode:'create'});
        if(!session.isCurrent(identity))throw new LiveCancelled('scope changed');
        setDirty(false);onSaved({projectId:out.project.id,icpVersionId:out.icpVersion.id});
      });
    }catch(cause){
      if(cause instanceof LiveCancelled)return;
      if(cause instanceof ProfileStepError){setPartial(`${t('Project saved; profile still needs saving.')} ${t('Retry this same action.')}`);
        setError(cause.cause instanceof LiveError?describeLiveError(cause.cause):cause.message);
      }else setError(cause instanceof LiveError?describeLiveError(cause):cause instanceof Error?cause.message:'Save failed');
    }finally{busyRef.current=false;setBusy(false);}
  }
  if(mode==='edit'&&!projectId)return <section className="panel" role="alert">{t('Choose a project to edit.')}</section>;
  if(loading)return <section className="panel" role="status">{t('Loading offer...')}</section>;
  return <section className="panel wizard" data-live-unsaved={dirty?'true':'false'} aria-label={t(mode==='create'?'Create project':'Edit project')}>
    <h2>{t(mode==='create'?'Create project':'Edit project')}</h2>
    <nav className="steps" aria-label={t('Offer steps')}>{labels.map((label,index)=><button key={label} type="button" disabled={index>step||busy} className={index===step?'active':''} onClick={()=>setStep(index)}><span>{index+1}</span>{t(label)}</button>)}</nav>
    <h3>{t(labels[step])}</h3>
    {step===0&&<>
      <label>{t('Company name')}<input value={offer.company} onChange={e=>update('company',e.target.value)}/></label>
      <label>{t('Product / service')}<input value={offer.product} onChange={e=>update('product',e.target.value)}/></label>
      <label>{t('Value proposition')}<textarea value={offer.value} onChange={e=>update('value',e.target.value)}/></label>
      <label>{t('Website (optional)')}<input value={offer.website} onChange={e=>update('website',e.target.value)}/></label>
      {mode==='edit'&&projectId&&<LiveOfferDocuments projectId={projectId} selected={selectedDocuments}
        onSelect={chooseDocument} onApply={applyCandidate} t={t}/>}
    </>}
    {step===1&&<>
      <label>{t('Markets (country codes or names)')}<input value={offer.markets} onChange={e=>update('markets',e.target.value)}/></label>
      <label>{t('Languages (codes or names)')}<input value={offer.language} onChange={e=>update('language',e.target.value)}/></label>
      <fieldset><legend>{t('Buyer type')}</legend>{['Distributor','Importer','Wholesaler','Retailer','System integrator','End-user business'].map(kind=><label key={kind}><input type="checkbox" checked={offer.buyerTypes?.includes(kind)??false} onChange={e=>update('buyerTypes',e.target.checked?[...(offer.buyerTypes??[]),kind]:(offer.buyerTypes??[]).filter(item=>item!==kind))}/>{t(kind)}</label>)}</fieldset>
      <label>{t('Desired buyer roles (optional)')}<input value={offer.roles??''} onChange={e=>update('roles',e.target.value)}/></label>
    </>}
    {step===2&&<>
      <label>{t('Must have')}<textarea value={offer.must} onChange={e=>update('must',e.target.value)}/></label>
      <label>{t('Nice to have')}<textarea value={offer.nice} onChange={e=>update('nice',e.target.value)}/></label>
      <label>{t('Exclude')}<textarea value={offer.exclude} onChange={e=>update('exclude',e.target.value)}/></label>
      <label><input type="checkbox" checked={offer.confirmed} onChange={e=>update('confirmed',e.target.checked)}/>{t('I confirm these buyer requirements. Changes create a new profile version.')}</label>
    </>}
    {step===3&&<div className="notice"><p>{offer.company} · {offer.product}</p><p>{offer.value}</p><p>{offer.markets} · {offer.language}</p><p>{t('Must have')}: {offer.must}</p><p>{t('No search or provider call starts when saving.')}</p></div>}
    {partial&&<p role="status">{partial}</p>}{error&&<p ref={errorRef} tabIndex={-1} role="alert">{t(error)}</p>}
    <div className="inline spread"><button type="button" disabled={step===0||busy} onClick={()=>setStep(current=>current-1)}>{t('Back')}</button>
      {step<3?<button type="button" disabled={busy} onClick={next}>{t('Continue')}</button>:<button type="button" disabled={busy||mode==='edit'&&!base} onClick={()=>void save()}>{busy?t('Saving profile...'):t('Save profile')}</button>}
    </div>
  </section>;
}
