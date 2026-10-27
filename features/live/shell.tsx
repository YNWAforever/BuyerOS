'use client';
import type {ReactNode} from 'react';
import {ChevronRight, ShieldCheck} from 'lucide-react';
import {discussionForPath} from './conversation-home';

/** Route copy for the live page heading. Paths mirror the workspace router in workspace-picker. */
export function liveRouteMeta(pathname: string, conversationHome=false): {title: string; description: string} {
  const discussion=discussionForPath(pathname,conversationHome);
  if(discussion)return {title:discussion.title,description:'A conversation for your project. Illustrative preview only.'};
  if (pathname === '/app/discover/new') return {title: 'New project', description: 'Describe your offer, then approve the buyer profile before research starts.'};
  if (pathname === '/app/discover/edit') return {title: 'Offer', description: 'Update offer facts and the buyer profile that research will use.'};
  if (pathname === '/app/discover') return {title: 'Buyers', description: 'Find the right companies. Know why they belong on your list.'};
  if (pathname === '/app/runs' || pathname.startsWith('/app/discover/')) return {title: 'Research runs', description: 'Track research progress, failures and recovery.'};
  if (pathname === '/app/results') return {title: 'Results', description: 'Review outcomes, costs and manual follow-up records.'};
  if (pathname === '/app/outreach') return {title: 'Drafts', description: 'Prepare grounded outreach. Every message stays under human review.'};
  if (pathname === '/app/settings') return {title: 'Settings', description: 'Members, roles, language, budgets and policy.'};
  if (pathname === '/app/operations') return {title: 'Operations', description: 'Readiness, jobs, retries and the audit trail.'};
  return {title: 'Overview', description: 'Your next actions across one connected buyer workspace.'};
}

/** Brand block shared by the signed-in sidebar and the sign-in card. */
export function LiveBrand() {
  return <div className="brand"><span className="brand-icon" aria-hidden="true">f</span><b>FIMMICK<span>BuyerOS</span></b></div>;
}

type FrameProps = {
  t: (value: string) => string;
  pathname: string;
  navigation: ReactNode;
  footer: ReactNode;
  header: ReactNode;
  children: ReactNode;
  conversationHome?: boolean;
};

/**
 * Signed-in layout in the FIMMICK design: a fixed sidebar on desktop that becomes a
 * sticky top strip with a horizontally scrolling section bar below 1024px. Layout is
 * CSS-only so every section button stays in the DOM and reachable at every width.
 */
export function LiveFrame({t, pathname, navigation, footer, header, children, conversationHome=false}: FrameProps) {
  const meta = liveRouteMeta(pathname,conversationHome);
  return <div className="live-app">
    <aside className="live-sidebar">
      <LiveBrand/>
      {navigation}
      <div className="live-sidebar-footer">{footer}</div>
    </aside>
    <main className="main-shell live-workspace">
      {header}
      <div className="content">
        <div className="page-heading live-page-heading">
          <div><h1>{t(meta.title)}</h1><p>{t(meta.description)}</p></div>
        </div>
        {children}
      </div>
    </main>
  </div>;
}

type HeaderProps = {t: (value: string) => string; pathname: string; languagePicker: ReactNode; signOut: ReactNode; conversationHome?: boolean};

export function LiveTopbar({t, pathname, languagePicker, signOut, conversationHome=false}: HeaderProps) {
  return <header className="topbar live-topbar">
    <div className="inline live-breadcrumb">
      <span className="breadcrumb">FIMMICK BuyerOS</span>
      <ChevronRight size={14} aria-hidden="true"/>
      <b>{t(liveRouteMeta(pathname,conversationHome).title)}</b>
    </div>
    <div className="inline top-right">
      <span className="live-indicator"><ShieldCheck size={14} aria-hidden="true"/>{t('Live workspace')}</span>
      {languagePicker}
      {signOut}
    </div>
  </header>;
}
