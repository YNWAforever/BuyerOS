"""C61-03: signed fixture JWT, real runtime role, controlled canonical membership."""
import asyncio
import importlib
import uuid

import jwt
import psycopg
import pytest

from buyeros_api.api.deps import dispose_engines
from buyeros_api.api.errors import ApiError
from tests import auth_fixtures as fx
from tests.test_buyer_review_db import ADMIN, OPERATOR, WORKSPACE_A, WORKSPACE_B, api


def run(rows, *, apply=False, token=None):
    async def exercise():
        module = importlib.import_module('buyeros_api.services.staff_onboarding')
        try:
            return await module.reconcile_staff_manifest(rows, token=token or fx.make_token(sub=ADMIN), apply=apply)
        finally:
            await dispose_engines()
    return asyncio.run(exercise())


@pytest.fixture
def staff(api, seeded):
    user = uuid.uuid4()
    with psycopg.connect(seeded) as owner:
        owner.execute('INSERT INTO users(id,issuer,subject,display_name) VALUES (%s,%s,%s,%s)',
                      (user, fx.ISSUER, 'c61-staff-' + str(user), 'Same display name'))
    yield seeded, user
    with psycopg.connect(seeded) as owner:
        owner.execute('DELETE FROM memberships WHERE user_id=%s', (user,))
        owner.execute('DELETE FROM users WHERE id=%s', (user,))


def row(user, *, workspace=WORKSPACE_A, roles=None, version=0):
    return {'canonical_user_id': str(user), 'workspace_id': workspace,
            'roles': roles or ['operator'], 'reason': 'Approved staffing change',
            'proof_ref': 'staff-change/approved-fixture-01', 'expected_version': version}


def counts(dsn):
    with psycopg.connect(dsn) as owner:
        return tuple(owner.execute('SELECT count(*) FROM ' + table).fetchone()[0]
                     for table in ('users', 'memberships', 'audit_events', 'idempotency_records', 'api_rate_windows'))


def test_onboarding_dry_run_no_write(staff):
    dsn, user = staff
    before = counts(dsn)
    result = run([row(user)])
    assert result[0]['status'] == 'would-create'
    assert result[0]['audit_ref'] is None
    assert counts(dsn) == before


def test_same_email_no_link(staff):
    dsn, _ = staff
    claims = jwt.decode(fx.make_token(sub=ADMIN), options={'verify_signature': False})
    claims['email'] = 'shared-fixture@example.invalid'
    token = jwt.encode(claims, fx._private_key, algorithm='RS256', headers={'kid': fx.KID})
    before = counts(dsn)
    assert run([row(uuid.uuid4())], token=token, apply=True)[0]['status'] == 'pending-identity'
    assert counts(dsn) == before


def test_conflict_no_escalation(staff):
    dsn, user = staff
    member = uuid.uuid4()
    with psycopg.connect(dsn) as owner:
        owner.execute('INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES (%s,%s,%s,%s,false)',
                      (member, WORKSPACE_A, user, ['viewer']))
    before = counts(dsn)
    result = run([row(user, roles=['workspace_admin'], version=1)], apply=True)
    assert result[0]['status'] == 'conflict'
    assert counts(dsn) == before
    with psycopg.connect(dsn) as owner:
        assert owner.execute('SELECT roles,active,version FROM memberships WHERE id=%s', (member,)).fetchone() == (['viewer'], False, 1)


def test_last_admin_survives(staff):
    dsn, _ = staff
    actor = uuid.uuid5(uuid.NAMESPACE_URL, ADMIN)
    result = run([row(actor, roles=['viewer'], version=1)], apply=True)
    assert result[0]['status'] == 'conflict'
    with psycopg.connect(dsn) as owner:
        assert owner.execute('SELECT roles,active,version FROM memberships WHERE workspace_id=%s AND user_id=%s',
                             (WORKSPACE_A, actor)).fetchone() == (['workspace_admin'], True, 1)


def test_apply_replays_exact_membership_without_duplicate_audit(staff):
    dsn, user = staff
    manifest = [row(user)]
    result = run(manifest, apply=True)[0]
    assert result['status'] == 'created' and result['version'] == 1 and result['audit_ref']
    first = counts(dsn)
    replay = run(manifest, apply=True)[0]
    assert replay == {**result, 'status': 'replayed'}
    # Rate admission is not used by this bounded administrative CLI; authority
    # remains current DB membership and every applied row is locked/audited.
    assert counts(dsn) == first
    with psycopg.connect(dsn) as owner:
        assert owner.execute('SELECT id FROM users WHERE id=%s', (user,)).fetchone() == (user,)
        audit = owner.execute('SELECT actor_id,subject_id,detail_digest FROM audit_events WHERE id=%s',
                              (result['audit_ref'],)).fetchone()
        assert audit[:2] == (uuid.uuid5(uuid.NAMESPACE_URL, ADMIN), result['membership_id'])
        assert audit[2].startswith('sha256:')


def test_revoked_replay_does_not_restore_or_duplicate(staff):
    dsn, user = staff
    manifest = [row(user)]
    first = run(manifest, apply=True)[0]
    with psycopg.connect(dsn) as owner:
        owner.execute('UPDATE memberships SET active=false,version=version+1 WHERE id=%s', (first['membership_id'],))
    before = counts(dsn)
    assert run(manifest, apply=True)[0]['status'] == 'conflict'
    assert counts(dsn) == before


