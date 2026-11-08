// Browser-only synthetic project records; no production, provider or backend access.
export const workspace='a1000000-0000-4000-8000-000000000001';
export const project='a2000000-0000-4000-8000-000000000001';
export const documentId='a3000000-0000-4000-8000-000000000001';
export const runId='a4000000-0000-4000-8000-000000000001';
export const profileId='a5000000-0000-4000-8000-000000000001';
export const factId='a6000000-0000-4000-8000-000000000001';
export const threadId='a7000000-0000-4000-8000-000000000001';
export const turnId='a8000000-0000-4000-8000-000000000001';
export const proposalId='a9000000-0000-4000-8000-000000000001';
export const outputId='aa000000-0000-4000-8000-000000000001';
export const newThreadId='ab000000-0000-4000-8000-000000000001';
export const newTurnId='ac000000-0000-4000-8000-000000000001';
export const clientMessageId='ad000000-0000-4000-8000-000000000001';
export const citationId=`document:${documentId}`;
const at='2026-10-01T00:00:00.000Z';
export function contextResponse(url){
 const common={workspace_id:workspace,project_id:project,data_mode:'live',version:1};
 const fact={id:factId,field:'product',value:'PRIVATE_FACT_CONTENT',provenance:'document_excerpt',source_document_id:documentId,approved:true};
 const page=(items,limit)=>({items,total:items.length,limit,offset:0});
 if(url.pathname.endsWith('/conversation-threads'))return page([],50);
 if(url.pathname.endsWith('/offer-documents'))return page([{...common,id:documentId,filename:'project-evidence.pdf',status:'ready',fact_candidates:[fact]}],20);
 if(url.pathname.endsWith('/icp-versions'))return page([{...common,id:profileId,number:1,status:'approved',is_current:true,basis_status:'current',basis_offer_revision:1,approved_by:'reviewer',approved_at:'2026-10-01T00:00:00Z',offer_facts:[fact]}],20);
 if(url.pathname.endsWith('/runs'))return page([{...common,id:runId,created_at:'2026-10-01T00:00:00Z',status:'awaiting_reconciliation',company_count:30}],10);
 if(url.pathname.endsWith('/usage'))return {...common,from:url.searchParams.get('from'),to:url.searchParams.get('to'),as_of:new Date().toISOString(),accepted_company_count:4,eligible_contactable_company_count:2,includes_partial_runs:true,categories:[]};
 if(url.pathname.endsWith('/'+project))return {...common,id:project,status:'active',offer_revision:1,active_icp_version_id:profileId,name:'Fixture project'};
 return null;
}
export function envelope(data){return {data,data_mode:'live',request_id:'conversation-studio'};}
export const userMessage={id:'b1000000-0000-4000-8000-000000000001',seq:1,role:'user',text:'Research this buyer',
 client_message_id:clientMessageId,turn_id:turnId,created_at:at,parts:[]};
export const assistantParts=[
 {kind:'text',text:'Here is the brief.'},
 {kind:'citations',items:[{id:citationId,label:'Offer document',kind:'document',href:`/app/discover/edit?document=${documentId}`}]},
 {kind:'tool_activity',call_id:'call-1',capability:'sales-research',title:'Research buyer',state:'completed',
  started_at:'2026-10-01T00:00:30.000Z',finished_at:'2026-10-01T00:01:00.000Z'},
 {kind:'proposal',proposal_id:proposalId,capability:'sales-contacts',title:'Enrich buyer',
  rationale:'Needs verified contact evidence',requires_approval:true,cost:{currency:'USD',amount:0.1}},
 {kind:'output_link',title:'Research brief',href:`/app/documents/${outputId}`,
  output:{output_id:outputId,kind:'research_brief',revision:1,status:'saved'}},
];
export const assistantMessage={id:'b3000000-0000-4000-8000-000000000001',seq:2,role:'assistant',text:'Here is the brief.',
 client_message_id:null,turn_id:turnId,created_at:'2026-10-01T00:01:00.000Z',parts:assistantParts};
/** Saved workspace thread returned by GET /conversation-threads/{id}. */
export const studioThread={id:threadId,version:3,templateId:'custom',title:'Research buyer',
 createdAt:Date.parse(at),updatedAt:Date.parse(at)+60_000,access:'owner',shareCount:0,
 messages:[userMessage,assistantMessage],
 sources:[{id:citationId,label:'Offer document'}],runs:[]};
