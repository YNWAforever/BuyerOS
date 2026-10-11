"""Declared frozen gates and per-run strata; all examples synthetic and offline."""
import copy,importlib,json,subprocess,sys,uuid
from pathlib import Path
import pytest
from tools.capture_research_predictions import digest

def tool():
    spec=importlib.util.find_spec('tools.evaluate_frozen_research')
    assert spec is not None,'C61-24 frozen strata/cost gate port missing'
    return importlib.import_module('tools.evaluate_frozen_research')

def fixture():
    rows=[]
    for i in range(200):
        company=str(uuid.UUID(int=i+1));workspace=str(uuid.UUID(int=999));verdict='match' if i%2==0 else 'not_match';market='HK' if i%4<2 else 'US'
        rows.append({'company_id':company,'workspace_id':workspace,'market':market,'language':'zh-HK' if market=='HK' else 'en','company_type':'synthetic','split':'train' if i<100 else 'holdout','reference_verdict':verdict,'annotations':[{'annotator_id':'synthetic-a','verdict':verdict},{'annotator_id':'synthetic-b','verdict':verdict}],'sources':[{'id':'synthetic-'+str(i),'company_id':company,'workspace_id':workspace,'url':'https://synthetic.example.test/source','date':'2026-10-01','current':True,'is_inference':False}]})
    gold={'schema':'buyeros.research-goldset.v1','evidence_mode':'fixture','owner':'synthetic-only','rows':rows}
    pred={'schema':'buyeros.research-predictions.v1','runs':[{'run_id':'synthetic-repeat-'+str(i),'rows':[{'company_id':row['company_id'],'predicted_company_id':row['company_id'],'workspace_id':row['workspace_id'],'verdict':row['reference_verdict'],'evidence_ids':[row['sources'][0]['id']]} for row in rows[100:]]} for i in range(3)]}
    threshold={'schema':'buyeros.research-thresholds.v1','owner':'synthetic-product-declaration','adopted':True,'frozen_at':'2026-10-01T00:00:00+00:00','precision_min':.95,'recall_min':.8,'coverage_min':.8,'abstention_max':.2,'maximum_cost':'1.000000','currency':'USD','minimum_companies':200,'minimum_stratum_companies':30,'safety_violations':0}
    capture={'schema':'buyeros.research-capture-provenance.v1','predictions_sha256':digest(pred),'goldset_sha256':digest(gold),'thresholds_sha256':digest(threshold),'frozen_at':threshold['frozen_at'],'observations':[{'run_id':run['run_id'],'company_id':row['company_id'],'blockers':[]} for run in pred['runs'] for row in run['rows']]}
    costs={'schema':'buyeros.research-cost-observations.v1','runs':[{'run_id':run['run_id'],'currency':'USD','settled_amount':'0.100000','active_hold':'0.000000','unknown_hold':'0.000000','billing_complete':True,'evidence_sha256':['a'*64]} for run in pred['runs']]}
    return gold,pred,threshold,capture,costs

def evaluate(data):
    gold,pred,threshold,capture,costs=data
    return tool().evaluate_frozen(gold,pred,threshold,capture,costs,input_hashes={'goldset':digest(gold),'predictions':digest(pred),'thresholds':digest(threshold),'capture':digest(capture),'costs':digest(costs)})

def rebind(data):
    gold,pred,threshold,capture,costs=data;capture.update(goldset_sha256=digest(gold),predictions_sha256=digest(pred),thresholds_sha256=digest(threshold));return data

def test_frozen_reports_separate_three_runs_and_strata_without_3n_pooling():
    data=fixture();before=copy.deepcopy(data);report=evaluate(data)
    assert report['quality_thresholds_met'] is True
    assert len(report['runs'])==3 and all(run['coverage']['denominator']==100 for run in report['runs'])
    assert len(report['strata'])==6 and all(row['companies']==50 and row['sufficient'] is True for row in report['strata'])
    assert all(row['coverage']['denominator']==50 for row in report['strata'])
    assert report['live_verified'] is report['release_accepted'] is False and report['provider_calls']==report['database_calls']==0
    assert report['label_verification']=='supplied declarations only; independence not authenticated' and data==before

def test_frozen_small_strata_are_insufficient_with_their_own_intervals():
    data=fixture();data[2]['minimum_stratum_companies']=51;rebind(data);report=evaluate(data)
    assert all(row['sufficient'] is False and row['companies']==50 for row in report['strata'])
    assert all(row['precision']['denominator']==25 and row['precision']['ci95'][0]<1 for row in report['strata'])
    assert report['quality_thresholds_met'] is False and 'insufficient_stratum' in report['blockers']

