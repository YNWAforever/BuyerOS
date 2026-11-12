/**
 * Increment 2.7: pure projection from already-persisted turn data to the
 * "Why this proposal" explainer. It never invents cost/policy/actor values: a
 * missing field projects as unknown, and internal ids/hashes never cross into
 * the ordinary view model.
 */
import type {CitationItem,MessagePart,ProposalCost,ProposalPart} from './types';

export type ExplainerArgument={label:string;value:string};
export type ExplainerEvidence={label:string;href?:string};
export type ExplainerCost=
  |{kind:'review_required'}
  |{kind:'amount';amount:string;unit:string|null;mayIncurProviderCharges:boolean}
  |{kind:'nonbillable';mayIncurProviderCharges:boolean}
  |{kind:'unknown'};
export type ExplainerPolicyNotice={code:string;message:string};
export type ExplainerDecision={choice:'approve'|'reject';actor:'you'|'a workspace member';decidedAt:string};
export type ProposalExplainer={
  rationale:string|null;
  argumentsKnown:boolean;
  argumentsTruncated:boolean;
  arguments:ExplainerArgument[];
  evidence:ExplainerEvidence[];
  cost:ExplainerCost;
  policyNotices:ExplainerPolicyNotice[];
  requiresApproval:boolean;
  decisionKnown:boolean;
  decision:ExplainerDecision|null;
};

const MAX_ARGUMENTS=12;
const MAX_ARGUMENT_VALUE=200;
const MAX_EVIDENCE=20;
const MAX_NOTICES=8;
// Internal identifiers/keys never belong in the ordinary explainer path. Keys are
// normalised so camelCase (`clientMessageId`, `sourceIds`) is caught too.
const INTERNAL_KEY=/(?:^|_)(?:id|ids|uuid|guid|hash|digest|fingerprint|token|secret|locator|protocol|schema|request|trace|email|mail)(?:$|_)/i;
// Values that look like identifiers/PII/protocol names are dropped even when the
// key itself is benign.
const INTERNAL_VALUE=/(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|(?:^|[^0-9a-f])[0-9a-f]{32,}(?:$|[^0-9a-f])|[\w.+-]+@[\w-]+\.[\w.-]+|(?:^|[^a-z0-9])[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+(?:$|[^a-z0-9])|(?:document|buyer|source|output|proposal|run|drive|call)\s*:\s*\S+)/i;
const POLICY_CODE=/POLICY|BUDGET|ADMISSION|CONFIG|RUNTIME|XVERUM|DRIVE|SOURCE/i;
function record(value:unknown):value is Record<string,unknown>{
  return typeof value==='object'&&value!==null&&!Array.isArray(value);
}
function internalKey(key:string):boolean{
  const normalized=key.replace(/([a-z0-9])([A-Z])/g,'$1_$2').replace(/([A-Z]+)([A-Z][a-z])/g,'$1_$2').toLowerCase();
  return INTERNAL_KEY.test(normalized);
}
function primitive(value:unknown):string|null{
  if(typeof value==='string'){
    const text=value.trim();
    return text&&!INTERNAL_VALUE.test(text)?text.slice(0,MAX_ARGUMENT_VALUE):null;
  }
  if(typeof value==='number'&&Number.isFinite(value))return String(value);
  if(typeof value==='boolean')return value?'Yes':'No';
  if(Array.isArray(value)){
    const items=value.slice(0,4).map(primitive).filter((item):item is string=>item!==null);
    return items.length?items.join(', ').slice(0,MAX_ARGUMENT_VALUE):null;
  }
  return null;
}
function readArguments(value:unknown):{items:ExplainerArgument[];known:boolean;truncated:boolean}{
  if(!record(value))return {items:[],known:false,truncated:false};
  const items:ExplainerArgument[]=[];
  let truncated=false;
  for(const [key,raw] of Object.entries(value)){
    if(internalKey(key))continue;
    const text=primitive(raw);
    if(!text)continue;
    if(items.length>=MAX_ARGUMENTS){truncated=true;break;}
    items.push({label:key.replaceAll('_',' '),value:text});
  }
  return {items,known:items.length>0,truncated};
}
function readCost(cost:ProposalCost|undefined):ExplainerCost{
  if(!cost)return {kind:'unknown'};
  const mayIncur=cost.may_incur_provider_charges===true;
  // Shipped semantics: an unknown provider tariff is never given a number.
  if(cost.kind==='provider_credits'&&cost.known===false)return {kind:'review_required'};
  if(cost.known===false)return {kind:'review_required'};
  if(cost.kind==='nonbillable')return {kind:'nonbillable',mayIncurProviderCharges:mayIncur};
  if(cost.amount===undefined)return {kind:'unknown'};
  return {kind:'amount',amount:String(cost.amount),unit:cost.unit??null,mayIncurProviderCharges:mayIncur};
}
function readEvidence(parts:ReadonlyArray<MessagePart>):ExplainerEvidence[]{
  const evidence:ExplainerEvidence[]=[],seen=new Set<string>();
  for(const part of parts){
    if(part.kind!=='citations')continue;
    for(const item of part.items as CitationItem[]){
      const key=`${item.label}\u0000${item.href}`;
      if(seen.has(key))continue;
      if(evidence.length>=MAX_EVIDENCE)return evidence;
      seen.add(key);
      evidence.push({label:item.label,...(item.href?{href:item.href}:{})});
    }
  }
  return evidence;
}
function readPolicyNotices(parts:ReadonlyArray<MessagePart>):ExplainerPolicyNotice[]{
  const notices:ExplainerPolicyNotice[]=[];
  for(const part of parts){
    if(part.kind!=='notice'||!POLICY_CODE.test(part.code))continue;
    if(notices.length>=MAX_NOTICES)break;
    notices.push({code:part.code,message:part.message});
  }
  return notices;
}
/**
 * Strictly validates the read-time decision decoration. Anything malformed or
 * privacy-widening (unknown actor labels, non-ISO time, extra/invalid choice)
 * degrades to absent so the explainer shows explicit Unknown rows instead.
 */
export function persistedDecision(value:unknown):ExplainerDecision|null{
  if(!record(value))return null;
  const keys=Object.keys(value);
  if(keys.length!==3||keys.some(key=>key!=='choice'&&key!=='decided_at'&&key!=='decided_by'))return null;
  const {choice,decided_at,decided_by}=value;
  if(choice!=='approve'&&choice!=='reject')return null;
  if(decided_by!=='you'&&decided_by!=='a workspace member')return null;
  if(typeof decided_at!=='string'||decided_at.length>64)return null;
  if(!/^\d{4}-\d\d-\d\dT/.test(decided_at)||!Number.isFinite(Date.parse(decided_at)))return null;
  return {choice,actor:decided_by,decidedAt:decided_at};
}
export function proposalExplain({proposal,turnParts,decision=null}:{
  proposal:ProposalPart;turnParts:ReadonlyArray<MessagePart>;decision?:ExplainerDecision|null;
}):ProposalExplainer{
  const args=readArguments(proposal.arguments_preview);
  return {
    rationale:typeof proposal.rationale==='string'&&proposal.rationale.trim()?proposal.rationale.trim().slice(0,1_000):null,
    argumentsKnown:args.known,
    argumentsTruncated:args.truncated,
    arguments:args.items,
    evidence:readEvidence(turnParts),
    cost:readCost(proposal.cost),
    policyNotices:readPolicyNotices(turnParts),
    requiresApproval:proposal.requires_approval!==false,
    decisionKnown:decision!==null,
    decision,
  };
}
