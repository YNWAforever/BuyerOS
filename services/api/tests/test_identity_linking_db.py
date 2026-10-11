"""C61-09 additive identities: real DB, immutable canonical IDs, no email linking."""
import asyncio
import hashlib
import json
import uuid
import psycopg
import pytest
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession,create_async_engine
from buyeros_api.api.auth import Principal
from buyeros_api.api.errors import ApiError
from tests.conftest import runtime_role_dsn

@pytest.fixture
def identity_db(seeded):
 users=[uuid.uuid4(),uuid.uuid4()];members=[uuid.uuid4(),uuid.uuid4()]
 workspace=uuid.UUID('11111111-1111-4111-8111-111111111111')
 with psycopg.connect(seeded,autocommit=True) as owner:
  for user_id,member_id in zip(users,members):
   owner.execute("INSERT INTO users(id,issuer,subject,display_name) VALUES (%s,'urn:c61:legacy',%s,'same@example.test')",(user_id,str(user_id)))
   owner.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active,version) VALUES (%s,%s,%s,'{viewer}',true,1)",(member_id,workspace,user_id))
   owner.execute("INSERT INTO workspace_preferences(id,workspace_id,user_id,locale,default_markets,version) VALUES (%s,%s,%s,'en','{US}',1)",(uuid.uuid4(),workspace,user_id))
 try:yield seeded
 finally:
  with psycopg.connect(seeded,autocommit=True) as owner:
   for user_id in users:
    owner.execute('DELETE FROM workspace_preferences WHERE user_id=%s',(user_id,))
    owner.execute('DELETE FROM memberships WHERE user_id=%s',(user_id,))
    owner.execute('DELETE FROM users WHERE id=%s',(user_id,))

def run(dsn,call):
 async def execute():
  engine=create_async_engine(dsn.replace('postgresql://','postgresql+psycopg://',1))
  try:
   async with AsyncSession(engine) as session:
    async with session.begin():return await call(session)
  finally:await engine.dispose()
 return asyncio.run(execute())

def historical_fks(owner,user_id):
 pairs=owner.execute("""SELECT c.conrelid::regclass::text,a.attname FROM pg_constraint c
 JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=c.conkey[1]
 WHERE c.contype='f' AND c.confrelid='public.users'::regclass AND cardinality(c.conkey)=1
 AND c.conrelid<>'public.user_identities'::regclass ORDER BY 1,2""").fetchall()
 result={}
 for table,column in pairs:
  # Catalog identifiers are quoted, never interpolated from a manifest.
  rows=owner.execute(sql.SQL('SELECT row_to_json(t)::text FROM {} t WHERE {}=%s').format(sql.Identifier(*table.split('.')),sql.Identifier(column)),(user_id,)).fetchall()
  result[(table,column)]=hashlib.sha256(json.dumps(sorted(row[0] for row in rows)).encode()).hexdigest()
 return result

def test_link_keeps_all_historical_foreign_keys_and_replays_once(identity_db):
 seeded=identity_db
 from buyeros_api.services.identity_linking import link_identity
 from buyeros_api.services.identity_resolver import resolve_user_id
 with psycopg.connect(seeded) as owner:
  user_id=owner.execute('SELECT user_id FROM memberships ORDER BY id LIMIT 1').fetchone()[0]
  users_before=owner.execute('SELECT id FROM users ORDER BY id').fetchall();before=historical_fks(owner,user_id)
 subject='c61-new-'+uuid.uuid4().hex
 async def link(session):return await link_identity(session,user_id=user_id,issuer='urn:c61:neon',subject=subject,proof_ref='admin-proof:'+subject)
 assert run(seeded,link)==user_id;assert run(seeded,link)==user_id
 assert run(runtime_role_dsn(seeded),lambda s:resolve_user_id(s,Principal('urn:c61:neon',subject)))==user_id
 with psycopg.connect(seeded) as owner:
  assert owner.execute('SELECT id FROM users ORDER BY id').fetchall()==users_before
  assert historical_fks(owner,user_id)==before
  assert owner.execute('SELECT count(*) FROM user_identities WHERE issuer=%s AND subject=%s',('urn:c61:neon',subject)).fetchone()==(1,)
  assert not owner.execute("SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname='buyeros_api'").fetchone()[0]

