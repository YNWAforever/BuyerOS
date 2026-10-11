"""C61-12: actual native signed-JWT HTTP/runtime-PG boundary; JWKS alone is offline."""
import json,time,uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import jwt,psycopg,pytest
from cryptography.hazmat.primitives.asymmetric import ed25519,rsa
from fastapi.testclient import TestClient
from buyeros_api.api import auth,verifier
from buyeros_api.api.auth import _verifier_from_settings as native_factory,jwks_uri_for
from buyeros_api.api.app import create_app
from buyeros_api.settings import get_settings
from tests.test_auth_routes_db import auth_env,WORKSPACE_A,WORKSPACE_B,PROJECT_B
from tests import auth_fixtures as fx

ISSUER='https://ep-c61-security.neonauth.us-east-2.aws.neon.tech/neondb/auth'
AUDIENCE='https://c61-security.example.test'
KID='same-kid-separate-issuers'
ROLES=('viewer','operator','reviewer','workspace_admin')

@pytest.fixture
def security_api(auth_env,seeded,monkeypatch):
    neon=ed25519.Ed25519PrivateKey.generate();legacy=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    neon_jwk={**json.loads(jwt.algorithms.OKPAlgorithm.to_jwk(neon.public_key())),'kid':KID,'alg':'EdDSA','use':'sig'}
    legacy_jwk={**json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(legacy.public_key())),'kid':KID,'alg':'RS256','use':'sig'}
    config={'AUTH_MODE':'dual','AUTH_MIGRATION_EXPIRES_AT':str(int(time.time())+600),'ENVIRONMENT':'preview','NEON_ISSUER':ISSUER,'NEON_AUDIENCE':AUDIENCE,'NEON_JWKS_URL':ISSUER+'/jwks','NEON_EXPECTED_ISSUER':ISSUER,'NEON_EXPECTED_AUDIENCE':AUDIENCE,'NEON_EXPECTED_JWKS_URL':ISSUER+'/jwks'}
    for key,value in config.items():monkeypatch.setenv('BUYEROS_'+key,value)
    get_settings.cache_clear();monkeypatch.setattr(auth,'_VERIFIER',None);monkeypatch.setattr(auth,'_VERIFIER_KEY',None);monkeypatch.setattr(auth,'_verifier_from_settings',native_factory)
    fetched=[]
    async def fetch(url):
        fetched.append(url)
        if url==ISSUER+'/jwks':return {'keys':[neon_jwk]}
        if url==jwks_uri_for(fx.ISSUER):return {'keys':[legacy_jwk]}
        raise AssertionError('Unapproved JWKS network target')
    monkeypatch.setattr(verifier,'fetch_jwks_document',fetch)
    identities={}
    with psycopg.connect(seeded) as db:
        for role in ROLES:
            canonical=uuid.uuid4();subject='c61-security-'+role+'-'+canonical.hex;member=uuid.uuid4()
            db.execute('INSERT INTO users(id,issuer,subject) VALUES (%s,%s,%s)',(canonical,fx.ISSUER,subject))
            db.execute('INSERT INTO user_identities(issuer,subject,user_id,proof_ref) VALUES (%s,%s,%s,%s)',(ISSUER,subject,canonical,'offline-admin-verified:'+canonical.hex))
            db.execute('INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES (%s,%s,%s,%s,true)',(member,WORKSPACE_A,canonical,[role]))
            identities[role]=(canonical,subject,member)
    def headers(role='viewer',*,issuer=ISSUER,key=None,algorithm=None,claims=None,jwt_headers=None):
        _,subject,_=identities[role];is_neon=issuer==ISSUER
        data={'iss':issuer,'aud':AUDIENCE if is_neon else fx.AUDIENCE,'sub':subject,'exp':int(time.time())+600,'roles':['workspace_admin'],'admin':True,**(claims or {})}
        token=jwt.encode(data,key or (neon if is_neon else legacy),algorithm=algorithm or ('EdDSA' if is_neon else 'RS256'),headers={'kid':KID,**(jwt_headers or {})})
        return {'Authorization':'Bearer '+token}
    with TestClient(create_app(),raise_server_exceptions=False) as client:
        yield client,headers,identities,fetched
    with psycopg.connect(seeded) as db:
        users=[row[0] for row in identities.values()]
        db.execute('DELETE FROM audit_events WHERE workspace_id=%s',(WORKSPACE_A,))
        db.execute('DELETE FROM idempotency_records WHERE actor_id=ANY(%s)',(users,))
        db.execute('DELETE FROM memberships WHERE user_id=ANY(%s)',(users,))
        db.execute('DELETE FROM users WHERE id=ANY(%s)',(users,))
    get_settings.cache_clear()

