/**
 * Inline approval state machine. A proposal is executable only from an explicit
 * authenticated decision; prose, a completed turn or a reload never approves it.
 */
import type {ProposalPart,ThreadAccess,ToolActivityPart,ToolState,TurnStatus} from './types';

export type DecisionChoice='approve'|'reject';
export type DecisionState='submitting'|'accepted'|'failed';
export type LocalDecision={choice:DecisionChoice;state:DecisionState;notice?:string};
export type ProposalUiState='awaiting'|'submitting'|'approved'|'rejected'|'failed'|'unknown_outcome'|'unavailable'|'not_required';
export type DecisionGate={canDecide:boolean;canReject:boolean;noticeKey:string};

export function proposalUiState(part:ProposalPart,turnStatus:TurnStatus|undefined,decision:LocalDecision|undefined,access:ThreadAccess):ProposalUiState{
  if(!part.requires_approval)return 'not_required';
  if(decision){
    if(decision.state==='submitting')return 'submitting';
    if(decision.state==='accepted')return decision.choice==='approve'?'approved':'rejected';
    return 'failed';
  }
  if(access==='viewer')return 'unavailable';
  if(turnStatus==='outcome_unknown')return 'unknown_outcome';
  if(turnStatus==='cancelled'||turnStatus==='failed')return 'unavailable';
  return 'awaiting';
}
export function decisionGate(state:ProposalUiState):DecisionGate{
  const canDecide=state==='awaiting'||state==='failed';
  return {canDecide,canReject:canDecide,noticeKey:approvalNoticeKey(state)};
}
export function approvalNoticeKey(state:ProposalUiState):string{
  switch(state){
    case 'submitting':return 'Sending your decision…';
    case 'approved':return 'Approved. This discussion continues with the result.';
    case 'rejected':return 'Rejected. Nothing was executed.';
    case 'failed':return 'The decision was not confirmed. Check the discussion, then retry the same choice.';
    case 'unknown_outcome':return 'The outcome is unknown. Check the discussion before deciding again.';
    case 'unavailable':return 'This proposal cannot be decided here. Ask a current editor to review it.';
    case 'not_required':return 'No approval is needed for this step.';
    default:return '';
  }
}
/** Stable identity for one decision; an uncertain retry reuses the same request key. */
export function decisionIntentKey(threadId:string,turnId:string|null,proposalId:string,choice:DecisionChoice):string{
  return JSON.stringify(['conversation-decision',threadId,turnId,proposalId,choice]);
}
export function isSettledDecision(decision:LocalDecision|undefined):boolean{
  return decision?.state==='accepted';
}
export const toolStateOrder:readonly ToolState[]=['proposed','approved','running','completed','failed','skipped','outcome_unknown'];
/** Tool activity supersedes a stale proposal card once the capability has run. */
export function toolStateAfterDecision(tool:ToolActivityPart|null):ToolState|null{
  return tool?tool.state:null;
}
export function followUpNoticeKey(state:ToolState|null):string{
  switch(state){
    case 'running':return 'Running the approved step…';
    case 'completed':return 'The approved step completed. Its result is shown inline.';
    case 'failed':return 'The approved step failed. Its error is shown inline; nothing is retried automatically.';
    case 'skipped':return 'The approved step was skipped. Review the inline notices.';
    case 'outcome_unknown':return 'The approved step did not return a confirmed result. Check the result before retrying.';
    default:return '';
  }
}