def test_same_email_or_display_name_cannot_link_or_create_user(identity_db):
 seeded=identity_db
 from buyeros_api.services.identity_linking import parse_identity_manifest
 from buyeros_api.services.identity_resolver import resolve_user_id
 user_id=uuid.uuid4();subject='c61-name-'+uuid.uuid4().hex
 with psycopg.connect(seeded,autocommit=True) as owner:owner.execute("INSERT INTO users(id,issuer,subject,display_name) VALUES (%s,'urn:c61:old',%s,'same@example.test')",(user_id,subject))
 try:
  assert run(runtime_role_dsn(seeded),lambda s:resolve_user_id(s,Principal('urn:c61:new','same@example.test'))) is None
  with pytest.raises((ValueError,TypeError)):parse_identity_manifest([{'email':'same@example.test','issuer':'urn:c61:new','subject':'unknown','proof_ref':'email-only'}])
  with psycopg.connect(seeded) as owner:assert owner.execute('SELECT count(*) FROM users WHERE id=%s',(user_id,)).fetchone()==(1,)
 finally:
  with psycopg.connect(seeded,autocommit=True) as owner:owner.execute('DELETE FROM users WHERE id=%s',(user_id,))

def test_link_conflict_is_atomic_and_cannot_reassign_identity(identity_db):
 seeded=identity_db
 from buyeros_api.services.identity_linking import link_identity
 with psycopg.connect(seeded) as owner:users=[row[0] for row in owner.execute('SELECT id FROM users ORDER BY id LIMIT 2')]
 subject='c61-conflict-'+uuid.uuid4().hex
 async def link(session,user):return await link_identity(session,user_id=user,issuer='urn:c61:conflict',subject=subject,proof_ref='verified-admin:'+subject)
 assert run(seeded,lambda s:link(s,users[0]))==users[0]
 with pytest.raises(ApiError) as rejected:run(seeded,lambda s:link(s,users[1]))
 assert rejected.value.status_code==409
 with psycopg.connect(seeded) as owner:assert owner.execute('SELECT user_id,count(*) OVER() FROM user_identities WHERE issuer=%s AND subject=%s',('urn:c61:conflict',subject)).fetchone()==(users[0],1)

def test_identity_revoked_next_request_denied_after_warm_resolution(identity_db):
 seeded=identity_db
 from buyeros_api.services.identity_linking import link_identity
 from buyeros_api.services.identity_resolver import resolve_user_id
 with psycopg.connect(seeded) as owner:user_id=owner.execute('SELECT id FROM users ORDER BY id LIMIT 1').fetchone()[0]
 subject='c61-revoke-'+uuid.uuid4().hex;principal=Principal('urn:c61:revoked',subject)
 async def link(session):return await link_identity(session,user_id=user_id,issuer=principal.issuer,subject=subject,proof_ref='verified-admin:'+subject)
 assert run(seeded,link)==user_id
 assert run(runtime_role_dsn(seeded),lambda s:resolve_user_id(s,principal))==user_id
 with psycopg.connect(seeded,autocommit=True) as owner:owner.execute("UPDATE user_identities SET status='revoked',version=version+1 WHERE issuer=%s AND subject=%s",(principal.issuer,subject))
 assert run(runtime_role_dsn(seeded),lambda s:resolve_user_id(s,principal)) is None
 with pytest.raises(ApiError):run(seeded,link)

