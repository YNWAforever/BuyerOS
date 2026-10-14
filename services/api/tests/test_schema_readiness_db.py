"""C61-31: real runtime-role catalog checks; owned disposable PG only."""
import asyncio
import hashlib
import importlib
import uuid
from urllib.parse import urlsplit

import psycopg
import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from tests.conftest import runtime_role_dsn

SHA = 'a' * 40


@pytest.fixture
def readiness_db(isolated_seeded):
    # Explicit probe prerequisite, independent of ordinary API permissions.
    # The production role currently lacks even this metadata column grant.
    with psycopg.connect(isolated_seeded) as owner:
        owner.execute('GRANT SELECT(version_num) ON public.alembic_version TO buyeros_api')
    return isolated_seeded


def contract(dsn, **changes):
    parsed = urlsplit(dsn)
    data = dict(contract_version='buyeros.schema-contract.v1', source_sha=SHA,
        required_revisions=['0038_c61_workspace_directory','0039_c61_user_identities'],
        compatible_heads=['0053_resumable_documents'],
        required_relations={'public.user_identities':['issuer','subject','user_id','status'],
                            'public.memberships':['id','workspace_id','user_id','roles','active']},
        required_functions=['public.buyeros_workspace_directory(uuid,bigint,integer)'],
        required_privileges=[{'relation':'public.user_identities','columns':['issuer','subject','user_id','status'],'privilege':'SELECT'}],
        required_rls=['public.memberships'],
        runtime_role_policy={'role':'buyeros_api','superuser':False,'bypass_rls':False},
        target={'database':parsed.path[1:],'endpoint_sha256':hashlib.sha256(f'{parsed.hostname}:{parsed.port or 5432}'.encode()).hexdigest(),
                'metadata_receipt_sha256':'b'*64},
        target_receipt={'database':parsed.path[1:],'endpoint_sha256':hashlib.sha256(f'{parsed.hostname}:{parsed.port or 5432}'.encode()).hexdigest(),
                'metadata_receipt_sha256':'b'*64}, evidence_mode='owned_disposable_fixture')
    data.update(changes)
    return data


def inspect(dsn, data=None, statements=None):
    try:
        module=importlib.import_module('buyeros_api.services.schema_readiness')
    except ModuleNotFoundError:
        module=None
    assert module is not None, 'read-only schema readiness probe is not implemented'
    async def run():
        engine=create_async_engine(runtime_role_dsn(dsn).replace('postgresql://','postgresql+psycopg://',1))
        if statements is not None:
            event.listen(engine.sync_engine,'before_cursor_execute',lambda conn,cursor,sql,params,context,many:statements.append(sql))
        try:
            async with engine.connect() as connection:
                result=await module.inspect_schema(connection,module.SchemaContract.model_validate(data or contract(dsn)))
                assert not connection.in_transaction(), 'probe must roll back its read-only snapshot'
                return result
        finally:
            await engine.dispose()
    return asyncio.run(run())


def test_expanded_compatible_schema_is_allowed(readiness_db):
    result=inspect(readiness_db)
    assert result.compatible is True and result.target_match is True
    assert result.observed_heads == ['0053_resumable_documents']
    assert result.blockers == []

def test_runtime_receipt_has_unambiguous_checks_for_promotion(readiness_db):
    result=inspect(readiness_db)
    codes=[item.code for item in result.checks]
    assert len(codes)==len(set(codes)), 'a valid runtime receipt cannot be rejected for repeated schema checks'

def test_runtime_receipt_binds_reviewed_schema_contract(readiness_db):
    result=inspect(readiness_db)
    assert hasattr(result,'contract_sha256'), 'release join needs the exact reviewed schema contract digest'
    changed=contract(readiness_db,statement_timeout_ms=4000)
    assert inspect(readiness_db,changed).contract_sha256!=result.contract_sha256

