"""Signed local protocol fixtures; no provider URL/account or production trust acceptance."""
import asyncio
import base64
import json
import time
from dataclasses import replace
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519,rsa
from buyeros_api.api.auth import AuthError,Principal,claims_to_principal
from buyeros_api.api.jwks import JwksKeyCache
from buyeros_api.api.verifier import TokenVerifier

AUTH0='https://legacy.example.test/'
NEON='https://ep-c61-verifier.neonauth.us-east-2.aws.neon.tech/neondb/auth'
AUD='https://c61-verifier.example.test'
def claims(issuer=NEON,**change):return {'iss':issuer,'aud':AUD,'sub':'verified-fixture-user','exp':int(time.time())+600,**change}
def run(value):return asyncio.run(value)
def trust(issuer=NEON,alg='EdDSA'):
 from buyeros_api.api.auth_trust import TrustConfig
 return TrustConfig(issuer=issuer,audience=AUD,jwks_url=issuer.rstrip('/')+'/jwks',algorithms=(alg,),key_types=('OKP' if alg=='EdDSA' else 'RSA',))
@pytest.fixture(scope='module')
def keypair():
 rsa_key=rsa.generate_private_key(public_exponent=65537,key_size=2048);ed=ed25519.Ed25519PrivateKey.generate()
 return {'RS256':(rsa_key,{**json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(rsa_key.public_key())),'kid':'shared-kid','alg':'RS256','use':'sig'}),'EdDSA':(ed,{**json.loads(jwt.algorithms.OKPAlgorithm.to_jwk(ed.public_key())),'kid':'shared-kid','alg':'EdDSA','use':'sig'})}
def verifier(config,keypair,fetches=None,clock=None):
 from buyeros_api.api.auth_trust import public_key_for
 async def fetch():
  if fetches is not None:fetches.append(config.jwks_url)
  return {'keys':[keypair[config.algorithms[0]][1]]}
 return TokenVerifier(JwksKeyCache(fetch,key_parser=lambda row:public_key_for(config,row),**({'now':clock} if clock else {})),trust=config)
def token(keypair,issuer=NEON,alg='EdDSA',header=None,**change):return jwt.encode(claims(issuer,**change),keypair[alg][0],algorithm=alg,headers={'kid':'shared-kid',**(header or {})})

@pytest.mark.parametrize('field,value',[('exp',True),('exp','9999999999'),('exp',float('inf')),('exp',float('nan')),('nbf',False),('nbf','0'),('nbf',[]),('sub',123),('sub',['u']),('sub','  '),('sub','u\n'),('aud',[AUD,123]),('aud',True)])
def test_invalid_claim_types_are_auth_errors(field,value):
 with pytest.raises(AuthError):claims_to_principal(claims(**{field:value}),issuer=NEON,audience=AUD)

def test_neon_exact_trust_and_auth0_same_kid_have_separate_cache(keypair):
 from buyeros_api.api.auth_trust import TrustSetVerifier
 seen=[];neon=trust();legacy=trust(AUTH0,'RS256');v=TrustSetVerifier([verifier(neon,keypair,seen),verifier(legacy,keypair,seen)])
 assert run(v.verify(token(keypair)))==Principal(NEON,'verified-fixture-user')
 assert run(v.verify(token(keypair,AUTH0,'RS256')))==Principal(AUTH0,'verified-fixture-user')
 assert set(seen)=={neon.jwks_url,legacy.jwks_url} and len(seen)==2
 assert run(v.verify(token(keypair)))==Principal(NEON,'verified-fixture-user');assert len(seen)==2

@pytest.mark.parametrize('change',[{'iss':NEON.replace('verifier','other')},{'aud':'other'},{'sub':None},{'exp':0}])
def test_wrong_branch_audience_expiry_or_subject_is_denied(keypair,change):
 with pytest.raises(AuthError):run(verifier(trust(),keypair).verify(token(keypair,**change)))

def test_same_kid_other_issuer_cannot_use_the_other_key(keypair):
 from buyeros_api.api.auth_trust import TrustSetVerifier
 v=TrustSetVerifier([verifier(trust(),keypair),verifier(trust(AUTH0,'RS256'),keypair)])
 for bad in [token(keypair,AUTH0,'EdDSA'),token(keypair,NEON,'RS256')]:
  with pytest.raises(AuthError):run(v.verify(bad))

@pytest.mark.parametrize('header',[{'jku':'https://attacker.example.test/keys'},{'x5u':'https://attacker.example.test/cert'},{'jwk':{}},{'crit':['b64']}])
def test_token_cannot_choose_jwks_or_critical_header(keypair,header):
 seen=[];v=verifier(trust(),keypair,seen)
 with pytest.raises(AuthError):run(v.verify(token(keypair,header=header)))
 assert not seen

