"""C61-24 captured DB metadata and abstention; synthetic labels are never live acceptance."""
import asyncio,copy,importlib,json,uuid
from pathlib import Path
from datetime import datetime,timedelta,timezone
import psycopg,pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from tests.test_run_admission_integration_db import admission_case,project_api,ICP_ID,PROJECT_A,WORKSPACE_A,OPERATOR
from tests.cutover_fixtures import role_dsn

def tool():
    spec=importlib.util.find_spec('tools.capture_research_predictions')
    assert spec is not None,'C61-24 read-only research capture port missing'
    return importlib.import_module('tools.capture_research_predictions')

def ident(i):return str(uuid.UUID(int=i))

def sample():
    now=datetime.now(timezone.utc);ws,project,actor=map(ident,[1,2,3]);runs=list(map(ident,[10,11,12]));company,buyer,evidence,source,receipt=map(ident,[20,21,22,23,24])
    manifest={'schema':'buyeros.research-capture-manifest.v1','dataset_marker':'synthetic-capture','environment':'owned-fixture','database':'buyeros_test_capture','workspace_id':ws,'project_id':project,'actor_id':actor,'frozen_at':(now-timedelta(hours=1)).isoformat(),'goldset_sha256':'a'*64,'thresholds_sha256':'b'*64,'goldset_file':'gold.json','thresholds_file':'thresholds.json','run_ids':runs,'holdout':[{'company_id':company,'buyer_id':buyer}]}
    snapshots={'runs':[{'id':run,'workspace_id':ws,'project_id':project,'actor_id':actor,'status':'completed','created_at':now.isoformat(),'snapshot_hash':'c'*64,'versions':{}} for run in runs],'buyers':[{'id':buyer,'company_id':company,'workspace_id':ws,'project_id':project}],'assessments':[],'evidence':[],'receipts':[]}
    for i,run in enumerate(runs):
        eid,rid=ident(22+i*100),ident(24+i*100)
        snapshots['assessments'].append({'id':ident(30+i),'workspace_id':ws,'project_id':project,'project_buyer_id':buyer,'run_id':run,'verdict':'match','evidence_ids':[eid],'fit_algorithm_version':'live-model-v1','model_provenance':{'receipt_id':rid,'request_hash':'d'*64,'response_hash':'e'*64,'evidence_revisions':[{'id':eid,'version':1,'source_id':source,'source_hash':'f'*64}]}})
        snapshots['evidence'].append({'id':eid,'workspace_id':ws,'project_id':project,'company_id':company,'run_id':run,'version':1,'source_id':source,'source_hash':'f'*64,'current':True,'is_inference':False,'stance':'supports'})
        snapshots['receipts'].append({'id':rid,'workspace_id':ws,'project_id':project,'run_id':run,'buyer_id':buyer,'company_id':company,'state':'received','request_hash':'d'*64,'response_hash':'e'*64,'redacted':False,'expired':False,'model_id':'synthetic-model','prompt_version':'synthetic-prompt','pricing_version':'synthetic-price','contract_hash':'1'*64})
    return manifest,snapshots

def test_capture_excludes_wrong_company_and_preserves_abstention():
    m,s=sample();s['buyers'][0]['company_id']=ident(999)
    predictions,proof=tool().capture_snapshot(m,s)
    assert len(predictions['runs'])==3 and all(len(run['rows'])==1 for run in predictions['runs'])
    assert all(run['rows'][0]['predicted_company_id']==ident(999) and run['rows'][0]['verdict']=='needs_review' and run['rows'][0]['evidence_ids']==[] for run in predictions['runs'])
    assert all('wrong_company' in row['blockers'] for row in proof['observations'])
    assert proof['live_verified'] is proof['release_accepted'] is False and proof['provider_calls']==0

