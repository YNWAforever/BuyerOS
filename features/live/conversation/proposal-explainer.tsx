'use client';
import {useMemo} from 'react';
import {Link2} from 'lucide-react';
import type {MessagePart,ProposalPart} from './types';
import {type ProposalUiState} from './approval';
import {persistedDecision,proposalExplain} from './explainer';

type Props={
  t:(value:string)=>string;
  locale:'en'|'zh-HK';
  navigate:(path:string)=>void;
  proposal:ProposalPart;
  turnParts:ReadonlyArray<MessagePart>;
  approvalState:ProposalUiState;
};
function approvalStateLabel(t:(value:string)=>string,state:ProposalUiState):string{
  switch(state){
    case 'awaiting':return t('Awaiting approval');
    case 'submitting':return t('Sending…');
    case 'approved':return t('Approved');
    case 'rejected':return t('Rejected');
    case 'failed':return t('Not confirmed');
    case 'unknown_outcome':return t('Outcome unknown');
    case 'unavailable':return t('This proposal cannot be decided here. Ask a current editor to review it.');
    case 'inert':return t('This step cannot run in the current configuration.');
    case 'not_required':return t('No approval is needed for this step.');
    default:return t('Unknown');
  }
}
function costText(t:(value:string)=>string,view:ReturnType<typeof proposalExplain>):string{
  if(view.cost.kind==='review_required')return t('Cost review required before any paid request.');
  if(view.cost.kind==='amount')return `${view.cost.amount}${view.cost.unit?` ${view.cost.unit}`:''}`;
  if(view.cost.kind==='nonbillable')return t('No provider charge');
  return t('Unknown');
}
function decidedAtLabel(value:string|null,locale:'en'|'zh-HK'):string|null{
  if(!value)return null;
  const parsed=Date.parse(value);
  if(!Number.isFinite(parsed))return value;
  return new Date(parsed).toLocaleString(locale==='zh-HK'?'zh-HK':'en-GB',{day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'});
}
/**
 * Collapsed-by-default explainer built strictly from persisted parts. Expanding it
 * performs no fetch and cannot mutate the turn.
 */
export function ProposalExplainer({t,locale,navigate,proposal,turnParts,approvalState}:Props){
  const view=useMemo(()=>proposalExplain({proposal,turnParts,
    decision:persistedDecision(proposal.decision)}),[proposal,turnParts]);
  const unknown=t('Unknown');
  const decidedAt=view.decisionKnown?decidedAtLabel(view.decision?.decidedAt??null,locale):null;
  const decisionLabel=view.decisionKnown&&view.decision?t(view.decision.choice==='approve'?'Approved':'Rejected'):unknown;
  const actorLabel=view.decisionKnown&&view.decision
    ?(view.decision.actor==='you'?t('You'):t('A workspace member')):unknown;
  return <details className="conversation-proposal-why">
    <summary>{t('Why this proposal')}</summary>
    <dl className="conversation-why">
      <div><dt>{t('Rationale')}</dt><dd>{view.rationale??unknown}</dd></div>
      <div><dt>{t('Arguments')}</dt><dd className="conversation-why-arguments">{view.argumentsKnown
        ?<ul>{view.arguments.map(item=><li key={item.label}><b>{t(item.label)}</b> {item.value}</li>)}</ul>
        :unknown}</dd></div>
      <div><dt>{t('Evidence')}</dt><dd>{view.evidence.length
        ?<ul className="conversation-citations">{view.evidence.map((item,index)=><li key={`${item.label}:${index}`}>{item.href
          ?<button type="button" onClick={()=>navigate(item.href!)}><Link2 size={13} aria-hidden="true"/>{t(item.label)}</button>
          :<span className="pill gray">{t(item.label)}</span>}</li>)}</ul>
        :unknown}</dd></div>
      <div><dt>{t('Cost basis')}</dt><dd className="conversation-why-cost">{costText(t,view)}</dd></div>
      <div><dt>{t('Policy and approval')}</dt><dd>{approvalStateLabel(t,approvalState)}
        {view.policyNotices.length>0&&<ul>{view.policyNotices.map(notice=><li key={`${notice.code}:${notice.message}`}>{notice.message}</li>)}</ul>}</dd></div>
      <div><dt>{t('Decision')}</dt><dd>{decisionLabel}</dd></div>
      <div><dt>{t('Decided by')}</dt><dd>{actorLabel}</dd></div>
      <div><dt>{t('Decided at')}</dt><dd>{decidedAt??unknown}</dd></div>
    </dl>
  </details>;
}