export const studioSummary={id:threadId,version:3,templateId:'custom',title:'Research buyer',
 createdAt:Date.parse(at),updatedAt:Date.parse(at)+60_000,access:'owner',shareCount:0,pinned:false,archived:false};
export function decisionTurn(){return {id:turnId,status:'completed',
 parts:[{kind:'notice',code:'DECISION_ACCEPTED',message:'Approved. The step is queued.'}],notices:[]};}
export function newConversation(firstText='Research this buyer'){
 const user={id:'b4000000-0000-4000-8000-000000000001',seq:1,role:'user',text:firstText,
  client_message_id:clientMessageId,turn_id:newTurnId,created_at:at,parts:[]};
 const assistant={id:'b5000000-0000-4000-8000-000000000001',seq:2,role:'assistant',text:'Here is the grounded brief.',
  client_message_id:null,turn_id:newTurnId,created_at:at,parts:[{kind:'text',text:'Here is the grounded brief.'},
   {kind:'citations',items:[{id:citationId,label:'Offer document',kind:'document',href:`/app/discover/edit?document=${documentId}`}]}]};
 return {thread:{id:newThreadId,version:1,templateId:'custom',title:firstText.slice(0,80),createdAt:Date.parse(at),updatedAt:Date.parse(at),
   access:'owner',shareCount:0,messages:[user,assistant],sources:[],runs:[]},
  turn:{id:newTurnId,status:'completed',parts:assistant.parts,notices:[]}};
}
export const browserEntry=`
import React,{useState,useSyncExternalStore} from 'react';
import {createRoot} from 'react-dom/client';
import {SessionScope} from '/services/live/session.ts';
import {createLiveClient} from '/services/live/client.ts';
import {LiveConversation} from '/features/live/discussion-workspace.tsx';
import {LiveNavigation} from '/features/live/navigation.tsx';
import {liveZh} from '/features/live/locale.ts';
const session=new SessionScope({mode:'live',actor:'actor-a',workspace:'${workspace}',project:'${project}'});session.setToken('browser-fixture-token');
const client=createLiveClient();window.fixtureSession=session;
const initial=new URL(location.href);const enabled=initial.searchParams.get('flag')!=='off';
function App(){
 const snapshot=useSyncExternalStore(session.subscribe,session.getSnapshot,session.getSnapshot);
 const [path,setPath]=useState(initial.searchParams.get('route')||'/app'),[locale,setLocale]=useState(initial.searchParams.get('locale')==='zh-HK'?'zh-HK':'en'),[offerAccess,setOfferAccess]=useState(true);
 const t=value=>locale==='zh-HK'?(liveZh[value]||value):value;
 const navigate=path=>{void session.transition(async()=>{
  const target=new URL(path,location.origin);target.searchParams.set('workspace',session.current().workspace);target.searchParams.set('project',session.current().project);
  window.lastDestination=target.pathname+target.search;setPath(target.pathname);
  const url=new URL(location.href);url.searchParams.set('route',target.pathname);history.replaceState(null,'',url);
 });};
 return <><label>Fixture project<select aria-label="Fixture project" value={snapshot.scope.project||''} onChange={e=>session.next({project:e.target.value})}><option value="${project}">A</option><option value="project-b">B</option></select></label>
 <button onClick={()=>{session.setToken(undefined);session.next({actor:'actor-b',workspace:'${workspace}',project:'${project}'});session.setToken('browser-second-actor');}}>Second actor</button>
 <button onClick={()=>{session.next({workspace:'workspace-b',project:'project-b'});}}>Second workspace</button>
 <button onClick={()=>setLocale(locale==='en'?'zh-HK':'en')}>Change language</button>
 <button onClick={()=>navigate('/app')}>Home</button><button onClick={()=>setOfferAccess(false)}>Revoke offer access</button><output id="fixture-path">{path}</output>
 <LiveNavigation t={t} navigate={navigate} pathname={path} authorized={true} projectKnown={true} canEdit={true} projectActive={true} canCreate={true} conversationHome={enabled}/>
 <LiveConversation enabled={enabled} session={session} client={client} pathname={path} locale={locale} t={t} navigate={navigate} canViewOffer={offerAccess} canViewResults={true}/></>;
}
createRoot(document.getElementById('root')).render(<App/>);
`;
