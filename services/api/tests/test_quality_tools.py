"""Q10 local quality-tool regressions; no live provider or human label claim."""
import copy
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / 'services/api/tools'


def metrics():
    assert (TOOLS / 'quality_metrics.py').is_file(), 'Q10 versioned quality metrics tool missing'
    return importlib.import_module('tools.quality_metrics')


def goldset():
    rows=[]
    for i in range(8):
        company=f'00000000-0000-4000-8000-{i+1:012d}'
        rows.append({'company_id':company,'workspace_id':'11111111-1111-4111-8111-111111111111',
            'market':'HK','language':'zh-HK','company_type':'fixture','split':'train' if i<2 else 'holdout',
            'reference_verdict':'match' if i in [2,3,4] else 'not_match',
            'annotations':[{'annotator_id':'fixture-a','verdict':'match' if i in [2,3,4] else 'not_match'},
                           {'annotator_id':'fixture-b','verdict':'match' if i in [2,3,4] else 'not_match'}],
            'sources':[{'id':f'fixture-evidence-{i}','company_id':company,
                'workspace_id':'11111111-1111-4111-8111-111111111111','url':'https://evidence.example.test/fixture',
                'date':'2026-10-03','current':True,'is_inference':False}]})
    return {'schema':'buyeros.research-goldset.v1','evidence_mode':'fixture','owner':'fixture-only', 'rows':rows}


def predictions():
    rows=goldset()['rows'][2:]
    verdicts=['match','match','needs_review','match','not_match','needs_review']
    runs=[]
    for k in range(3):
        runs.append({'run_id':f'fixture-repeat-{k}', 'rows':[
            {'company_id':r['company_id'],'predicted_company_id':r['company_id'],'workspace_id':r['workspace_id'],
             'verdict':verdicts[i],'evidence_ids':[r['sources'][0]['id']] if verdicts[i]=='match' else []}
            for i,r in enumerate(rows)]})
    return {'schema':'buyeros.research-predictions.v1','runs':runs}


def evaluator():
    assert (TOOLS/'evaluate_research_goldset.py').is_file(), 'Q10 offline goldset evaluator missing'
    return importlib.import_module('tools.evaluate_research_goldset')


def test_latency_errors_use_all_requests_and_p99_is_not_faked():
    samples=[{'latency_ms':t,'status':s,'bytes':10,'queries':q,'sql_ms':1.0,'invalid_context':i}
             for t,s,q,i in [(10,200,4,False),(20,503,2,False),(30,200,4,True),(40,None,0,False)]]
    result=metrics().summarize_requests(samples)
    assert result['requests']==4
    assert result['latency_ms']=={'p50':25.0,'p95':38.5,'p99':39.7,'max':40.0,'p99_stable':False}
    assert result['errors']=={'denominator':4,'http_5xx':1,'http_non_2xx':1,'transport':1,'invalid_context':1,'failed_requests':3,'rate':0.75}
    assert result['queries']=={'total':10,'min':0,'max':4,'mean':2.5}
    assert result['bytes']=={'total':40,'min':10,'max':10}


@pytest.mark.parametrize('change',[{'latency_ms':float('nan')},{'latency_ms':-1},{'status':True},{'queries':True},{'bytes':-1}])
def test_invalid_observations_fail_closed(change):
    row={'latency_ms':10,'status':200,'bytes':10,'queries':4,'sql_ms':1,'invalid_context':False}
    with pytest.raises(ValueError):metrics().summarize_requests([{**row,**change}])


def test_empty_sample_is_not_a_passing_benchmark():
    with pytest.raises(ValueError):metrics().summarize_requests([])


def test_zero_denominator_and_small_n_wilson_are_explicit():
    assert metrics().proportion(0,0)=={'numerator':0,'denominator':0,'estimate':None,'ci95':None}
    result=metrics().proportion(1,1)
    assert result['estimate']==1.0
    assert result['ci95']==pytest.approx([0.2065493144,1.0])
    with pytest.raises(ValueError):metrics().proportion(2,1)


