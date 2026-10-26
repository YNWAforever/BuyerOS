/* eslint-disable @next/next/no-img-element -- Fixed-dimension local synthetic screenshots, no remote image service. */
import {siteCopy, pageFaq, type FaqId, type Locale, type PageId, type SiteCopy} from './content';
import {SiteShell, DemoLink, Arrow} from './site';
import {publicPath} from './routes';
import {SampleWorkflow} from './sample';
import {DemoForm} from './demo-form';
import {publishing} from './publishing';
import {structuredData, jsonLd} from './seo';

function SectionHeading({eyebrow, title, intro}: {eyebrow?: string; title: string; intro?: string}) {
  return <div className="m-section-heading">{eyebrow && <p className="m-eyebrow">{eyebrow}</p>}<h2>{title}</h2>{intro && <p>{intro}</p>}</div>;
}
function PageHero({locale, page}: {locale: Locale; page: Exclude<PageId, 'home'>}) {
  const current = siteCopy[locale].pages[page];
  const column = page === 'privacy' || page === 'terms' ? 'm-reading-column' : page === 'faq' ? 'm-faq-section' : '';
  return <section className={`m-page-hero m-container ${column}`}><p className="m-eyebrow">{current.eyebrow}</p><h1 className="m-display">{current.title}</h1><p className="m-hero-intro">{current.intro}</p></section>;
}
export function FAQ({locale, questions}: {locale: Locale; questions?: readonly FaqId[]}) {
  const items = questions ? questions.map(id => siteCopy[locale].faq.find(item => item.id === id)!) : pageFaq(locale, 'home');
  return <div className="m-faq-list">{items.map((item, i) => <details key={item.id}><summary><span className="m-faq-number" aria-hidden="true">{String(i + 1).padStart(2, '0')}</span>{item.question}<span aria-hidden="true" className="m-faq-plus">+</span></summary><div><p>{item.answer}</p></div></details>)}</div>;
}
function Steps({locale, detailed = false}: {locale: Locale; detailed?: boolean}) {
  const Heading = detailed ? 'h2' : 'h3';
  return <ol className="m-steps">{siteCopy[locale].steps.map((item, i) => <li key={item.title}><span className="m-step-number">0{i + 1}</span><Heading>{item.title}</Heading><p>{item.text}</p>{detailed && <p className="m-step-detail">{item.detail}</p>}</li>)}</ol>;
}
function FeatureCards({locale, features}: {locale: Locale; features: readonly string[]}) {
  return <div className="m-feature-grid">{features.map(id => {
    const item = siteCopy[locale].features.find(feature => feature.id === id)!;
    return <article className="m-feature-card" key={id}><h3>{item.title}</h3><p>{item.text}</p><p className="m-card-detail">{item.detail}</p></article>;
  })}</div>;
}
function Closing({locale}: {locale: Locale}) {
  const copy = siteCopy[locale];
  return <section className="m-closing"><div className="m-container"><div><p className="m-eyebrow">BuyerOS</p><h2>{copy.home.closingTitle}</h2><p>{copy.home.closingBody}</p></div><DemoLink locale={locale} position="closing" /></div></section>;
}
function ProductCapture({locale, name, eager = false}: {locale: Locale; name: 'overview' | 'criteria' | 'drafts'; eager?: boolean}) {
  const caption = siteCopy[locale].extra.captureCaption;
  return <figure className="m-product-capture"><div className="m-capture-bar"><span aria-hidden="true">● ● ●</span><span>{siteCopy[locale].common.sampleLabel}</span></div><img src={`/marketing/product-${name}-${locale}.png`} width="1280" height="820" loading={eager ? 'eager' : 'lazy'} decoding="async" alt={`${siteCopy[locale].nav[name === 'criteria' ? 'how-it-works' : 'features']} — ${caption}`} /><figcaption>{caption}</figcaption></figure>;
}
function Home({locale}: {locale: Locale}) {
  const copy = siteCopy[locale], home = copy.home;
  return <>
    <section className="m-hero m-container">
      <div className="m-hero-copy"><p className="m-eyebrow"><span />{copy.pages.home.eyebrow}</p><h1 className="m-display">{home.headline}</h1><p className="m-hero-intro">{home.intro}</p><div className="m-hero-actions"><DemoLink locale={locale} position="hero" /><a className="m-text-link" href="#sample">{home.secondary}<Arrow diagonal /></a></div><p className="m-hero-footnote">{copy.extra.heroFootnote}</p></div>
      <ProductCapture locale={locale} name="overview" eager />
    </section>
    <section id="why" className="m-section m-container">
      <SectionHeading title={home.problemTitle} intro={home.problemIntro} />
      <div className="m-benefits">{home.benefits.map((item, i) => <article key={item.title}><span className="m-small-label">0{i + 1}</span><h3>{item.title}</h3><p>{item.text}</p></article>)}</div>
      <div className="m-before-after"><div><span>{copy.extra.beforeLabel}</span><p>{copy.extra.beforeBody}</p></div><span aria-hidden="true">→</span><div><span>BuyerOS</span><p>{copy.extra.afterBody}</p></div></div><p className="m-figure-note">{copy.extra.illustrationNote}</p>
    </section>
    <section id="sample" className="m-section m-tinted">
      <div className="m-container"><SectionHeading eyebrow={copy.nav['how-it-works']} title={home.workflowTitle} /><Steps locale={locale} />
        <div className="m-sample-layout"><div><h3>{home.sampleTitle}</h3><p>{copy.common.sampleCaption}</p><a className="m-text-link" href={publicPath(locale, 'how-it-works')}>{copy.common.learnMore}<Arrow /></a></div><SampleWorkflow locale={locale} /></div>
      </div>
    </section>
    <section id="capabilities" className="m-section m-container">
      <SectionHeading eyebrow={copy.nav.features} title={home.featuresTitle} />
      <div className="m-capabilities">{copy.featureGroups.map(group => <article key={group.id}><h3>{group.title}</h3><p>{group.text}</p><a className="m-text-link" href={`${publicPath(locale, 'features')}#${group.id}`}>{copy.common.allFeatures}<Arrow /></a></article>)}</div>
    </section>
    <section id="teams" className="m-section m-container m-team-strip"><SectionHeading title={home.personasTitle} /><div className="m-personas">{home.personas.map(item => <article key={item.title}><h3>{item.title}</h3><p>{item.text}</p></article>)}</div></section>
    <section id="plans" className="m-section m-container m-pricing-teaser"><div><p className="m-eyebrow">{copy.nav.pricing}</p><h2>{copy.pages.pricing.title}</h2><p>{copy.pricing.status}</p></div><a className="m-text-link" href={publicPath(locale, 'pricing')}>{copy.nav.pricing}<Arrow /></a></section>
    <section id="questions" className="m-section m-container m-faq-section"><SectionHeading eyebrow="FAQ" title={copy.pages.faq.title} /><FAQ locale={locale} /><a className="m-text-link" href={publicPath(locale, 'faq')}>{copy.common.allFaq}<Arrow /></a></section>
    <Closing locale={locale} />
  </>;
}
function Legal({locale, page}: {locale: Locale; page: 'privacy' | 'terms'}) {
  const copy: SiteCopy = siteCopy[locale], publisher = publishing();
  return <div className="m-container m-reading-column m-prose m-legal"><aside className="m-legal-status"><strong>{publisher.legalApproved ? copy.nav[page] : copy.legal.draftLabel}</strong>{!publisher.legalApproved && <p>{copy.legal.publisherMissing}</p>}</aside>
    <dl className="m-publisher"><div><dt>{copy.legal.controllerLabel}</dt><dd>{publisher.legalEntity ?? copy.extra.pending}</dd></div><div><dt>{copy.legal.contactLabel}</dt><dd>{publisher.contactEmail ? <a href={`mailto:${publisher.contactEmail}`}>{publisher.contactEmail}</a> : copy.extra.pending}</dd></div><div><dt>{copy.legal.retentionLabel}</dt><dd>{publisher.leadRetentionDays ? `${publisher.leadRetentionDays} ${copy.extra.days}` : copy.extra.retentionDisabled}</dd></div></dl>
    {copy.pages[page].sections.map(section => <section key={section.heading}><h2>{section.heading}</h2>{section.body.map(text => <p key={text}>{text}</p>)}{section.items && <ul>{section.items.map(item => <li key={item.title}><strong>{item.title}</strong> {item.text}</li>)}</ul>}</section>)}</div>;
}
function Interior({locale, page}: {locale: Locale; page: Exclude<PageId, 'home'>}) {
  const copy: SiteCopy = siteCopy[locale], current = copy.pages[page];
  return <>
    <PageHero locale={locale} page={page} />
    {page === 'features' && copy.featureGroups.map(group => <section key={group.id} id={group.id} className="m-section m-container m-feature-section">
      <SectionHeading title={group.title} intro={group.text} /><FeatureCards locale={locale} features={group.features} />
      {group.id !== 'review' && <ProductCapture locale={locale} name={group.id === 'define' ? 'criteria' : 'drafts'} />}
    </section>)}
    {page === 'how-it-works' && <><section className="m-section m-container m-topless"><Steps locale={locale} detailed /><div className="m-workflow-example"><SampleWorkflow locale={locale} /></div></section></>}
    {page === 'pricing' && <section className="m-section m-container m-topless"><article className="m-pricing-teaser m-pricing-card"><div><span className="m-eyebrow">{copy.nav.pricing}</span><h2>{copy.pricing.status}</h2><ul>{copy.pricing.topics.map(text => <li key={text}><span aria-hidden="true">✓</span>{text}</li>)}</ul>{current.sections.map(section => <div className="m-prose" key={section.heading}><h3>{section.heading}</h3>{section.body.map(text => <p key={text}>{text}</p>)}</div>)}</div><DemoLink locale={locale} position="pricing-page">{copy.pricing.cta}</DemoLink></article></section>}
    {page === 'faq' && <div className="m-section m-container m-topless m-faq-section">{copy.faqGroups.map(group => <section className="m-faq-group" key={group.title}><SectionHeading title={group.title} /><FAQ locale={locale} questions={group.questions} /></section>)}</div>}
    {page === 'demo' && <section className="m-section m-container m-topless m-demo-layout">
      <div><h2>{copy.form.start}</h2>{current.sections.map(section => <section className="m-demo-expectation" key={section.heading}><h3>{section.heading}</h3>{section.body.map(text => <p key={text}>{text}</p>)}{section.items?.map(item => <p key={item.title}><strong>{item.title}</strong> {item.text}</p>)}</section>)}</div>
      <div className="m-demo-form-column">
        {process.env.MARKETING_ENABLED !== '1' && <p className="m-demo-availability">{copy.form.unavailable}</p>}
        {process.env.MARKETING_ENABLED === '1' && process.env.MARKETING_SYNTHETIC_MODE === '1' && <p className="m-demo-availability">{copy.form.syntheticNotice}</p>}
        <DemoForm locale={locale} copy={copy.form} enabled={process.env.MARKETING_ENABLED === '1'} synthetic={process.env.MARKETING_SYNTHETIC_MODE === '1'} />
        <p className="m-form-privacy"><a href={publicPath(locale, 'privacy')}>{copy.form.privacy}<Arrow diagonal /></a></p>
      </div>
    </section>}
    {(page === 'privacy' || page === 'terms') && <Legal locale={locale} page={page} />}
    {!['privacy', 'terms', 'demo'].includes(page) && <>{page !== 'pricing' && <section className="m-section m-container m-prose m-editorial">{current.sections.map(section => <section key={section.heading}><h2>{section.heading}</h2>{section.body.map(text => <p key={text}>{text}</p>)}</section>)}</section>}<Closing locale={locale} /></>}
  </>;
}
export function MarketingPage({locale, page}: {locale: Locale; page: PageId}) {
  return <SiteShell locale={locale} page={page}>{structuredData(locale, page).map((value, i) => <script key={i} type="application/ld+json" dangerouslySetInnerHTML={{__html: jsonLd(value)}} />)}{page === 'home' ? <Home locale={locale} /> : <Interior locale={locale} page={page} />}</SiteShell>;
}