def test_runtime_role_cannot_write_mapping_or_read_proof(identity_db):
 seeded=identity_db
 from buyeros_api.services.identity_linking import link_identity
 with psycopg.connect(seeded) as owner:user_id=owner.execute('SELECT id FROM users ORDER BY id LIMIT 1').fetchone()[0]
 async def link(session):return await link_identity(session,user_id=user_id,issuer='urn:c61:forged',subject='forged',proof_ref='pretend-admin')
 with pytest.raises(ApiError) as rejected:run(runtime_role_dsn(seeded),link)
 assert rejected.value.status_code==403
 with psycopg.connect(runtime_role_dsn(seeded)) as runtime:
  with pytest.raises(psycopg.errors.InsufficientPrivilege):runtime.execute('SELECT proof_ref FROM user_identities')


def test_neon_only_new_user_gets_one_canonical_row_without_membership(identity_db):
 from buyeros_api.services.identity_linking import create_canonical_user
 principal=Principal('urn:c61:neon-only','new-'+uuid.uuid4().hex);proof='verified-principal:'+principal.subject
 async def create(session):return await create_canonical_user(session,principal=principal,proof_ref=proof)
 first=run(identity_db,create);assert run(identity_db,create)==first
 with psycopg.connect(identity_db) as owner:
  assert owner.execute('SELECT id FROM users WHERE issuer=%s AND subject=%s',(principal.issuer,principal.subject)).fetchall()==[(first,)]
  assert owner.execute('SELECT user_id,proof_ref,status FROM user_identities WHERE issuer=%s AND subject=%s',(principal.issuer,principal.subject)).fetchone()==(first,proof,'active')
  assert owner.execute('SELECT count(*) FROM memberships WHERE user_id=%s',(first,)).fetchone()==(0,)

def test_concurrent_conflicting_links_leave_one_mapping_and_all_user_ids(identity_db):
 from concurrent.futures import ThreadPoolExecutor
 from buyeros_api.services.identity_linking import link_identity
 with psycopg.connect(identity_db) as owner:before=owner.execute('SELECT id FROM users ORDER BY id').fetchall()
 subject='c61-race-'+uuid.uuid4().hex
 def attempt(user):
  async def call(session):return await link_identity(session,user_id=user,issuer='urn:c61:race',subject=subject,proof_ref='verified-admin:'+subject,expected_version=0)
  try:return run(identity_db,call)
  except ApiError as error:return error.status_code
 with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,[before[0][0],before[1][0]]))
 assert results.count(409)==1
 with psycopg.connect(identity_db) as owner:
  assert owner.execute('SELECT id FROM users ORDER BY id').fetchall()==before
  actual=owner.execute('SELECT user_id FROM user_identities WHERE issuer=%s AND subject=%s',('urn:c61:race',subject)).fetchall()
  assert len(actual)==1 and actual[0][0] in results

def test_identity_association_and_proof_are_immutable_at_database_boundary(identity_db):
 from buyeros_api.services.identity_linking import link_identity
 with psycopg.connect(identity_db) as owner:users=[row[0] for row in owner.execute('SELECT id FROM users ORDER BY id LIMIT 2')]
 subject='c61-immutable-'+uuid.uuid4().hex
 async def link(session):return await link_identity(session,user_id=users[0],issuer='urn:c61:immutable',subject=subject,proof_ref='verified-admin:'+subject,expected_version=0)
 run(identity_db,link)
 with psycopg.connect(identity_db,autocommit=True) as owner:
  for assignment,params in [('user_id=%s',(users[1],)),('proof_ref=%s',('other-proof',)),('subject=%s',('other-subject',)),('created_at=clock_timestamp()',())]:
   with pytest.raises(psycopg.errors.CheckViolation):owner.execute(sql.SQL('UPDATE user_identities SET '+assignment+',version=version+1 WHERE issuer=%s AND subject=%s'),(*params,'urn:c61:immutable',subject))
  assert owner.execute('SELECT user_id,version FROM user_identities WHERE issuer=%s AND subject=%s',('urn:c61:immutable',subject)).fetchone()==(users[0],1)

