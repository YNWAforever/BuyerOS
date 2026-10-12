"""Finite fixture driver; empty time-budget cycles keep their returned cursor."""
from time import monotonic
import math
import os
import sys
from pathlib import Path


class _OwnedRssUnavailableError(ValueError):
    """Missing Linux VmRSS requires a second authoritative owned-Popen check."""


def _process_rss(pid):
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)] + [(name,ctypes.c_size_t) for name in (
                'PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage',
                'QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
        memory=ctypes.WinDLL('psapi',use_last_error=True).GetProcessMemoryInfo
        memory.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD];memory.restype=wintypes.BOOL
        handle=kernel.OpenProcess(0x0400|0x0010,False,pid)
        if not handle:raise ctypes.WinError(ctypes.get_last_error())
        try:
            counters=Counters();counters.cb=ctypes.sizeof(counters)
            if not memory(handle,ctypes.byref(counters),counters.cb):raise ctypes.WinError(ctypes.get_last_error())
            return counters.WorkingSetSize,'windows_GetProcessMemoryInfo_WorkingSetSize'
        finally:kernel.CloseHandle(handle)
    if sys.platform.startswith('linux'):
        status=Path(f'/proc/{pid}/status').read_text().splitlines()
        if any(line.startswith('State:') and line.split()[1] in {'Z','X'} for line in status):
            # Kernel-confirmed exit is compatible with the caller's poll/OSError
            # race check; a live process without VmRSS still fails closed below.
            raise ProcessLookupError('owned process exited during RSS sampling')
        for line in status:
            if line.startswith('VmRSS:'):
                value,unit=line.split()[1:]
                if unit!='kB':raise ValueError('unexpected proc RSS unit')
                return int(value)*1024,'linux_proc_status_VmRSS'
        raise _OwnedRssUnavailableError('live process RSS unavailable')
    raise NotImplementedError('owned RSS capture supports Windows and Linux only')


def _owned_process_tree(pid):
    if os.name!='nt':return [(pid,None,0)]
    import ctypes
    from ctypes import wintypes
    class Entry(ctypes.Structure):
        _fields_=[('dwSize',wintypes.DWORD),('cntUsage',wintypes.DWORD),('th32ProcessID',wintypes.DWORD),
                  ('th32DefaultHeapID',ctypes.c_size_t),('th32ModuleID',wintypes.DWORD),('cntThreads',wintypes.DWORD),
                  ('th32ParentProcessID',wintypes.DWORD),('pcPriClassBase',wintypes.LONG),('dwFlags',wintypes.DWORD),
                  ('szExeFile',wintypes.WCHAR*260)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD];kernel.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    kernel.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)];kernel.Process32FirstW.restype=wintypes.BOOL
    kernel.Process32NextW.argtypes=kernel.Process32FirstW.argtypes;kernel.Process32NextW.restype=wintypes.BOOL
    kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
    handle=kernel.CreateToolhelp32Snapshot(2,0)
    if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    parents={}
    try:
        entry=Entry();entry.dwSize=ctypes.sizeof(entry)
        if not kernel.Process32FirstW(handle,ctypes.byref(entry)):raise ctypes.WinError(ctypes.get_last_error())
        while True:
            parents[entry.th32ProcessID]=entry.th32ParentProcessID
            if not kernel.Process32NextW(handle,ctypes.byref(entry)):
                if ctypes.get_last_error()!=18:raise ctypes.WinError(ctypes.get_last_error())
                break
    finally:kernel.CloseHandle(handle)
    if pid not in parents:raise ProcessLookupError('owned launcher exited during sampling')
    nodes=[(pid,None,0)]
    for parent,_,depth in nodes:
        for child,p in parents.items():
            if p==parent and child!=pid:
                if len(nodes)>=16 or depth>=4:raise ValueError('owned process tree exceeded capture bound')
                nodes.append((child,parent,depth+1))
    return nodes


