'use client';
import {useEffect,useRef} from 'react';
export type DirtyDecision='save'|'discard'|'cancel';
export async function guardDraftTransition({dirty,choose,save,proceed}:{dirty:boolean;choose:()=>Promise<DirtyDecision>;save:()=>Promise<void>;proceed:()=>Promise<void>}):Promise<boolean>{
  if(dirty){const decision=await choose();if(decision==='cancel')return false;if(decision==='save')await save();}
  await proceed();return true;
}
export function DraftDirtyDialog({decide,canSave,t,kind='draft',notice}:{decide:(value:DirtyDecision)=>void;canSave:boolean;t:(value:string)=>string;kind?:'draft'|'preparation';notice?:string}){
  const ref=useRef<HTMLDialogElement>(null);
  useEffect(()=>{const dialog=ref.current,previous=document.activeElement;dialog?.showModal();dialog?.querySelector<HTMLButtonElement>('[data-cancel]')?.focus();
    return()=>{dialog?.close();if(previous instanceof HTMLElement&&previous.isConnected)previous.focus();};},[]);
  return <dialog ref={ref} aria-labelledby="draft-dirty-title" onCancel={event=>{event.preventDefault();decide('cancel');}} style={{maxWidth:'min(32rem,90vw)',padding:'1.5rem',borderRadius:'1rem'}}>
    <h2 id="draft-dirty-title">{t(kind==='preparation'?'Unsaved preparation changes':'Unsaved draft changes')}</h2><p>{t(kind==='preparation'?'Save your changes, discard them, or stay with this preparation.':'Save your changes, discard them, or stay with this draft.')}</p>
    {notice&&<p>{notice}</p>}
    <div className="inline"><button type="button" disabled={!canSave} onClick={()=>decide('save')}>{t('Save')}</button><button type="button" onClick={()=>decide('discard')}>{t('Discard')}</button><button type="button" data-cancel onClick={()=>decide('cancel')}>{t('Cancel')}</button></div>
  </dialog>;
}
