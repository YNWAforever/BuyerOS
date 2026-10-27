import type {LucideIcon} from 'lucide-react';
import {Activity, ChartNoAxesCombined, FilePenLine, LayoutDashboard, Mail, MessageSquare, Plus, Search, Settings, Wrench} from 'lucide-react';
import {discussionForPath, illustrativeDiscussions} from './conversation-home';

type Props = {
  t: (value:string)=>string;
  navigate: (path:string)=>void;
  pathname: string;
  authorized: boolean;
  projectKnown: boolean;
  canEdit: boolean;
  projectActive: boolean;
  canCreate: boolean;
  conversationHome?: boolean;
};

/** Groups follow the buyer workflow; the parent session and scope checks remain authoritative. */
export function LiveNavigation({t,navigate,pathname,authorized,projectKnown,canEdit,projectActive,canCreate,conversationHome=false}:Props){
  const runRoute=pathname==='/app/runs'||/^\/app\/discover\/[^/]+$/.test(pathname)&&!['new','edit'].includes(pathname.split('/')[3]);
  const item=(label:string,Icon:LucideIcon,path:string,active:boolean,disabled:boolean)=>
    <button className="live-nav-item" aria-current={active?'page':undefined} data-active={active} onClick={()=>navigate(path)} disabled={disabled}>
      <Icon size={18} aria-hidden="true"/><span>{t(label)}</span>
    </button>;
  const projectWork=<>
    {item('Overview',LayoutDashboard,conversationHome?'/app/overview':'/app',pathname===(conversationHome?'/app/overview':'/app'),false)}
    <div className="live-nav-group" role="group" aria-label={t('Discover & review')}>
      <div className="nav-label" aria-hidden="true">{t('Discover & review')}</div>
      {item('Offer',FilePenLine,projectKnown?'/app/discover/edit':'/app/discover/new',pathname==='/app/discover/edit'||pathname==='/app/discover/new',!authorized || !(projectKnown?canEdit&&projectActive:canCreate))}
      {item('Research runs',Activity,'/app/runs',runRoute,!projectKnown)}
      {item('Buyers',Search,'/app/discover',pathname==='/app/discover',!projectKnown)}
    </div>
    <div className="live-nav-group" role="group" aria-label={t('Follow up')}>
      <div className="nav-label" aria-hidden="true">{t('Follow up')}</div>
      {item('Drafts',Mail,'/app/outreach',pathname==='/app/outreach',!projectKnown)}
      {item('Results',ChartNoAxesCombined,'/app/results',pathname==='/app/results',!projectKnown)}
    </div>
    <div className="live-nav-group" role="group" aria-label={t('Manage')}>
      <div className="nav-label" aria-hidden="true">{t('Manage')}</div>
      {item('Settings',Settings,'/app/settings',pathname==='/app/settings',!authorized)}
      {item('Operations',Wrench,'/app/operations',pathname==='/app/operations',!authorized)}
    </div>
  </>;
  const discussion=discussionForPath(pathname,conversationHome);
  return <nav aria-label="BuyerOS sections" className="live-nav">
    {conversationHome && <>
      {item('New discussion',Plus,'/app/discussions/new',discussion?.id==='new',!authorized||!projectKnown)}
      <div className="live-nav-group" role="group" aria-label={t('Discussions')}>
        <div className="nav-label" aria-hidden="true">{t('Discussions')} <small>· {t('Examples')}</small></div>
        {illustrativeDiscussions.map(entry=><div className="live-nav-discussion" key={entry.id}>{item(entry.title,MessageSquare,`/app/discussions/${entry.id}`,discussion?.id===entry.id,!authorized||!projectKnown)}</div>)}
      </div>
    </>}
    {conversationHome ? <div className="live-nav-retained" role="group" aria-label={t('Project work (retained)')}>
      <div className="nav-label live-nav-retained-label" aria-hidden="true">{t('Project work (retained)')}</div>
      {projectWork}
    </div> : projectWork}
  </nav>;
}
