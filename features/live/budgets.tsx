'use client';
import {useEffect,useRef,useState} from 'react';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import {createOperationClient} from '@/services/live/operations';
import {ActionIntent} from '@/services/live/action-intent';
import type {SessionScope} from '@/services/live/session';
import type {components} from '@/services/generated/buyeros-api';

type Money=components['schemas']['Money'];
type Budget=components['schemas']['BudgetAccount'];
type Page=components['schemas']['BudgetAccountPage'];
function budgetContext(session:SessionScope){
  const captured=session.captureWriteContext();
  return {...captured,getToken:async()=>{const token=session.token();if(!token)throw new Error('Sign-in required');return token;},
    isCurrent:()=>session.isCurrent(captured.identity)};
}
const money=(value:Money)=>`${value.amount} ${value.currency}`;
const normalize=(value:string)=>/^(0|[1-9][0-9]{0,13})(\.[0-9]{1,6})?$/.test(value)?`${value.split('.')[0]}.${(value.split('.')[1]||'').padEnd(6,'0')}`:null;

export function BudgetSettings({workspace,isAdmin,t}:{workspace:string;isAdmin:boolean;t:(value:string)=>string}){
  const {session,client}=useWorkspaceSession(),scope=useSessionSnapshot();
  const [page,setPage]=useState<Page|null>(null),[offset,setOffset]=useState(0),[error,setError]=useState(''),[status,setStatus]=useState(''),[pending,setPending]=useState(false);
  const updateIntent=useRef(new ActionIntent<Budget>());
  useEffect(()=>{
    if(!session.token())return;
    let active=true;
    void (async()=>{
      try{
        const ctx=budgetContext(session);
        const value=await createOperationClient(client).requestOperation('listBudgets',
          {path:{workspace_id:workspace},query:{offset,limit:20}},ctx);
        if(active){setPage(value);setError('');}
      }catch(cause){if(active&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    })();
    return()=>{active=false;};
  },[client,session,workspace,offset,scope.identity]);
  async function update(row:Budget,amount:string,reason:string){
    const formatted=normalize(amount);
    if(!formatted){setError('Enter a nonnegative USD amount with up to six decimal places.');return;}
    if(reason.trim().length<3){setError('Enter a reason of at least three characters.');return;}
    setPending(true);setError('');setStatus('');
    try{
      const ctx=budgetContext(session);
      const body={approved_limit:{amount:formatted,currency:'USD' as const},reason:reason.trim()};
      const value=await updateIntent.current.run(JSON.stringify({identity:ctx.identity,id:row.id,version:row.version,body}),key=>
        createOperationClient(client).requestOperation('updateBudget',{
          path:{workspace_id:workspace,budget_id:row.id},
          header:{'Idempotency-Key':key,'If-Match':`"${row.version}"`},body},ctx));
      if(!ctx.isCurrent())return;
      setPage(current=>current?{...current,items:current.items.map(item=>item.id===value.id?value:item)}:current);
      setStatus('Budget limit saved.');
    }catch(e){if(!(e instanceof LiveCancelled))setError(describeLiveError(e));}finally{setPending(false);}
  }
  return <section aria-label={t('Budget settings')}><h3>{t('Budget settings')}</h3>
    <p>{t('Limits start at zero. Provider spending remains disabled until verified capabilities are activated.')}</p>
    {!page&&!error&&<p role="status">{t('Loading budgets…')}</p>}
    {page?.items.map(row=><BudgetRow key={row.id} row={row} isAdmin={isAdmin} pending={pending} t={t} onSave={update}/>)}
    {page&&<div className="inline"><button disabled={offset===0} onClick={()=>setOffset(value=>Math.max(0,value-20))}>{t('Previous')}</button>
      <span>{offset+1}–{Math.min(offset+20,page.total)} / {page.total}</span>
      <button disabled={offset+20>=page.total} onClick={()=>setOffset(value=>value+20)}>{t('Next')}</button></div>}
    {error&&<p role="alert">{t(error)}</p>}{status&&<p role="status">{t(status)}</p>}
  </section>;
}
function BudgetRow({row,isAdmin,pending,t,onSave}:{row:Budget;isAdmin:boolean;pending:boolean;t:(value:string)=>string;onSave:(row:Budget,amount:string,reason:string)=>Promise<void>}){
  const [amount,setAmount]=useState(row.approved_limit.amount),[reason,setReason]=useState('');
  const label=`${t(row.scope)} ${row.scope_id.slice(-8)} · ${t(row.category)} · ${row.period_start.slice(0,7)}`;
  return <div className="budget-row" style={{display:'grid',gap:'0.35rem',padding:'1rem 0',borderBottom:'1px solid #d9e1e8',overflowWrap:'anywhere'}}><strong>{label}</strong>
    <span>{t('Limit')}: {money(row.approved_limit)}</span>
    <span>{t('Settled')}: {money(row.settled)}</span>
    <span>{t('Reserved')}: {money(row.reserved)}</span>
    <span>{t('Carried')}: {money(row.carried_reserved)}</span>
    <span>{t('Remaining')}: {money(row.remaining)}</span>
    {row.effective_state==='frozen_pending_budget'&&<strong>{t('Frozen for new spending')}</strong>}
    {isAdmin&&<div className="inline" style={{flexWrap:'wrap'}}>
      <label>{t('Approved limit')} <input aria-label={`${t('Approved limit')} ${label}`} inputMode="decimal" value={amount} onChange={event=>setAmount(event.target.value)}/></label>
      <label>{t('Change reason')} <input aria-label={`${t('Change reason')} ${label}`} value={reason} onChange={event=>setReason(event.target.value)}/></label>
      <button disabled={pending||!normalize(amount)||reason.trim().length<3||normalize(amount)===row.approved_limit.amount} onClick={()=>void onSave(row,amount,reason)}>{t('Save limit')}</button>
    </div>}
  </div>;
}