@pytest.mark.parametrize('change',[{'kty':'RSA'},{'crv':'Ed448'},{'alg':'RS256'},{'use':'enc'},{'key_ops':['sign']},{'d':'private-fixture-material'},{'x':'invalid'}])
def test_neon_key_parser_refuses_other_key_types_and_private_material(keypair,change):
 from buyeros_api.api.auth_trust import public_key_for
 assert public_key_for(trust(),{**keypair['EdDSA'][1],**change}) is None

def test_auth0_parser_does_not_gain_eddsa(keypair):
 from buyeros_api.api.auth_trust import public_key_for
 assert public_key_for(trust(AUTH0,'RS256'),keypair['EdDSA'][1]) is None
 with pytest.raises(AuthError):run(TokenVerifier(JwksKeyCache(lambda:None),issuer=AUTH0,audience=AUD).verify(token(keypair,AUTH0,'EdDSA')))

def test_none_hs_and_mixed_algorithm_trust_are_rejected(keypair):
 for alg,key in [('none',''),('HS256','offline-negative-test-only-no-real-key-32-plus')]:
  bad=jwt.encode(claims(),key,algorithm=alg,headers={'kid':'shared-kid'})
  with pytest.raises(AuthError):run(verifier(trust(),keypair).verify(bad))
 with pytest.raises(ValueError):replace(trust(),algorithms=('RS256','EdDSA'))

def test_rotation_unknown_kid_bound_and_hard_stale(keypair):
 from buyeros_api.api.auth_trust import public_key_for
 config=trust();now=[0.0];calls=[];available=[True]
 async def fetch():
  calls.append(now[0])
  if not available[0]:raise OSError('offline outage')
  return {'keys':[keypair['EdDSA'][1]]}
 cache=JwksKeyCache(fetch,key_parser=lambda row:public_key_for(config,row),cache_seconds=10,max_stale_seconds=20,min_refetch_seconds=5,now=lambda:now[0]);v=TokenVerifier(cache,trust=config)
 assert run(v.verify(token(keypair))).issuer==NEON
 available[0]=False;now[0]=11
 assert run(v.verify(token(keypair))).issuer==NEON
 for i in range(4):
  with pytest.raises(AuthError):run(v.verify(token(keypair,header={'kid':'unknown'+str(i)})))
 assert calls==[0.0,11]
 now[0]=20
 with pytest.raises(AuthError):run(v.verify(token(keypair)))
 assert calls==[0.0,11,20]

def configured(mode='dual',**change):
 from buyeros_api.settings import Settings
 return Settings(auth_mode=mode,auth0_issuer=AUTH0,auth0_audience=AUD,neon_issuer=NEON,neon_audience=AUD,neon_jwks_url=NEON+'/jwks',neon_expected_issuer=NEON,neon_expected_audience=AUD,neon_expected_jwks_url=NEON+'/jwks',auth_migration_expires_at=str(int(time.time())+120),environment='preview',**change)

def test_runtime_exact_neon_binding_and_explicit_auth0_are_separate():
 from buyeros_api.api.auth_trust import trusts_from_settings
 from buyeros_api.settings import Settings
 assert [t.algorithms for t in trusts_from_settings(configured())]==[('RS256',),('EdDSA',)]
 assert [t.issuer for t in trusts_from_settings(configured('neon'))]==[NEON]
 assert [t.algorithms for t in trusts_from_settings(Settings(auth_mode='auth0',auth0_issuer=AUTH0,auth0_audience=AUD))]==[('RS256',)]

@pytest.mark.parametrize('environment',['preview','production'])
def test_unset_auth_mode_verifies_neon_and_does_not_trust_legacy_issuer(environment,keypair,monkeypatch):
 from buyeros_api.api import verifier as verifier_module
 from buyeros_api.settings import Settings
 monkeypatch.delenv('BUYEROS_AUTH_MODE',raising=False)
 monkeypatch.setenv('AUTH_MODE','auth0')  # Only the BUYEROS-prefixed setting selects a provider.
 settings=Settings(**configured('neon').model_dump(exclude={'auth_mode','environment'}),environment=environment)
 seen=[]
 async def fetch(url):
  seen.append(url)
  return {'keys':[keypair['EdDSA'][1]]}
 monkeypatch.setattr(verifier_module,'fetch_jwks_document',fetch)
 active=verifier_module.default_verifier(settings)
 assert run(active.verify(token(keypair)))==Principal(NEON,'verified-fixture-user')
 with pytest.raises(AuthError):run(active.verify(token(keypair,AUTH0,'RS256')))
 assert seen==[NEON+'/jwks']

