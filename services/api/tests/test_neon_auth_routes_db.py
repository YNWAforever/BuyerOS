"""Actual PG/API and native verifier, offline signed Ed25519/JWKS protocol only."""
import json,time,uuid
import jwt,psycopg,pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from fastapi.testclient import TestClient
from buyeros_api.api import auth,verifier
from buyeros_api.api.auth import _verifier_from_settings as native_factory
from buyeros_api.api.app import create_app
from buyeros_api.settings import get_settings
from tests.test_auth_routes_db import auth_env,WORKSPACE_A,WORKSPACE_B,VIEWER

ISSUER='https://ep-c61-signed-api.neonauth.us-east-2.aws.neon.tech/neondb/auth'
AUDIENCE='https://c61-signed-api.example.test'
SUB='offline-neon-viewer-alias'
@pytest.fixture
def neon_api(auth_env,seeded,monkeypatch):
    private=ed25519.Ed25519PrivateKey.generate()
    public={**json.loads(jwt.algorithms.OKPAlgorithm.to_jwk(private.public_key())),'kid':'actual-api-key','alg':'EdDSA','use':'sig'}
    settings={'AUTH_MODE':'neon','ENVIRONMENT':'preview','NEON_ISSUER':ISSUER,'NEON_AUDIENCE':AUDIENCE,'NEON_JWKS_URL':ISSUER+'/jwks','NEON_EXPECTED_ISSUER':ISSUER,'NEON_EXPECTED_AUDIENCE':AUDIENCE,'NEON_EXPECTED_JWKS_URL':ISSUER+'/jwks'}
    for key,value in settings.items():monkeypatch.setenv('BUYEROS_'+key,value)
    get_settings.cache_clear();monkeypatch.setattr(auth,'_VERIFIER',None);monkeypatch.setattr(auth,'_VERIFIER_KEY',None);monkeypatch.setattr(auth,'_verifier_from_settings',native_factory)
    fetched=[]
    async def fetch(url):
        assert url==ISSUER+'/jwks';fetched.append(url);return {'keys':[public]}
    monkeypatch.setattr(verifier,'fetch_jwks_document',fetch)
    canonical=uuid.uuid5(uuid.NAMESPACE_URL,VIEWER)
    with psycopg.connect(seeded) as owner:
        owner.execute('INSERT INTO user_identities(issuer,subject,user_id,proof_ref) VALUES (%s,%s,%s,%s)',(ISSUER,SUB,canonical,'offline-admin-verified-alias'))
    value=jwt.encode({'iss':ISSUER,'aud':AUDIENCE,'sub':SUB,'exp':int(time.time())+600,'roles':['workspace_admin'],'admin':True},private,algorithm='EdDSA',headers={'kid':'actual-api-key'})
    with TestClient(create_app(),raise_server_exceptions=False) as client:
        yield client,{'Authorization':'Bearer '+value},canonical,fetched
    with psycopg.connect(seeded) as owner:owner.execute('DELETE FROM user_identities WHERE issuer=%s AND subject=%s',(ISSUER,SUB))
    get_settings.cache_clear()

def test_signed_neon_alias_current_DB_role_and_tenant_win_over_admin_JWT(neon_api,seeded):
    client,headers,canonical,fetched=neon_api
    before=client.get(f'/v1/workspaces/{WORKSPACE_A}/projects',headers=headers)
    assert before.status_code==200 and {row['name'] for row in before.json()['data']['items']}=={'ProjectA'}
    foreign=client.get(f'/v1/workspaces/{WORKSPACE_B}/projects',headers=headers)
    assert foreign.status_code==404 and 'ProjectB' not in foreign.text
    with psycopg.connect(seeded) as owner:count=owner.execute('SELECT count(*) FROM projects').fetchone()[0]
    denied=client.post(f'/v1/workspaces/{WORKSPACE_A}/projects',headers={**headers,'Idempotency-Key':'c61-jwt-role-denied'},json={'name':'JWT role must not create','company_name':'Offline fixture','offer':'None','markets':['US'],'language_preferences':['en']})
    assert denied.status_code==403,denied.text
    with psycopg.connect(seeded) as owner:
        assert owner.execute('SELECT count(*) FROM projects').fetchone()[0]==count
        assert owner.execute('SELECT roles FROM memberships WHERE workspace_id=%s AND user_id=%s',(WORKSPACE_A,canonical)).fetchone()[0]==['viewer']
    assert len(fetched)==1

def test_signed_neon_identity_revocation_is_denied_with_same_warm_JWT(neon_api,seeded):
    client,headers,canonical,fetched=neon_api;path=f'/v1/workspaces/{WORKSPACE_A}/projects'
    assert client.get(path,headers=headers).status_code==200
    with psycopg.connect(seeded) as owner:
        owner.execute("UPDATE user_identities SET status='revoked',version=version+1 WHERE issuer=%s AND subject=%s",(ISSUER,SUB))
    after=client.get(path,headers=headers)
    assert after.status_code==404 and after.json()['code']=='NOT_FOUND'
    assert len(fetched)==1
    with psycopg.connect(seeded) as owner:
        assert owner.execute('SELECT id FROM users WHERE id=%s',(canonical,)).fetchone()==(canonical,)
        assert owner.execute('SELECT active FROM memberships WHERE workspace_id=%s AND user_id=%s',(WORKSPACE_A,canonical)).fetchone()==(True,)
