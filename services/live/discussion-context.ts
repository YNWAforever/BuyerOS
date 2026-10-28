import type {components} from '@/services/generated/buyeros-api';
import {LiveCancelled,LiveError,type LiveClient,type LiveRequest} from './client';
import type {SessionScope} from './session';
import {listRuns} from './runs';
import {getUsage,utcMonth} from './usage';

export interface ContextItem {id:string;label:string;title:string;detail?:string;status:string;path:string;}
export interface ContextSection {title:string;items:ContextItem[];notice?:string;}

type Document=components['schemas']['OfferDocument'];
type Profile=components['schemas']['ICPVersion'];
type Fact=components['schemas']['OfferFact'];
type Project=components['schemas']['Project'];
type Page<T>={items:T[];offset:number;limit:number;total:number};
type Scope={workspace:string;project:string};
const PAGE_SIZE=20;
const FACT_LIMIT=40;
const uuid=/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
const documentStatuses=new Set(['quarantined','queued','parsing','ready','failed','deleted']);
const runStatuses=new Set(['draft','queued','running','partial','paused_budget','cancel_requested','cancelled','failed','completed','awaiting_reconciliation']);
class UnverifiedContext extends Error {}
function check(value:unknown):asserts value {if(!value)throw new UnverifiedContext();}
function object(value:unknown):value is Record<string,unknown>{return typeof value==='object'&&value!==null&&!Array.isArray(value);}
function text(value:unknown,max=20000):value is string{return typeof value==='string'&&value.trim().length>0&&value.length<=max;}
function identifier(value:unknown):value is string{return typeof value==='string'&&uuid.test(value);}
function count(value:unknown):value is number{return Number.isSafeInteger(value)&&Number(value)>=0;}
function date(value:unknown):value is string{return typeof value==='string'&&value.length<=64&&/^\d{4}-\d\d-\d\dT/.test(value)&&Number.isFinite(Date.parse(value));}
function scopedRow(value:unknown,scope:Scope):Record<string,unknown>{
  check(object(value)&&identifier(value.id)&&value.workspace_id===scope.workspace&&value.project_id===scope.project&&value.data_mode==='live');
  return value;
}
function readPage(value:unknown,offset:number,limit:number):Page<unknown>{
  check(object(value)&&Array.isArray(value.items)&&value.offset===offset&&value.limit===limit&&count(value.total));
  check(value.items.length===Math.min(limit,Math.max(0,value.total-offset)));
  return value as Page<unknown>;
}
function readFacts(value:unknown):Fact[]{
  check(Array.isArray(value)&&value.length<=100);
  const seen=new Set<string>();
  for(const fact of value){
    check(object(fact)&&identifier(fact.id)&&!seen.has(fact.id)&&text(fact.field,200)&&text(fact.value)&&
      ['user_entered','document_excerpt','model_inference'].includes(String(fact.provenance))&&typeof fact.approved==='boolean');
    check(fact.source_document_id==null||identifier(fact.source_document_id));
    seen.add(fact.id);
  }
  return value as Fact[];
}
function readDocuments(value:unknown,scope:Scope):Page<Document>{
  const page=readPage(value,0,PAGE_SIZE),seen=new Set<string>();
  for(const item of page.items){
    const row=scopedRow(item,scope);
    check(identifier(row.id)&&!seen.has(row.id)&&text(row.filename,1000)&&documentStatuses.has(String(row.status)));
    const facts=readFacts(row.fact_candidates===undefined?[]:row.fact_candidates);
    check(facts.every(fact=>!fact.source_document_id||fact.source_document_id===row.id));
    seen.add(row.id);
  }
  return page as Page<Document>;
}
function readProject(value:unknown,scope:Scope):Project{
  check(object(value)&&value.id===scope.project&&value.workspace_id===scope.workspace&&value.data_mode==='live'&&
    count(value.offer_revision)&&value.offer_revision>=1&&['active','archived'].includes(String(value.status))&&
    (value.active_icp_version_id===null||identifier(value.active_icp_version_id)));
  return value as Project;
}
function readProfiles(value:unknown,scope:Scope,offset:number):Page<Profile>{
  const page=readPage(value,offset,PAGE_SIZE),seen=new Set<string>();
  for(const item of page.items){
    const row=scopedRow(item,scope);
    check(identifier(row.id)&&!seen.has(row.id)&&count(row.number)&&row.number>=1&&
      ['saved','approved','superseded'].includes(String(row.status))&&['current','stale','unknown'].includes(String(row.basis_status))&&
      typeof row.is_current==='boolean'&&(row.basis_offer_revision===null||count(row.basis_offer_revision)));
    check((row.approved_by==null||text(row.approved_by,200))&&(row.approved_at==null||date(row.approved_at)));
    readFacts(row.offer_facts);
    seen.add(row.id);
  }
  return page as Page<Profile>;
}
function notice(error:unknown):string{
  if(error instanceof LiveError&&[401,403,404].includes(error.status))return 'Access denied for this workspace.';
  if(error instanceof UnverifiedContext)return 'Context is unavailable because the response could not be verified.';
  return 'Service temporarily unavailable. Try again later.';
}
function documentPath(id:string){return `/app/discover/edit?document=${encodeURIComponent(id)}#offer-documents`;}
function factItem(fact:Fact,source:{kind:'profile'|'document';id:string},approved:boolean):ContextItem{
  return {id:`fact:${source.kind}:${source.id}:${fact.id}`,label:approved?'Approved offer fact':'Candidate offer fact',
    title:fact.field,detail:fact.value,status:approved?'approved':'candidate',
    path:source.kind==='profile'?`/app/overview?profile=${encodeURIComponent(source.id)}`:documentPath(source.id)};
}

