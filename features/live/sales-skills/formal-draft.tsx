import {useState} from 'react';
import {loadDraftContext} from '@/services/live/drafts';
import {salesOutputs} from '@/services/live/sales-outputs';
import type {SalesSchema as S} from '@/services/live/sales-transport';
import {salesError,type SalesProps} from './workspace';
import {nativePath} from './output-panel';
export function FormalDraft({client,session,t,navigate,output}:{output:S['OutputVersion']}&Omit<SalesProps,'locale'>){
 const api=salesOutputs(client,session),buyers=output.citations.filter(s=>s.kind==='buyer');
 const [buyer,setBuyer]=useState(buyers.length===1?buyers[0].id:''),[context,setContext]=useState<Awaited<ReturnType<typeof loadDraftContext>>|null>(null),[recipient,setRecipient]=useState(''),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
 const recipients=context?.buyer.contacts.filter(c=>c.access_state==='visible'&&c.value&&c.validity==='provider_marked_valid'&&c.checked_at&&c.retention_until)??[];
 async function run(fn:()=>Promise<void>){if(busy)return;setBusy(true);try{await fn();}catch(e){if(session.isCurrent(api.identity)){setNotice(salesError(e));setContext(null);setRecipient('');}}finally{if(session.isCurrent(api.identity))setBusy(false);}}
 return <section><h3>{t('Create formal draft')}</h3>{notice&&<p role="alert">{t(notice)}</p>}<p>{t('Create a project draft for native review. Sending requires separate approval.')}</p>{buyers.length!==1&&<label>{t('Buyer')}<select value={buyer} onChange={e=>{setBuyer(e.target.value);setContext(null);setRecipient('');}}><option value="">{t('Choose')}</option>{buyers.map((b,i)=><option key={b.id} value={b.id}>{t('Buyer')} {i+1} · {t('Revision')} {b.version}</option>)}</select></label>}<button disabled={busy||!buyer} onClick={()=>void run(async()=>{const current=await loadDraftContext(client,session,buyer);if(session.isCurrent(api.identity)){setContext(current);setRecipient('');}})}>{t('Review eligible recipients')}</button>
 {context&&<>{!context.project.sender_identity&&<button onClick={()=>navigate('/app/settings')}>{t('Review sender identity')}</button>}<label>{t('Eligible recipient')}<select value={recipient} onChange={e=>setRecipient(e.target.value)}><option value="">{t('Choose')}</option>{recipients.map(c=><option key={c.id} value={c.id}>{c.value}</option>)}</select></label><button disabled={busy||!context.project.sender_identity||!recipient||!recipients.some(c=>c.id===recipient)} onClick={()=>void run(async()=>{const ref=await api.formalDraft(output.id,{recipient_id:recipient,expected_revision:output.revision});if(session.isCurrent(api.identity))navigate(nativePath(ref));})}>{t('Create formal draft')}</button></>}
 </section>;
}