@pytest.mark.parametrize('variable',['BUYEROS_TEST_DATABASE_URL','BUYEROS_DATABASE_URL','DATABASE_URL','BUYEROS_WORKER_DATABASE_URL'])
def test_legacy_benchmark_refuses_each_inherited_database_before_pytest(variable,tmp_path):
    env={k:v for k,v in os.environ.items() if k not in ['BUYEROS_TEST_DATABASE_URL','BUYEROS_DATABASE_URL','DATABASE_URL','BUYEROS_WORKER_DATABASE_URL']}
    env[variable]='postgresql://not-used.example/shared'
    # RED safety: if old wrapper ignores this DSN, collect only. No DB fixture
    # starts, so the test proves the guard without touching any shared database.
    env['PYTEST_ADDOPTS']='--collect-only'
    result=subprocess.run([sys.executable,str(ROOT/'scripts/benchmark-buyeros.py'),'--fixture-size','1000',
                           '--workspaces','1','--output',str(tmp_path/'result.json')],env=env,capture_output=True,text=True,timeout=45)
    assert result.returncode==2, result.stdout+result.stderr
    assert variable in result.stderr
    assert not (tmp_path/'result.json').exists()


def test_three_fixture_runs_have_hand_derived_precision_recall_and_abstention():
    result=evaluator().evaluate(goldset(),predictions())
    assert result['holdout_companies']==6 and result['total_companies']==8
    assert len(result['runs'])==3
    first=result['runs'][0]
    assert first['confusion']=={'tp':2,'fp':1,'tn':1,'fn':1,'needs_review':2}
    assert first['precision']['estimate']==pytest.approx(2/3)
    assert first['recall']['estimate']==pytest.approx(2/3)
    assert first['coverage']['estimate']==pytest.approx(4/6)
    assert first['needs_review']['estimate']==pytest.approx(2/6)
    assert result['live_verified'] is False
    assert result['provider_calls']==0
    assert result['quality_thresholds_met'] is False
    assert result['safety_violations']==[]
    assert result['repeat_policy']=='separate per-run intervals; no pooled 3n sample'


@pytest.mark.parametrize('mutation',['company_split','same_annotator','unadjudicated','bad_reference','missing_holdout','duplicate_prediction','two_runs','train_prediction','unknown_company'])
def test_incomplete_or_leaky_goldset_comparisons_are_rejected(mutation):
    data=goldset();pred=predictions()
    if mutation=='company_split':data['rows'].append({**copy.deepcopy(data['rows'][2]),'split':'train'})
    elif mutation=='same_annotator':data['rows'][2]['annotations'][1]['annotator_id']='fixture-a'
    elif mutation=='unadjudicated':data['rows'][2]['annotations'][1]['verdict']='not_match'
    elif mutation=='bad_reference':data['rows'][2]['reference_verdict']='not_match'
    elif mutation=='missing_holdout':pred['runs'][0]['rows'].pop()
    elif mutation=='duplicate_prediction':pred['runs'][0]['rows'].append(copy.deepcopy(pred['runs'][0]['rows'][0]))
    elif mutation=='two_runs':pred['runs'].pop()
    elif mutation=='train_prediction':pred['runs'][0]['rows'][0]['company_id']=data['rows'][0]['company_id']
    elif mutation=='unknown_company':pred['runs'][0]['rows'][0]['company_id']='ffffffff-ffff-4fff-8fff-ffffffffffff'
    with pytest.raises(ValueError):evaluator().evaluate(data,pred)


def test_disagreement_requires_separate_adjudicator_and_reason():
    data=goldset();data['rows'][2]['annotations'][1]['verdict']='not_match'
    data['rows'][2]['adjudication']={'annotator_id':'fixture-c','verdict':'match','reason':'fixture-only independent adjudication'}
    assert evaluator().evaluate(data,predictions())['holdout_companies']==6
    data['rows'][2]['adjudication']['annotator_id']='fixture-a'
    with pytest.raises(ValueError):evaluator().evaluate(data,predictions())


@pytest.mark.parametrize('mutation,violation',[('wrong_company','wrong_company'),('wrong_workspace','wrong_workspace'),('unsupported','unsupported_evidence'),('no_evidence','match_without_qualified_evidence'),('stale_source','unsupported_evidence'),('inference_source','unsupported_evidence')])
def test_structural_source_and_scope_violations_are_not_hidden(mutation,violation):
    data=goldset();pred=predictions();row=pred['runs'][0]['rows'][0]
    if mutation=='wrong_company':row['predicted_company_id']='ffffffff-ffff-4fff-8fff-ffffffffffff'
    elif mutation=='wrong_workspace':row['workspace_id']='22222222-2222-4222-8222-222222222222'
    elif mutation=='unsupported':row['evidence_ids']=['unqualified-id']
    elif mutation=='no_evidence':row['evidence_ids']=[]
    elif mutation=='stale_source':data['rows'][2]['sources'][0]['current']=False
    elif mutation=='inference_source':data['rows'][2]['sources'][0]['is_inference']=True
    result=evaluator().evaluate(data,pred)
    assert violation in [v['code'] for v in result['safety_violations']]
    assert result['quality_thresholds_met'] is False and result['live_verified'] is False


