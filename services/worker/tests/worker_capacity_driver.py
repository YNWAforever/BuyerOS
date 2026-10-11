"""Finite fixture driver; empty time-budget cycles keep their returned cursor."""
from time import monotonic

async def collect_bounded_backlog(dispatch,published,total,cursor,cycles,*,max_cycles):
    for _ in range(max_cycles):
        if len(published)>=total:return
        started=monotonic()
        result=await dispatch(cursor)
        result['wall_seconds']=monotonic()-started
        cycles.append(result);cursor=result['next_cursor']
    assert len(published)==total,'bounded backlog incomplete; all cycle evidence retained'
