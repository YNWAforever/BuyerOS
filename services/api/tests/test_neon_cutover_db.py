"""C61-13 isolated migration/cutover proof; no real provider or production switch."""
import uuid
from contextlib import asynccontextmanager
import psycopg,pytest
from tests.fixture_reports import fresh_report_path
from tests.test_identity_reconciliation_db import identity_admin,run,row,counts
from tests.test_buyer_review_db import ADMIN,api
from tests.test_identity_linking_db import historical_fks

@pytest.mark.parametrize("collision_position",[0,1])
def test_identity_collision_stops_entire_cutover_batch(identity_admin,collision_position):
    dsn,user=identity_admin;fresh=row(user);collision=row(user)
    with psycopg.connect(dsn) as db:
        db.execute("INSERT INTO user_identities(issuer,subject,user_id,proof_ref) VALUES (%s,%s,%s,%s)",(collision['issuer'],collision['subject'],uuid.uuid5(uuid.NAMESPACE_URL,ADMIN),'different-verified-owner'))
        fks=historical_fks(db,user)
    manifest=[fresh];manifest.insert(collision_position,collision);before=counts(dsn)
    result=run(dsn,manifest,apply=True)
    assert result[collision_position]['status']=='conflict'
    assert all(x['status'] not in ('linked','replayed') and x['audit_ref'] is None for x in result)
    assert counts(dsn)==before
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT count(*) FROM user_identities WHERE issuer=%s AND subject=%s',(fresh['issuer'],fresh['subject'])).fetchone()[0]==0
        assert historical_fks(db,user)==fks

def test_later_denied_workspace_rolls_back_earlier_mapping(identity_admin):
    dsn,user=identity_admin;fresh=row(user);denied=row(user,workspace='22222222-2222-4222-8222-222222222222');before=counts(dsn)
    result=run(dsn,[fresh,denied],apply=True)
    assert result[1]['status']=='denied'
    assert result[0]['status'] not in ('linked','replayed') and result[0]['audit_ref'] is None
    assert counts(dsn)==before

def test_unknown_batch_commit_has_one_transaction_and_only_readonly_recovery(identity_admin,monkeypatch):
    from sqlalchemy.exc import OperationalError
    from buyeros_api.db import session as db_session
    dsn,user=identity_admin;manifest=[row(user),row(user)];before=counts(dsn);original=db_session.tenant_session;writes=[]
    @asynccontextmanager
    async def committed_but_lost(*args,**kwargs):
        if not kwargs.get('read_only',False):writes.append(1)
        async with original(*args,**kwargs) as session:yield session
        if not kwargs.get('read_only',False):raise OperationalError('owned lost batch acknowledgement',{},RuntimeError('offline fixture response lost'))
    with monkeypatch.context() as patch:
        patch.setattr(db_session,'tenant_session',committed_but_lost)
        result=run(dsn,manifest,apply=True)
    assert [x['status'] for x in result]==['unknown-commit','unknown-commit']
    assert writes==[1]
    after=counts(dsn);assert after[1]==before[1]+2 and after[3]==before[3]+2
    recovered=run(dsn,manifest)
    assert all(x['status']=='replayed' and x['audit_ref'] for x in recovered)
    assert counts(dsn)==after


def test_neon_cutover_rollback_preserves_new_users(monkeypatch,tmp_path):
    from tests.cutover_fixtures import cold_cutover
    import json
    with cold_cutover(monkeypatch,tmp_path) as case:
        neon_only_login_after_rollback=case['reopened']['statuses']['neon_only']==200
        canonical_ids_before=case['before']['canonical_ids'];canonical_ids_after=case['after']['canonical_ids']
        unknown_holds_before=case['before']['ledger_and_unknown'];unknown_holds_after=case['after']['ledger_and_unknown']
        assert neon_only_login_after_rollback is True
        assert canonical_ids_after==canonical_ids_before
        assert unknown_holds_after==unknown_holds_before
        assert case['before']['historical_fks']==case['after']['historical_fks']
        assert case['reopened']['statuses']['revoked']==404
        proof={k:v for k,v in case.items() if k not in ['new_user']}
        from tests.cutover_fixtures import ROOT
        fresh_report_path(ROOT/'artifacts/c61/C61-19-page-cold-compatible-api-rehearsal.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')

def test_restore_replays_deletion_before_reopen(monkeypatch,tmp_path):
    from tests.cutover_fixtures import cold_cutover,ROOT
    import json
    with cold_cutover(monkeypatch,tmp_path) as case:
        assert set(case['closed_before']['statuses'].values())=={503}
        assert set(case['closed_after']['statuses'].values())=={503}
        assert case['tombstone_replayed'] and case['unknown_holds_preserved'] and case['old_epoch_fenced']
        steps=[x['step'] for x in case['timeline']]
        assert steps.index('external_fixture_tombstone')<steps.index('restored_backup_still_closed')
        assert steps.index('tombstone_replayed_twice_and_ledger_reconciled_reads_still_closed')<steps.index('local_reviewer_reopens_only_reads_with_compatible_neon_api_workers_unready')
        assert case['reopened']['ready'] is False
        proof={k:v for k,v in case.items() if k not in ['new_user']}
        fresh_report_path(ROOT/'artifacts/c61/C61-19-page-cold-deletion-replay-rehearsal.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')


def test_atomic_manifest_scopes_multiple_workspaces_and_replays(identity_admin):
    from tests.test_buyer_review_db import WORKSPACE_A,WORKSPACE_B
    dsn,user=identity_admin;admin=uuid.uuid5(uuid.NAMESPACE_URL,ADMIN)
    with psycopg.connect(dsn) as db:
        for actor,roles in [(admin,['workspace_admin']),(user,['viewer'])]:
            db.execute('INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES (%s,%s,%s,%s,true)',(uuid.uuid4(),WORKSPACE_B,actor,roles))
    manifest=[row(user,workspace=WORKSPACE_B),row(user,workspace=WORKSPACE_A)];before=counts(dsn)
    linked=run(dsn,manifest,apply=True);assert all(x['status']=='linked' and x['audit_ref'] for x in linked)
    after=counts(dsn);assert after[1]==before[1]+2 and after[3]==before[3]+2
    replayed=run(dsn,manifest,apply=True);assert all(x['status']=='replayed' for x in replayed)
    assert [x['audit_ref'] for x in replayed]==[x['audit_ref'] for x in linked]
    assert counts(dsn)==after
