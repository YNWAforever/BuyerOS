"""Private operational cluster: readiness transitions must not contaminate rollback fixtures."""
import psycopg
from tests.cloudflare_fixtures import cloudflare_database as migrated
from tests.contract_validation import assert_contract_response
from tests.test_buyer_review_db import ADMIN, VIEWER, WORKSPACE_A, _h, api
ROOT=f"/v1/workspaces/{WORKSPACE_A}"

def test_readiness_uses_observed_worker_heartbeat_not_environment_flag(api, seeded):
    from datetime import datetime, timedelta, timezone
    path=f"{ROOT}/readiness"
    with psycopg.connect(seeded,autocommit=True) as owner:
        from buyeros_api.services.worker_recovery import set_execution_runtime
        epoch=owner.execute('SELECT epoch FROM worker_runtime_control').fetchone()[0]
        # Guarded operator transitions only in this private owned module cluster.
        set_execution_runtime(seeded,expected_epoch=epoch,backend='celery',enabled=True,reason='Fictional readiness enable',apply=True)
        owner.execute("DELETE FROM worker_heartbeats")
        try:
            none=api.get(path,headers=_h(subject=ADMIN))
            assert none.status_code==200,none.text
            assert_contract_response("ReadinessResponse", none.json())
            assert none.json()['data']['database']=='ready'
            assert none.json()['data']['worker']=='unavailable'
            assert none.json()['data']['ready'] is False
            owner.execute("INSERT INTO worker_heartbeats(worker_id,observed_at,broker_state) VALUES (%s,%s,'ready')",
                          ('test-sweeper',datetime.now(timezone.utc)-timedelta(minutes=5)))
            stale=api.get(path,headers=_h(subject=ADMIN))
            assert stale.json()['data']['worker']=='stale'
            assert stale.json()['data']['queue']=='unavailable'
            owner.execute("UPDATE worker_heartbeats SET observed_at=%s WHERE worker_id='test-sweeper'",
                          (datetime.now(timezone.utc),))
            fresh=api.get(path,headers=_h(subject=ADMIN))
            assert fresh.json()['data']['worker']=='ready'
            assert fresh.json()['data']['queue']=='ready'
            assert fresh.json()['data']['ready'] is True
            assert api.get(path,headers=_h(subject=VIEWER)).status_code==403
        finally:
            owner.execute("DELETE FROM worker_heartbeats")
            set_execution_runtime(seeded,expected_epoch=epoch+1,backend='celery',enabled=False,reason='Fictional readiness pause',apply=True)


def test_paused_celery_selector_cannot_report_ready_from_a_fresh_legacy_heartbeat(api, seeded):
    from datetime import datetime, timezone
    with psycopg.connect(seeded, autocommit=True) as owner:
        assert owner.execute("SELECT backend,enabled FROM worker_runtime_control").fetchone() == ('celery',False)
        owner.execute("INSERT INTO worker_heartbeats(worker_id,observed_at,broker_state) VALUES('paused-fixture',%s,'ready')",(datetime.now(timezone.utc),))
        try:
            response=api.get(f"{ROOT}/readiness",headers=_h(subject=ADMIN))
            assert response.status_code==200,response.text
            assert_contract_response('ReadinessResponse',response.json())
            assert response.json()['data']['ready'] is False
            assert response.json()['data']['worker']=='unavailable'
            assert response.json()['data']['queue']=='unavailable'
        finally:
            owner.execute("DELETE FROM worker_heartbeats WHERE worker_id='paused-fixture'")
