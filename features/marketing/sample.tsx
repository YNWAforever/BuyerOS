import {siteCopy, type Locale} from './content';

export function SampleWorkflow({locale, compact = false}: {locale: Locale; compact?: boolean}) {
  const copy = siteCopy[locale], sample = copy.sample;
  return <figure className={`sample-workflow ${compact ? 'm-sample-compact' : ''}`}>
    <div className="m-sample-top"><span className="m-live-dot" />BuyerOS <span className="m-sample-badge">{copy.common.sampleLabel}</span></div>
    <div className="m-sample-content">
      <div className="m-sample-criteria"><span className="m-small-label">01 / {sample.criteriaLabel}</span><p>{sample.criteria}</p><div className="m-source-tags"><span>{copy.extra.sensorTag}</span><span>{copy.extra.buyerTag}</span></div></div>
      <div className="m-sample-record"><div className="m-company-monogram" aria-hidden="true">E<span>↗</span></div><div><span className="m-small-label">02 / {sample.companyLabel}</span><p className="m-sample-record-title">{sample.company}</p><span className="m-review-badge">{sample.review}</span></div></div>
      <div className="m-source-note"><span className="m-small-label">{sample.sourceLabel}</span><p>{sample.source}</p></div>
      <div className="m-sample-draft"><span className="m-small-label">03 / {sample.draftLabel}</span><p className="m-sample-draft-title">{sample.draftSubject}</p><p>{sample.draftBody}</p><div className="m-draft-footer"><span className="m-draft-bars" aria-hidden="true"><i /><i /><i /></span><span>{copy.extra.draftStatus}</span></div></div>
    </div>
    <figcaption>{copy.common.sampleCaption}</figcaption>
  </figure>;
}
