"""Owned C13 cold clusters and pinned compatible API archive, never deployment."""
import asyncio,hashlib,io,json,os,subprocess,sys,tarfile,time,uuid
from contextlib import contextmanager
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
import jwt,psycopg
from cryptography.hazmat.primitives.asymmetric import ed25519
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.auth import Principal
from buyeros_api.api.deps import async_database_url
from buyeros_api.db.session import tenant_session
from buyeros_api.services.identity_linking import create_canonical_user,link_identity
from buyeros_api.services.retention import expire_subject_data
from buyeros_api.settings import get_settings
from tests.conftest import _start_container,ALEMBIC_INI,SERVICE_ROOT,DB_USER,DB_NAME,runtime_role_dsn
from tests.test_backup_restore_t28 import _docker_binary
from tests.test_cloudflare_provider_steps_db import seed_research,SearchFixture,run_provider
from tests.test_identity_linking_db import historical_fks

from tests.retained_archive import ROLLBACK_SHA,retained_rollback_archive
ISSUER='https://ep-c61-cutover.neonauth.us-east-2.aws.neon.tech/neondb/auth'
AUDIENCE='https://c61-cutover.example.test'
ROOT=SERVICE_ROOT.parent.parent

def role_dsn(dsn,role):
    parts=urlsplit(dsn);return urlunsplit(parts._replace(netloc=f'{role}:test-only@{parts.hostname}:{parts.port}'))

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()

def snapshot(dsn,users,workspace):
    with psycopg.connect(dsn) as db:
        identities=db.execute('SELECT issuer,subject,user_id,status,proof_ref,version FROM user_identities ORDER BY issuer,subject').fetchall()
        tables={}
        for table in ['budget_accounts','budget_reservations','provider_operations','cost_events']:
            rows=db.execute('SELECT row_to_json(t)::text FROM '+table+' t WHERE workspace_id=%s ORDER BY id',(workspace,)).fetchall()
            tables[table]={'count':len(rows),'sha256':digest([x[0] for x in rows])}
        return {'canonical_ids':[str(x[0]) for x in db.execute('SELECT id FROM users ORDER BY id').fetchall()],
                'identities':{'count':len(identities),'sha256':digest(identities)},'ledger_and_unknown':tables,
                'historical_fks':{str(u):{str(k):v for k,v in historical_fks(db,u).items()} for u in users}}

