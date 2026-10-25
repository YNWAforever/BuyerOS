/* eslint-disable @next/next/no-html-link-for-pages -- Native links preserve independent root documents and no-JS navigation. */
import type {ReactNode} from 'react';
import {siteCopy, type Locale, type PageId} from './content';
import {publicPath, otherLocale} from './routes';
import {publishing} from './publishing';
import './marketing.css';

function MarketingClicks() {
  // Runs with the document, before hydration, so a click is recorded even when
  // the dev runtime has not finished loading the client bundle.
  const code = `(function(){if(window.__buyerosMarketingClick)window.removeEventListener('click',window.__buyerosMarketingClick,true);window.__buyerosMarketingClick=function(event){var node=event.target&&event.target.closest&&event.target.closest('[data-marketing-event]');if(!node)return;var name=node.getAttribute('data-marketing-event');if(name!=='cta_click'&&name!=='locale_change')return;var root=document.querySelector('[data-marketing-path]');window.dispatchEvent(new CustomEvent('buyeros:marketing',{detail:{name:name,locale:root?root.getAttribute('data-marketing-locale'):document.documentElement.lang,path:root?root.getAttribute('data-marketing-path'):location.pathname,position:(node.getAttribute('data-position')||'link').slice(0,40)}}));};window.addEventListener('click',window.__buyerosMarketingClick,true);})();`;
  return <script dangerouslySetInnerHTML={{__html: code}} />;
}

export function Arrow({diagonal = false}: {diagonal?: boolean}) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.7"><path d={diagonal ? 'M6 18 18 6M6 6h12v12' : 'M4 12h15m-6-6 6 6-6 6'} /></svg>;
}
export function PublicDocument({locale, children}: {locale: Locale; children: ReactNode}) {
  return <html lang={locale}><body className="marketing-shell">{children}</body></html>;
}
export function DemoLink({locale, position, children, secondary = false}: {locale: Locale; position: string; children?: ReactNode; secondary?: boolean}) {
  return <a className={secondary ? 'm-text-link' : 'm-button'} href={publicPath(locale, 'demo')} data-marketing-event="cta_click" data-position={position}>
    {children ?? siteCopy[locale].common.demo}<Arrow />
  </a>;
}

export function SiteShell({locale, page, children}: {locale: Locale; page: PageId; children: ReactNode}) {
  const copy = siteCopy[locale], alternate = otherLocale(locale);
  const navigation: PageId[] = ['features', 'how-it-works', 'pricing', 'faq'];
  return <>
    <MarketingClicks />
    <a className="marketing-skip" href="#content">{copy.common.skip}</a>
    <header className="m-site-header" data-marketing-locale={locale} data-marketing-path={publicPath(locale, page)}>
      <div className="m-container m-nav-row">
        <a className="m-brand" href={publicPath(locale)}><span className="m-brand-symbol" aria-hidden="true">b<span>·</span></span>BuyerOS</a>
        <nav className="m-desktop-nav" aria-label={copy.common.navLabel}>
          {navigation.map(id => <a key={id} href={publicPath(locale, id)} aria-current={page === id ? 'page' : undefined}>{copy.nav[id]}</a>)}
        </nav>
        <div className="m-nav-actions">
          <a className="m-language" href={publicPath(alternate, page)} hrefLang={alternate} lang={alternate} data-marketing-event="locale_change" data-position="header">{alternate === 'en' ? 'English' : '繁體中文'}</a>
          <a className="m-login" href="/app">{copy.common.login}</a>
          <a className="m-button m-nav-cta" href={publicPath(locale, 'demo')} data-marketing-event="cta_click" data-position="header"><span className="m-long-label">{copy.common.demo}</span><span className="m-short-label">{copy.extra.mobileDemo}</span><Arrow /></a>
          <details className="m-mobile-nav">
            <summary aria-label={copy.common.menu}><svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M4 6h16M4 12h16M4 18h16" /></svg></summary>
            <nav aria-label={copy.common.navLabel}>
              {(['home', ...navigation, 'demo'] as PageId[]).map(id => <a key={id} href={publicPath(locale, id)} aria-current={page === id ? 'page' : undefined}>{copy.nav[id]}<Arrow /></a>)}
              <a className="m-menu-login" href="/app">{copy.common.login}<Arrow diagonal /></a>
            </nav>
          </details>
        </div>
      </div>
    </header>
    <main id="content" tabIndex={-1}>{children}</main>
    <footer className="m-site-footer">
      <div className="m-container m-footer-top"><div><a className="m-brand" href={publicPath(locale)}>BuyerOS<span className="m-brand-dot">·</span></a><p>{copy.common.footer}</p></div>
        <nav aria-label={copy.common.navLabel}>{(['features', 'how-it-works', 'pricing', 'faq', 'demo', 'privacy', 'terms'] as PageId[]).map(id => <a key={id} href={publicPath(locale, id)}>{copy.nav[id]}</a>)}</nav>
      </div>
      <div className="m-container m-footer-bottom"><p>{copy.common.footerNote}</p><span>BuyerOS{!publishing().indexable ? ` · ${copy.common.preview}` : ''}</span></div>
    </footer>
  </>;
}
