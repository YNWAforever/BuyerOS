'use client';
import {ArrowUp, FileText, MessageSquare, PanelRight, Sparkles} from 'lucide-react';
import {illustrativeDiscussions, type IllustrativeDiscussion} from './conversation-home';

type Props = {
  t: (value: string) => string;
  discussion: IllustrativeDiscussion;
  navigate: (path: string) => void;
};

/** Static chrome only. Actions use the existing guarded module navigation. */
export function LiveDiscussion({t, discussion, navigate}: Props) {
  return <section className="live-discussion" aria-label={t('Discussion')}>
    <div className="live-discussion-thread panel">
      <header className="live-discussion-chrome">
        <span className="inline"><MessageSquare size={18} aria-hidden="true"/><b>{t('Discussion')}</b></span>
        <span className="pill gray">{t('Illustrative conversation')}</span>
      </header>
      <p className="live-discussion-notice">{t('No research, approval or save is executed. Messages and outputs are examples only.')}</p>
      <div className="live-discussion-messages" aria-label={t('Example messages')}>
        {discussion.prompt && <article className="live-discussion-message live-discussion-user">
          <b>{t('You · example')}</b><p>{t(discussion.prompt)}</p>
        </article>}
        <article className="live-discussion-message">
          <b className="inline"><Sparkles size={16} aria-hidden="true"/>{t('BuyerOS · example')}</b>
          <p>{t(discussion.reply)}</p>
          {discussion.id !== 'new' && <div className="live-discussion-output">
            <FileText size={22} aria-hidden="true"/>
            <div><b>{t('Follow-up outline · example')}</b><p>{t('Preview only. Open Drafts to work with existing drafts.')}</p>
              <button onClick={() => navigate('/app/outreach')}>{t('Preview output / Opens in Drafts')}</button>
            </div>
          </div>}
        </article>
        {discussion.id === 'new' && <div className="live-discussion-suggestions">
          {illustrativeDiscussions.map(item => <button key={item.id} onClick={() => navigate(`/app/discussions/${item.id}`)}>{t(item.title)}</button>)}
        </div>}
      </div>
      <div className="live-discussion-composer">
        <label htmlFor="illustrative-message">{t('Message · preview only')}</label>
        <textarea id="illustrative-message" rows={2} disabled placeholder={t('Conversation input is unavailable in this preview.')}/>
        <div><small>{t('Illustrative only · messages are not sent or saved')}</small><button disabled><ArrowUp size={16} aria-hidden="true"/>{t('Send')}</button></div>
      </div>
    </div>
    <aside className="live-discussion-resources" aria-label={t('Discussion resources')}>
      <section className="panel">
        <h2 className="inline"><FileText size={18} aria-hidden="true"/>{t('Templates')}</h2>
        <p>{t('Start with an outline, then continue in Drafts.')}</p>
        <button onClick={() => navigate('/app/outreach')}>{t('Browse templates in Drafts')}</button>
      </section>
      <section className="panel">
        <h2 className="inline"><PanelRight size={18} aria-hidden="true"/>{t('Saved results')}</h2>
        <p>{t('Nothing is saved from this conversation. View existing project results in Results.')}</p>
        <button onClick={() => navigate('/app/results')}>{t('Open Results')}</button>
      </section>
    </aside>
  </section>;
}
