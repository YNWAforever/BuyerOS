"""Bounded signed-token cross-loop regression; no network or DB fixture."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event,Thread
import sys
import pytest
from buyeros_api.api.auth import AuthError
from buyeros_api.api.jwks import JwksKeyCache
from buyeros_api.api.verifier import TokenVerifier
from tests import auth_fixtures as fx

if sys.platform=='win32':asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

@pytest.mark.parametrize('response',['signed-success','outage','invalid-document'])
def test_signed_cold_requests_on_two_event_loops_finish_without_foreign_loop_wakeup(response):
    fetching=Event();release=Event();joined=Event();done=[Event(),Event()];loops={};results={};calls=[]
    async def fetch():
        calls.append(1);fetching.set()
        while not release.is_set():await asyncio.sleep(.002)
        if response=='outage':raise RuntimeError('fixture JWKS outage')
        return fx.jwks_document() if response=='signed-success' else {'keys':'invalid-fixture-list'}
    verifier=TokenVerifier(JwksKeyCache(fetch),issuer=fx.ISSUER,audience=fx.AUDIENCE)
    tokens=[fx.make_token(sub='auth0|cross-loop-first'),fx.make_token(sub='auth0|cross-loop-second')]
    async def verify(index):
        if index==1:asyncio.get_running_loop().call_soon(joined.set)
        try:results[index]=await verifier.verify(tokens[index])
        except BaseException as error:results[index]=error
        finally:done[index].set()
    def run(index):
        loop=asyncio.new_event_loop();loops[index]=loop
        try:loop.run_until_complete(verify(index))
        finally:loop.close()
    threads=[Thread(target=run,args=(i,),daemon=True) for i in range(2)]
    completed=False
    try:
        threads[0].start();assert fetching.wait(2),'owner did not reach controlled fetch'
        threads[1].start();assert joined.wait(2),'second real token did not yield on its own event loop'
        release.set();assert done[0].wait(2),'owner did not finish controlled fetch'
        completed=done[1].wait(.5)
    finally:
        release.set()
        # Wake only for bounded test cleanup, after recording whether production
        # cache completion itself woke the waiting event loop.
        for loop in list(loops.values()):
            if not loop.is_closed():loop.call_soon_threadsafe(lambda:None)
        for thread in threads:
            if thread.ident is not None:thread.join(2)
    assert all(not thread.is_alive() for thread in threads),'bounded cleanup did not finish'
    assert completed,'shared cold JWKS completion stranded the other event loop until external wakeup'
    assert len(calls)==1,'one cold request cohort must not cause duplicate fetches'
    if response=='signed-success':assert [results[i].subject for i in range(2)]==['auth0|cross-loop-first','auth0|cross-loop-second']
    else:assert all(isinstance(results[i],AuthError) for i in range(2)), 'failed fetch/document must fail signed requests closed'

def test_two_warm_signed_requests_keep_independent_subjects_without_refetch():
    calls=[]
    async def fetch():calls.append(1);return fx.jwks_document()
    verifier=TokenVerifier(JwksKeyCache(fetch),issuer=fx.ISSUER,audience=fx.AUDIENCE)
    asyncio.run(verifier.verify(fx.make_token(sub='auth0|warm-owner')))
    def run(subject):return asyncio.run(verifier.verify(fx.make_token(sub=subject))).subject
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,['auth0|warm-first','auth0|warm-second']))
    assert results==['auth0|warm-first','auth0|warm-second'] and len(calls)==1


def test_cancelling_one_waiter_does_not_cancel_original_fetch_or_other_signed_request():
    async def exercise():
        entered=asyncio.Event();release=asyncio.Event();calls=[]
        async def fetch():calls.append(1);entered.set();await release.wait();return fx.jwks_document()
        verifier=TokenVerifier(JwksKeyCache(fetch),issuer=fx.ISSUER,audience=fx.AUDIENCE)
        owner=asyncio.create_task(verifier.verify(fx.make_token(sub='auth0|cancel-owner')))
        await entered.wait()
        cancelled=asyncio.create_task(verifier.verify(fx.make_token(sub='auth0|cancel-waiter')))
        survivor=asyncio.create_task(verifier.verify(fx.make_token(sub='auth0|cancel-survivor')))
        await asyncio.sleep(0);cancelled.cancel()
        with pytest.raises(asyncio.CancelledError):await cancelled
        assert not owner.done() and not survivor.done()
        release.set();results=await asyncio.wait_for(asyncio.gather(owner,survivor),2)
        assert [value.subject for value in results]==['auth0|cancel-owner','auth0|cancel-survivor'] and len(calls)==1
    asyncio.run(exercise())


def test_cancelling_fetch_owner_finishes_other_signed_request_fail_closed_without_refetch():
    async def exercise():
        entered=asyncio.Event();never=asyncio.Event();calls=[]
        async def fetch():calls.append(1);entered.set();await never.wait();return fx.jwks_document()
        verifier=TokenVerifier(JwksKeyCache(fetch),issuer=fx.ISSUER,audience=fx.AUDIENCE)
        owner=asyncio.create_task(verifier.verify(fx.make_token(sub='auth0|cancel-fetch-owner')))
        await entered.wait()
        waiter=asyncio.create_task(verifier.verify(fx.make_token(sub='auth0|cancel-fetch-waiter')))
        await asyncio.sleep(0);owner.cancel()
        with pytest.raises(asyncio.CancelledError):await owner
        with pytest.raises(AuthError):await asyncio.wait_for(waiter,2)
        with pytest.raises(AuthError):await verifier.verify(fx.make_token(sub='auth0|after-owner-cancel'))
        assert len(calls)==1
    asyncio.run(exercise())