def cold_api(archive,dsn,case,*,reads):
    env={k:v for k,v in os.environ.items() if not k.startswith('BUYEROS_') and k not in ['DATABASE_URL','PYTHONPATH']}
    env.update(PYTHONPATH=str(archive/'services/api'),PYTHONUTF8='1',BUYEROS_DATABASE_URL=runtime_role_dsn(dsn),BUYEROS_LIVE_READ_ENABLED=str(reads).lower(),BUYEROS_AUTH_MODE='neon',BUYEROS_ENVIRONMENT='preview',BUYEROS_NEON_ISSUER=ISSUER,BUYEROS_NEON_AUDIENCE=AUDIENCE,BUYEROS_NEON_JWKS_URL=ISSUER+'/jwks',BUYEROS_NEON_EXPECTED_ISSUER=ISSUER,BUYEROS_NEON_EXPECTED_AUDIENCE=AUDIENCE,BUYEROS_NEON_EXPECTED_JWKS_URL=ISSUER+'/jwks')
    probe=Path(__file__).with_name('cutover_api_probe.py')
    payload={k:case[k] for k in ['workspace','project','tokens','jwk']};payload['expected_package']=str(archive/'services/api/buyeros_api');payload['issuer']=ISSUER
    result=subprocess.run([sys.executable,str(probe)],cwd=archive,input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8',env=env,timeout=45)
    assert result.returncode==0,result.stderr[-2000:]
    return json.loads(result.stdout.strip().splitlines()[-1])

@contextmanager
def cold_cutover(monkeypatch,tmp_path):
    source=target=None;timeline=[]
    def mark(step,**data):timeline.append({'step':step,'utc':datetime.now(timezone.utc).isoformat(),**data})
    try:
        source,source_dsn=_start_container();target,target_dsn=_start_container()
        monkeypatch.setenv('BUYEROS_DATABASE_URL',source_dsn);get_settings.cache_clear()
        config=Config(str(ALEMBIC_INI));config.set_main_option('script_location',str(SERVICE_ROOT/'alembic'));command.upgrade(config,'0039_c61_user_identities')
        with psycopg.connect(source_dsn) as db:
            db.execute("ALTER ROLE buyeros_api LOGIN PASSWORD 'test-only'")
            db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
            # Current admission verifies an exact legacy head before excluding
            # the not-yet-installed pilot policy. This is metadata read only;
            # the cold fixture still uses the ordinary non-bypass worker role.
            db.execute("GRANT SELECT ON alembic_version TO buyeros_worker")
            db.execute("UPDATE worker_runtime_control SET backend='cloudflare',enabled=true,epoch=epoch+1 WHERE singleton=1")
            epoch=db.execute('SELECT epoch FROM worker_runtime_control').fetchone()[0]
        monkeypatch.setenv('BUYEROS_EXECUTION_DATABASE_URL',role_dsn(source_dsn,'buyeros_worker'));monkeypatch.setenv('BUYEROS_CLOUDFLARE_EXECUTION_ENABLED','true');get_settings.cache_clear()
        research=seed_research(source_dsn,epoch);workspace=research['envelope'].workspace_id;legacy=research['actor']
        key=ed25519.Ed25519PrivateKey.generate();subject='new-neon-only-'+uuid.uuid4().hex;old_subject='migrated-'+legacy.hex;revoked_subject='revoked-'+legacy.hex
        async def prepare_identities():
            engine=create_async_engine(async_database_url(source_dsn))
            try:
                async with tenant_session(engine,workspace) as session:
                    new_user=await create_canonical_user(session,principal=Principal(ISSUER,subject),proof_ref='offline-verified:'+subject)
                    await link_identity(session,user_id=legacy,issuer=ISSUER,subject=old_subject,proof_ref='offline-admin-verified:'+old_subject)
                    await link_identity(session,user_id=legacy,issuer=ISSUER,subject=revoked_subject,proof_ref='offline-admin-verified:'+revoked_subject)
                return new_user
            finally:await engine.dispose()
        new_user=asyncio.run(prepare_identities())
        source_id=uuid.uuid4();foreign=uuid.uuid4()
        with psycopg.connect(source_dsn) as db:
            db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES (%s,%s,%s,'{viewer}',true)",(uuid.uuid4(),workspace,new_user))
            db.execute("INSERT INTO workspace_preferences(id,workspace_id,user_id,locale,default_markets,version) VALUES (%s,%s,%s,'zh-HK','{HK}',1)",(uuid.uuid4(),workspace,new_user))
            db.execute("UPDATE user_identities SET status='revoked',version=version+1 WHERE issuer=%s AND subject=%s",(ISSUER,revoked_subject))
            db.execute("INSERT INTO workspaces(id,name,data_mode) VALUES (%s,'Foreign owned fixture','live')",(foreign,))
            db.execute("INSERT INTO source_documents(id,workspace_id,project_id,canonical_url,digest,storage_mode,object_key,excerpt,retention_until) VALUES(%s,%s,%s,%s,%s,'private_object',%s,'Private fictional source',now()-interval '1 day')",(source_id,workspace,research['project'],f'https://fixture.invalid/{source_id}','a'*64,f'tenants/{workspace}/{source_id}'))
            db.execute('UPDATE budget_accounts SET settled_spend=0.050000 WHERE workspace_id=%s',(workspace,))
            db.execute("INSERT INTO cost_events(id,workspace_id,kind,amount,pricing_version) VALUES (%s,%s,'commit',0.050000,'fixture-price-v1')",(uuid.uuid4(),workspace))
        adapter=SearchFixture(research,timeout=True);outcome=run_provider(research['envelope'],adapter=adapter)
        assert outcome.state=='reconcile' and outcome.code=='PROVIDER_UNKNOWN' and adapter.calls==1, (outcome, adapter.calls)
        before=snapshot(source_dsn,[legacy,new_user],workspace)
        assert before['ledger_and_unknown']['budget_reservations']['count']==1 and before['ledger_and_unknown']['provider_operations']['count']==1
        mark('expand_and_map',snapshot=before)
        command.downgrade(config,'0038_c61_workspace_directory');assert snapshot(source_dsn,[legacy,new_user],workspace)==before
        command.upgrade(config,'0039_c61_user_identities');assert snapshot(source_dsn,[legacy,new_user],workspace)==before
        mark('schema_rollback_and_reupgrade_preserve_all_rows',snapshot=before)
        # Keep the historical identity rollback proof; current retention needs its expanded schema.
        command.upgrade(config,'head')
        with psycopg.connect(source_dsn) as db:
            assert db.execute('SELECT version_num FROM alembic_version').fetchone()==('0055_lead_workflow',)
        expanded=snapshot(source_dsn,[legacy,new_user],workspace)
        assert {k:v for k,v in expanded.items() if k!='historical_fks'}=={k:v for k,v in before.items() if k!='historical_fks'}
        for user,prior in before['historical_fks'].items():
            current=expanded['historical_fks'][user]
            assert all(current[k]==v for k,v in prior.items())
            added=set(current)-set(prior)
            expected_added={str((service+'_receipts','actor_id')) for service in ('search','model','contact')}|{str(('delivery_messages','actor_id')),str(('document_uploads','actor_user_id')),str(('buyer_source_checks','recorded_by_user_id'))}
            expected_added|={str(('lead_action_intents','actor_id'))}|{str((table,'recorded_by_user_id')) for table in (
                'lead_observations','lead_reviews','lead_preparation_revisions','lead_preparation_content_reviews',
                'pilot_cost_events','pilot_credit_observations','pilot_reconciliations')}
            assert added==expected_added, (sorted(added),sorted(expected_added))
            assert all(current[k]==hashlib.sha256(json.dumps([]).encode()).hexdigest() for k in added)
        before=expanded
        mark('current_receipt_privacy_schema_before_backup',schema='0055_lead_workflow',snapshot=before)
        dump=_docker_binary(['exec',source,'pg_dump','-U',DB_USER,'-d',DB_NAME,'--format=custom','--no-owner'])
        mark('older_backup',bytes=len(dump),sha256=hashlib.sha256(dump).hexdigest())
        policy='c61-offline-retention-v1'
        async def expire(dsn):
            engine=create_async_engine(async_database_url(runtime_role_dsn(dsn)))
            try:
                async with tenant_session(engine,workspace) as session:return await expire_subject_data(session,source_id,policy,datetime.now(timezone.utc),subject_type='source_document')
            finally:await engine.dispose()
        assert asyncio.run(expire(source_dsn))['expired'] is True
        journal={'workspace_id':str(workspace),'subject_id':str(source_id),'subject_type':'source_document','policy_version':policy,'policy_digest':'sha256:'+hashlib.sha256(policy.encode()).hexdigest()}
        journal_path=tmp_path/'external-tombstone.json';journal_path.write_text(json.dumps(journal),encoding='utf-8');mark('external_fixture_tombstone',sha256=hashlib.sha256(journal_path.read_bytes()).hexdigest())
        with psycopg.connect(target_dsn) as db:
            db.execute("CREATE ROLE buyeros_api NOBYPASSRLS LOGIN PASSWORD 'test-only'")
            db.execute("CREATE ROLE buyeros_worker NOBYPASSRLS LOGIN PASSWORD 'test-only'")
        _docker_binary(['exec','-i',target,'pg_restore','-U',DB_USER,'-d',DB_NAME,'--no-owner'],input_bytes=dump)
        with psycopg.connect(target_dsn) as db:
            db.execute('GRANT USAGE ON SCHEMA public TO buyeros_api,buyeros_worker')
            assert db.execute('SELECT excerpt FROM source_documents WHERE id=%s',(source_id,)).fetchone()==('Private fictional source',)
            assert db.execute('SELECT rolbypassrls FROM pg_roles WHERE rolname=%s',('buyeros_api',)).fetchone()==(False,)
            assert db.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname='source_documents'").fetchone()==(True,True)
        assert snapshot(target_dsn,[legacy,new_user],workspace)==before
        from buyeros_api.services.worker_recovery import set_execution_runtime
        paused=set_execution_runtime(target_dsn,expected_epoch=epoch,backend='cloudflare',enabled=False,reason='Owned restored cluster; old worker epoch fenced',apply=True)
        assert paused['epoch']==epoch+1 and paused['enabled'] is False
        mark('restored_workers_paused_and_epoch_advanced_before_replay',epoch=paused['epoch'])
        archive_bytes=retained_rollback_archive()
        archive=tmp_path/'compatible-api-artifact';archive.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as tar:
            for member in tar.getmembers():
                assert (member.isdir() or member.isfile()) and (archive/member.name).resolve().is_relative_to(archive.resolve())
            tar.extractall(archive,filter='data')
        jwk={**json.loads(jwt.algorithms.OKPAlgorithm.to_jwk(key.public_key())),'kid':'c61-rollback','alg':'EdDSA','use':'sig'}
        tokens={name:jwt.encode({'iss':ISSUER,'aud':AUDIENCE,'sub':sub,'exp':int(time.time())+600},key,algorithm='EdDSA',headers={'kid':'c61-rollback'}) for name,sub in [('migrated',old_subject),('neon_only',subject),('revoked',revoked_subject)]}
        case={'workspace':str(workspace),'project':str(research['project']),'tokens':tokens,'jwk':jwk}
        closed_before=cold_api(archive,target_dsn,case,reads=False)
        assert closed_before['statuses']=={'migrated':503,'neon_only':503,'revoked':503} and set(closed_before['codes'].values())=={'READ_DISABLED'}
        mark('restored_backup_still_closed',api=closed_before,rollback_sha=ROLLBACK_SHA,archive_sha256=hashlib.sha256(archive_bytes).hexdigest())
        actual=json.loads(journal_path.read_text());assert actual==journal
        assert actual['policy_digest']=='sha256:'+hashlib.sha256(actual['policy_version'].encode()).hexdigest()
        assert asyncio.run(expire(target_dsn))['expired'] is True
        assert asyncio.run(expire(target_dsn))['expired'] is False
        with psycopg.connect(target_dsn) as db:
            assert db.execute('SELECT canonical_url,excerpt FROM source_documents WHERE id=%s',(source_id,)).fetchone()==(f'https://redacted.invalid/{source_id}',None)
            assert db.execute("SELECT count(*) FROM audit_events WHERE action='source.expired' AND subject_id=%s",(str(source_id),)).fetchone()==(1,)
            assert db.execute('SELECT count(*) FROM outbox_events WHERE intent_key=%s',(f'source.delete:{source_id}',)).fetchone()==(1,)
            assert db.execute('SELECT state,upper_bound,remaining_hold FROM budget_reservations WHERE workspace_id=%s',(workspace,)).fetchone()==('active',Decimal('0.100000'),Decimal('0.100000'))
            assert all(x[0]==Decimal('0.050000') for x in db.execute('SELECT settled_spend FROM budget_accounts WHERE workspace_id=%s',(workspace,)).fetchall())
            assert db.execute("SELECT sum(amount) FROM cost_events WHERE kind='commit' AND workspace_id=%s",(workspace,)).fetchone()==(Decimal('0.050000'),)
        after=snapshot(target_dsn,[legacy,new_user],workspace);assert after==before
        closed_after=cold_api(archive,target_dsn,case,reads=False);assert closed_after['statuses']==closed_before['statuses']
        mark('tombstone_replayed_twice_and_ledger_reconciled_reads_still_closed',snapshot=after,api=closed_after)
        with psycopg.connect(runtime_role_dsn(target_dsn)) as db:
            db.execute("SELECT set_config('app.workspace_id',%s,true)",(str(foreign),))
            assert db.execute('SELECT count(*) FROM source_documents').fetchone()==(0,)
            assert db.execute('SELECT count(*) FROM budget_reservations').fetchone()==(0,)
        monkeypatch.setenv('BUYEROS_EXECUTION_DATABASE_URL',role_dsn(target_dsn,'buyeros_worker'));get_settings.cache_clear()
        fenced=run_provider(research['envelope'],adapter=adapter)
        assert fenced.state=='stale' and adapter.calls==1 and adapter.status_calls==0
        assert snapshot(target_dsn,[legacy,new_user],workspace)==before
        mark('old_epoch_cannot_resume_or_submit',epoch=paused['epoch'],old_epoch=epoch,provider_calls=adapter.calls,provider_status_calls=adapter.status_calls)
        reopened=cold_api(archive,target_dsn,case,reads=True)
        assert reopened['statuses']=={'migrated':200,'neon_only':200,'revoked':404},reopened
        assert reopened['canonical_project_ids']=={'migrated':str(research['project']),'neon_only':str(research['project'])}
        assert reopened['ready'] is False
        assert snapshot(target_dsn,[legacy,new_user],workspace)==before
        mark('local_reviewer_reopens_only_reads_with_compatible_neon_api_workers_unready',api=reopened)
        yield {'before':before,'after':after,'reopened':reopened,'closed_before':closed_before,'closed_after':closed_after,'rollback_sha':ROLLBACK_SHA,'archive_sha256':hashlib.sha256(archive_bytes).hexdigest(),'timeline':timeline,'unknown_holds_preserved':True,'tombstone_replayed':True,'old_epoch_fenced':True,'new_user':str(new_user)}
    finally:
        get_settings.cache_clear()
        for name in [target,source]:
            if name:subprocess.run(['docker','rm','-f',name],capture_output=True)
