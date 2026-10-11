"""Signed administrator proof + owned DB; identity CLI must default to dry-run."""
import asyncio
import uuid
import psycopg
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import dispose_engines
from tests import auth_fixtures as fx
from tests.test_buyer_review_db import ADMIN, OPERATOR, WORKSPACE_A, WORKSPACE_B, api

@pytest.fixture
def identity_admin(api, seeded):
    user = uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR)
    yield seeded, user

def row(user, *, workspace=WORKSPACE_A, subject=None, proof=None, version=0):
    subject = subject or 'c61-verified-' + uuid.uuid4().hex
    return {'workspace_id': workspace, 'canonical_user_id': str(user), 'issuer': 'urn:c61:neon',
            'subject': subject, 'proof_kind': 'administrator_verified',
            'proof_ref': proof or 'admin-verified:' + subject, 'reason': 'Verified both principal records',
            'expected_version': version}

def run(dsn, rows, *, apply=False, subject=ADMIN):
    async def exercise():
        from buyeros_api.services.identity_linking import reconcile_identity_manifest
        engine=create_async_engine(dsn.replace('postgresql://','postgresql+psycopg://',1))
        try:return await reconcile_identity_manifest(rows, token=fx.make_token(sub=subject), writer_engine=engine, apply=apply)
        finally:await engine.dispose();await dispose_engines()
    return asyncio.run(exercise())

def counts(dsn):
    with psycopg.connect(dsn) as owner:
        return tuple(owner.execute('SELECT count(*) FROM ' + table).fetchone()[0]
                     for table in ('users','user_identities','memberships','audit_events','idempotency_records','api_rate_windows'))

def test_identity_cli_defaults_dry_run_without_any_write(identity_admin):
    dsn,user=identity_admin;before=counts(dsn)
    result=run(dsn,[row(user)])
    assert result[0]['status']=='would-link' and result[0]['audit_ref'] is None
    assert counts(dsn)==before

def test_identity_cli_apply_exact_receipt_replays_without_duplicate_audit(identity_admin):
    dsn,user=identity_admin;manifest=[row(user)];before=counts(dsn)
    first=run(dsn,manifest,apply=True);second=run(dsn,manifest,apply=True)
    assert first[0]['status']=='linked' and first[0]['audit_ref']
    assert second[0]['status']=='replayed' and second[0]['audit_ref']==first[0]['audit_ref']
    after=counts(dsn);assert after[0]==before[0] and after[2]==before[2] and after[1]==before[1]+1 and after[3]==before[3]+1

def test_identity_cli_requires_current_db_admin_and_target_workspace_membership(identity_admin):
    dsn,user=identity_admin;before=counts(dsn)
    assert run(dsn,[row(user)],apply=True,subject=OPERATOR)[0]['status']=='denied'
    assert run(dsn,[row(user,workspace=WORKSPACE_B)],apply=True)[0]['status']=='denied'
    assert counts(dsn)==before

def test_identity_cli_revoked_admin_cannot_apply_after_prior_verified_token(identity_admin):
    dsn,user=identity_admin;manifest=[row(user)]
    assert run(dsn,manifest)[0]['status']=='would-link'
    with psycopg.connect(dsn) as owner:
        owner.execute("UPDATE memberships SET active=false,version=version+1 WHERE workspace_id=%s AND user_id=%s",(WORKSPACE_A,uuid.uuid5(uuid.NAMESPACE_URL,ADMIN)))
    before=counts(dsn)
    assert run(dsn,manifest,apply=True)[0]['status']=='denied'
    assert counts(dsn)==before

def test_identity_cli_different_proof_or_stale_version_cannot_replay(identity_admin):
    dsn,user=identity_admin;manifest=[row(user)]
    assert run(dsn,manifest,apply=True)[0]['status']=='linked'
    before=counts(dsn)
    for changed in [dict(manifest[0],proof_ref='different-admin-proof'),dict(manifest[0],expected_version=7)]:
        assert run(dsn,[changed],apply=True)[0]['status']=='conflict'
    assert counts(dsn)==before


def test_identity_cli_lost_commit_is_unknown_then_readonly_receipt_recovers(identity_admin,monkeypatch):
    from contextlib import asynccontextmanager
    from sqlalchemy.exc import OperationalError
    from buyeros_api.db import session as db_session
    dsn,user=identity_admin;manifest=[row(user)];before=counts(dsn);original=db_session.tenant_session
    @asynccontextmanager
    async def committed_but_lost(*args,**kwargs):
        async with original(*args,**kwargs) as session:yield session
        raise OperationalError('owned lost commit acknowledgement',{},RuntimeError('fixture lost response'))
    with monkeypatch.context() as patch:
        patch.setattr(db_session,'tenant_session',committed_but_lost)
        result=run(dsn,manifest,apply=True)
    assert result[0]['status']=='unknown-commit'
    after=counts(dsn);assert after[1]==before[1]+1 and after[3]==before[3]+1
    recovered=run(dsn,manifest)
    assert recovered[0]['status']=='replayed' and recovered[0]['audit_ref']
    assert counts(dsn)==after
