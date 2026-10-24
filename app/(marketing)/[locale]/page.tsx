/* eslint-disable @next/next/no-html-link-for-pages -- Native document navigation keeps independent root layouts and works without JavaScript. */
import {publicCopy} from '@/features/marketing/copy';

export default async function MarketingSample({params}: {params: Promise<{locale: string}>}) {
  const copy = publicCopy((await params).locale);
  return <>
    <a className="marketing-skip" href="#content">{copy.skip}</a>
    <header className="marketing-header">
      <a className="marketing-brand" href="/">BuyerOS</a>
      <nav aria-label={copy.navigation}>
        <a href={`/${copy.alternateLocale}`} hrefLang={copy.alternateLocale} lang={copy.alternateLocale}>{copy.alternateLabel}</a>
        <a href="/app">{copy.login}</a>
      </nav>
    </header>
    <main id="content" tabIndex={-1}>
      <section className="marketing-hero" aria-labelledby="marketing-title">
        <p className="marketing-eyebrow">{copy.preview}</p>
        <h1 id="marketing-title">{copy.headline}</h1>
        <p className="marketing-intro">{copy.intro}</p>
        <div className="marketing-actions">
          <a className="marketing-primary" href="#request-demo">{copy.cta}</a>
          <a href="#workflow">{copy.workflowLink} <span aria-hidden="true">↗</span></a>
        </div>
      </section>
      <section id="workflow" className="marketing-workflow" aria-labelledby="workflow-title">
        <h2 id="workflow-title">{copy.workflow}</h2>
        <ol>{copy.steps.map((step, i) => <li key={step.title}>
          <span className="marketing-step" aria-hidden="true">0{i + 1}</span>
          <h3>{step.title}</h3><p>{step.body}</p>
        </li>)}</ol>
      </section>
      <section id="request-demo" className="marketing-demo" aria-labelledby="demo-title">
        <h2 id="demo-title">{copy.demoTitle}</h2>
        <p>{copy.demoNotice}</p>
      </section>
    </main>
    <footer className="marketing-footer"><p>{copy.scope}</p></footer>
  </>;
}