/** Read-only, scope-owned context. No storage, provider work, polling or subscriptions. */
export async function loadDiscussionContext(client:LiveClient,session:SessionScope,options:{enabled:boolean;canViewOffer:boolean;canViewResults:boolean;signal:AbortSignal}):Promise<ContextSection[]>{
  if(!options.enabled||options.signal.aborted)return [];
  const current=session.current(),identity=session.identity();
  if(current.mode!=='live'||!current.actor||!current.workspace||!current.project||!session.token())return [];
  const scope={workspace:current.workspace,project:current.project};
  const signal=AbortSignal.any([options.signal,session.controller().signal]);
  const active=()=>!signal.aborted&&session.isCurrent(identity)&&!!session.token();
  const guard=()=>{if(!active())throw new LiveCancelled('scope changed');};
  // Existing run/usage clients capture the session themselves. This boundary also
  // carries the caller's lifetime and rejects delayed data from transports ignoring abort.
  const scopedClient:LiveClient={...client,async request<T>(request:LiveRequest):Promise<T>{
    guard();check((request.method??'GET')==='GET'&&request.scope===identity);
    const value=await client.request<T>({...request,method:'GET',signal});
    guard();return value;
  }};
  const root=`/v1/workspaces/${encodeURIComponent(scope.workspace)}/projects/${encodeURIComponent(scope.project)}`;
  const read=(path:string)=>scopedClient.request<unknown>({path,method:'GET',token:session.token(),scope:identity,signal});
  const section=async(title:string,load:()=>Promise<Omit<ContextSection,'title'>>):Promise<ContextSection>=>{
    try{return {title,...await load()};}
    catch(error){return {title,items:[],notice:notice(error)};}
  };
  let stop=()=>{};
  const stopped=new Promise<ContextSection[]>(resolve=>{stop=()=>resolve([]);signal.addEventListener('abort',stop,{once:true});});
  try{
    const sections:Promise<ContextSection>[]=[];
    if(options.canViewOffer){
      const documents=read(`${root}/offer-documents?offset=0&limit=${PAGE_SIZE}`).then(value=>readDocuments(value,scope));
      sections.push(section('Documents & outputs',async()=>{
        const page=await documents;
        return {items:page.items.map(row=>({id:`document:${row.id}`,label:'Offer document',title:row.filename,status:row.status,path:documentPath(row.id)})),
          ...(page.total>page.items.length?{notice:'Only recent documents are shown. Open the offer for all documents.'}:
            page.items.length===0?{notice:'No offer documents yet.'}:{})};
      }));
      sections.push(section('Offer facts',async()=>{
        const [documentPage,project,head]=await Promise.all([documents,read(root).then(value=>readProject(value,scope)),
          read(`${root}/icp-versions?offset=0&limit=${PAGE_SIZE}`).then(value=>readProfiles(value,scope,0))]);
        let profiles=head.items;
        if(head.total>head.items.length){
          const offset=Math.max(head.items.length,head.total-PAGE_SIZE);
          const tail=readProfiles(await read(`${root}/icp-versions?offset=${offset}&limit=${PAGE_SIZE}`),scope,offset);
          check(tail.total===head.total);
          profiles=[...head.items,...tail.items];
          check(new Set(profiles.map(row=>row.id)).size===profiles.length);
        }
        const activeProfile=profiles.find(row=>row.id===project.active_icp_version_id);
        const latest=profiles.reduce<Profile|undefined>((best,row)=>!best||row.number>best.number?row:best,undefined);
        const selected=[...(activeProfile?[activeProfile]:[]),...(latest&&latest.id!==activeProfile?.id?[latest]:[])];
        const items:ContextItem[]=[];
        for(const row of selected){
          const approved=row.id===project.active_icp_version_id&&row.status==='approved'&&row.is_current===true&&
            row.basis_status==='current'&&row.basis_offer_revision===project.offer_revision&&text(row.approved_by)&&date(row.approved_at);
          for(const fact of row.offer_facts)items.push(factItem(fact,{kind:'profile',id:row.id},
            approved&&fact.approved===true&&['user_entered','document_excerpt'].includes(fact.provenance)));
        }
        for(const document of documentPage.items){
          if(document.status==='ready')for(const fact of document.fact_candidates??[])items.push(factItem(fact,{kind:'document',id:document.id},false));
        }
        const partial=documentPage.total>documentPage.items.length||head.total>profiles.length||items.length>FACT_LIMIT||
          Boolean(project.active_icp_version_id&&!activeProfile);
        return {items:items.slice(0,FACT_LIMIT),...(partial?{notice:'Some offer facts are not shown. Open the offer or profile for the full context.'}:
          items.length===0?{notice:'No offer facts available.'}:{})};
      }));
    }
    sections.push(section('Recent research runs',async()=>{
      const raw=await listRuns({client:scopedClient,session,workspaceId:scope.workspace,projectId:scope.project,apiBaseUrl:''},0,10);
      const page=readPage(raw,0,10),seen=new Set<string>();
      const items=page.items.map(item=>{
        const row=scopedRow(item,scope);
        check(identifier(row.id)&&!seen.has(row.id)&&runStatuses.has(String(row.status))&&date(row.created_at));
        seen.add(row.id);
        return {id:`run:${row.id}`,label:'Research run',title:row.created_at,status:String(row.status),path:`/app/discover/${encodeURIComponent(row.id)}`};
      });
      return {items,...(page.total>items.length?{notice:'Only recent research runs are shown. Open research for all runs.'}:
        items.length===0?{notice:'No research runs yet.'}:{})};
    }));
    if(options.canViewResults)sections.push(section('Results summary',async()=>{
      const period=utcMonth(),value=await getUsage(scopedClient,session,period.from,period.to);
      check(object(value)&&value.workspace_id===scope.workspace&&value.project_id===scope.project&&
        date(value.from)&&date(value.to)&&Date.parse(value.from)===Date.parse(period.from)&&Date.parse(value.to)===Date.parse(period.to)&&date(value.as_of)&&
        count(value.accepted_company_count)&&count(value.eligible_contactable_company_count)&&
        value.eligible_contactable_company_count<=value.accepted_company_count&&value.includes_partial_runs===true&&Array.isArray(value.categories));
      return {items:[{id:`results:${scope.project}`,label:'Results summary',title:'New accepted companies / Contactable accepted companies',
        detail:`${value.accepted_company_count} / ${value.eligible_contactable_company_count} · ${period.from.slice(0,10)} – ${period.to.slice(0,10)} UTC`,
        status:'snapshot',path:'/app/results'}],notice:'Current calendar month in UTC. Counts include partial runs.'};
    }));
    const result=await Promise.race([Promise.all(sections),stopped]);
    return active()?result:[];
  }finally{signal.removeEventListener('abort',stop);}
}
