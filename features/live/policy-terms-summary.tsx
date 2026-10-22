import type {components} from '@/services/generated/buyeros-api';
type Terms=components['schemas']['PolicyTerms'];
/** Read-only presentation of the exact canonical object used for the decision. */
export function PolicyTermsSummary({terms,approver,t}:{terms:Terms;approver:string|null;t:(value:string)=>string}){
 const values=[
  ['Purpose',t(terms.purpose)],['Regions',terms.countries.length?terms.countries.join(', '):t('Unknown')],
  ['Data categories',terms.allowed_data_categories.map(t).join(', ')||t('Unknown')],
  ['Permitted actions',terms.allowed_actions.join(', ')||t('Unknown')],
  ['Source domains',terms.allowed_sources.domains.join(', ')||t('Unknown')],
  ['Provided documents',String(terms.allowed_sources.document_ids.length)],
  ['Responsible approver',approver||t('Unavailable member')],
  ['Owner evidence reference',terms.owner_evidence_reference||t('Unknown')],
  ['Valid from (UTC)',terms.valid_from],['Expires at (UTC)',terms.expires_at],
  ['Retention days',String(terms.retention_days)],['Deletion arrangement reference',terms.deletion_plan.reference],
 ] as const;
 return <div data-testid="policy-business-summary"><h3>{t('Policy summary')}</h3>
   <dl className="policy-summary">{values.map(([label,value])=><div key={label}><dt>{t(label)}</dt><dd>{value}</dd></div>)}</dl>
   <p>{t('Policy approval does not authorize paid research, enrichment or external sending.')}</p>
 </div>;
}