def test_evaluator_cli_writes_versioned_fixture_report_and_preserves_inputs(tmp_path):
    data=tmp_path/'gold.json';pred=tmp_path/'pred.json';output=tmp_path/'report.json'
    data.write_text(json.dumps(goldset()),encoding='utf-8');pred.write_text(json.dumps(predictions()),encoding='utf-8')
    before=data.read_bytes(),pred.read_bytes()
    command=[sys.executable,str(TOOLS/'evaluate_research_goldset.py'),'--goldset',str(data),'--predictions',str(pred),'--output',str(output)]
    result=subprocess.run(command,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    report=json.loads(output.read_text())
    assert report['schema']=='buyeros.research-goldset-evaluation.v1'
    assert report['live_verified'] is False and report['evidence_mode']=='fixture'
    assert len(report['input_hashes']['goldset'])==64
    assert before==(data.read_bytes(),pred.read_bytes())
    assert subprocess.run(command,capture_output=True,timeout=30).returncode==2
    assert subprocess.run(command[:-1]+[str(data)],capture_output=True,timeout=30).returncode==2
    assert before==(data.read_bytes(),pred.read_bytes())


def test_no_predicted_matches_reports_unavailable_precision():
    pred=predictions()
    for run in pred['runs']:
        for row in run['rows']:row['verdict']='needs_review';row['evidence_ids']=[]
    result=evaluator().evaluate(goldset(),pred)
    assert result['runs'][0]['precision']['estimate'] is None
    assert result['runs'][0]['precision']['ci95'] is None
    assert result['runs'][0]['coverage']['estimate']==0
    assert result['quality_thresholds_met'] is False


def test_fixture_perfect_precision_is_never_release_or_live_verification():
    data=goldset();pred=predictions()
    for run in pred['runs']:
        for item,row in zip(run['rows'],data['rows'][2:]):
            item['verdict']=row['reference_verdict']
            item['evidence_ids']=[row['sources'][0]['id']] if item['verdict']=='match' else []
    result=evaluator().evaluate(data,pred)
    assert result['quality_thresholds_met'] is True
    assert result['live_verified'] is result['release_accepted'] is False


def test_declared_human_labels_require_real_sample_size_without_claiming_independence():
    data=goldset();data['evidence_mode']='declared_human_labels'
    with pytest.raises(ValueError,match='200'):evaluator().evaluate(data,predictions())


def test_duplicate_run_ids_are_not_three_independent_repeats():
    pred=predictions();pred['runs'][1]['run_id']=pred['runs'][0]['run_id']
    with pytest.raises(ValueError,match='distinct run'):evaluator().evaluate(goldset(),pred)


def test_p99_with_only_one_expected_tail_observation_stays_unstable():
    rows=[dict(latency_ms=i+1,status=200,bytes=1,queries=4,sql_ms=1,invalid_context=False) for i in range(100)]
    assert metrics().summarize_requests(rows)['latency_ms']['p99_stable'] is False


def test_legacy_benchmark_preserves_existing_dispatcher_evidence(tmp_path):
    env={k:v for k,v in os.environ.items() if k not in ['BUYEROS_TEST_DATABASE_URL','BUYEROS_DATABASE_URL','DATABASE_URL','BUYEROS_WORKER_DATABASE_URL']}
    env['PYTEST_ADDOPTS']='--collect-only'
    output=tmp_path/'result.json';dispatcher=tmp_path/'result-dispatcher.json'
    dispatcher.write_bytes(b'previous dispatcher evidence')
    result=subprocess.run([sys.executable,str(ROOT/'scripts/benchmark-buyeros.py'),'--fixture-size','1000','--workspaces','100','--output',str(output)],env=env,capture_output=True,text=True,timeout=45)
    assert result.returncode==2 and 'existing evidence' in result.stderr
    assert dispatcher.read_bytes()==b'previous dispatcher evidence' and not output.exists()
