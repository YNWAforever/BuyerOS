import type {LucideIcon} from 'lucide-react';
import {Activity, ChartNoAxesCombined, FilePenLine, FileText, LayoutDashboard, Mail, Plus, Search, Settings, Wrench} from 'lucide-react';
import {discussionForPath} from './conversation-home';

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
  // Conversation-first shell: conversation is the front door and the project tools are
  // one group. Workspace administration sits in a small Manage group so owners can still
  // reach settings without it competing with the daily path.
  if(conversationHome){
    const discussion=discussionForPath(pathname,true);
    return <nav aria-label="BuyerOS sections" className="live-nav live-nav-conversation">
      {item('New discussion',Plus,'/app/discussions/new',discussion?.id==='new',!authorized||!projectKnown)}
      {item('Home',LayoutDashboard,'/app',discussion?.id==='home',!authorized||!projectKnown)}
      <div className="live-nav-group" role="group" aria-label={t('This project')}>
        <div className="nav-label" aria-hidden="true">{t('This project')}</div>
        {item('Offer',FilePenLine,projectKnown?'/app/discover/edit':'/app/discover/new',pathname==='/app/discover/edit'||pathname==='/app/discover/new',!authorized || !(projectKnown?canEdit&&projectActive:canCreate))}
        {item('Buyers',Search,'/app/discover',pathname==='/app/discover',!projectKnown)}
        {item('Research',Activity,'/app/runs',runRoute,!projectKnown)}
        {item('Outreach',Mail,'/app/outreach',pathname==='/app/outreach',!projectKnown)}
        {item('Results',ChartNoAxesCombined,'/app/results',pathname==='/app/results',!projectKnown)}
        {item('Documents',FileText,'/app/documents',pathname.startsWith('/app/documents'),!projectKnown)}
      </div>
      <div className="live-nav-group" role="group" aria-label={t('Manage')}>
        <div className="nav-label" aria-hidden="true">{t('Manage')}</div>
        {item('Settings',Settings,'/app/settings',pathname==='/app/settings',!authorized)}
        {item('Operations',Wrench,'/app/operations',pathname==='/app/operations',!authorized)}
      </div>
    </nav>;
  }
  const projectWork=<>
    {item('Overview',LayoutDashboard,'/app',pathname==='/app',false)}
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
  return <nav aria-label="BuyerOS sections" className="live-nav">
    {projectWork}
  </nav>;
}