def test_capture_keeps_failed_and_needs_review_in_each_run_denominator():
    m,s=sample();s['runs'][1]['status']='failed';s['assessments'].pop(1);s['assessments'][1]['verdict']='needs_review'
    pred,proof=tool().capture_snapshot(m,s)
    assert [run['rows'][0]['verdict'] for run in pred['runs']]==['match','needs_review','needs_review']
    assert [row['run_status'] for row in proof['observations']]==['completed','failed','completed']
    assert 'missing_assessment' in proof['observations'][1]['blockers']

@pytest.mark.parametrize('gate',['unsupported','stale','inference','contradiction','receipt-unknown','receipt-erased','receipt-expired','receipt-hash','receipt-company','revision','ambiguous'])
def test_capture_never_turns_unqualified_or_unrecoverable_saved_data_into_match(gate):
    m,s=sample()
    if gate=='unsupported':s['assessments'][0]['evidence_ids']=[ident(999)]
    elif gate=='stale':s['evidence'][0]['current']=False
    elif gate=='inference':s['evidence'][0]['is_inference']=True
    elif gate=='contradiction':s['evidence'][0]['stance']='contradicts'
    elif gate=='receipt-unknown':s['receipts'][0]['state']='unknown'
    elif gate=='receipt-erased':s['receipts'][0]['redacted']=True
    elif gate=='receipt-expired':s['receipts'][0]['expired']=True
    elif gate=='receipt-hash':s['receipts'][0]['response_hash']='0'*64
    elif gate=='receipt-company':s['receipts'][0]['company_id']=ident(999)
    elif gate=='revision':s['evidence'][0]['version']=2
    else:s['assessments'].append(copy.deepcopy(s['assessments'][0]))
    pred,proof=tool().capture_snapshot(m,s);assert pred['runs'][0]['rows'][0]['verdict']=='needs_review' and proof['observations'][0]['blockers']
    assert len(pred['runs'])==3 and len(pred['runs'][0]['rows'])==1

@pytest.mark.parametrize('gate',['duplicate-run','duplicate-company','duplicate-buyer','foreign-project','running','posthoc'])
def test_capture_rejects_leaky_nonterminal_or_posthoc_manifest(gate):
    m,s=sample()
    if gate=='duplicate-run':m['run_ids'][1]=m['run_ids'][0]
    elif gate=='duplicate-company':m['holdout'].append({**m['holdout'][0],'buyer_id':ident(999)})
    elif gate=='duplicate-buyer':m['holdout'].append({**m['holdout'][0],'company_id':ident(999)})
    elif gate=='foreign-project':s['runs'][0]['project_id']=ident(999)
    elif gate=='running':s['runs'][0]['status']='running'
    else:m['frozen_at']=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
    module=tool()
    with pytest.raises(ValueError):module.capture_snapshot(m,s)

def test_capture_does_not_modify_inputs_and_serializes_original_prediction_schema():
    m,s=sample();before=copy.deepcopy((m,s));pred,proof=tool().capture_snapshot(m,s)
    from tools.evaluate_research_goldset import Predictions
    assert Predictions.model_validate(pred).runs[0].rows[0].verdict=='match'
    assert (m,s)==before and proof['repeat_policy']=='separate company-level runs; no pooled 3n sample'