@pytest.mark.parametrize('role',ROLES)
def test_signed_neon_DB_roles_and_foreign_workspace_existence(security_api,seeded,role):
    client,h,ids,_=security_api;headers=h(role)
    own=client.get(f'/v1/workspaces/{WORKSPACE_A}/projects',headers=headers)
    assert own.status_code==200 and {row['name'] for row in own.json()['data']['items']}=={'ProjectA'}
    for path in [f'/v1/workspaces/{WORKSPACE_B}/projects',f'/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_B}',f'/v1/workspaces/{uuid.uuid4()}/projects']:
        denied=client.get(path,headers=headers);assert denied.status_code==404 and denied.json()['code']=='NOT_FOUND'
        assert 'ProjectB' not in denied.text and PROJECT_B not in denied.text
    directory=client.get(f'/v1/workspaces/{WORKSPACE_A}/memberships',headers=headers)
    assert directory.status_code==(200 if role=='workspace_admin' else 403),directory.text
    with psycopg.connect(seeded) as db:
        assert db.execute('SELECT roles FROM memberships WHERE id=%s',(ids[role][2],)).fetchone()[0]==[role]

@pytest.mark.parametrize('role',ROLES)
@pytest.mark.parametrize('revocation',['membership','identity'])
def test_same_warm_signed_JWT_obeys_current_revocation(security_api,seeded,role,revocation):
    client,h,ids,fetched=security_api;headers=h(role);user,subject,member=ids[role];path=f'/v1/workspaces/{WORKSPACE_A}/projects'
    assert client.get(path,headers=headers).status_code==200
    with psycopg.connect(seeded) as db:
        if revocation=='membership':db.execute('UPDATE memberships SET active=false,version=version+1 WHERE id=%s',(member,))
        else:db.execute("UPDATE user_identities SET status='revoked',version=version+1 WHERE issuer=%s AND subject=%s",(ISSUER,subject))
    for suffix in ['',f'/{WORKSPACE_A}']:
        response=client.get('/v1/workspaces'+suffix+('/projects' if suffix else ''),headers=headers)
        if suffix:assert response.status_code==404 and 'ProjectA' not in response.text
        else:assert response.status_code==200 and not response.json()['data']['items']
    assert fetched==[ISSUER+'/jwks']
    with psycopg.connect(seeded) as db:
        assert db.execute('SELECT id FROM users WHERE id=%s',(user,)).fetchone()==(user,)
        assert db.execute('SELECT user_id FROM user_identities WHERE issuer=%s AND subject=%s',(ISSUER,subject)).fetchone()==(user,)

@pytest.mark.parametrize('suffix',['claim','step','status','publication','maintenance'])
def test_valid_neon_user_JWT_is_never_worker_serviceauth(security_api,seeded,suffix):
    client,h,_,_=security_api
    with psycopg.connect(seeded) as db:before=db.execute('SELECT count(*) FROM worker_bridge_nonces').fetchone()[0]
    response=client.post('/v1/internal/worker/'+suffix,headers=h('workspace_admin'),json={})
    assert response.status_code==401,response.text
    with psycopg.connect(seeded) as db:assert db.execute('SELECT count(*) FROM worker_bridge_nonces').fetchone()[0]==before

def test_worker_headers_and_cookie_cannot_replace_API_bearer(security_api):
    client,_,_,_=security_api
    response=client.get(f'/v1/workspaces/{WORKSPACE_A}/projects',headers={'Cookie':'__Secure-neon-auth.session_token=synthetic','x-buyeros-worker-key-id':'synthetic','x-buyeros-worker-signature':'a'*64})
    assert response.status_code==401 and 'ProjectA' not in response.text

def test_same_kid_both_issuers_are_verified_in_their_own_key_cache(security_api,monkeypatch):
    client,h,_,fetched=security_api;path=f'/v1/workspaces/{WORKSPACE_A}/projects'
    for issuer in [ISSUER,fx.ISSUER,ISSUER,fx.ISSUER]:assert client.get(path,headers=h(issuer=issuer)).status_code==200
    forged=h(issuer=fx.ISSUER,claims={'iss':ISSUER,'aud':AUDIENCE})
    response=client.get(path,headers=forged);assert response.status_code==401 and response.json()['message']=='token rejected'
    assert sorted(fetched)==sorted([ISSUER+'/jwks',jwks_uri_for(fx.ISSUER)])
    monkeypatch.setenv('BUYEROS_AUTH_MODE','neon');get_settings.cache_clear()
    assert client.get(path,headers=h(issuer=fx.ISSUER)).status_code==401
    assert client.get(path,headers=h()).status_code==200