def test_restore_uses_exact_previous_roles_and_current_version(staff):
    dsn, user = staff
    member = uuid.uuid4()
    with psycopg.connect(dsn) as owner:
        owner.execute('INSERT INTO memberships(id,workspace_id,user_id,roles,active,version) VALUES (%s,%s,%s,%s,false,3)',
                      (member, WORKSPACE_A, user, ['operator']))
    assert run([row(user, version=2)], apply=True)[0]['status'] == 'conflict'
    result = run([row(user, version=3)], apply=True)[0]
    assert result['status'] == 'restored' and result['membership_id'] == str(member) and result['version'] == 4


@pytest.mark.parametrize('subject,workspace', [(OPERATOR, WORKSPACE_A), (ADMIN, WORKSPACE_B), ('auth0|unknown-staff', WORKSPACE_A)])
def test_existing_current_admin_authority_required(staff, subject, workspace):
    dsn, user = staff
    before = counts(dsn)
    result = run([row(user, workspace=workspace)], apply=True, token=fx.make_token(sub=subject))[0]
    assert result['status'] == 'denied' and result['code'] in ('NOT_FOUND', 'PERMISSION_DENIED')
    assert counts(dsn) == before


@pytest.mark.parametrize('token', ['malformed-token', fx.make_token(sub=ADMIN, aud='wrong-audience'), fx.make_token(sub=ADMIN, exp=1)])
def test_cli_uses_gateway_jwt_verification_before_writes(staff, token):
    dsn, user = staff
    before = counts(dsn)
    with pytest.raises(ApiError) as denied:
        run([row(user)], token=token, apply=True)
    assert denied.value.status_code == 401 and counts(dsn) == before


@pytest.mark.parametrize('change', [{'email': 'shared-fixture@example.invalid'}, {'expected_version': True},
    {'expected_version': -1}, {'roles': ['superuser']}, {'roles': ['viewer', 'viewer']}, {'proof_ref': ''}])
def test_manifest_rejects_unknown_email_bad_versions_roles_and_missing_proof_before_writes(staff, change):
    from pydantic import ValidationError
    dsn, user = staff
    before = counts(dsn)
    with pytest.raises(ValidationError):
        run([{**row(user), **change}], apply=True)
    assert counts(dsn) == before


def test_duplicate_targets_rejected_before_any_row_writes(staff):
    dsn, user = staff
    before = counts(dsn)
    with pytest.raises(ValueError):
        run([row(user), row(user)], apply=True)
    assert counts(dsn) == before


def test_concurrent_same_manifest_commits_one_membership_and_receipt(staff):
    dsn, user = staff
    async def exercise():
        module = importlib.import_module('buyeros_api.services.staff_onboarding')
        try:
            return await asyncio.gather(*(module.reconcile_staff_manifest([row(user)], token=fx.make_token(sub=ADMIN), apply=True) for _ in range(2)))
        finally:
            await dispose_engines()
    outcomes = [items[0] for items in asyncio.run(exercise())]
    assert sorted(r['status'] for r in outcomes) == ['created', 'replayed']
    assert len({r['membership_id'] for r in outcomes}) == 1
    assert len({r['audit_ref'] for r in outcomes}) == 1
    with psycopg.connect(dsn) as owner:
        assert owner.execute('SELECT count(*) FROM memberships WHERE workspace_id=%s AND user_id=%s', (WORKSPACE_A, user)).fetchone()[0] == 1
        assert owner.execute("SELECT count(*) FROM idempotency_records WHERE operation_id='reconcileStaffMembership'").fetchone()[0] == 1


def test_migration_owner_login_is_refused_even_if_admin_is_valid(staff, monkeypatch):
    from buyeros_api.settings import get_settings
    dsn, user = staff
    monkeypatch.setenv('BUYEROS_DATABASE_URL', dsn)
    get_settings.cache_clear()
    before = counts(dsn)
    try:
        assert run([row(user)], apply=True)[0]['status'] == 'denied'
        assert counts(dsn) == before
    finally:
        get_settings.cache_clear()


def test_waiting_staff_write_rechecks_revoked_admin_under_same_lock(staff):
    from concurrent.futures import ThreadPoolExecutor
    from hashlib import sha256
    import time
    dsn, user = staff
    actor = uuid.uuid5(uuid.NAMESPACE_URL, ADMIN)
    lock = int.from_bytes(sha256(f'membership-admin:{WORKSPACE_A}'.encode()).digest()[:8], 'big', signed=True)
    # Warm only the actual signed fixture verifier, whose cold concurrency has
    # its own independently failing/passing C61-02 tests.
    assert run([row(user)])[0]['status'] == 'would-create'
    with psycopg.connect(dsn) as blocker, ThreadPoolExecutor(max_workers=1) as pool:
        blocker.execute('SELECT pg_advisory_xact_lock(%s)', (lock,))
        future = pool.submit(run, [row(user)], apply=True)
        deadline = time.monotonic() + 10
        waiting = False
        with psycopg.connect(dsn, autocommit=True) as owner:
            while time.monotonic() < deadline:
                waiting = owner.execute("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE usename='buyeros_api' AND wait_event='advisory')").fetchone()[0]
                if waiting:
                    break
                time.sleep(.05)
            assert waiting, 'the real runtime writer must be waiting on the membership-admin lock'
            owner.execute('UPDATE memberships SET active=false,version=version+1 WHERE workspace_id=%s AND user_id=%s', (WORKSPACE_A, actor))
        blocker.commit()
        result = future.result(timeout=10)[0]
    assert result['status'] == 'denied' and result['code'] == 'NOT_FOUND'
    with psycopg.connect(dsn) as owner:
        assert owner.execute('SELECT count(*) FROM memberships WHERE user_id=%s', (user,)).fetchone()[0] == 0
