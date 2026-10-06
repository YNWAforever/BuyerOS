"""C61-02 valid concurrent tokens share one actual cold-key fetch, fail closed."""
import asyncio
from buyeros_api.api.jwks import JwksKeyCache,JwksError
from buyeros_api.api.verifier import TokenVerifier
from buyeros_api.api.auth import AuthError
from tests import auth_fixtures as fx


def test_valid_parallel_signed_tokens_wait_for_same_cold_jwks_fetch():
    async def exercise():
        tokens=[fx.make_token(sub='cold-a'),fx.make_token(sub='cold-b')]
        started,release=asyncio.Event(),asyncio.Event();calls=0
        async def fetch():
            nonlocal calls
            calls+=1;started.set();await release.wait();return fx.jwks_document()
        verifier=TokenVerifier(JwksKeyCache(fetch),issuer=fx.ISSUER,audience=fx.AUDIENCE)
        first=asyncio.create_task(verifier.verify(tokens[0]));await started.wait()
        second=asyncio.create_task(verifier.verify(tokens[1]));await asyncio.sleep(0)
        try:
            assert not second.done(),'valid concurrent token rejected while its only JWKS fetch is pending'
        finally:
            release.set();results=await asyncio.gather(first,second,return_exceptions=True)
        assert calls==1 and [r.subject for r in results]==['cold-a','cold-b']
    asyncio.run(exercise())


def test_cold_fetch_outage_rejects_all_waiters_without_refetch_or_trust_fallback():
    async def exercise():
        started,release=asyncio.Event(),asyncio.Event();calls=0
        async def fetch():
            nonlocal calls
            calls+=1;started.set();await release.wait();raise RuntimeError('controlled offline fetch failure')
        cache=JwksKeyCache(fetch)
        first=asyncio.create_task(cache.get_key('fixture'));await started.wait()
        second=asyncio.create_task(cache.get_key('fixture'));await asyncio.sleep(0)
        release.set();results=await asyncio.gather(first,second,return_exceptions=True)
        assert all(isinstance(result,JwksError) for result in results) and calls==1
        try:await cache.get_key('fixture')
        except JwksError:pass
        else:raise AssertionError('outage must stay fail closed')
        assert calls==1
    asyncio.run(exercise())