@pytest.mark.parametrize('claims',[{'aud':'foreign-api'},{'exp':100},{'sub':'unmapped-account'},{'email':'same-as-admin@example.test','sub':'unmapped-same-email'}])
def test_invalid_or_unmapped_neon_never_links_by_email(security_api,seeded,claims):
    client,h,_,_=security_api
    with psycopg.connect(seeded) as db:before=db.execute('SELECT count(*) FROM users').fetchone()[0]
    response=client.get(f'/v1/workspaces/{WORKSPACE_A}/projects',headers=h(claims=claims))
    assert response.status_code==(404 if 'sub' in claims else 401) and 'ProjectA' not in response.text
    with psycopg.connect(seeded) as db:assert db.execute('SELECT count(*) FROM users').fetchone()[0]==before

def test_signed_neon_two_admin_self_demotions_preserve_one_admin(security_api,seeded):
    client,h,ids,_=security_api
    with psycopg.connect(seeded) as db:db.execute("UPDATE memberships SET roles='{workspace_admin}' WHERE id=%s",(ids['operator'][2],))
    barrier=Barrier(2)
    def demote(role):
        with TestClient(create_app(),raise_server_exceptions=False) as c:
            headers={**h(role),'Idempotency-Key':'c61-neon-demote-'+role,'If-Match':'"1"'}
            barrier.wait(timeout=10)
            return c.patch(f'/v1/workspaces/{WORKSPACE_A}/memberships/{ids[role][2]}',headers=headers,json={'roles':['viewer'],'active':True,'reason':'Offline signed-Neon concurrent rotation'})
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(demote,role) for role in ['operator','workspace_admin']];responses=[f.result(timeout=30) for f in futures]
    assert sorted(r.status_code for r in responses)==[200,409],[r.text for r in responses]
    assert next(r for r in responses if r.status_code==409).json()['code']=='LAST_ADMIN'
    with psycopg.connect(seeded) as db:
        assert db.execute("SELECT count(*) FROM memberships WHERE workspace_id=%s AND active AND 'workspace_admin'=ANY(roles)",(WORKSPACE_A,)).fetchone()[0]==1
        assert db.execute("SELECT count(*) FROM audit_events WHERE workspace_id=%s AND action='membership.updated'",(WORKSPACE_A,)).fetchone()[0]==1


@pytest.mark.parametrize('claims',[{'iss':ISSUER.replace('security','copied-preview')},{'aud':42},{'aud':[AUDIENCE,42]},{'exp':True},{'exp':'9999999999'},{'exp':float('nan')},{'exp':float('inf')},{'nbf':True},{'iat':'now'},{'sub':False},{'sub':' leading-space'},{'sub':'a'*256}])
def test_signed_neon_bad_claim_types_and_copied_branch_are_controlled_HTTP_401(security_api,claims):
    client,h,_,_=security_api
    response=client.get(f'/v1/workspaces/{WORKSPACE_A}/projects',headers=h(claims=claims))
    assert response.status_code==401 and response.json()['message']=='token rejected'
    assert 'ProjectA' not in response.text

@pytest.mark.parametrize('header',[{'jku':'https://foreign.example.test/keys'},{'x5u':'https://foreign.example.test/cert'},{'jwk':{'kty':'OKP','x':'copied'}},{'crit':['unsupported']},{'b64':False}])
def test_signed_untrusted_header_never_redirects_key_fetch(security_api,header):
    client,h,_,fetched=security_api
    response=client.get(f'/v1/workspaces/{WORKSPACE_A}/projects',headers=h(jwt_headers=header))
    assert response.status_code==401 and response.json()['message']=='token rejected'
    assert not any('foreign.example.test' in target for target in fetched)

@pytest.mark.parametrize('algorithm',['HS256','RS256','EdDSA-forged'])
def test_algorithm_confusion_and_same_kid_forgery_fail_actual_HTTP(security_api,algorithm):
    client,h,_,_=security_api
    if algorithm=='HS256':headers=h(key=b'offline-untrusted-HMAC-key-only',algorithm='HS256')
    elif algorithm=='RS256':headers=h(key=rsa.generate_private_key(public_exponent=65537,key_size=2048),algorithm='RS256')
    else:headers=h(key=ed25519.Ed25519PrivateKey.generate(),algorithm='EdDSA')
    response=client.get(f'/v1/workspaces/{WORKSPACE_A}/projects',headers=headers)
    assert response.status_code==401 and response.json()['message']=='token rejected'