@pytest.fixture
def capture_db(admission_case):
    api,dsn=admission_case;ws=uuid.UUID(WORKSPACE_A);project=uuid.UUID(PROJECT_A);actor=uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR);companies=[uuid.uuid4(),uuid.uuid4()];buyers=[uuid.uuid4(),uuid.uuid4()];runs=[uuid.uuid4() for _ in range(3)];frozen=datetime.now(timezone.utc)-timedelta(minutes=1)
    with psycopg.connect(dsn) as db:
        for company,buyer in zip(companies,buyers):
            db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name,domain) VALUES(%s,%s,'synthetic capture','synthetic capture','sensors.example.test')",(company,ws))
            db.execute('INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES(%s,%s,%s,%s)',(buyer,ws,project,company))
        for run,status in zip(runs,['completed','failed','partial']):db.execute("INSERT INTO search_runs(id,workspace_id,project_id,icp_version_id,status,execution_snapshot) VALUES(%s,%s,%s,%s,%s,%s::jsonb)",(run,ws,project,uuid.UUID(ICP_ID),status,json.dumps({'actor_id':str(actor),'capability':{'provider':'fixture','price_version':'fixture-price'}})))
    manifest={'schema':'buyeros.research-capture-manifest.v1','dataset_marker':'synthetic-capture-db','environment':'owned-fixture','database':make_url(async_database_url(role_dsn(dsn,'buyeros_api'))).database,'workspace_id':str(ws),'project_id':str(project),'actor_id':str(actor),'frozen_at':frozen.isoformat(),'goldset_sha256':'a'*64,'thresholds_sha256':'b'*64,'goldset_file':'gold.json','thresholds_file':'thresholds.json','run_ids':list(map(str,runs)),'holdout':[{'company_id':str(company),'buyer_id':str(buyer)} for company,buyer in zip(companies,buyers)]}
    try:yield {'dsn':dsn,'manifest':manifest,'ws':ws,'project':project,'actor':actor,'runs':runs}
    finally:
        with psycopg.connect(dsn) as db:
            db.execute('DELETE FROM search_runs WHERE id=ANY(%s)',(runs,));db.execute('DELETE FROM project_buyers WHERE id=ANY(%s)',(buyers,));db.execute('DELETE FROM companies WHERE id=ANY(%s)',(companies,))

@pytest.mark.parametrize('gate',['none','actor','policy','database','owner-role'])
def test_actual_runtime_readonly_capture_keeps_all_rows_and_denies_current_scope(capture_db,gate):
    c=capture_db;m=copy.deepcopy(c['manifest']);module=tool()
    with psycopg.connect(c['dsn']) as db:
        if gate=='actor':db.execute('UPDATE memberships SET active=false WHERE workspace_id=%s AND user_id=%s',(c['ws'],c['actor']))
        elif gate=='policy':db.execute("UPDATE policy_decisions SET status='blocked' WHERE workspace_id=%s",(c['ws'],))
    if gate=='database':m['database']='buyeros_test_wrong_target'
    async def run():
        dsn=c['dsn'] if gate=='owner-role' else role_dsn(c['dsn'],'buyeros_api')
        engine=create_async_engine(async_database_url(dsn),isolation_level='REPEATABLE READ')
        try:return await module.capture_from_db(engine,m)
        finally:await engine.dispose()
    if gate!='none':
        with pytest.raises(ValueError):asyncio.run(run())
    else:
        pred,proof=asyncio.run(run());assert len(pred['runs'])==3 and all(len(row['rows'])==2 for row in pred['runs'])
        assert all(row['verdict']=='needs_review' for run in pred['runs'] for row in run['rows'])
        assert proof['database_read_only'] is True and proof['database_role']=='buyeros_api' and proof['isolation']=='repeatable read'
        assert proof['provider_calls']==0 and proof['live_verified'] is False and len(proof['observations'])==6
        with psycopg.connect(c['dsn']) as db:assert db.execute('SELECT count(*) FROM fit_assessments WHERE run_id=ANY(%s)',(c['runs'],)).fetchone()==(0,)


def test_capture_missing_both_receipt_hashes_cannot_be_equal_authority():
    m,s=sample()
    for key in ['request_hash','response_hash']:
        s['receipts'][0][key]=None;s['assessments'][0]['model_provenance'][key]=None
    pred,proof=tool().capture_snapshot(m,s)
    assert pred['runs'][0]['rows'][0]['verdict']=='needs_review'
    assert 'unproven_model_receipt' in proof['observations'][0]['blockers']


