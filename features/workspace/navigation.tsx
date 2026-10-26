'use client';

import {
  ArrowUpRight, ChartNoAxesCombined, ChevronDown, FolderOpen, Globe2,
  LayoutDashboard, Mail, Search, Settings, Wallet,
} from 'lucide-react';
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarHeader,
  SidebarMenu, SidebarMenuButton, SidebarMenuItem, useSidebar,
} from '@/components/ui/sidebar';
import { Progress } from '@/components/ui/progress';
import { money } from '@/services/mock-client';

const navGroups = [
  {title: 'Discover & review', items: [
    ['Buyers', '/app/discover', Search],
    ['Buyer Lists', '/app/lists', FolderOpen],
  ]},
  {title: 'Follow up', items: [
    ['Drafts', '/app/outreach', Mail],
    ['Results', '/app/results', ChartNoAxesCombined],
  ]},
  {title: 'Manage', items: [['Settings', '/app/settings', Settings]]},
] as const;

type DemoNavigationProps = {
  t: (text: string) => string;
  navTitle: string;
  isWizard: boolean;
  isFull: boolean;
  isSettings: boolean;
  go: (url: string) => void;
  listCount: number;
  spent: number;
  budget: number;
  discoveryBudget: number;
  onUsage: () => void;
};

export function DemoNavigation({
  t, navTitle, isWizard, isFull, isSettings, go, listCount,
  spent, budget, discoveryBudget, onUsage,
}: DemoNavigationProps) {
  const { setOpenMobile } = useSidebar();
  const navigate = (url: string) => { go(url); setOpenMobile(false); };
  return (
    <Sidebar className="brand-sidebar">
      <SidebarHeader>
        <div className="brand">
          <span className="brand-icon">f</span>
          <b>FIMMICK<span>BuyerOS</span></b>
        </div>
        <div className="workspace-tag">
          <div className="workspace-avatar">F</div>
          <span>{t('Fimmick workspace')}<small>{t('Demo workspace')}</small></span>
          <ChevronDown size={14} />
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarMenu><SidebarMenuItem><SidebarMenuButton isActive={navTitle === 'Overview'} onClick={() => navigate('/app')}>
            <LayoutDashboard size={18} /><span>{t('Overview')}</span>
          </SidebarMenuButton></SidebarMenuItem></SidebarMenu>
        </SidebarGroup>
        {navGroups.map(group => <SidebarGroup key={group.title} role="group" aria-label={t(group.title)}>
          <div className="nav-label" aria-hidden="true">{t(group.title)}</div>
          <SidebarMenu>
            {group.items.map(([title, url, Icon]) => (
              <SidebarMenuItem key={url}>
                <SidebarMenuButton
                  isActive={navTitle === title || (title === 'Buyers' && (isWizard || isFull)) || (title === 'Settings' && isSettings)}
                  onClick={() => navigate(url)}
                >
                  <Icon size={18} />
                  <span>{t(title)}</span>
                  {title === 'Buyer Lists' && <small>{listCount}</small>}
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroup>)}
        <div className="sidebar-project">
          <div className="nav-label">{t('ACTIVE PROJECT')}</div>
          <span className="project-symbol"><Globe2 size={16} /></span>
          <b>HarbourSense</b>
          <p>{t('European market discovery')}</p>
          <div className="inline">
            <span>{t('3 markets')}</span><span>·</span><span>{t('Profile v1')}</span>
          </div>
        </div>
      </SidebarContent>
      <SidebarFooter>
        <div className="budget-mini">
          <div className="inline spread">
            <Wallet size={16} />
            <small>{t('Budget & usage')}</small>
            <button aria-label="Open usage" onClick={() => { onUsage(); navigate('/app/results'); }}>
              <ArrowUpRight size={15} />
            </button>
          </div>
          <p><b>{money(spent)}</b><span> {t('illustrative spend')}</span></p>
          <Progress value={Math.min(100, spent / (budget + discoveryBudget) * 100)} />
          <small>{t('No charge · demo only')}</small>
        </div>
        <div className="user-profile">
          <div className="avatar">WL</div>
          <span><b>Willy Lai</b><small>{t('Fimmick workspace')}</small></span>
          <span className="demo-tag">{t('DEMO')}</span>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
