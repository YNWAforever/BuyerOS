'use client';
import type {ReactNode} from 'react';
import type {GroundedReply} from '@/services/live/discussion-citations';
import {ArrowUp, FileText, MessageSquare, PanelRight} from 'lucide-react';
import {guidedTemplates, templateForId} from './conversation-home';
import type {LocalThread,SelectedSource} from '@/services/live/discussions';
import type {ContextSection} from '@/services/live/discussion-context';
import {citationPath} from '@/services/live/discussion-citations';

type Props = {
  t:(value:string)=>string; locale:'en'|'zh-HK'; thread:LocalThread|null; threads:LocalThread[];
  entryTemplate?:string; value:string; notice:string; context:ContextSection[]|null;
  navigate:(path:string)=>void; onTemplate:(id:string)=>void; onChange:(text:string)=>void;
  onSend:()=>void; onSource:(source:SelectedSource,selected:boolean)=>void; onRefresh:()=>void;
  research?:ReactNode; liveReply?:GroundedReply;
  onAsk?:()=>void; asking?:boolean; replyNotice?:string; canAsk?:boolean;
};

/** Rendering and local callbacks only. All server reads live in the scope-owned context adapter. */
export function LiveDiscussion({t,locale,thread,threads,entryTemplate,value,notice,context,navigate,onTemplate,onChange,onSend,onSource,onRefresh,research,liveReply,onAsk,asking=false,replyNotice='',canAsk=false}:Props) {
  const guidance=templateForId(thread?.templateId??entryTemplate??'custom');
  const open=(destination:string,path:string)=><button type="button" onClick={()=>navigate(path)}>{t(`Open in ${destination}`)}</button>;
  const guidedStep=<article className="live-discussion-message">
    <b>{t('BuyerOS')} · {t('Guided step · no AI')}</b>
    <p>{t(guidance.question)}</p>
    <div className="live-discussion-suggestions">{guidance.choices.map(choice=><button type="button" key={choice} onClick={()=>onChange(t(choice))}>{t(choice)}</button>)}</div>
    {open(guidance.destination,guidance.path)}
  </article>;
  return <section className="live-discussion" aria-label={t('Discussion')}>
    <div className="live-discussion-thread panel">
      <header className="live-discussion-chrome"><span className="inline"><MessageSquare size={18} aria-hidden="true"/><b>{thread?.title??t('What would you like to achieve?')}</b></span><span className="pill gray">{t(thread?.messages.some(message=>'kind' in message)?'AI reply · needs review':'Guided step · no AI')}</span></header>
      <p className="live-discussion-notice">{t('Saved on this device only · not shared')}</p>
      <p className="live-discussion-notice">{t('Messages stay local. Ask BuyerOS sends your question and selected IDs for source checks. Research requires a separate confirmation. Approval and sending stay in their existing work surfaces.')}</p>
      {notice&&<p className="live-discussion-notice" role="status">{t(notice)}</p>}
      {thread?<div className="live-discussion-messages" aria-label={t('Discussion messages')} aria-live="polite" aria-relevant="additions">
        {thread.messages.map((message,index)=>'kind' in message?<article key={message.id} className="live-discussion-message">
          <b>{t('BuyerOS')} · {t('AI reply · needs review')}</b><p>{t(message.fixture?'Fixture reply · no live model':'Live AI reply · needs review')}</p><p>{message.text}</p>
          <div className="live-discussion-suggestions" aria-label={t('Reply citations')}>{message.citations.map(ref=><button key={ref.id} type="button" onClick={()=>navigate(citationPath(ref))}>{t(ref.label)}</button>)}</div>
          <small>{t('Check the cited sources. This reply does not approve, research or send anything.')}</small>
        </article>:<div key={message.id} className="live-discussion-turn"><article className="live-discussion-message live-discussion-user"><b>{t('You')}</b><p>{message.text}</p></article>{thread.messages[index+1]&&'kind' in thread.messages[index+1]?null:guidedStep}</div>)}
      </div>:<div className="live-discussion-messages">
        {entryTemplate&&<><p>{t(guidance.prompt)}</p>{guidedStep}<button type="button" onClick={()=>onTemplate(guidance.id)}>{t('Start this discussion')}</button></>}
        <h2>{t('Guided templates')}</h2>
        <div className="live-discussion-templates">{guidedTemplates.map(item=><button type="button" key={item.id} onClick={()=>onTemplate(item.id)}><b>{t(item.title)}</b><small>{t(`Open in ${item.destination}`)}</small></button>)}</div>
      </div>}
      {liveReply&&<article className="live-discussion-message live-discussion-ephemeral">
        <b>{t('Live AI reply · needs review')}</b><p>{liveReply.text}</p>
        <div className="live-discussion-suggestions" aria-label={t('Reply citations')}>{liveReply.citations.map(ref=><button key={ref.id} type="button" onClick={()=>navigate(citationPath(ref))}>{t(ref.label)}</button>)}</div>
        <small>{t('Live replies stay in this tab and are not saved on this device. Check the cited sources.')}</small>
      </article>}
      {research}
      <form className="live-discussion-composer" onSubmit={event=>{event.preventDefault();onSend();}}>
        <label htmlFor="discussion-message">{t(thread?'Discussion message':'What would you like to achieve?')}</label>
        <textarea id="discussion-message" rows={3} maxLength={4000} value={value} onChange={event=>onChange(event.target.value)} placeholder={t('Describe your next step. Avoid private buyer details or document text.')}/>
        <div><small>{t('Send saves your message locally. No AI reply.')}</small><button type="submit" disabled={asking||!value.trim()}><ArrowUp size={16} aria-hidden="true"/>{t('Send')}</button>
          {onAsk&&<button type="button" onClick={onAsk} disabled={asking||!canAsk||!value.trim()||!thread?.sources.length||thread.sources.length>20} aria-describedby="discussion-ai-help">{t(asking?'Checking selected sources…':'Ask BuyerOS')}</button>}
        </div>
        {onAsk&&<p id="discussion-ai-help"><small>{t('Select 1–20 approved sources to ask BuyerOS. A live reply reserves up to USD 0.10; unknown results keep the hold for reconciliation. AI may be unavailable; your question stays here.')}</small></p>}
        <div role="status" aria-live="polite">{asking?t('Checking selected sources…'):replyNotice?t(replyNotice):null}</div>
      </form>
      {!thread&&<section className="live-discussion-continue" aria-label={t('Continue working')}><h2>{t('Continue working')}</h2>
        {!threads.length?<p>{t('No discussions in this project yet.')}</p>:<ul>{threads.map(item=><li key={item.id}><button type="button" onClick={()=>navigate(`/app/discussions/${item.id}`)}><b>{item.title}</b><span>{t(templateForId(item.templateId).title)}</span><time dateTime={new Date(item.updatedAt).toISOString()}>{new Date(item.updatedAt).toLocaleString(locale)}</time></button></li>)}</ul>}
      </section>}
    </div>
    <aside className="live-discussion-resources" aria-label={t('Discussion resources')}>
      <section className="panel"><h2 className="inline"><FileText size={18} aria-hidden="true"/>{t('Documents & outputs')}</h2>
        <p>{t('Read-only project context. Selecting a source saves its ID and label only.')}</p><p>{t('Extracted facts need reviewer approval.')}</p>
        {!thread&&<p>{t('Start a discussion to select sources.')}</p>}
        <button type="button" onClick={onRefresh}>{t('Refresh project context')}</button>
        {!context?<p role="status">{t('Loading project context…')}</p>:context.map((section,index)=><section className="live-discussion-context" key={index} aria-label={t(section.title)}><h3>{t(section.title)}</h3>
          {section.notice&&<p role="status">{t(section.notice)}</p>}
          {section.items.map(item=><article key={item.id}>
            <label><input type="checkbox" disabled={!thread} checked={thread?.sources.some(source=>source.id===item.id)??false} onChange={event=>onSource({id:item.id,label:item.label},event.target.checked)}/><span>{item.title===item.label||item.id.startsWith('results:')?t(item.title):item.title}<small>{t(item.status==='candidate'?'Candidate offer fact':item.status==='snapshot'?'Results summary':item.status)}</small></span></label>
            {item.detail&&<p>{item.detail}</p>}
            <button type="button" onClick={()=>navigate(item.path)}>{t('Open source')}</button>
          </article>)}
        </section>)}
        {thread&&<details><summary>{t('Selected for this discussion')} ({thread.sources.length})</summary>
          {thread.sources.length===0?<p>{t('No sources selected.')}</p>:<ul>{thread.sources.map(source=><li key={source.id}>{t(source.label)} <button type="button" onClick={()=>onSource(source,false)}>{t('Remove selection')}</button></li>)}</ul>}
          <p>{t('A saved selection does not grant access. Current project permissions apply.')}</p>
        </details>}
      </section>
      <section className="panel"><h2>{t('Connections / Available context')}</h2><ul className="live-discussion-connections">
        <li><b>{t('BuyerOS project records')}</b><p>{t('Available with existing project permissions.')}</p></li>
        <li><b>{t('Web research')}</b><p>{t('Propose research in this discussion or open Research runs. Scope and budget confirmation are required.')}</p>{open('Research runs','/app/runs')}</li>
        <li><b>{t('Shared library / CRM')}</b><p>{t('Not connected · later')}</p></li>
      </ul></section>
      <section className="panel"><h2>{t('Templates')}</h2><p>{t('Continue preparing follow-ups in existing Drafts.')}</p>{open('Drafts','/app/outreach')}</section>
      <section className="panel"><h2 className="inline"><PanelRight size={18} aria-hidden="true"/>{t('Saved results')}</h2><p>{t('View existing project results in Results.')}</p>{open('Results','/app/results')}</section>
    </aside>
  </section>;
}
