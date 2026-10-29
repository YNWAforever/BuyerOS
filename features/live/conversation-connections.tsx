'use client';
import {useEffect,useMemo,useRef,useState} from 'react';
import type {LiveClient} from '@/services/live/client';
import {LiveCancelled} from '@/services/live/client';
import type {SessionScope} from '@/services/live/session';
import type {SelectedSource} from '@/services/live/discussions';
import {scopedConnections,driveNotice,driveReadNotice,driveNotices,type DriveStatus,type DriveFolder} from '@/services/live/conversation-connections';

type Props={client:LiveClient;session:SessionScope;t:(text:string)=>string;selected:SelectedSource[];onSource:(source:SelectedSource,selected:boolean)=>void;readOnly:boolean};
export function DriveConnections({client,session,t,selected,onSource,readOnly}:Props){
  const identity=session.identity(),api=useMemo(()=>scopedConnections(client,session,identity),[client,session,identity]);
  const [status,setStatus]=useState<DriveStatus|null>(null),[candidates,setCandidates]=useState<DriveFolder[]|null>(null),[chosen,setChosen]=useState<string[]>([]),[items,setItems]=useState<SelectedSource[]>([]),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
  const mounted=useRef(true),pending=useRef(false);
  const generation=useRef(0);
  const current=()=>mounted.current&&session.isCurrent(identity)&&!!session.token();
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  async function reload(){
    if(pending.current)return;pending.current=true;const read=++generation.current;api.refresh();setBusy(true);setNotice('');setCandidates(null);setItems([]);setStatus(null);
    try{const row=await api.status();if(current()&&read===generation.current){setStatus(row);setChosen(row.folders.map(folder=>folder.id));}const sources=row.connected&&row.available?await api.items():[];if(current()&&read===generation.current)setItems(sources);}
    catch(error){if(current()&&read===generation.current&&!(error instanceof LiveCancelled))setNotice(driveReadNotice(error));}
    finally{pending.current=false;if(current())setBusy(false);}
  }
  useEffect(()=>{let active=true;const read=++generation.current;void (async()=>{try{const row=await api.status();if(active&&session.isCurrent(identity)&&read===generation.current){setStatus(row);setChosen(row.folders.map(folder=>folder.id));}const sources=row.connected&&row.available?await api.items():[];if(active&&session.isCurrent(identity)&&read===generation.current)setItems(sources);}catch(error){if(active&&read===generation.current&&!(error instanceof LiveCancelled))setNotice(driveReadNotice(error));}})();return()=>{active=false;};},[api,session,identity]);
  async function change(action:()=>Promise<DriveStatus>){
    if(pending.current||!status?.can_manage)return;pending.current=true;++generation.current;setBusy(true);setNotice('');
    try{const row=await action();if(!current())return;setStatus(row);setCandidates(null);setChosen(row.folders.map(folder=>folder.id));setItems([]);setNotice('Google Drive connection updated. Reload available items.');}
    catch(error){if(current()&&!(error instanceof LiveCancelled))setNotice(driveNotice(error));}
    finally{pending.current=false;if(current())setBusy(false);}
  }
  async function chooseFolders(){
    if(pending.current)return;pending.current=true;setBusy(true);setNotice('');
    try{const rows=await api.folders();if(current())setCandidates([...rows,...(status?.folders??[]).filter(folder=>!rows.some(row=>row.id===folder.id))]);}
    catch(error){if(current()&&!(error instanceof LiveCancelled))setNotice(driveReadNotice(error));}
    finally{pending.current=false;if(current())setBusy(false);}
  }
  async function selectSource(source:SelectedSource,selected:boolean){
    if(readOnly||pending.current)return;
    if(!selected){onSource(source,false);return;}
    pending.current=true;setBusy(true);setNotice('');api.refresh();
    try{const rows=await api.items();if(current()){setItems(rows);if(rows.some(row=>row.id===source.id))onSource(source,true);else setNotice('Selected sources are unavailable or not approved. Refresh project context and review your selection.');}}
    catch(error){if(current()&&!(error instanceof LiveCancelled)){setItems([]);setNotice(driveReadNotice(error));}}
    finally{pending.current=false;if(current())setBusy(false);}
  }
  return <section className="live-drive" aria-label={t('Google Drive')}>
    <h3>{t('Google Drive')}</h3>
    <p>{t('Read-only · Fimmick OAuth · approved folders only')}</p>
    <p>{t('HK residency preferred. File content is used only in request memory; no content cache.')}</p>
    <p role="status">{t(notice||(!status?'Loading Google Drive…':!status.available?driveNotices.unavailable:status.connected?'Google Drive connected':'Google Drive not connected'))}</p>
    <button type="button" disabled={busy} onClick={()=>void reload()}>{t('Reload Google Drive')}</button>
    {status&&!status.available&&notice&&notice!==driveNotices.unavailable&&<p>{t('Google Drive is unavailable. Ask a workspace admin to check the connection.')}</p>}
    {status?.can_manage&&<>
      {status.connected?<><button type="button" disabled={busy||!status.available} onClick={()=>void chooseFolders()}>{t('Choose approved folders')}</button><button type="button" disabled={busy} onClick={()=>void change(()=>api.disconnect(status.version))}>{t('Disconnect Google Drive')}</button></>:<button type="button" disabled={busy||!status.available} onClick={()=>void change(()=>api.connect(status.version))}>{t('Connect Google Drive')}</button>}
      {candidates&&<fieldset disabled={busy}><legend>{t('Approved Google Drive folders')}</legend>
        {!candidates.length&&<p>{t('No Google Drive folders are available.')}</p>}
        {candidates.map((folder,index)=><label key={folder.id}><input type="checkbox" checked={chosen.includes(folder.id)} disabled={!chosen.includes(folder.id)&&chosen.length>=20} onChange={event=>setChosen(rows=>event.target.checked?[...rows,folder.id]:rows.filter(id=>id!==folder.id))}/>{t(folder.label)} {index+1}<small>{folder.id}</small></label>)}
        <p>{t('Choose up to 20 folders. Changing approvals invalidates previous Drive selections.')}</p>
        <button type="button" onClick={()=>void change(()=>api.approve(status.version,chosen))}>{t('Save approved folders')}</button>
      </fieldset>}
    </>}
    {status?.connected&&status.available&&<><p>{t('Approved Google Drive folders')}: {status.folders.length}</p>
      {!items.length&&<p>{t('No approved Google Drive items are available. Reload after an admin approves folders.')}</p>}
      {items.map((item,index)=><label key={item.id}><input type="checkbox" disabled={readOnly||busy} checked={selected.some(source=>source.id===item.id)} onChange={event=>void selectSource(item,event.target.checked)}/>{t(item.label)} {index+1}<small>{item.id.split(':').at(-1)}</small></label>)}
    </>}
  </section>;
}
