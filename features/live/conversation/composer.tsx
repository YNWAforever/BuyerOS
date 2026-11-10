'use client';
import {useLayoutEffect,useRef,useState,type KeyboardEvent} from 'react';
import {ArrowUp,Building2,Paperclip,Sparkles} from 'lucide-react';
import {UPLOAD_ACCEPT} from '@/services/live/document-upload';
import type {ConversationDrafts} from './draft';
import type {TurnCapability} from './types';
import {SKILL_MENU_EMPTY,SKILL_MENU_LABEL,commandInsertion,filterSkillCommands,
  groupSkillCommands,skillMenuKey,skillMoreLabel,visibleSkillCommands,type SkillCommand} from './skill-library';

export type ComposerChip={key:string;label:string;prompt:string;skillId:string|null};
export type ComposerAttachment={
  visible:boolean;busy:boolean;percent:number;label:string;
  notice:string;retryable:boolean;onFile:(file:File)=>void;onRetry:()=>void;
};
type Props={
  t:(value:string)=>string;
  locale:'en'|'zh-HK';
  threadKey:string;
  drafts:ConversationDrafts;
  canWrite:boolean;
  sending:boolean;
  projectName:string|null;
  companyName:string|null;
  chips:ComposerChip[];
  commands:SkillCommand[];
  capability:TurnCapability;
  capabilityNotice:string;
  onRetryCapability:()=>void;
  sendFailed:boolean;
  notice:string;
  attachment:ComposerAttachment|null;
  onSend:(text:string,clientMessageId:string,skillId:string|null)=>Promise<boolean>;
};
/** Composer owns its unsent text and the exact-once id for an uncertain retry. */
export function ConversationComposer({t,locale,threadKey,drafts,canWrite,sending,projectName,companyName,chips,commands,capability,capabilityNotice,onRetryCapability,sendFailed,notice,attachment,onSend}:Props){
  const [text,setText]=useState(()=>drafts.read(threadKey)?.text??'');
  const [pending,setPending]=useState(false);
  const [currentSkill,setCurrentSkill]=useState<string|null>(null);
  const [menuDismissed,setMenuDismissed]=useState(false);
  const [activeIndex,setActiveIndex]=useState(0);
  const area=useRef<HTMLTextAreaElement>(null);
  const busy=sending||pending;
  useLayoutEffect(()=>{
    const node=area.current;if(!node)return;
    node.style.height='auto';node.style.height=`${Math.min(node.scrollHeight,192)}px`;
  },[text]);
  function change(value:string){
    setText(value);
    setCurrentSkill(null);
    setMenuDismissed(false);
    setActiveIndex(0);
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
  function choose(command:SkillCommand|undefined){
    if(!command)return;
    const insertion=commandInsertion(command);
    if(!insertion)return;
    change(insertion.text);
    setCurrentSkill(insertion.skillId);
    setMenuDismissed(true);
    area.current?.focus();
  }
  function onKeyDown(event:KeyboardEvent<HTMLTextAreaElement>){
    if(menuOpen){
      const action=skillMenuKey(event.key,active,visible.length);
      if(action.type==='move'){event.preventDefault();setActiveIndex(action.index);return;}
      if(action.type==='close'){event.preventDefault();setMenuDismissed(true);area.current?.focus();return;}
      if(action.type==='select'){event.preventDefault();choose(visible[action.index]);return;}
      if(event.key==='Enter'){event.preventDefault();return;}
    }
    if(event.key==='Enter'&&!event.shiftKey&&!event.nativeEvent.isComposing){event.preventDefault();void submit(text,currentSkill);}
  }
  const slashMatch=/^\/(\S*)$/.exec(text),slashOpen=slashMatch!==null;
  const menuCandidate=slashOpen&&commands.length>0&&!menuDismissed;
  const menuOpen=menuCandidate;
  const matches=menuCandidate?filterSkillCommands(commands,slashMatch?.[1]??''):[];
  const {items:visible,more}=visibleSkillCommands(matches);
  const active=visible.length?Math.min(activeIndex,visible.length-1):-1;
  const menuGroups=groupSkillCommands(visible);
  const activeCommand=active>=0?visible[active]:null;
  // The textarea keeps the textbox role and focus; the combobox/listbox ARIA is spread
  // so assistive tech announces the owned listbox without changing the control role.
  const menuAria:Record<string,string|boolean|undefined>=menuOpen?{
    'aria-haspopup':'listbox','aria-expanded':true,'aria-controls':'conversation-skill-menu',
    'aria-activedescendant':activeCommand?`conversation-skill-option-${activeCommand.id}`:undefined,
  }:{};
  return <section className="conversation-compose" aria-label={t('Message composer')} style={{minWidth:0,maxWidth:'100%'}}>
    {capabilityNotice&&<p className="conversation-compose-notice" role="status">{t(capabilityNotice)}{capability==='unavailable'&&<button type="button" onClick={onRetryCapability}>{t('Retry')}</button>}</p>}
    {notice&&<p className="conversation-compose-notice" role="status">{t(notice)}</p>}
    {attachment?.notice&&<p className="conversation-compose-notice" role="status"><span style={{minWidth:0,overflowWrap:'anywhere'}}>{t(attachment.notice)}</span>
      {attachment.retryable&&<button type="button" onClick={attachment.onRetry}>{t('Retry attachment')}</button>}</p>}
    {capability==='absent'&&<p className="conversation-compose-note">{t('Continuous replies are unavailable here. Your messages are saved as notes.')}</p>}
    {!drafts.available&&<p className="conversation-compose-note">{t('This browser will not keep unsent text after reload.')}</p>}
    {text.trim()===''&&!slashOpen&&chips.length>0&&<div className="conversation-chips" role="group" aria-label={t('Quick actions')} data-skill-ids={chips.some(chip=>chip.skillId)?'ready':'pending'}>
      {chips.slice(0,8).map(chip=><button type="button" key={chip.key} disabled={busy||!canWrite} onClick={()=>void submit(chip.prompt,chip.skillId)}><Sparkles size={13} aria-hidden="true"/>{t(chip.label)}</button>)}
    </div>}
    <div className="conversation-compose-box" style={{minWidth:0,maxWidth:'100%',boxSizing:'border-box'}}>
      <div className="conversation-compose-context"><span className="conversation-project">{projectName??t('This project')}</span>{companyName&&<span className="conversation-company" aria-label={t('Linked company')}><Building2 size={12} aria-hidden="true"/>{companyName}</span>}{capability==='absent'&&<span className="pill gray">{t('Notes only')}</span>}</div>
      {attachment?.busy&&<div role="progressbar" aria-label={attachment.label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={attachment.percent}
        style={{height:4,width:'100%',maxWidth:'100%',minWidth:0,boxSizing:'border-box',background:'var(--buyeros-border)',borderRadius:2,overflow:'hidden',marginTop:2}}>
        <span style={{display:'block',height:'100%',width:`${attachment.percent}%`,maxWidth:'100%',background:'var(--buyeros-accent)',transition:'width .2s'}}/>
      </div>}
      {menuOpen&&<div style={{minWidth:0,maxWidth:'100%',border:'1px solid var(--buyeros-border)',borderRadius:'var(--buyeros-radius-small)',background:'var(--buyeros-surface)',padding:4,maxHeight:260,overflowY:'auto',boxSizing:'border-box'}}>
        <div role="listbox" id="conversation-skill-menu" aria-label={t(SKILL_MENU_LABEL)} style={{minWidth:0,maxWidth:'100%'}}>
          {menuGroups.map(group=><div role="group" key={group.categoryId} aria-label={group.label}>
            {group.items.map(command=>{
              const index=visible.indexOf(command),selected=index===active;
              return <div role="option" key={command.id} id={`conversation-skill-option-${command.id}`}
                aria-selected={selected} aria-disabled={!command.available}
                onMouseDown={event=>{event.preventDefault();if(command.available)choose(command);}}
                style={{display:'flex',flexDirection:'column',gap:1,minWidth:0,padding:'5px 7px',borderRadius:4,cursor:command.available?'pointer':'not-allowed',
                  background:selected?'var(--buyeros-accent-soft)':'transparent',opacity:command.available?1:.55,overflowWrap:'anywhere'}}>
                <span style={{fontSize:12,fontWeight:600}}>{command.label}</span>
                {!command.available&&<small style={{fontSize:11,color:'var(--buyeros-muted)'}}>{command.reason}</small>}
              </div>;
            })}
          </div>)}
        </div>
        {visible.length===0&&<p style={{margin:'4px 6px',fontSize:12,color:'var(--buyeros-muted)'}}>{t(SKILL_MENU_EMPTY)}</p>}
        {more>0&&<p style={{margin:'4px 6px 2px',fontSize:11,color:'var(--buyeros-muted)'}}>{skillMoreLabel(more,locale)}</p>}
      </div>}
      <label className="conversation-sr" htmlFor="conversation-message">{t('Message BuyerOS')}</label>
      <textarea id="conversation-message" ref={area} rows={2} maxLength={4000} value={text} disabled={!canWrite}
        aria-describedby="conversation-compose-help" placeholder={t('Ask about this project, or choose a quick action')}
        {...menuAria} onChange={event=>change(event.target.value)} onKeyDown={onKeyDown}/>
      <div className="conversation-compose-actions" style={{minWidth:0}}>
        <small id="conversation-compose-help">{t('Enter to send · Shift+Enter for a new line')}</small>
        {attachment?.visible&&!attachment.busy&&<label htmlFor="conversation-attach" style={{display:'inline-flex',alignItems:'center',flex:'0 1 auto',minWidth:0,maxWidth:'100%',cursor:canWrite?'pointer':'default',padding:'0 4px'}}>
          <Paperclip size={16} aria-hidden="true"/>
          {/* Zero-size anchored wrapper: the native input can never contribute intrinsic width. */}
          <span style={{position:'absolute',width:0,height:0,overflow:'hidden',clip:'rect(0 0 0 0)',whiteSpace:'nowrap'}}>
            <input id="conversation-attach" type="file" accept={UPLOAD_ACCEPT}
              aria-label={t('Attach document')} disabled={!canWrite}
              onChange={event=>{const file=event.target.files?.[0];event.target.value='';if(file)attachment.onFile(file);}}/>
          </span>
        </label>}
        {sendFailed&&<button type="button" className="conversation-retry" disabled={busy||!canWrite} onClick={()=>void submit(text,currentSkill)}>{t('Retry send')}</button>}
        <button type="button" className="live-primary conversation-send" disabled={busy||!canWrite||!text.trim()} aria-label={t(busy?'Sending…':'Send message')} onClick={()=>void submit(text,currentSkill)}>
          <ArrowUp size={16} aria-hidden="true"/>{t(busy?'Sending…':'Send')}
        </button>
      </div>
    </div>
  </section>;
}
