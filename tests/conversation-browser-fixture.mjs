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
export const buyerId='ae000000-0000-4000-8000-000000000001';
export const buyerThreadId='af000000-0000-4000-8000-000000000001';
export const buyerTurnId='ba000000-0000-4000-8000-000000000001';
export const buyerDecisionTurnId='bb000000-0000-4000-8000-000000000001';
export const buyerProposalId='bc000000-0000-4000-8000-000000000001';
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
export const buyerCitationId=`buyer:${buyerId}`;
function buyerAssistantParts(){
 return [{kind:'text',text:'Here is what we can verify about DeltaGrid.'},
  {kind:'citations',items:[{id:buyerCitationId,label:'DeltaGrid',kind:'buyer'}]},
  {kind:'proposal',proposal_id:buyerProposalId,capability:'xverum.enrich_company',title:'Enrich company',
   rationale:'Verified contact and channel evidence is needed before outreach.',requires_approval:true,
   arguments_preview:{company_id:buyerId,buyer_id:buyerId},
   cost:{kind:'provider_credits',amount:'0',unit:'credits',may_incur_provider_charges:true,known:false}}];
}
/** Thread-first "Discuss this company" response: buyer link, buyer citation, always-approved enrichment proposal. */
export function buyerConversation(){
 const user={id:'bd000000-0000-4000-8000-000000000001',seq:1,role:'user',text:'Discuss this company and what to verify before outreach.',
  client_message_id:'be000000-0000-4000-8000-000000000001',turn_id:buyerTurnId,created_at:at,parts:[]};
 const parts=buyerAssistantParts();
 const assistant={id:'bf000000-0000-4000-8000-000000000001',seq:2,role:'assistant',text:'Here is what we can verify about DeltaGrid.',
  client_message_id:null,turn_id:buyerTurnId,created_at:at,parts};
 return {thread:{id:buyerThreadId,version:1,templateId:'check-company',title:'DeltaGrid company discussion',
   createdAt:Date.parse(at),updatedAt:Date.parse(at),access:'owner',shareCount:0,buyerId,
   messages:[user,assistant],sources:[],runs:[]},
  turn:{id:buyerTurnId,status:'needs_approval',parts,notices:[]}};
}
/** Terminal configuration outcome after approving the proposal-only capability. */
export function terminalBuyerConversation(){
 const base=buyerConversation();
 const notice={kind:'notice',code:'XVERUM_DISPATCH_NOT_ENABLED',
  message:'Company enrichment cannot run until Xverum dispatch is enabled by an administrator. Nothing was executed.'};
 const tool={kind:'tool_activity',call_id:buyerDecisionTurnId,capability:'xverum.enrich_company',title:'Enrich company',
  state:'failed',started_at:at,finished_at:at,error_code:'XVERUM_DISPATCH_NOT_ENABLED'};
 const continuation={id:'c0000000-0000-4000-8000-000000000001',seq:3,role:'assistant',
  text:'Company enrichment cannot run until Xverum dispatch is enabled by an administrator. Nothing was executed.',
  client_message_id:null,turn_id:buyerDecisionTurnId,created_at:at,parts:[notice,tool]};
 return {thread:{...base.thread,version:2,messages:[...base.thread.messages,continuation]},
  turn:{id:buyerDecisionTurnId,status:'failed',parts:[notice,tool],notices:[notice]}};
}
export function newConversation(firstText='Research this buyer'){ const user={id:'b4000000-0000-4000-8000-000000000001',seq:1,role:'user',text:firstText,
  client_message_id:clientMessageId,turn_id:newTurnId,created_at:at,parts:[]};
 const assistant={id:'b5000000-0000-4000-8000-000000000001',seq:2,role:'assistant',text:'Here is the grounded brief.',
  client_message_id:null,turn_id:newTurnId,created_at:at,parts:[{kind:'text',text:'Here is the grounded brief.'},
   {kind:'citations',items:[{id:citationId,label:'Offer document',kind:'document',href:`/app/discover/edit?document=${documentId}`}]}]};
 return {thread:{id:newThreadId,version:1,templateId:'custom',title:firstText.slice(0,80),createdAt:Date.parse(at),updatedAt:Date.parse(at),
   access:'owner',shareCount:0,messages:[user,assistant],sources:[],runs:[]},
  turn:{id:newTurnId,status:'completed',parts:assistant.parts,notices:[]}};
}
export const streamTurnId='c4000000-0000-4000-8000-000000000001';
export function userRow({id,seq,text,turnId=null}){return {id,seq,role:'user',text,client_message_id:null,turn_id:turnId,created_at:at,parts:[]};}
export function assistantRow({id,seq,text,turnId,parts}){return {id,seq,role:'assistant',text,client_message_id:null,turn_id:turnId,created_at:at,parts};}
export function threadWith({messages=studioThread.messages,version=studioThread.version,access='owner'}){
  return {...studioThread,version,access,messages,title:studioThread.title};
}
/** `text/event-stream` body in the API envelope shape `{seq, turn_id, kind, payload}`. */
export function sse(events){
  return events.map(([seq,event,payload])=>`event: ${event}\ndata: ${JSON.stringify({seq,turn_id:streamTurnId,kind:event,payload})}\n\n`).join('');
}
export const browserEntry=`
import React,{useState,useSyncExternalStore} from 'react';
import {createRoot} from 'react-dom/client';
import {SessionScope} from '/services/live/session.ts';
import {createLiveClient} from '/services/live/client.ts';
import {LiveConversation} from '/features/live/discussion-workspace.tsx';
import {DiscussCompanyButton} from '/features/live/conversation/company-discussion.tsx';
import {LiveNavigation} from '/features/live/navigation.tsx';
import {LiveFrame,LiveTopbar} from '/features/live/shell.tsx';
import {ScopeSwitcher} from '/features/live/scope-switcher.tsx';
import {AccountMenu} from '/features/live/account-menu.tsx';
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
 const shell=initial.searchParams.get('shell')==='1';
 const frame=conversation=><LiveFrame t={t} pathname={path} conversationHome={enabled}
   navigation={<LiveNavigation t={t} navigate={navigate} pathname={path} authorized={true} projectKnown={true} canEdit={true} projectActive={true} canCreate={true} conversationHome={enabled}/>}
   scope={<ScopeSwitcher t={t} workspace="${workspace}" project="${project}" workspaces={{kind:'ready',items:[{id:'${workspace}',name:'FIMMICK',roles:['workspace_admin']}]}}
     projects={{kind:'ready',items:[{id:'${project}',name:'Fixture project'}]}} authorized canCreate accessChecking={false} accessError="" notice=""
     onWorkspace={()=>{}} onProject={()=>{}} onNewProject={()=>{}} onCheckAccess={()=>{}}/>}
   footer={<AccountMenu t={t} email="owner@example.test" workspaceName="FIMMICK" roles={['workspace_admin']} authorized locale={locale}
     onLocale={value=>setLocale(value)} localeSaving={false} localeDisabled={false} accessDetails={null} accessChecking={false} accessError="" diagnostic={null}
     onRetryAccess={()=>{}} onSignOut={()=>{}}/>}
   header={<LiveTopbar t={t} pathname={path} projectName="Fixture project" conversationHome={enabled} hidePageTitle={path==='/app'||path.startsWith('/app/discussions')}/>}
   hideHeading={path==='/app'||path.startsWith('/app/discussions')}>{conversation}</LiveFrame>;
 const conversation=<><LiveConversation enabled={enabled} session={session} client={client} pathname={path} locale={locale} t={t} navigate={navigate} canViewOffer={offerAccess} canViewResults={true}/></>;
 if(shell&&enabled)return <>{frame(conversation)}</>;
 return <><label>Fixture project<select aria-label="Fixture project" value={snapshot.scope.project||''} onChange={e=>session.next({project:e.target.value})}><option value="${project}">A</option><option value="project-b">B</option></select></label>
 <button onClick={()=>{session.setToken(undefined);session.next({actor:'actor-b',workspace:'${workspace}',project:'${project}'});session.setToken('browser-second-actor');}}>Second actor</button>
 <button onClick={()=>{session.next({workspace:'workspace-b',project:'project-b'});}}>Second workspace</button>
 <button onClick={()=>setLocale(locale==='en'?'zh-HK':'en')}>Change language</button>
 <button onClick={()=>navigate('/app')}>Fixture home</button><button onClick={()=>setOfferAccess(false)}>Revoke offer access</button><output id="fixture-path" style={{display:'block',maxWidth:'100%',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{path}</output>
 <DiscussCompanyButton client={client} session={session} t={t} locale={locale} buyerId="${buyerId}" buyerName="DeltaGrid" navigate={navigate}/>
 <LiveNavigation t={t} navigate={navigate} pathname={path} authorized={true} projectKnown={true} canEdit={true} projectActive={true} canCreate={true} conversationHome={enabled}/>
 {conversation}</>;
}
createRoot(document.getElementById('root')).render(<App/>);
`;
