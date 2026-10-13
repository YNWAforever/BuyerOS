import type {LucideIcon} from 'lucide-react';
import {Activity, ChartNoAxesCombined, FilePenLine, LayoutDashboard, Mail, Search, Settings, Wrench} from 'lucide-react';

type Props = {
  t: (value:string)=>string;
  navigate: (path:string)=>void;
  pathname: string;
  authorized: boolean;
  projectKnown: boolean;
  canEdit: boolean;
  projectActive: boolean;
  canCreate: boolean;
};

/** Route navigation keeps the parent workspace session and scope checks authoritative. Button order is part of the tested contract. */
export function LiveNavigation({t,navigate,pathname,authorized,projectKnown,canEdit,projectActive,canCreate}:Props){
  const runRoute=pathname==='/app/runs'||/^\/app\/discover\/[^/]+$/.test(pathname)&&!['new','edit'].includes(pathname.split('/')[3]);
  const item=(label:string,Icon:LucideIcon,path:string,active:boolean,disabled:boolean)=>
    <button className="live-nav-item" aria-current={active?'page':undefined} data-active={active} onClick={()=>navigate(path)} disabled={disabled}>
      <Icon size={18} aria-hidden="true"/><span>{t(label)}</span>
    </button>;
  return <nav aria-label="BuyerOS sections" className="live-nav">
    <div className="nav-label">{t('WORKSPACE')}</div>
    {item('Overview',LayoutDashboard,'/app',pathname==='/app',false)}
    {item('Offer',FilePenLine,projectKnown?'/app/discover/edit':'/app/discover/new',pathname==='/app/discover/edit'||pathname==='/app/discover/new',!authorized || !(projectKnown?canEdit&&projectActive:canCreate))}
    {item('Buyers',Search,'/app/discover',pathname==='/app/discover',!projectKnown)}
    {item('Results',ChartNoAxesCombined,'/app/results',pathname==='/app/results',!projectKnown)}
    {item('Research runs',Activity,'/app/runs',runRoute,!projectKnown)}
    {item('Drafts',Mail,'/app/outreach',pathname==='/app/outreach',!projectKnown)}
    <div className="nav-label">{t('ADMIN')}</div>
    {item('Settings',Settings,'/app/settings',pathname==='/app/settings',!authorized)}
    {item('Operations',Wrench,'/app/operations',pathname==='/app/operations',!authorized)}
  </nav>;
}
