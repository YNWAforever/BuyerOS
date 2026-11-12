'use client';
import type {ReactNode} from 'react';
import {Plus,Pin,Search,X} from 'lucide-react';
import type {ServerSummary} from '@/services/live/conversation-threads';
import {sortThreadRows} from './thread-management';

export type ThreadListItem=ServerSummary&{pinned?:boolean;archived?:boolean};
type Props={
  t:(value:string)=>string;
  locale:'en'|'zh-HK';
  items:ThreadListItem[];
  total:number;
  currentId:string|null;
  fresh:boolean;
  notice:string;
  loading:boolean;
  query:string;
  archived:boolean;
  onQuery:(value:string)=>void;
  onToggleArchived:()=>void;
  onNew:()=>void;
  onOpen:(id:string)=>void;
  onMore?:()=>void;
  onClose?:()=>void;
  /** Secondary surfaces that belong beside the thread list, never in the transcript. */
  footer?:ReactNode;
};
function dateLabel(updatedAt:number,locale:'en'|'zh-HK'):string{
  const date=new Date(updatedAt),now=new Date();
  if(date.toDateString()===now.toDateString())return date.toLocaleTimeString(locale==='zh-HK'?'zh-HK':'en-GB',{hour:'2-digit',minute:'2-digit'});
  return date.toLocaleDateString(locale==='zh-HK'?'zh-HK':'en-GB',{day:'numeric',month:'short'});
}
/** Recent discussions beside the transcript; selection never invents a thread. */
export function ConversationThreadList({t,locale,items,total,currentId,fresh,notice,loading,query,archived,onQuery,onToggleArchived,onNew,onOpen,onMore,onClose,footer}:Props){
  const ordered=sortThreadRows(items);
  return <aside className="conversation-threads" aria-label={t('Discussions')}>
    <div className="conversation-threads-head">
      <button type="button" className="live-primary conversation-new" onClick={onNew} data-active={fresh||undefined}><Plus size={15} aria-hidden="true"/>{t('New discussion')}</button>
      {onClose&&<button type="button" className="conversation-icon-button" onClick={onClose} aria-label={t('Close discussions')}><X size={17} aria-hidden="true"/></button>}
    </div>
    <label className="conversation-search"><Search size={14} aria-hidden="true"/><span className="conversation-sr">{t('Search discussions')}</span><input type="search" value={query} placeholder={t('Search discussions')} onChange={event=>onQuery(event.target.value)}/></label>
    <button type="button" className="conversation-archive-toggle" aria-pressed={archived} onClick={onToggleArchived}>{t(archived?'Archived discussions':'Archive view')}</button>
    {notice&&<p className="conversation-threads-notice" role="status">{t(notice)}</p>}
    {loading&&!ordered.length?<p className="conversation-threads-status" role="status">{t('Loading discussions…')}</p>:
      ordered.length?<ul className="conversation-thread-items">{ordered.map(thread=>
        <li key={thread.id}><button type="button" onClick={()=>onOpen(thread.id)} aria-label={thread.title} aria-current={thread.id===currentId?'page':undefined} data-active={thread.id===currentId||undefined}>
          <span className="conversation-thread-row"><span className="conversation-thread-name">{thread.title}</span>{thread.pinned&&<Pin size={13} aria-hidden="true"/>}</span>
          <span className="conversation-thread-row"><span>{dateLabel(thread.updatedAt,locale)}</span>{thread.access!=='owner'?<span className="pill gray">{t(thread.access==='viewer'?'Viewer':'Editor')}</span>:thread.shareCount>0?<span className="pill gray">{t('Shared')}</span>:null}{thread.archived&&<span className="pill gray">{t('Archived')}</span>}</span>
        </button></li>)}
      </ul>:<p className="conversation-threads-status">{t('No discussions in this project yet.')}</p>}
    {onMore&&items.length<total&&<button type="button" className="conversation-more" onClick={onMore}>{t('Load more discussions')}</button>}
    {footer&&<div className="conversation-threads-extra">{footer}</div>}
  </aside>;
}
