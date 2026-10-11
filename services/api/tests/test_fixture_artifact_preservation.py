"""Report hygiene only; mocked case is not a cold-restore protocol proof."""
from contextlib import contextmanager
import json
import pytest
from tests import cutover_fixtures, test_neon_cutover_db

@pytest.mark.parametrize('name,filename',[
 ('test_neon_cutover_rollback_preserves_new_users','C61-19-page-cold-compatible-api-rehearsal.json'),
 ('test_restore_replays_deletion_before_reopen','C61-19-page-cold-deletion-replay-rehearsal.json'),
])
def test_fixture_report_writer_preserves_existing_historical_bytes(monkeypatch,tmp_path,name,filename):
    # All protocol assertions still run; this synthetic object isolates report IO.
    case={'before':{'canonical_ids':['fixed-canonical-id'],'ledger_and_unknown':['unknown-hold'],'historical_fks':['fixed-fk']},
          'after':{'canonical_ids':['fixed-canonical-id'],'ledger_and_unknown':['unknown-hold'],'historical_fks':['fixed-fk']},
          'reopened':{'statuses':{'neon_only':200,'revoked':404},'ready':False},
          'closed_before':{'statuses':{'neon_only':503}},'closed_after':{'statuses':{'neon_only':503}},
          'tombstone_replayed':True,'unknown_holds_preserved':True,'old_epoch_fenced':True,
          'timeline':[{'step':s} for s in ['external_fixture_tombstone','restored_backup_still_closed',
              'tombstone_replayed_twice_and_ledger_reconciled_reads_still_closed',
              'local_reviewer_reopens_only_reads_with_compatible_neon_api_workers_unready']],
          'new_user':'excluded-test-only'}
    @contextmanager
    def stub(*args,**kwargs):
        yield case
    monkeypatch.setattr(cutover_fixtures,'cold_cutover',stub)
    monkeypatch.setattr(cutover_fixtures,'ROOT',tmp_path)
    historical=tmp_path/'artifacts/c61'/filename;historical.parent.mkdir(parents=True)
    sentinel=b'original dirty historical bytes\r\n';historical.write_bytes(sentinel)
    getattr(test_neon_cutover_db,name)(monkeypatch,tmp_path)
    assert historical.read_bytes()==sentinel
    reports=[p for p in historical.parent.rglob(filename) if p!=historical]
    assert len(reports)==1
    actual=json.loads(reports[0].read_text(encoding='utf-8'))
    assert actual=={k:v for k,v in case.items() if k!='new_user'}
