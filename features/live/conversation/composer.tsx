'use client';
import {useLayoutEffect,useRef,useState,type KeyboardEvent} from 'react';
import {ArrowUp,Building2,Paperclip,Sparkles} from 'lucide-react';
import type {ConversationDrafts} from './draft';
import type {TurnCapability} from './types';

export type ComposerChip={key:string;label:string;prompt:string;skillId:string|null};
export type ComposerAttachment={
  visible:boolean;busy:boolean;percent:number;label:string;
  notice:string;retryable:boolean;onFile:(file:File)=>void;onRetry:()=>void;
};
type Props={
  t:(value:string)=>string;
  threadKey:string;
  drafts:ConversationDrafts;
  canWrite:boolean;
  sending:boolean;
  projectName:string|null;
  companyName:string|null;
  chips:ComposerChip[];
  capability:TurnCapability;
  capabilityNotice:string;
  onRetryCapability:()=>void;
  sendFailed:boolean;
  notice:string;
  attachment:ComposerAttachment|null;
  onSend:(text:string,clientMessageId:string,skillId:string|null)=>Promise<boolean>;
};
/** Composer owns its unsent text and the exact-once id for an uncertain retry. */
export function ConversationComposer({t,threadKey,drafts,canWrite,sending,projectName,companyName,chips,capability,capabilityNotice,onRetryCapability,sendFailed,notice,attachment,onSend}:Props){
  const [text,setText]=useState(()=>drafts.read(threadKey)?.text??'');
  const [pending,setPending]=useState(false);
  const [currentSkill,setCurrentSkill]=useState<string|null>(null);
  const area=useRef<HTMLTextAreaElement>(null);
  const busy=sending||pending;
  useLayoutEffect(()=>{
    const node=area.current;if(!node)return;
    node.style.height='auto';node.style.height=`${Math.min(node.scrollHeight,192)}px`;
  },[text]);
  function change(value:string){
    setText(value);
    setCurrentSkill(null);
    drafts.write(threadKey,value);
  }
  async function submit(raw:string,skillId:string|null){
    if(busy||!canWrite||!raw.trim())return;
    // Persist before the call so a reload or a lost response keeps the same id.
    const draft=drafts.write(threadKey,raw);
    if(!draft)return;
    setPending(true);
    try{
      if(await onSend(raw,draft.clientMessageId,skillId)){drafts.clear(threadKey);setText('');setCurrentSkill(null);}
    }finally{setPending(false);}
  }
  function onKeyDown(event:KeyboardEvent<HTMLTextAreaElement>){
    if(event.key==='Enter'&&!event.shiftKey&&!event.nativeEvent.isComposing){event.preventDefault();void submit(text,currentSkill);}
  }
  const slashMatch=/^\/(\S*)$/.exec(text),slashOpen=slashMatch!==null,slash=slashMatch?.[1]??'';
  const filtered=slashOpen?chips.filter(chip=>!slash||chip.label.toLowerCase().includes(slash.toLowerCase())||chip.prompt.toLowerCase().includes(slash.toLowerCase())):chips;
  return <section className="conversation-compose" aria-label={t('Message composer')}>
    {capabilityNotice&&<p className="conversation-compose-notice" role="status">{t(capabilityNotice)}{capability==='unavailable'&&<button type="button" onClick={onRetryCapability}>{t('Retry')}</button>}</p>}
    {notice&&<p className="conversation-compose-notice" role="status">{t(notice)}</p>}
    {attachment?.notice&&<p className="conversation-compose-notice" role="status">{attachment.notice}
      {attachment.retryable&&<button type="button" onClick={attachment.onRetry}>{t('Retry attachment')}</button>}</p>}
    {capability==='absent'&&<p className="conversation-compose-note">{t('Continuous replies are unavailable here. Your messages are saved as notes.')}</p>}
    {!drafts.available&&<p className="conversation-compose-note">{t('This browser will not keep unsent text after reload.')}</p>}
    {(text.trim()===''||slashOpen)&&chips.length>0&&<div className="conversation-chips" role="group" aria-label={t('Quick actions')} data-skill-ids={chips.some(chip=>chip.skillId)?'ready':'pending'}>
      {filtered.slice(0,8).map(chip=><button type="button" key={chip.key} disabled={busy||!canWrite} onClick={()=>void submit(chip.prompt,chip.skillId)}><Sparkles size={13} aria-hidden="true"/>{t(chip.label)}</button>)}
    </div>}
    <div className="conversation-compose-box">
      <div className="conversation-compose-context"><span className="conversation-project">{projectName??t('This project')}</span>{companyName&&<span className="conversation-company" aria-label={t('Linked company')}><Building2 size={12} aria-hidden="true"/>{companyName}</span>}{capability==='absent'&&<span className="pill gray">{t('Notes only')}</span>}</div>
      {attachment?.busy&&<div role="progressbar" aria-label={attachment.label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={attachment.percent}
        style={{height:4,width:'100%',background:'var(--buyeros-border)',borderRadius:2,overflow:'hidden',marginTop:2}}>
        <span style={{display:'block',height:'100%',width:`${attachment.percent}%`,background:'var(--buyeros-accent)',transition:'width .2s'}}/>
      </div>}
      <label className="conversation-sr" htmlFor="conversation-message">{t('Message BuyerOS')}</label>
      <textarea id="conversation-message" ref={area} rows={2} maxLength={4000} value={text} disabled={!canWrite}
        aria-describedby="conversation-compose-help" placeholder={t('Ask about this project, or choose a quick action')}
        onChange={event=>change(event.target.value)} onKeyDown={onKeyDown}/>
      <div className="conversation-compose-actions">
        <small id="conversation-compose-help">{t('Enter to send · Shift+Enter for a new line')}</small>
        {attachment?.visible&&!attachment.busy&&<label style={{display:'inline-flex',alignItems:'center',cursor:canWrite?'pointer':'default',padding:'0 4px'}}>
          <Paperclip size={16} aria-hidden="true"/>
          <input type="file" className="conversation-sr" accept=".pdf,.txt,.md,.pptx"
            aria-label={t('Attach document')} disabled={!canWrite}
            onChange={event=>{const file=event.target.files?.[0];event.target.value='';if(file)attachment.onFile(file);}}/>
        </label>}
        {sendFailed&&<button type="button" className="conversation-retry" disabled={busy||!canWrite} onClick={()=>void submit(text,currentSkill)}>{t('Retry send')}</button>}
        <button type="button" className="live-primary conversation-send" disabled={busy||!canWrite||!text.trim()} aria-label={t(busy?'Sending…':'Send message')} onClick={()=>void submit(text,currentSkill)}>
          <ArrowUp size={16} aria-hidden="true"/>{t(busy?'Sending…':'Send')}
        </button>
      </div>
    </div>
  </section>;
}
