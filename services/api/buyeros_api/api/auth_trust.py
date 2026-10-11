"""Explicit provider trust; a token can select only an already configured issuer."""
import os
import re
import time
from dataclasses import dataclass
from urllib.parse import urlsplit
import jwt
from .auth import AuthError,jwks_uri_for

def exact(value,limit=2048):
    return isinstance(value,str) and 0<len(value)<=limit and value==value.strip() and not any(ord(c)<32 or ord(c)==127 for c in value)

def endpoint(value,*,loopback=False):
    if not exact(value):return False
    try:
        url=urlsplit(value)
        return bool(url.hostname and not url.username and not url.password and not url.query and not url.fragment and (url.scheme=='https' or loopback and url.scheme=='http' and url.hostname in {'localhost','127.0.0.1','::1'}))
    except ValueError:return False

@dataclass(frozen=True)
class TrustConfig:
    issuer:str
    audience:str
    jwks_url:str
    algorithms:tuple[str,...]
    key_types:tuple[str,...]

    def __post_init__(self):
        if (self.algorithms,self.key_types) not in [(('RS256',),('RSA',)),(('EdDSA',),('OKP',))]:
            raise ValueError('unsupported provider trust')
        legacy=self.algorithms==('RS256',)
        if not exact(self.issuer,255) or not exact(self.audience) or not endpoint(self.issuer,loopback=legacy) or not endpoint(self.jwks_url,loopback=legacy):
            raise ValueError('invalid provider trust')

def public_key_for(trust:TrustConfig,entry:dict):
    if not isinstance(entry,dict) or entry.get('kty') not in trust.key_types or entry.get('alg') not in (None,trust.algorithms[0]) or entry.get('use') not in (None,'sig') or 'd' in entry:
        return None
    operations=entry.get('key_ops')
    if operations is not None and (not isinstance(operations,list) or operations!=['verify']):return None
    try:
        if trust.algorithms==('RS256',):return jwt.algorithms.RSAAlgorithm.from_jwk(entry)
        if entry.get('crv')!='Ed25519':return None
        return jwt.algorithms.OKPAlgorithm.from_jwk(entry)
    except (jwt.PyJWTError,ValueError,TypeError,KeyError):return None

def trusts_from_settings(settings,*,now=None):
    now=time.time() if now is None else now
    mode=settings.auth_mode
    if mode not in {'auth0','dual','neon'}:raise AuthError('authentication configuration unavailable')
    try:
        trusts=[]
        if mode in {'auth0','dual'}:
            trusts.append(TrustConfig(settings.auth0_issuer,settings.auth0_audience,jwks_uri_for(settings.auth0_issuer or ''),('RS256',),('RSA',)))
        if mode in {'neon','dual'}:
            if settings.environment not in {'local','preview','production'}:raise ValueError('invalid environment')
            if any(value and value!='0' for name,value in os.environ.items() if name.startswith(('BUYEROS_NEON_FIXTURE','BUYEROS_NEON_TEST_'))):raise ValueError('fixture trust forbidden')
            actual=(settings.neon_issuer,settings.neon_audience,settings.neon_jwks_url)
            expected=(settings.neon_expected_issuer,settings.neon_expected_audience,settings.neon_expected_jwks_url)
            if actual!=expected or not all(exact(value) for value in actual):raise ValueError('missing exact target binding')
            for value in (settings.neon_issuer,settings.neon_jwks_url):
                if not endpoint(value) or not urlsplit(value).hostname.endswith('.neon.tech'):raise ValueError('invalid Neon target')
            trusts.append(TrustConfig(*actual,('EdDSA',),('OKP',)))
        if mode=='dual':
            value=settings.auth_migration_expires_at
            if not isinstance(value,str) or not re.fullmatch(r'[0-9]{1,12}',value) or int(value)<=now:raise ValueError('migration expired')
        if len({trust.issuer for trust in trusts})!=len(trusts):raise ValueError('duplicate issuer')
        return tuple(trusts)
    except (ValueError,TypeError,AttributeError) as error:
        raise AuthError('authentication configuration unavailable') from error

class TrustSetVerifier:
    def __init__(self,verifiers,*,expires_at=None,now=time.time):
        self._verifiers={verifier.issuer:verifier for verifier in verifiers}
        if not self._verifiers or len(self._verifiers)!=len(verifiers):raise ValueError('distinct explicit issuers required')
        self._expires_at=expires_at;self._now=now

    async def verify(self,token):
        if self._expires_at is not None and self._now()>=self._expires_at:raise AuthError('migration trust expired')
        if not isinstance(token,str) or not 0<len(token)<=16384:raise AuthError('malformed token')
        try:
            # Unverified issuer is only a lookup in this fixed allowlist. The
            # selected verifier still checks its signature and every claim.
            claims=jwt.decode(token,options={'verify_signature':False})
            issuer=claims.get('iss')
            verifier=self._verifiers.get(issuer) if isinstance(issuer,str) else None
        except jwt.PyJWTError as error:raise AuthError('malformed token') from error
        if verifier is None:raise AuthError('issuer not allowed')
        return await verifier.verify(token)
