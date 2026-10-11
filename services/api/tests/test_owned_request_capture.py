"""Owned measurement failures remain observations; no DB/provider traffic."""
import asyncio
import contextvars
import importlib
import httpx
import pytest
from tools.quality_metrics import summarize_requests

def capture():
    return importlib.import_module("tools.owned_request_capture").capture_http_request

def test_owned_capture_separates_concurrent_actor_sql_and_restores_outer_context():
    current=contextvars.ContextVar("test_capture",default=None)
    outer={"outer":True};current.set(outer)
    async def run():
        async def one(actor):
            async def call():
                await asyncio.sleep(0)
                row=current.get();row["queries"]+=actor+1;row["sql_ms"]+=actor+0.5
                return httpx.Response(200,json={"actor":actor})
            clock=iter([1.0,1.02]).__next__
            return await capture()(current,call,lambda response:response.json()=={"actor":actor},actor_index=actor,repetition=3,clock=clock)
        rows=await asyncio.gather(one(0),one(1))
        assert current.get() is outer
        return rows
    rows=asyncio.run(run());assert current.get() is outer
    assert [(r["actor_index"],r["queries"],r["sql_ms"]) for r in rows]==[(0,1,0.5),(1,2,1.5)]
    assert all(r["repetition"]==3 and r["status"]==200 and r["latency_ms"]==pytest.approx(20) and r["pool_wait_ms"] is None for r in rows)

@pytest.mark.parametrize("outcome",["503","429","timeout","wrong_scope","malformed"])
def test_owned_capture_keeps_non2xx_timeout_and_scope_failures(outcome):
    current=contextvars.ContextVar("test_fail",default=None)
    async def call():
        row=current.get();row["queries"]=2;row["sql_ms"]=3.0
        if outcome=="timeout":raise httpx.ReadTimeout("owned fixture timeout")
        if outcome=="malformed":return httpx.Response(200,content=b"not-json")
        return httpx.Response(int(outcome) if outcome.isdigit() else 200,json={"actor":1})
    row=asyncio.run(capture()(current,call,lambda response:response.json()=={"actor":0},actor_index=0,repetition=0,clock=iter([1,1.5]).__next__))
    assert current.get() is None and row["queries"]==2 and row["latency_ms"]==500
    summary=summarize_requests([row]);assert summary["errors"]["denominator"]==1 and summary["errors"]["failed_requests"]==1
    assert summary["pool_wait_ms"]["observed"]==0 and summary["pool_wait_ms"]["denominator"]==1
    if outcome=="timeout":assert row["status"] is None and row["transport_error"]=="ReadTimeout"
    elif outcome=="malformed":assert row["status"]==200 and row["invalid_context"] and row["validation_error"]=="JSONDecodeError"
    elif outcome in ("503","429"):assert row["status"]==int(outcome)
    else:assert row["status"]==200 and row["invalid_context"]

def test_owned_capture_preserves_measured_queue_and_unexpected_exception_restoration():
    current=contextvars.ContextVar("test_queue",default=None);outer={};current.set(outer)
    async def call():
        current.get().update(pool_wait_ms=7.5,pool_queue_gets=1)
        return httpx.Response(200,json={})
    row=asyncio.run(capture()(current,call,lambda r:True,actor_index=0,repetition=None,clock=iter([1,2]).__next__))
    assert row["pool_wait_ms"]==7.5 and row["pool_queue_gets"]==1 and current.get() is outer
    async def unexpected():raise RuntimeError("unexpected implementation failure")
    with pytest.raises(RuntimeError,match="unexpected implementation"):
        asyncio.run(capture()(current,unexpected,lambda r:True,actor_index=0,repetition=0))
    assert current.get() is outer

@pytest.mark.parametrize("end",[0.5,float("nan"),float("inf")])
def test_owned_capture_refuses_invalid_monotonic_measurement(end):
    current=contextvars.ContextVar("test_clock",default=None)
    async def call():return httpx.Response(200,json={})
    with pytest.raises(ValueError,match="monotonic"):
        asyncio.run(capture()(current,call,lambda r:True,actor_index=0,repetition=0,clock=iter([1,end]).__next__))
    assert current.get() is None
