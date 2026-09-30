'use client';
import {useCallback,useEffect,useRef,useState} from 'react';
import type {components} from '@/services/generated/buyeros-api';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import {ActionIntent} from '@/services/live/action-intent';
import {createOperationClient} from '@/services/live/operations';
import {buyerFiltersForQuery,buyerOperationContext,type BuyerQuery} from '@/services/live/buyers';
import type {ReviewSelection} from '@/services/live/buyer-selection';
import {isAsyncJob} from './bulk-actions';
import {liveZh} from './locale';

type BuyerList=components['schemas']['BuyerList'];
type FilterPreset=components['schemas']['FilterPreset'];
export function LiveBuyerManagementControls({query,onApplyQuery,selection,canManage,onJob,locale='en'}:{
  query:BuyerQuery;onApplyQuery:(patch:Partial<BuyerQuery>)=>void;selection:ReviewSelection|null;canManage:boolean;onJob:(id:string)=>void;locale?:'en'|'zh-HK';
}){
  const t=useCallback((value:string)=>locale==='zh-HK'?(liveZh[value]||value):value,[locale]);
  const {session,client}=useWorkspaceSession(),scope=useSessionSnapshot().scope;
  const [lists,setLists]=useState<BuyerList[]>([]),[presets,setPresets]=useState<FilterPreset[]>([]);
  const [listName,setListName]=useState(''),[presetName,setPresetName]=useState('');
  const [listId,setListId]=useState(query.listId),[presetId,setPresetId]=useState('');
  const [busy,setBusy]=useState(false),[refresh,setRefresh]=useState(0);
  const [message,setMessage]=useState(''),[error,setError]=useState('');
  const createIntent=useRef(new ActionIntent<BuyerList>());
  const renameIntent=useRef(new ActionIntent<BuyerList>());
  const membershipIntent=useRef(new ActionIntent<components['schemas']['BulkResult']|components['schemas']['AsyncJob']>());
  const presetIntent=useRef(new ActionIntent<FilterPreset>());
  const workspace=scope.workspace,project=scope.project;
  useEffect(()=>{
    if(!workspace||!project)return;
    let active=true;
    void(async()=>{
      try{
        const op=createOperationClient(client),ctx=buyerOperationContext(session);
        const nextLists:BuyerList[]=[],nextPresets:FilterPreset[]=[];
        for(let offset=0;;){
          const page=await op.requestOperation('listBuyerLists',{path:{workspace_id:workspace,project_id:project},query:{offset,limit:100}},ctx);
          nextLists.push(...page.items);if(nextLists.length>=page.total)break;
          if(!page.items.length)throw new Error(t('Incomplete list page'));offset+=page.items.length;
        }
        for(let offset=0;;){
          const page=await op.requestOperation('listFilterPresets',{path:{workspace_id:workspace,project_id:project},query:{offset,limit:100}},ctx);
          nextPresets.push(...page.items);if(nextPresets.length>=page.total)break;
          if(!page.items.length)throw new Error(t('Incomplete preset page'));offset+=page.items.length;
        }
        if(active){setLists(nextLists);setPresets(nextPresets);setError('');}
      }catch(cause){if(active&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    })();
    return()=>{active=false;};
  },[client,session,workspace,project,refresh,t]);
  async function createList(){
    if(!canManage||!workspace||!project||!listName.trim()||busy)return;
    setBusy(true);setError('');setMessage('');
    try{
      const ctx=buyerOperationContext(session),name=listName.trim();
      const result=await createIntent.current.run(JSON.stringify({op:'createBuyerList',ctx:ctx.identity,name}),key=>
        createOperationClient(client).requestOperation('createBuyerList',{path:{workspace_id:workspace,project_id:project},header:{'Idempotency-Key':key},body:{name}},ctx));
      setListId(result.id);setListName('');setMessage(t('Created list {name}').replace('{name}',result.name));setRefresh(value=>value+1);
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    finally{setBusy(false);}
  }
  async function renameList(){
    const selectedList=lists.find(item=>item.id===listId);
    if(!canManage||!workspace||!listName.trim()||busy)return;
    if(!selectedList){setError(t('List is still loading. Retry when its count appears.'));return;}
    setBusy(true);setError('');setMessage('');
    try{
      const ctx=buyerOperationContext(session),name=listName.trim();
      const result=await renameIntent.current.run(JSON.stringify({op:'renameBuyerList',ctx:ctx.identity,listId,version:selectedList.version,name}),key=>
        createOperationClient(client).requestOperation('renameBuyerList',{
          path:{workspace_id:workspace,list_id:listId},
          header:{'Idempotency-Key':key,'If-Match':`"${selectedList.version}"`},body:{name},
        },ctx));
      setLists(previous=>previous.map(item=>item.id===result.id?result:item));
      setListName('');setMessage(t('Renamed list to {name}').replace('{name}',result.name));setRefresh(value=>value+1);
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    finally{setBusy(false);}
  }
  async function changeList(operation:'add'|'remove'){
    const selectedList=lists.find(item=>item.id===listId);
    if(!canManage||!workspace||!selection||busy)return;
    if(!selectedList){setError(t('List is still loading. Retry when its count appears.'));return;}
    setBusy(true);setError('');setMessage('');
    try{
      const ctx=buyerOperationContext(session),body={selection,operation};
      const result=await membershipIntent.current.run(JSON.stringify({op:'changeListMemberships',ctx:ctx.identity,listId,version:selectedList.version,body}),key=>
        createOperationClient(client).requestOperation('changeListMemberships',{path:{workspace_id:workspace,list_id:listId},header:{'Idempotency-Key':key,'If-Match':`"${selectedList.version}"`},body},ctx));
      if(isAsyncJob(result)){onJob(result.id);setMessage(t('{count} list changes queued. Review job progress below.').replace('{count}',String(result.requested)));}
      else{setMessage(`${t('{updated} updated; {blocked} blocked; {conflicts} conflicts.').replace('{updated}',String(result.updated)).replace('{blocked}',String(result.blocked)).replace('{conflicts}',String(result.conflicts))} ${result.results.filter(row=>row.status==='blocked'||row.status==='conflict').map(row=>`${row.id}: ${t(row.reason_code??row.status)}`).join('; ')}`);setRefresh(value=>value+1);}
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    finally{setBusy(false);}
  }
  async function savePreset(){
    if(!workspace||!project||!presetName.trim()||busy)return;
    setBusy(true);setError('');setMessage('');
    try{
      const ctx=buyerOperationContext(session),body={name:presetName.trim(),filters:buyerFiltersForQuery(query),sort:query.sort};
      const result=await presetIntent.current.run(JSON.stringify({op:'saveFilterPreset',ctx:ctx.identity,body}),key=>
        createOperationClient(client).requestOperation('saveFilterPreset',{path:{workspace_id:workspace,project_id:project},header:{'Idempotency-Key':key},body},ctx));
      setPresetId(result.id);setPresetName('');setMessage(t('Saved preset {name}').replace('{name}',result.name));setRefresh(value=>value+1);
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    finally{setBusy(false);}
  }
  function applyPreset(){
    const preset=presets.find(item=>item.id===presetId);
    if(!preset){setError(t('Preset is still loading. Retry when its name appears.'));return;}
    const fit=preset.filters.fit?.[0]??'',review=preset.filters.review?.[0]??'';
    if(preset.filters.list_id)setListId(preset.filters.list_id);
    onApplyQuery({q:preset.filters.q??'',fit:fit as BuyerQuery['fit'],review:review as BuyerQuery['review'],listId:preset.filters.list_id??'',sort:preset.sort});
    setMessage(t('Applied preset {name}; selection cleared.').replace('{name}',preset.name));
  }
  const listReady=lists.some(item=>item.id===listId);
  const presetReady=presets.some(item=>item.id===presetId);
  return <section className="panel" aria-label={t('Buyer lists and saved filters')}>
    <h3>{t('Lists and saved filters')}</h3>
    {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
    <div className="inline"><label>{t('Buyer list')} <select aria-label={t('Buyer list')} value={listId} onChange={event=>setListId(event.target.value)}><option value="">{t('Choose list')}</option>{lists.map(item=><option value={item.id} key={item.id}>{item.name} ({item.member_count})</option>)}</select></label>
      {canManage&&<><label>{t('List name')} <input aria-label={t('List name')} value={listName} onChange={event=>setListName(event.target.value)}/></label>
        <button type="button" disabled={busy||!listName.trim()} onClick={()=>void createList()}>{t('Create list')}</button>
        <button type="button" disabled={busy||!listReady||!listName.trim()} onClick={()=>void renameList()}>{t('Rename selected list')}</button>
        <button type="button" disabled={busy||!listReady||!selection} onClick={()=>void changeList('add')}>{t('Add selected to list')}</button>
        <button type="button" disabled={busy||!listReady||!selection} onClick={()=>void changeList('remove')}>{t('Remove selected from list')}</button></>}
      <button type="button" disabled={!listReady||busy} onClick={()=>onApplyQuery({listId})}>{t('Show list buyers')}</button>
      {query.listId&&<button type="button" onClick={()=>onApplyQuery({listId:''})}>{t('Show all buyers')}</button>}
    </div>
    <div className="inline"><label>{t('Saved filter')} <select aria-label={t('Saved filter')} value={presetId} onChange={event=>setPresetId(event.target.value)}><option value="">{t('Choose preset')}</option>{presets.map(item=><option value={item.id} key={item.id}>{item.name}</option>)}</select></label>
      <button type="button" disabled={!presetReady||busy} onClick={applyPreset}>{t('Apply saved filter')}</button>
      <label>{t('Preset name')} <input aria-label={t('Preset name')} value={presetName} onChange={event=>setPresetName(event.target.value)}/></label>
      <button type="button" disabled={busy||!presetName.trim()} onClick={()=>void savePreset()}>{t('Save current filter')}</button>
    </div>
  </section>;
}
