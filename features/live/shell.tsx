import type {ReactNode} from 'react';
import {ChevronRight} from 'lucide-react';
import {discussionForPath} from './conversation-home';

/** Route copy for the live page heading. Paths mirror the workspace router in workspace-picker. */
export function liveRouteMeta(pathname: string, conversationHome=false): {title: string; description: string} {
  const discussion=discussionForPath(pathname,conversationHome);
  if(discussion){const server=discussion.id.startsWith('s/');return {title:discussion.title,description:server?'Saved to this workspace. Results and sources stay linked to this discussion.':'New discussion in this project.'};}
  if (pathname === '/app/discover/new') return {title: 'New project', description: 'Describe your offer, then approve the buyer profile before research starts.'};
  if (pathname === '/app/discover/edit') return {title: 'Offer', description: 'Update offer facts and the buyer profile that research will use.'};
  if (pathname === '/app/discover') return {title: 'Buyers', description: 'Find the right companies. Know why they belong on your list.'};
  if (pathname === '/app/runs' || pathname.startsWith('/app/discover/')) return {title: 'Research', description: 'Track research progress, failures and recovery.'};
  if (pathname === '/app/results') return {title: 'Results', description: 'Review outcomes, costs and manual follow-up records.'};
  if (pathname === '/app/outreach') return {title: 'Outreach', description: 'Prepare grounded outreach. Every message stays under human review.'};
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
  /** One-time workspace/project context, placed above the section list. */
  scope?: ReactNode;
  footer: ReactNode;
  header: ReactNode;
  children: ReactNode;
  conversationHome?: boolean;
  /** Conversation routes own their heading; the shell must not repeat it. */
  hideHeading?: boolean;
};

/**
 * Signed-in layout in the FIMMICK design: a fixed sidebar on desktop that becomes a
 * sticky top strip with a horizontally scrolling section bar below 1024px. Layout is
 * CSS-only so every section button stays in the DOM and reachable at every width.
 */
export function LiveFrame({t, pathname, navigation, scope, footer, header, children, conversationHome=false, hideHeading=false}: FrameProps) {
  const meta = liveRouteMeta(pathname,conversationHome);
  return <div className="live-app">
    <aside className="live-sidebar">
      <LiveBrand/>
      {scope}
      {navigation}
      <div className="live-sidebar-footer">{footer}</div>
    </aside>
    <main className="main-shell live-workspace">
      {header}
      <div className="content">
        {!hideHeading && <div className="page-heading live-page-heading">
          <div><h1>{t(meta.title)}</h1><p>{t(meta.description)}</p></div>
        </div>}
        {children}
      </div>
    </main>
  </div>;
}

type HeaderProps = {
  t: (value: string) => string;
  pathname: string;
  projectName: string | null;
  conversationHome?: boolean;
  /** Conversation routes show one heading inside the studio, not a page title too. */
  hidePageTitle?: boolean;
};

/** Breadcrumb first, one deliberate account control in the sidebar. */
export function LiveTopbar({t, pathname, projectName, conversationHome=false, hidePageTitle=false}: HeaderProps) {
  const meta = liveRouteMeta(pathname,conversationHome);
  return <header className={'topbar live-topbar'+(hidePageTitle?' live-topbar-bare':'')}>
    <div className="inline live-breadcrumb">
      <span className="breadcrumb">{projectName || t('This project')}</span>
      {!hidePageTitle && <><ChevronRight size={14} aria-hidden="true"/><b>{t(meta.title)}</b></>}
    </div>
  </header>;
}