def test_unset_auth_mode_with_only_legacy_settings_fails_closed(monkeypatch):
 from buyeros_api.api.verifier import default_verifier
 from buyeros_api.settings import Settings
 monkeypatch.delenv('BUYEROS_AUTH_MODE',raising=False)
 with pytest.raises(AuthError):default_verifier(Settings(auth0_issuer=AUTH0,auth0_audience=AUD))

def test_unset_auth_mode_with_wrong_neon_binding_never_falls_back(monkeypatch):
 from buyeros_api.api.verifier import default_verifier
 from buyeros_api.settings import Settings
 monkeypatch.delenv('BUYEROS_AUTH_MODE',raising=False)
 values=configured('neon').model_dump(exclude={'auth_mode'})
 values['neon_expected_issuer']=NEON.replace('verifier','other')
 with pytest.raises(AuthError):default_verifier(Settings(**values))

@pytest.mark.parametrize('name',['neon_issuer','neon_audience','neon_jwks_url','neon_expected_issuer','neon_expected_audience','neon_expected_jwks_url','auth_migration_expires_at'])
def test_dual_missing_explicit_binding_or_expiry_never_falls_back(name):
 from buyeros_api.api.auth_trust import trusts_from_settings
 settings=configured();setattr(settings,name,None)
 with pytest.raises(AuthError):trusts_from_settings(settings)

def test_wrong_branch_and_expired_dual_config_denied_even_warm(keypair):
 from buyeros_api.api.auth_trust import TrustSetVerifier,trusts_from_settings
 settings=configured();settings.neon_jwks_url=NEON.replace('verifier','other')+'/jwks'
 with pytest.raises(AuthError):trusts_from_settings(settings)
 now=[0];v=TrustSetVerifier([verifier(trust(),keypair)],expires_at=2,now=lambda:now[0])
 assert run(v.verify(token(keypair))).issuer==NEON
 now[0]=2
 with pytest.raises(AuthError):run(v.verify(token(keypair)))

def test_invalid_header_kid_returns401_at_actual_API_boundary(keypair,monkeypatch):
 from fastapi import Depends,FastAPI
 from fastapi.testclient import TestClient
 from buyeros_api.api import auth
 from buyeros_api.api.app import create_app
 from buyeros_api.settings import Settings
 valid=token(keypair,AUTH0,'RS256');parts=valid.split('.')
 parts[0]=base64.urlsafe_b64encode(json.dumps({'alg':'RS256','kid':['invalid']}).encode()).decode().rstrip('=')
 monkeypatch.setattr(auth,'get_settings',lambda:Settings(auth_mode='auth0',auth0_issuer=AUTH0,auth0_audience=AUD))
 async def keys():return {'keys':[keypair['RS256'][1]]}
 monkeypatch.setattr(auth,'_verifier_from_settings',lambda:TokenVerifier(JwksKeyCache(keys),issuer=AUTH0,audience=AUD))
 app=create_app()
 @app.get('/c61-protected')
 async def protected(principal=Depends(auth.get_principal)):return {'sub':principal.subject}
 with TestClient(app,raise_server_exceptions=False) as client:
  response=client.get('/c61-protected',headers={'Authorization':'Bearer '+'.'.join(parts)})
 assert response.status_code==401 and response.json()['code']=='UNAUTHENTICATED'

@pytest.mark.parametrize('field,value',[('auth_mode','unknown'),('environment','staging'),('neon_expected_audience','wrong'),('auth_migration_expires_at','0'),('auth_migration_expires_at','invalid'),('auth_migration_expires_at',' 9999999999')])
def test_runtime_invalid_configuration_is_not_a_trust_fallback(field,value):
 from buyeros_api.api.auth_trust import trusts_from_settings
 settings=configured();setattr(settings,field,value)
 with pytest.raises(AuthError):trusts_from_settings(settings)

def test_neon_fixture_trust_and_test_credentials_are_refused(monkeypatch):
 from buyeros_api.api.auth_trust import trusts_from_settings
 for name in ['BUYEROS_NEON_FIXTURE_MODE','BUYEROS_NEON_TEST_PASSWORD']:
  with monkeypatch.context() as context:
   context.setenv(name,'offline-forbidden')
   with pytest.raises(AuthError):trusts_from_settings(configured('neon'))

def test_neon_only_trust_rejects_auth0_without_an_extra_jwks_fetch(keypair):
 from buyeros_api.api.auth_trust import TrustSetVerifier
 seen=[];v=TrustSetVerifier([verifier(trust(),keypair,seen)])
 with pytest.raises(AuthError):run(v.verify(token(keypair,AUTH0,'RS256')))
 assert seen==[]
