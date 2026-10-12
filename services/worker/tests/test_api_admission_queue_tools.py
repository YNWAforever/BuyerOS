"""Counts must conserve the actual scoped SQL rows and terminal distribution."""
import copy
import pytest
from tests.test_api_admitted_mixed_tools import positive,validate


def test_final_workspace_distribution_matches_all_138_durable_outboxes():
    r=positive()
    assert [x['done'] for x in r['samples'][-1]['spaces']]==[30]+[12]*9
    assert sum(x['done'] for x in r['samples'][-1]['spaces'])==138
    assert validate(r)


@pytest.mark.parametrize('corruption',[
    'impossible_count','wrong_final_count','negative_time','float_time','boolean_time',
    'outside_capture','reversed_sql_window','missing_raw_row','foreign_raw_row','duplicate_raw_row',
    'wrong_raw_state','changed_creation','creation_after_read','premature_done','missing_final_rows',
    'missing_terminal_creation','capture_finishes_early'])
def test_impossible_queue_or_time_denominator_is_refused(corruption):
    r=copy.deepcopy(positive());s=r['samples'][-1]
    if corruption=='impossible_count':s['spaces'][0]['done']+=999999
    elif corruption=='wrong_final_count':s['spaces'][0]['done']=0
    elif corruption=='negative_time':r['samples'][0]['at_ns']=-1
    elif corruption=='float_time':s['at_ns']=6000.5
    elif corruption=='boolean_time':r['samples'][0]['at_ns']=True
    elif corruption=='outside_capture':s['at_ns']=7000
    elif corruption=='reversed_sql_window':s['sql_started_ns']=6001
    elif corruption=='missing_raw_row':s['outboxes'].pop()
    elif corruption=='foreign_raw_row':s['outboxes'][0]['id']='foreign'
    elif corruption=='duplicate_raw_row':s['outboxes'].append(copy.deepcopy(s['outboxes'][0]))
    elif corruption=='wrong_raw_state':s['outboxes'][0]['state']='ready'
    elif corruption=='changed_creation':s['outboxes'][0]['created_at']='2026-10-12T00:00:00+00:00'
    elif corruption=='creation_after_read':s['sql_observed_at']='2026-10-12T00:00:00+00:00'
    elif corruption=='premature_done':
        first=r['samples'][0];first['outboxes']=copy.deepcopy(s['outboxes']);first['spaces']=copy.deepcopy(s['spaces']);first['sql_observed_at']=s['sql_observed_at']
    elif corruption=='missing_final_rows':s['outboxes']=[]
    elif corruption=='missing_terminal_creation':del r['terminal'][0]['created_at']
    elif corruption=='capture_finishes_early':r['capture_finished_ns']=2000
    assert not validate(r)