@pytest.mark.parametrize('gate',['unknown-hold','active-hold','unsettled','no-billing-proof','cost-ceiling','currency','not-adopted','capture-violation','wrong-company','unsupported','abstention'])
def test_frozen_quality_and_cost_gates_never_hide_unknowns_or_unsafe_rows(gate):
    data=list(fixture());gold,pred,threshold,capture,costs=data
    if gate=='unknown-hold':costs['runs'][0]['unknown_hold']='0.100000'
    elif gate=='active-hold':costs['runs'][0]['active_hold']='0.100000'
    elif gate=='unsettled':costs['runs'][0]['billing_complete']=False
    elif gate=='no-billing-proof':costs['runs'][0]['evidence_sha256']=[]
    elif gate=='cost-ceiling':costs['runs'][0]['settled_amount']='1.000001'
    elif gate=='currency':costs['runs'][0]['currency']='HKD'
    elif gate=='not-adopted':threshold['adopted']=False
    elif gate=='capture-violation':capture['observations'][0]['blockers']=['unsupported_evidence']
    elif gate=='wrong-company':pred['runs'][0]['rows'][0]['predicted_company_id']=str(uuid.UUID(int=998))
    elif gate=='unsupported':pred['runs'][0]['rows'][0]['evidence_ids']=['absent-evidence']
    else:
        for row in pred['runs'][0]['rows']:row.update(verdict='needs_review',evidence_ids=[])
    rebind(data);report=evaluate(data)
    assert report['quality_thresholds_met'] is report['release_accepted'] is report['live_verified'] is False
    assert report['blockers']
    if gate=='abstention':
        assert report['runs'][0]['precision']['estimate'] is None
        assert report['runs'][0]['recall']['denominator']==50 and report['runs'][0]['recall']['numerator']==0
        assert report['runs'][0]['coverage']['denominator']==100 and report['runs'][0]['needs_review']['numerator']==100

@pytest.mark.parametrize('gate',['gold-hash','predictions-hash','threshold-hash','freeze','missing-capture-row','duplicate-capture-row','missing-cost-run','duplicate-cost-run','negative-cost','bool-minimum','lower-precision','larger-safety','bool-safety','empty-owner'])
def test_frozen_rejects_changed_or_incomplete_original_bindings(gate):
    data=list(fixture());gold,pred,threshold,capture,costs=data
    if gate=='gold-hash':capture['goldset_sha256']='0'*64
    elif gate=='predictions-hash':capture['predictions_sha256']='0'*64
    elif gate=='threshold-hash':capture['thresholds_sha256']='0'*64
    elif gate=='freeze':capture['frozen_at']='2026-10-02T00:00:00+00:00'
    elif gate=='missing-capture-row':capture['observations'].pop()
    elif gate=='duplicate-capture-row':capture['observations'].append(copy.deepcopy(capture['observations'][0]))
    elif gate=='missing-cost-run':costs['runs'].pop()
    elif gate=='duplicate-cost-run':costs['runs'][1]['run_id']=costs['runs'][0]['run_id']
    elif gate=='negative-cost':costs['runs'][0]['settled_amount']='-0.000001'
    elif gate=='bool-minimum':threshold['minimum_companies']=True
    elif gate=='lower-precision':threshold['precision_min']=.94
    elif gate=='larger-safety':threshold['safety_violations']=1
    elif gate=='bool-safety':threshold['safety_violations']=False
    else:threshold['owner']='   '
    if gate in {'bool-safety','empty-owner'}:rebind(data)
    module=tool()
    with pytest.raises(ValueError):module.evaluate_frozen(gold,pred,threshold,capture,costs,input_hashes={'goldset':digest(gold),'predictions':digest(pred),'thresholds':digest(threshold),'capture':digest(capture),'costs':digest(costs)})

@pytest.mark.parametrize('style',['canonical','pretty'])
def test_frozen_cli_writes_new_report_and_preserves_all_input_and_output_evidence(tmp_path,style):
    data=fixture();gold,pred,threshold,capture,costs=data;paths={}
    for key,value in zip(['goldset','predictions','thresholds','capture','costs'],data):
        p=tmp_path/(key+'.json')
        if key=='capture':
            import hashlib
            value.update(goldset_sha256=hashlib.sha256(paths['goldset'].read_bytes()).hexdigest(),thresholds_sha256=hashlib.sha256(paths['thresholds'].read_bytes()).hexdigest())
        raw=json.dumps(value,indent=2) if style=='pretty' else json.dumps(value,sort_keys=True,separators=(',',':'))
        p.write_text(raw,encoding='utf-8');paths[key]=p
    before={p:p.read_bytes() for p in paths.values()};output=tmp_path/'report.json';module=tool();script=Path(module.__file__)
    command=[sys.executable,str(script)]
    for key,p in paths.items():command.extend(['--'+key,str(p)])
    command.extend(['--output',str(output)]);result=subprocess.run(command,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
    report=json.loads(output.read_text());assert report['quality_thresholds_met'] is True and report['live_verified'] is report['release_accepted'] is False
    assert subprocess.run(command,capture_output=True,text=True,timeout=30).returncode==2
    assert subprocess.run(command[:-1]+[str(paths['goldset'])],capture_output=True,text=True,timeout=30).returncode==2
    assert before=={p:p.read_bytes() for p in paths.values()}