@pytest.mark.parametrize('gate',['none','gold-hash','existing-main','existing-sidecar','holdout','threshold-freeze'])
def test_actual_capture_cli_preserves_frozen_inputs_and_exclusive_outputs(capture_db,tmp_path,gate):
    import hashlib,os,subprocess,sys
    c=capture_db;m=copy.deepcopy(c['manifest']);gold={'schema':'buyeros.research-goldset.v1','evidence_mode':'fixture','owner':'synthetic-only','rows':[]}
    for row in m['holdout']:
        gold['rows'].append({'company_id':row['company_id'],'workspace_id':m['workspace_id'],'market':'HK','language':'zh-HK','company_type':'synthetic','split':'holdout','reference_verdict':'not_match','annotations':[{'annotator_id':'synthetic-a','verdict':'not_match'},{'annotator_id':'synthetic-b','verdict':'not_match'}],'sources':[]})
    thresholds={'schema':'buyeros.research-thresholds.v1','frozen_at':m['frozen_at'],'recall_min':None,'coverage_min':None,'cost_max':None,'adoption':'pending product approval'}
    if gate=='holdout':gold['rows'][0]['company_id']=ident(999)
    if gate=='threshold-freeze':thresholds['frozen_at']=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
    gp=tmp_path/'gold.json';tp=tmp_path/'thresholds.json';mp=tmp_path/'manifest.json';output=tmp_path/'captured.json';sidecar=tmp_path/'captured-provenance.json'
    gp.write_text(json.dumps(gold),encoding='utf-8');tp.write_text(json.dumps(thresholds),encoding='utf-8');m.update(goldset_sha256=hashlib.sha256(gp.read_bytes()).hexdigest(),thresholds_sha256=hashlib.sha256(tp.read_bytes()).hexdigest());mp.write_text(json.dumps(m),encoding='utf-8')
    if gate=='gold-hash':gp.write_bytes(gp.read_bytes()+b' ')
    if gate=='existing-main':output.write_bytes(b'previous main evidence')
    if gate=='existing-sidecar':sidecar.write_bytes(b'previous sidecar evidence')
    before={p:p.read_bytes() for p in [gp,tp,mp,output,sidecar] if p.exists()}
    root=Path(__file__).resolve().parents[3];env=os.environ.copy();env['C61_RESEARCH_CAPTURE_DATABASE_URL']=role_dsn(c['dsn'],'buyeros_api')
    result=subprocess.run([sys.executable,str(root/'services/api/tools/capture_research_predictions.py'),'--manifest',str(mp),'--output',str(output)],cwd=root,env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode==(0 if gate=='none' else 2),result.stdout+result.stderr
    assert all(p.read_bytes()==raw for p,raw in before.items())
    if gate=='none':
        pred=json.loads(output.read_text());proof=json.loads(sidecar.read_text());assert len(pred['runs'])==3 and all(len(run['rows'])==2 for run in pred['runs'])
        assert proof['database_read_only'] is True and proof['provider_calls']==0 and proof['live_verified'] is proof['release_accepted'] is False
        from tools.evaluate_research_goldset import evaluate
        evaluated=evaluate(gold,pred);assert all(run['needs_review']['denominator']==2 and run['needs_review']['numerator']==2 for run in evaluated['runs'])
        assert evaluated['quality_thresholds_met'] is evaluated['live_verified'] is evaluated['release_accepted'] is False
    else:
        assert not output.exists() or gate=='existing-main'
        assert not sidecar.exists() or gate=='existing-sidecar'


def test_capture_preserves_valid_not_match_with_qualified_contradictory_evidence():
    m,s=sample();s['assessments'][0]['verdict']='not_a_match';s['evidence'][0]['stance']='contradicts'
    pred,proof=tool().capture_snapshot(m,s)
    assert pred['runs'][0]['rows'][0]['verdict']=='not_match'
    assert pred['runs'][0]['rows'][0]['evidence_ids']==[s['evidence'][0]['id']]
    assert proof['observations'][0]['blockers']==[]
