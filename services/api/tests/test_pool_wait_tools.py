"""Owned opt-in queue timing, never latency-minus-SQL estimates."""
from types import SimpleNamespace
import pytest
from tools import quality_metrics as metrics

def probe():
    assert hasattr(metrics,'install_queue_wait_probe'), 'owned pool queue timing port missing'
    return metrics.install_queue_wait_probe

def test_owned_queue_wait_records_actual_queue_call_and_restores():
    sentinel=object();calls=[];queue=SimpleNamespace(get=lambda *a,**kw:calls.append((a,kw)) or sentinel);original=queue.get;row={};ticks=iter([1.0,1.125])
    restore=probe()(queue,lambda:row,lambda:next(ticks))
    assert queue.get(True,timeout=1) is sentinel
    assert calls==[((True,),{'timeout':1})] and row=={'pool_wait_ms':125.0,'pool_queue_gets':1}
    restore();assert queue.get is original

def test_owned_queue_wait_keeps_exception_and_failed_wait_in_denominator():
    error=TimeoutError('synthetic timeout');row={};ticks=iter([2.0,2.5])
    def get():raise error
    queue=SimpleNamespace(get=get);restore=probe()(queue,lambda:row,lambda:next(ticks))
    with pytest.raises(TimeoutError) as failed:queue.get()
    assert failed.value is error and row=={'pool_wait_ms':500.0,'pool_queue_gets':1};restore()

def test_owned_queue_wait_without_observation_is_plain_passthrough():
    queue=SimpleNamespace(get=lambda:'observed');restore=probe()(queue,lambda:None,lambda:pytest.fail('no inactive timer'))
    assert queue.get()=='observed';restore()

def test_owned_queue_restore_cannot_overwrite_another_patch():
    queue=SimpleNamespace(get=lambda:None);restore=probe()(queue,lambda:None);replacement=lambda:'retain';queue.get=replacement
    with pytest.raises(ValueError):restore()
    assert queue.get is replacement

def rows():return [dict(latency_ms=100.0,sql_ms=10.0,queries=4,bytes=100,status=200,invalid_context=False,pool_wait_ms=float(i),pool_queue_gets=2) for i in range(30)]

def test_pool_wait_summary_keeps_partial_and_unmeasured_denominators():
    observed=rows();report=metrics.summarize_requests(observed)['pool_wait_ms']
    assert report['complete'] and report['observed']==report['denominator']==30 and report['total']==435.0 and report['p95']==27.55 and report['queue_gets']==60
    observed[0]['pool_wait_ms']=None;report=metrics.summarize_requests(observed)['pool_wait_ms']
    assert not report['complete'] and report['observed']==29 and report['denominator']==30
    for row in observed:row.pop('pool_wait_ms')
    report=metrics.summarize_requests(observed)['pool_wait_ms'];assert not report['complete'] and report['observed']==0 and report['p95'] is None

@pytest.mark.parametrize('invalid',[True,-1.0,float('nan')])
def test_pool_wait_rejects_invalid_measurements(invalid):
    observed=rows();observed[0]['pool_wait_ms']=invalid
    with pytest.raises(ValueError):metrics.summarize_requests(observed)
