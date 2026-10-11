"""Offline declared frozen strata/cost gate; never authenticates live acceptance."""
import argparse,hashlib,json,sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated,Literal
from pydantic import BaseModel,ConfigDict,Field,StrictBool,StrictFloat,StrictInt,StrictStr
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.evaluate_research_goldset import evaluate,Goldset,Predictions
from tools.capture_research_predictions import digest
from tools.quality_metrics import proportion,provenance,write_new_report

Hash=Annotated[StrictStr,Field(pattern=r'^[0-9a-f]{64}$')]
Amount=Annotated[StrictStr,Field(pattern=r'^[0-9]+(?:\.[0-9]{1,6})?$')]

class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid')

class Thresholds(StrictModel):
    schema_version:Literal['buyeros.research-thresholds.v1']=Field(alias='schema')
    owner:StrictStr=Field(min_length=1,max_length=128)
    adopted:StrictBool
    frozen_at:datetime
    precision_min:StrictFloat=Field(ge=.95,le=1)
    recall_min:StrictFloat=Field(ge=0,le=1)
    coverage_min:StrictFloat=Field(ge=0,le=1)
    abstention_max:StrictFloat=Field(ge=0,le=1)
    maximum_cost:Amount
    currency:StrictStr=Field(pattern=r'^[A-Z]{3}$')
    minimum_companies:StrictInt=Field(ge=200)
    minimum_stratum_companies:StrictInt=Field(ge=1)
    safety_violations:StrictInt=Field(ge=0,le=0)

class CostRow(StrictModel):
    run_id:StrictStr=Field(min_length=1)
    currency:StrictStr=Field(pattern=r'^[A-Z]{3}$')
    settled_amount:Amount
    active_hold:Amount
    unknown_hold:Amount
    billing_complete:StrictBool
    evidence_sha256:list[Hash]

class Costs(StrictModel):
    schema_version:Literal['buyeros.research-cost-observations.v1']=Field(alias='schema')
    runs:list[CostRow]=Field(min_length=3,max_length=3)

def _metrics(gold,rows):
    reference={str(row.company_id):row.reference_verdict for row in gold};counts=dict(tp=0,fp=0,tn=0,fn=0,needs_review=0)
    for row in rows:
        positive=reference[str(row.company_id)]=='match'
        if row.verdict=='match':counts['tp' if positive else 'fp']+=1
        elif positive:counts['fn']+=1
        elif row.verdict=='not_match':counts['tn']+=1
        if row.verdict=='needs_review':counts['needs_review']+=1
    n=len(gold)
    return {'confusion':counts,'precision':proportion(counts['tp'],counts['tp']+counts['fp']),'recall':proportion(counts['tp'],sum(row.reference_verdict=='match' for row in gold)),'coverage':proportion(n-counts['needs_review'],n),'needs_review':proportion(counts['needs_review'],n)}

def _threshold_blockers(row,threshold):
    blockers=[]
    for key,minimum in [('precision',threshold.precision_min),('recall',threshold.recall_min),('coverage',threshold.coverage_min)]:
        value=row[key]['estimate']
        if value is None:blockers.append(key+'_unavailable')
        elif value<minimum:blockers.append(key+'_below_threshold')
    if row['needs_review']['estimate']>threshold.abstention_max:blockers.append('abstention_above_threshold')
    return blockers

