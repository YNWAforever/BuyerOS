import {useState} from 'react';
import type {SalesSchema as S} from '@/services/live/sales-transport';
import type {SalesOutputs} from '@/services/live/sales-outputs';
import {salesError} from './workspace';
export function NativeAction({output,api,t,onSaved}:{output:S['OutputVersion'];api:SalesOutputs;t:(v:string)=>string;onSaved:()=>void}){
 const [target,setTarget]=useState(''),[note,setNote]=useState(''),[approved,setApproved]=useState(false),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
 const buyers=output.native_refs.filter(r=>r.surface==='buyer');if(!buyers.length)return null;
 async function save(){const ref=buyers.find(r=>r.id===target);if(!ref||!approved||!note.trim()||busy)return;setBusy(true);try{await api.apply({id:api.actionId(JSON.stringify([output.id,output.revision,target,note])),capability:'buyers.review',arguments:{refs:[ref],purpose:'Save reviewed buyer note',output:{id:output.id,revision:output.revision},mutation:{note}},source_versions:[{id:output.id,version:output.revision,kind:'output',locator:'output:'+output.id,retention_class:'durable'}]},ref.revision);setNotice('Saved to buyer');onSaved();}catch(e){setNotice(salesError(e));}finally{setBusy(false);}}
 return <details><summary>{t('Save to buyer')}</summary><label>{t('Buyer')}<select value={target} onChange={e=>{setTarget(e.target.value);setApproved(false);}}><option value="">{t('Choose')}</option>{buyers.map(r=><option key={r.id} value={r.id}>{r.id}</option>)}</select></label><label>{t('Buyer note')}<textarea value={note} maxLength={20000} onChange={e=>{setNote(e.target.value);setApproved(false);}}/></label><label><input type="checkbox" checked={approved} onChange={e=>setApproved(e.target.checked)}/>{t('Selected changes will be visible to the project.')}</label><button disabled={busy||!approved||!target||!note.trim()} onClick={()=>void save()}>{t('Save to buyer')}</button>{notice&&<p role="status">{t(notice)}</p>}</details>;
}
