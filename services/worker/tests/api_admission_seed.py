"""Seed synthetic retained liabilities only in a guarded owned database."""
import json,os
from pathlib import Path
from tests.controlled_policy_fixtures import owned_policy_gate
import psycopg
from tests.conftest import _require_disposable_test_dsn
from tests.test_contact_uncertainty_db import _setup


def main():
    dsn=os.environ['BUYEROS_TEST_DATABASE_URL'];_require_disposable_test_dsn(dsn)
    assert os.environ.get('BUYEROS_OWNED_API_ADMISSION')=='1'
    receipt=Path(os.environ['BUYEROS_POLICY_TARGET_RECEIPT'])
    owned_policy_gate().inspect_target(receipt)  # Independent child metadata gate before the first SQL client.
    job,_=_setup(dsn,count=2)
    with psycopg.connect(dsn) as db:
        ops=db.execute('SELECT id FROM provider_operations WHERE job_id=%s ORDER BY id',(job,)).fetchall()
        db.execute("UPDATE provider_operations SET status='unknown',provider_ref=NULL WHERE id=%s",(ops[0][0],))
        db.execute("UPDATE provider_operations SET status='accepted',provider_ref='fixture-retained-accepted' WHERE id=%s",(ops[1][0],))
        db.execute("UPDATE outbox_events SET state='done' WHERE intent_key=%s",('contact.lookup:'+str(job),))
    print(json.dumps({'job_id':str(job)}))


if __name__=='__main__':main()