def test_real_probe_check_set_joins_gate_but_fixture_cannot_promote(readiness_db):
    import importlib.util
    from pathlib import Path
    root=Path(__file__).resolve().parents[3]
    def load(name,path):
        spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    fixtures=load('release_fixture_contract',root/'tests/test_release_readiness.py')
    gate=load('release_gate_contract',root/'scripts/check-release-readiness.py')
    manifest,receipts=fixtures.candidate()
    probe=inspect(readiness_db)
    manifest['schema_contract_sha256']=probe.contract_sha256
    receipts['items']['schema']['data']=probe.model_dump(mode='json',by_alias=True)
    result=gate.evaluate_release(manifest,receipts,'workspace')
    assert not result['promotable'] and 'schema_not_live' in result['blockers']
    assert 'schema_required_checks_missing_or_failed' not in result['blockers']
    assert 'schema_contract_mismatch' not in result['blockers']

def test_createdb_runtime_role_is_not_a_compatible_api_role(readiness_db):
    with psycopg.connect(readiness_db) as owner:owner.execute('ALTER ROLE buyeros_api CREATEDB')
    try:
        result=inspect(readiness_db)
        assert not result.compatible and 'runtime_role_privileged' in result.blockers
    finally:
        with psycopg.connect(readiness_db) as owner:owner.execute('ALTER ROLE buyeros_api NOCREATEDB')


def test_missing_identity_relation_blocks_readiness(readiness_db):
    with psycopg.connect(readiness_db) as owner:
        owner.execute('ALTER TABLE public.user_identities RENAME TO owned_hidden_identities')
    result=inspect(readiness_db)
    assert result.compatible is False
    assert 'relation_missing:public.user_identities' in result.blockers


def test_same_head_wrong_target_is_blocked(readiness_db):
    data=contract(readiness_db)
    data['target']['metadata_receipt_sha256']='c'*64
    result=inspect(readiness_db,data)
    assert result.observed_heads == ['0053_resumable_documents']
    assert result.target_match is False and result.compatible is False


def test_runtime_role_cannot_see_required_relation(readiness_db):
    with psycopg.connect(readiness_db) as owner:
        owner.execute('REVOKE SELECT(issuer,subject,user_id,status) ON public.user_identities FROM buyeros_api')
    result=inspect(readiness_db)
    assert result.compatible is False
    assert 'privilege_missing:public.user_identities:SELECT' in result.blockers


def test_unknown_schema_is_not_ready(readiness_db):
    with psycopg.connect(readiness_db) as owner:
        owner.execute("UPDATE public.alembic_version SET version_num='0099_unreviewed_future'")
    assert 'schema_head_unknown' in inspect(readiness_db).blockers


def test_declared_compatible_head_cannot_omit_required_revision(readiness_db):
    data=contract(readiness_db)
    data['required_revisions']=['0099_unreviewed_future']
    assert 'required_revision_unproven' in inspect(readiness_db,data).blockers


def test_probe_never_writes_or_leaves_session_settings(readiness_db):
    statements=[]
    result=inspect(readiness_db,statements=statements)
    assert result.compatible
    assert all(s.lstrip().upper().startswith(('SELECT','SET TRANSACTION')) for s in statements)
    assert any('READ ONLY' in s for s in statements)
    assert all('UPDATE ' not in s.upper() and 'INSERT ' not in s.upper() for s in statements)


@pytest.mark.parametrize('change',['missing_receipt','wrong_endpoint','owner_role','rls_disabled','search_path_hidden'])
def test_unsafe_or_unproven_runtime_is_not_ready(readiness_db,change):
    data=contract(readiness_db)
    if change=='missing_receipt': data['target_receipt']=None
    elif change=='wrong_endpoint': data['target_receipt']['endpoint_sha256']='d'*64
    elif change=='owner_role': data['runtime_role_policy']['role']='neondb_owner'
    else:
        with psycopg.connect(readiness_db) as owner:
            if change=='rls_disabled': owner.execute('ALTER TABLE public.memberships DISABLE ROW LEVEL SECURITY')
            else: owner.execute("ALTER ROLE buyeros_api IN DATABASE "+urlsplit(readiness_db).path[1:]+" SET search_path=pg_catalog")
    assert inspect(readiness_db,data).compatible is False