def evaluate_frozen(goldset,predictions,thresholds,capture,costs,*,input_hashes):
    threshold=Thresholds.model_validate(thresholds);cost=Costs.model_validate(costs)
    if threshold.frozen_at.tzinfo is None or not threshold.owner.strip() or type(threshold.safety_violations) is not int:raise ValueError('explicit aware freeze and zero safety ceiling required')
    if set(input_hashes)!={'goldset','predictions','thresholds','capture','costs'} or any(not isinstance(value,str) or len(value)!=64 or set(value)-set('0123456789abcdef') for value in input_hashes.values()):raise ValueError('all exact input hashes required')
    if (capture.get('schema')!='buyeros.research-capture-provenance.v1'
        or capture.get('goldset_sha256')!=input_hashes['goldset']
        or capture.get('thresholds_sha256')!=input_hashes['thresholds']
        or capture.get('predictions_sha256')!=digest(predictions)
        or datetime.fromisoformat(capture['frozen_at'])!=threshold.frozen_at):raise ValueError('original capture/goldset/predictions/threshold freeze changed')
    report=evaluate(goldset,predictions);gold=Goldset.model_validate(goldset);pred=Predictions.model_validate(predictions)
    holdout=[row for row in gold.rows if row.split=='holdout'];expected={(run.run_id,str(row.company_id)) for run in pred.runs for row in holdout}
    observations=capture.get('observations',[]);actual=[(row.get('run_id'),row.get('company_id')) for row in observations]
    if len(actual)!=len(expected) or set(actual)!=expected:raise ValueError('capture must retain exactly each company in each original run')
    if any(not isinstance(row.get('blockers'),list) or any(not isinstance(code,str) for code in row['blockers']) for row in observations):raise ValueError('capture blockers must remain observable')
    costs_by_run={row.run_id:row for row in cost.runs}
    if len(costs_by_run)!=3 or set(costs_by_run)!={run.run_id for run in pred.runs}:raise ValueError('one cost observation per original distinct run required')
    blockers=[]
    if not threshold.adopted:blockers.append('threshold_adoption_pending')
    if len(gold.rows)<threshold.minimum_companies:blockers.append('insufficient_total_companies')
    if report['safety_violations']:blockers.append('safety_violation')
    if any(row['blockers'] for row in observations):blockers.append('capture_guard_blocked')
    for row in report['runs']:
        row['threshold_blockers']=_threshold_blockers(row,threshold)
        if row['threshold_blockers']:blockers.append('run_threshold_unmet')
    groups=defaultdict(list)
    for row in holdout:groups[(row.market,row.language,row.company_type)].append(row)
    strata=[]
    for run in pred.runs:
        for (market,language,company_type),subjects in sorted(groups.items()):
            company_ids={row.company_id for row in subjects};metrics=_metrics(subjects,[row for row in run.rows if row.company_id in company_ids]);sufficient=len(subjects)>=threshold.minimum_stratum_companies
            metrics.update(run_id=run.run_id,market=market,language=language,company_type=company_type,companies=len(subjects),sufficient=sufficient,threshold_blockers=_threshold_blockers(metrics,threshold))
            if not sufficient:blockers.append('insufficient_stratum')
            if metrics['threshold_blockers']:blockers.append('stratum_threshold_unmet')
            strata.append(metrics)
    cost_reports=[]
    for run in pred.runs:
        row=costs_by_run[run.run_id];remaining=Decimal(row.active_hold)+Decimal(row.unknown_hold);liability=Decimal(row.settled_amount)+remaining;reasons=[]
        if row.currency!=threshold.currency:reasons.append('cost_currency_mismatch')
        if not row.billing_complete:reasons.append('billing_unsettled')
        if not row.evidence_sha256:reasons.append('billing_evidence_missing')
        if remaining>0:reasons.append('hold_unsettled')
        if liability>Decimal(threshold.maximum_cost):reasons.append('cost_ceiling_exceeded')
        if reasons:blockers.append('cost_gate_unmet')
        cost_reports.append({**row.model_dump(mode='json'),'maximum_liability':format(liability,'f'),'blockers':reasons,'billing_authenticated':False})
    report.update(schema='buyeros.frozen-research-evaluation.v1',thresholds=threshold.model_dump(mode='json',by_alias=True),strata=strata,costs=cost_reports,blockers=list(dict.fromkeys(blockers)),quality_thresholds_met=not blockers,input_hashes=input_hashes,threshold_adoption_authenticated=False,capture_authenticity_authenticated=False,billing_authenticated=False,live_verified=False,release_accepted=False,provider_calls=0,database_calls=0,repeat_policy='separate per-run/company/stratum intervals; no pooled 3n sample',minimum_sample_note='reported stratum counts and configured sufficiency are declarations; interval remains visible when insufficient',cost_note='settled + disjoint active/unknown holds, per run; no settlement inferred from zero events, received or unknown')
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['goldset','predictions','thresholds','capture','costs','output']:parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();inputs=[getattr(args,key) for key in ['goldset','predictions','thresholds','capture','costs']]
    try:
        if args.output.exists() or args.output.resolve() in {p.resolve() for p in inputs}:raise ValueError('new output required; input/previous evidence aliases refused')
        raw=[p.read_bytes() for p in inputs];hashes=dict(zip(['goldset','predictions','thresholds','capture','costs'],[hashlib.sha256(value).hexdigest() for value in raw]))
        report=evaluate_frozen(*[json.loads(value) for value in raw],input_hashes=hashes)
        root=Path(__file__).resolve().parents[3];report.update(provenance(root,[Path(__file__).resolve(),Path(__file__).with_name('evaluate_research_goldset.py'),Path(__file__).with_name('capture_research_predictions.py'),Path(__file__).with_name('quality_metrics.py')]))
        write_new_report(args.output,report,tuple(inputs))
    except (OSError,ValueError,KeyError,TypeError) as error:parser.error(str(error))
    print('Offline declared gate report written; live_verified=false; release_accepted=false; provider_calls=0; database_calls=0')
    return 0 if report['quality_thresholds_met'] else 1

if __name__=='__main__':raise SystemExit(main())