def sample_worker_resources(processes,at_seconds,samples):
    """Read only the owned Popen children; a sample is not the all-time peak."""
    for process in processes:
        if process.poll() is None:
            for pid,parent,depth in _owned_process_tree(process.pid):
                try:
                    rss,method=_process_rss(pid)
                except _OwnedRssUnavailableError:
                    # The first poll and /proc read race with owned interpreter
                    # exit. Only its own reaped Popen proves that outcome; no
                    # missing live/descendant measurement or invalid unit passes.
                    if pid!=process.pid or process.poll() is None:raise
                    break
                samples.append(dict(owner_pid=process.pid,pid=pid,parent_pid=parent,depth=depth,at_seconds=at_seconds,rss_bytes=rss,method=method))


def resource_measurements_complete(report):
    """Refuse missing denominators and invalid units; does not adopt any SLO."""
    def nonnegative(value):
        return type(value) in (int,float) and math.isfinite(value) and value>=0
    samples=report.get('worker_resource_samples');pids=report.get('worker_pids')
    snapshots=report.get('backlog_snapshots');initial=report.get('initial_backlogs')
    if not all(isinstance(items,list) and items for items in (samples,pids,snapshots,initial)):return False
    if any(not isinstance(s,dict) or s.get('owner_pid') not in pids
           or type(s.get('pid')) is not int or s['pid']<=0
           or type(s.get('depth')) is not int or not 0<=s['depth']<=4
           or type(s.get('rss_bytes')) is not int or s['rss_bytes']<=0
           or not nonnegative(s.get('at_seconds'))
           or s.get('method') not in {'linux_proc_status_VmRSS','windows_GetProcessMemoryInfo_WorkingSetSize'} for s in samples):return False
    if {s['owner_pid'] for s in samples}!=set(pids):return False
    methods={s['method'] for s in samples}
    if len(methods)!=1:return False
    if methods=={'windows_GetProcessMemoryInfo_WorkingSetSize'} and any(
        not any(s['owner_pid']==pid and s['depth']>0 for s in samples) for pid in pids):return False
    groups={}
    for sample in samples:groups.setdefault((sample['owner_pid'],sample['at_seconds']),[]).append(sample)
    for (owner,_),rows in groups.items():
        indexed={row['pid']:row for row in rows}
        if len(rows)>16 or len(indexed)!=len(rows) or owner not in indexed:return False
        if indexed[owner]['parent_pid'] is not None or indexed[owner]['depth']!=0:return False
        for row in rows:
            if row['pid']==owner:continue
            parent=indexed.get(row.get('parent_pid'))
            if parent is None or row['depth']!=parent['depth']+1:return False
    if [s['at_seconds'] for s in samples]!=sorted(s['at_seconds'] for s in samples):return False
    if any(not isinstance(row,dict) or not isinstance(row.get('workspace'),str) or not row['workspace']
           or type(row.get('count')) is not int or row['count']<=0 for row in initial):return False
    expected={row['workspace']:row['count'] for row in initial}
    if len(expected)!=len(initial) or sum(expected.values())!=29:return False
    for snapshot in snapshots:
        if not isinstance(snapshot,dict) or not nonnegative(snapshot.get('at_seconds')):return False
        rows=snapshot.get('rows')
        if not isinstance(rows,list) or not rows:return False
        if any(not isinstance(row,dict) or row.get('workspace') not in expected
               or row.get('state') not in {'ready','dispatched','done'}
               or type(row.get('count')) is not int or row['count']<=0
               or not nonnegative(row.get('oldest_age_seconds')) for row in rows):return False
        pairs=[(row['workspace'],row['state']) for row in rows]
        if len(set(pairs))!=len(pairs):return False
        if {w:sum(row['count'] for row in rows if row['workspace']==w) for w in expected}!=expected:return False
    if len(snapshots)<2 or [s['at_seconds'] for s in snapshots]!=sorted(s['at_seconds'] for s in snapshots):return False
    if any(row['state']!='ready' for row in snapshots[0]['rows']):return False
    return all(row['state']=='done' for row in snapshots[-1]['rows'])

async def collect_bounded_backlog(dispatch,published,total,cursor,cycles,*,max_cycles):
    for _ in range(max_cycles):
        if len(published)>=total:return
        started=monotonic()
        result=await dispatch(cursor)
        result['wall_seconds']=monotonic()-started
        cycles.append(result);cursor=result['next_cursor']
    assert len(published)==total,'bounded backlog incomplete; all cycle evidence retained'
