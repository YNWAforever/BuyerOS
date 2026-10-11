"""Opt-in owned HTTP measurement; never discard expected request failures."""
import math
import time
import httpx

async def capture_http_request(current, call, validate, *, actor_index, repetition, clock=time.perf_counter, pool_measured=False):
    observation=dict(actor_index=actor_index,repetition=repetition,latency_ms=0.0,status=None,bytes=0,queries=0,sql_ms=0.0,invalid_context=False,pool_wait_ms=0.0 if pool_measured else None,pool_queue_gets=0)
    token=current.set(observation)
    try:
        started=clock()
        try:
            response=await call()
            observation.update(status=response.status_code,bytes=len(response.content))
            if 200<=response.status_code<300:
                try:
                    valid=validate(response)
                    if type(valid) is not bool:raise ValueError("validator must return bool")
                    observation["invalid_context"]=not valid
                except ValueError as exc:
                    observation.update(invalid_context=True,validation_error=type(exc).__name__)
        except httpx.HTTPError as exc:
            observation["transport_error"]=type(exc).__name__
        finally:
            elapsed=(clock()-started)*1000
            if not math.isfinite(elapsed) or elapsed<0:raise ValueError("invalid monotonic request timer")
            observation["latency_ms"]=elapsed
        return observation
    finally:
        current.reset(token)