def test_expected_version_allows_only_exact_initial_replay(identity_db):
 from buyeros_api.services.identity_linking import link_identity
 with psycopg.connect(identity_db) as owner:user_id=owner.execute('SELECT id FROM users ORDER BY id LIMIT 1').fetchone()[0]
 subject='c61-version-'+uuid.uuid4().hex;proof='verified-admin:'+subject
 async def link(session,expected=0,ref=proof):return await link_identity(session,user_id=user_id,issuer='urn:c61:version',subject=subject,proof_ref=ref,expected_version=expected)
 assert run(identity_db,link)==user_id;assert run(identity_db,link)==user_id
 for expected,ref in [(3,proof),(0,'other-proof')]:
  with pytest.raises(ApiError) as rejected:run(identity_db,lambda session:link(session,expected,ref))
  assert rejected.value.status_code==409
 with psycopg.connect(identity_db) as owner:assert owner.execute('SELECT user_id,version,proof_ref FROM user_identities WHERE issuer=%s AND subject=%s',('urn:c61:version',subject)).fetchone()==(user_id,1,proof)


def test_concurrent_new_canonical_principal_creates_one_user_without_membership(identity_db):
 from concurrent.futures import ThreadPoolExecutor
 from buyeros_api.services.identity_linking import create_canonical_user
 principal=Principal('urn:c61:concurrent-new','new-'+uuid.uuid4().hex)
 def create(_):return run(identity_db,lambda s:create_canonical_user(s,principal=principal,proof_ref='verified-new:'+principal.subject))
 with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(create,range(2)))
 assert results[0]==results[1]
 with psycopg.connect(identity_db) as owner:
  assert owner.execute('SELECT id FROM users WHERE issuer=%s AND subject=%s',(principal.issuer,principal.subject)).fetchall()==[(results[0],)]
  assert owner.execute('SELECT count(*) FROM memberships WHERE user_id=%s',(results[0],)).fetchone()==(0,)

def test_revoked_principal_cannot_create_replacement_canonical_user(identity_db):
 from buyeros_api.services.identity_linking import create_canonical_user
 principal=Principal('urn:c61:revoked-new','new-'+uuid.uuid4().hex)
 async def create(s):return await create_canonical_user(s,principal=principal,proof_ref='verified-new:'+principal.subject)
 first=run(identity_db,create)
 with psycopg.connect(identity_db) as owner:
  owner.execute("UPDATE user_identities SET status='revoked',version=version+1 WHERE issuer=%s AND subject=%s",(principal.issuer,principal.subject))
  before=owner.execute('SELECT id FROM users ORDER BY id').fetchall()
 with pytest.raises(ApiError) as rejected:run(identity_db,create)
 assert rejected.value.status_code==409
 with psycopg.connect(identity_db) as owner:
  assert owner.execute('SELECT id FROM users ORDER BY id').fetchall()==before
  assert owner.execute('SELECT user_id,status FROM user_identities WHERE issuer=%s AND subject=%s',(principal.issuer,principal.subject)).fetchone()==(first,'revoked')

def test_runtime_proof_setting_never_authorizes_canonical_creation(identity_db):
 from buyeros_api.services.identity_linking import create_canonical_user
 principal=Principal('urn:c61:runtime-forged','new-'+uuid.uuid4().hex)
 async def create(s):
  await s.execute(text("SELECT set_config('app.identity_proof_ref','forged-proof',true)"))
  return await create_canonical_user(s,principal=principal,proof_ref='forged-proof')
 with pytest.raises(ApiError) as rejected:run(runtime_role_dsn(identity_db),create)
 assert rejected.value.status_code==403
 with psycopg.connect(identity_db) as owner:
  assert owner.execute('SELECT count(*) FROM users WHERE issuer=%s AND subject=%s',(principal.issuer,principal.subject)).fetchone()==(0,)
