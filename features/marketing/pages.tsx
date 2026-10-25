/* eslint-disable @next/next/no-img-element -- Fixed-dimension local synthetic screenshots, no remote image service. */
import {siteCopy, type Locale, type PageId, type SiteCopy} from './content';
import {SiteShell, DemoLink, Arrow} from './site';
import {publicPath} from './routes';
import {SampleWorkflow} from './sample';
import {DemoForm} from './demo-form';
import {publishing} from './publishing';
import {structuredData, jsonLd} from './seo';

function SectionHeading({eyebrow, title, intro}: {eyebrow?: string; title: string; intro?: string}) {
  return <div className="m-section-heading">{eyebrow && <p className="m-eyebrow">{eyebrow}</p>}<h2>{title}</h2>{intro && <p>{intro}</p>}</div>;
}
export function FAQ({locale}: {locale: Locale}) {
  return <div className="m-faq-list">{siteCopy[locale].faq.map((item, i) => <details key={item.question}><summary><span className="m-faq-number" aria-hidden="true">{String(i + 1).padStart(2, '0')}</span>{item.question}<span aria-hidden="true" className="m-faq-plus">+</span></summary><div><p>{item.answer}</p></div></details>)}</div>;
}
function Steps({locale, detailed = false}: {locale: Locale; detailed?: boolean}) {
  const Heading = detailed ? 'h2' : 'h3';
  return <ol className="m-steps">{siteCopy[locale].steps.map((item, i) => <li key={item.title}><span className="m-step-number">0{i + 1}</span><Heading>{item.title}</Heading><p>{item.text}</p>{detailed && <p className="m-step-detail">{item.detail}</p>}</li>)}</ol>;
}
function FeatureCards({locale, standalone = false}: {locale: Locale; standalone?: boolean}) {
  const Heading = standalone ? 'h2' : 'h3';
  return <div className="m-feature-grid">{siteCopy[locale].features.map((item, i) => <article className="m-feature-card" key={item.id}><span className="m-feature-icon" aria-hidden="true">{['⌘', '↗', '✓', '≡', '⇣', '▤'][i]}</span><Heading>{item.title}</Heading><p>{item.text}</p><p className="m-card-detail">{item.detail}</p></article>)}</div>;
}
function Closing({locale}: {locale: Locale}) {
  const copy = siteCopy[locale];
  return <section className="m-closing"><div className="m-container"><div><p className="m-eyebrow">BuyerOS</p><h2>{copy.home.closingTitle}</h2><p>{copy.home.closingBody}</p></div><DemoLink locale={locale} position="closing" /></div></section>;
}
function ProductCapture({locale, name}: {locale: Locale; name: string}) {
  const caption = siteCopy[locale].extra.captureCaption;
  return <figure className="m-product-capture"><div className="m-capture-bar"><span aria-hidden="true">● ● ●</span><span>{siteCopy[locale].common.sampleLabel}</span></div><img src={`/marketing/product-${name}-${locale}.png`} width="1280" height="820" loading="lazy" decoding="async" alt={`${siteCopy[locale].nav[name === 'criteria' ? 'how-it-works' : 'features']} — ${caption}`} /><figcaption>{caption}</figcaption></figure>;
}
function Home({locale}: {locale: Locale}) {
  const copy = siteCopy[locale], home = copy.home;
  return <>
    <section className="m-hero m-container"><div className="m-hero-copy"><p className="m-eyebrow"><span />{copy.pages.home.eyebrow}</p><h1>{home.headline}</h1><p className="m-hero-intro">{home.intro}</p><div className="m-hero-actions"><DemoLink locale={locale} position="hero" /><a className="m-text-link" href="#sample">{home.secondary}<Arrow diagonal /></a></div><p className="m-hero-footnote">{copy.extra.heroFootnote}</p></div><SampleWorkflow locale={locale} compact /></section>
    <section className="m-proof-strip"><div className="m-container">{home.proof.map((item, i) => <div key={item.title}><span aria-hidden="true">0{i + 1}</span><h2>{item.title}</h2><p>{item.text}</p></div>)}</div></section>
    <section className="m-section m-container"><SectionHeading eyebrow={copy.nav.features} title={home.problemTitle} intro={home.problemIntro} /><div className="m-benefits">{home.benefits.map((item, i) => <article key={item.title}><span className="m-small-label">0{i + 1}</span><h3>{item.title}</h3><p>{item.text}</p></article>)}</div><div className="m-before-after"><div><span>{copy.extra.beforeLabel}</span><p>{copy.extra.beforeBody}</p></div><span aria-hidden="true">→</span><div><span>BuyerOS</span><p>{copy.extra.afterBody}</p></div></div><p className="m-figure-note">{copy.extra.illustrationNote}</p></section>
    <section className="m-section m-tinted"><div className="m-container"><SectionHeading eyebrow={copy.nav['how-it-works']} title={home.workflowTitle} /><Steps locale={locale} /><a className="m-text-link" href={publicPath(locale, 'how-it-works')}>{copy.common.learnMore}<Arrow /></a></div></section>
    <section className="m-section m-container"><SectionHeading eyebrow={copy.nav.features} title={home.featuresTitle} /><FeatureCards locale={locale} /><ProductCapture locale={locale} name="overview" /></section>
    <section id="sample" className="m-section m-sample-section"><div className="m-container m-sample-layout"><div><SectionHeading eyebrow={copy.common.sampleLabel} title={home.sampleTitle} intro={copy.common.sampleCaption} /><ol className="m-sample-checks">{copy.steps.map(item => <li key={item.title}><span aria-hidden="true">✓</span>{item.title}</li>)}</ol><a className="m-text-link" href={publicPath(locale, 'how-it-works')}>{copy.nav['how-it-works']}<Arrow /></a></div><SampleWorkflow locale={locale} /></div></section>
    <section className="m-section m-container"><SectionHeading title={home.personasTitle} /><div className="m-personas">{home.personas.map((item, i) => <article key={item.title}><span className="m-persona-symbol" aria-hidden="true">{['↗', '⌕', '✓'][i]}</span><h3>{item.title}</h3><p>{item.text}</p></article>)}</div></section>
    <section className="m-section m-container m-pricing-teaser"><div><p className="m-eyebrow">{copy.nav.pricing}</p><h2>{copy.pages.pricing.title}</h2><p>{copy.pricing.status}</p></div><DemoLink locale={locale} position="pricing">{copy.pricing.cta}</DemoLink></section>
    <section className="m-section m-container m-faq-section"><SectionHeading eyebrow="FAQ" title={copy.pages.faq.title} /><FAQ locale={locale} /></section><Closing locale={locale} />
  </>;
}
function Legal({locale, page}: {locale: Locale; page: 'privacy' | 'terms'}) {
  const copy: SiteCopy = siteCopy[locale], publisher = publishing();
  return <div className="m-container m-legal"><aside className="m-legal-status"><strong>{publisher.legalApproved ? copy.nav[page] : copy.legal.draftLabel}</strong>{!publisher.legalApproved && <p>{copy.legal.publisherMissing}</p>}</aside>
    <dl className="m-publisher"><div><dt>{copy.legal.controllerLabel}</dt><dd>{publisher.legalEntity ?? copy.extra.pending}</dd></div><div><dt>{copy.legal.contactLabel}</dt><dd>{publisher.contactEmail ? <a href={`mailto:${publisher.contactEmail}`}>{publisher.contactEmail}</a> : copy.extra.pending}</dd></div><div><dt>{copy.legal.retentionLabel}</dt><dd>{publisher.leadRetentionDays ? `${publisher.leadRetentionDays} ${copy.extra.days}` : copy.extra.retentionDisabled}</dd></div></dl>
    {copy.pages[page].sections.map(section => <section key={section.heading}><h2>{section.heading}</h2>{section.body.map(text => <p key={text}>{text}</p>)}{section.items && <ul>{section.items.map(item => <li key={item.title}><strong>{item.title}</strong> {item.text}</li>)}</ul>}</section>)}</div>;
}
function Interior({locale, page}: {locale: Locale; page: Exclude<PageId, 'home'>}) {
  const copy: SiteCopy = siteCopy[locale], current = copy.pages[page];
  return <>
    <section className={`m-page-hero m-container ${page === 'demo' ? 'm-demo-hero' : ''}`}><p className="m-eyebrow">{current.eyebrow}</p><h1>{current.title}</h1><p>{current.intro}</p></section>
    {page === 'features' && <><section className="m-section m-container m-topless"><FeatureCards locale={locale} standalone /></section><section className="m-section m-tinted"><div className="m-container m-product-pair"><ProductCapture locale={locale} name="criteria" /><ProductCapture locale={locale} name="drafts" /></div></section></>}
    {page === 'how-it-works' && <><section className="m-section m-container m-topless"><Steps locale={locale} detailed /><div className="m-workflow-example"><SampleWorkflow locale={locale} /></div></section></>}
    {page === 'pricing' && <section className="m-section m-container m-topless"><article className="m-pricing-card"><div><span className="m-eyebrow">{copy.nav.pricing}</span><h2>{copy.pricing.status}</h2><ul>{copy.pricing.topics.map(text => <li key={text}><span aria-hidden="true">✓</span>{text}</li>)}</ul></div><DemoLink locale={locale} position="pricing-page">{copy.pricing.cta}</DemoLink></article></section>}
    {page === 'faq' && <section className="m-section m-container m-topless m-faq-section"><FAQ locale={locale} /></section>}
    {page === 'demo' && <section className="m-section m-container m-topless m-demo-layout"><div><h2>{copy.form.start}</h2>{current.sections.map(section => <section className="m-demo-expectation" key={section.heading}><h3>{section.heading}</h3>{section.body.map(text => <p key={text}>{text}</p>)}{section.items?.map(item => <p key={item.title}><strong>{item.title}</strong> {item.text}</p>)}</section>)}<p className="m-form-privacy"><a href={publicPath(locale, 'privacy')}>{copy.form.privacy}<Arrow diagonal /></a></p></div><DemoForm locale={locale} copy={copy.form} enabled={process.env.MARKETING_ENABLED === '1'} synthetic={process.env.MARKETING_SYNTHETIC_MODE === '1'} /></section>}
    {(page === 'privacy' || page === 'terms') && <Legal locale={locale} page={page} />}
    {!['privacy', 'terms', 'demo'].includes(page) && <><section className="m-section m-container m-editorial">{current.sections.map(section => <section key={section.heading}><h2>{section.heading}</h2>{section.body.map(text => <p key={text}>{text}</p>)}</section>)}</section><Closing locale={locale} /></>}
  </>;
}
export function MarketingPage({locale, page}: {locale: Locale; page: PageId}) {
  return <SiteShell locale={locale} page={page}>{structuredData(locale, page).map((value, i) => <script key={i} type="application/ld+json" dangerouslySetInnerHTML={{__html: jsonLd(value)}} />)}{page === 'home' ? <Home locale={locale} /> : <Interior locale={locale} page={page} />}</SiteShell>;
}
