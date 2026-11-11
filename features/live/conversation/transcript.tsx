'use client';
import {useLayoutEffect,useRef,useState} from 'react';
import {ArrowDown} from 'lucide-react';
import type {TranscriptEntry} from './parts';
import {groupTranscript} from './parts';
import {MessageParts,type PartActions} from './inline-parts';
function readerOffset():number{
  // The studio mounts client-side; the server render (tests/static markup) keeps UTC.
  return typeof window==='undefined'?0:new Date().getTimezoneOffset();
}

type Props={
  t:(value:string)=>string;
  locale:'en'|'zh-HK';
  entries:TranscriptEntry[];
  actions:PartActions;
  busy:boolean;
  statusLine:string;
  emptyTitle:string;
};
function timeLabel(createdAt:number|null,locale:'en'|'zh-HK'):string{
  if(createdAt===null)return '';
  return new Date(createdAt).toLocaleTimeString(locale==='zh-HK'?'zh-HK':'en-GB',{hour:'2-digit',minute:'2-digit'});
}
function dayLabel(dayStart:number|null,locale:'en'|'zh-HK',t:(value:string)=>string):string{
  if(dayStart===null)return '';
  const now=new Date(),today=new Date(now.getFullYear(),now.getMonth(),now.getDate()).getTime();
  if(dayStart>=today)return t('Today');
  if(dayStart>=today-86_400_000)return t('Yesterday');
  return new Date(dayStart).toLocaleDateString(locale==='zh-HK'?'zh-HK':'en-GB',{weekday:'short',day:'numeric',month:'short',year:'numeric'});
}
/** Continuous transcript: day groups, sequence labels, autoscroll with an explicit jump. */
export function ConversationTranscript({t,locale,entries,actions,busy,statusLine,emptyTitle}:Props){
  const scroller=useRef<HTMLDivElement>(null),atBottom=useRef(true),primed=useRef(false);
  const [showJump,setShowJump]=useState(false);
  // Offset is read once per mount; day groups then match the reader's zone.
  const [offset]=useState(readerOffset);
  function scrollToLatest(behavior:ScrollBehavior='smooth'){
    const node=scroller.current;
    if(!node)return;
    node.scrollTo({top:node.scrollHeight,behavior});
    atBottom.current=true;setShowJump(false);
  }
  useLayoutEffect(()=>{
    const node=scroller.current;
    if(!node)return;
    if(!primed.current&&entries.length){primed.current=true;node.scrollTop=node.scrollHeight;atBottom.current=true;return;}
    if(atBottom.current)scrollToLatest('auto');
  },[entries.length]);
  function onScroll(){
    const node=scroller.current;
    if(!node)return;
    const bottom=node.scrollHeight-node.scrollTop-node.clientHeight<120;
    atBottom.current=bottom;
    setShowJump(!bottom&&entries.length>0);
  }
  const groups=groupTranscript(entries,offset);
  return <div className="conversation-transcript-wrap">
    <div className="conversation-transcript" role="log" aria-label={t('Discussion messages')} aria-live="polite" aria-relevant="additions" ref={scroller} onScroll={onScroll}>
      {!entries.length&&<div className="conversation-empty"><h2>{emptyTitle}</h2></div>}
      {groups.map(group=><section className="conversation-day" key={group.key} aria-label={dayLabel(group.dayStart,locale,t)||undefined}>
        {group.dayStart!==null&&<h3 className="conversation-day-label">{dayLabel(group.dayStart,locale,t)}</h3>}
        {group.entries.map(entry=>entry.role==='user'
          ?<article className="conversation-message conversation-user" key={entry.key}>
            <p className="conversation-part-text">{entry.message.text}</p>
            {(entry.seq!==null||entry.createdAt!==null)&&<p className="conversation-meta">{entry.seq!==null&&<span>#{entry.seq}</span>}{entry.createdAt!==null&&<time dateTime={new Date(entry.createdAt).toISOString()}>{timeLabel(entry.createdAt,locale)}</time>}</p>}
          </article>
          :<article className="conversation-message conversation-assistant" key={entry.key} aria-label={t('BuyerOS reply')}>
            <span className="conversation-speaker" aria-hidden="true"/>
            <div className="conversation-reply">
              <span className="conversation-sr">{t('BuyerOS reply')}</span>
              <MessageParts entry={entry} actions={actions}/>
              {(entry.ephemeral||entry.seq!==null||entry.createdAt!==null)&&<p className="conversation-meta">{entry.ephemeral&&<span className="pill gray">{t('Shown in this tab only')}</span>}{entry.seq!==null&&<span>#{entry.seq}</span>}{entry.createdAt!==null&&<time dateTime={new Date(entry.createdAt).toISOString()}>{timeLabel(entry.createdAt,locale)}</time>}</p>}
            </div>
          </article>)}
      </section>)}
      {busy&&<div className="conversation-typing" role="status"><span className="conversation-dots" aria-hidden="true"><i/><i/><i/></span>{t('Preparing a reply…')}</div>}
    </div>
    {showJump&&<button type="button" className="conversation-jump" onClick={()=>scrollToLatest()}><ArrowDown size={15} aria-hidden="true"/>{t('Jump to latest')}</button>}
    {/* Presentation-only: the same notice is announced by the inline/composer status
        region, so this visible line must not be a second live region. */}
    <p className="conversation-status" aria-hidden="true">{statusLine}</p>
  </div>;
}
