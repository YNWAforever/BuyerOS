"""Executing Windows descendants and their measured ancestry are required."""
import copy
import pytest
from tests.test_api_admitted_mixed_tools import positive,validate


def windows():
    r=positive()
    for w in r['workers']:w['tree_pids'].append(w['popen_pid']+100)
    for e in r['events']:e['pid']+=100
    for s in r['samples']:
        rows=[]
        for root in s['resources']:
            root['method']='windows_GetProcessMemoryInfo_WorkingSetSize'
            rows.append(root)
            rows.append(dict(owner_pid=root['pid'],pid=root['pid']+100,parent_pid=root['pid'],depth=1,rss_bytes=100000000,method=root['method']))
        s['resources']=rows
    return r


def test_executing_windows_descendants_and_linux_solo_are_valid():
    assert validate(windows())
    assert validate(positive())


@pytest.mark.parametrize('corruption',[
    'launcher_only','rebound_owner','duplicate_pid','root_parent','root_depth',
    'child_parent','child_depth','overlapping_trees','boolean_pid'])
def test_missing_or_rebound_executing_resource_is_refused(corruption):
    r=copy.deepcopy(windows())
    s=r['samples'][0]
    if corruption=='launcher_only':s['resources']=[x for x in s['resources'] if x['depth']==0]
    elif corruption=='rebound_owner':
        for x in s['resources']:x['owner_pid']=203-x['owner_pid']
    elif corruption=='duplicate_pid':s['resources'].append(copy.deepcopy(s['resources'][1]))
    elif corruption=='root_parent':s['resources'][0]['parent_pid']=102
    elif corruption=='root_depth':s['resources'][0]['depth']=1
    elif corruption=='child_parent':s['resources'][1]['parent_pid']=102
    elif corruption=='child_depth':s['resources'][1]['depth']=2
    elif corruption=='overlapping_trees':r['workers'][0]['tree_pids'].append(202)
    elif corruption=='boolean_pid':r['workers'][0]['tree_pids'].append(True)
    assert not validate(r)
