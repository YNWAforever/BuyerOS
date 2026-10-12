"""Owned-only observation below the unchanged registered Celery task."""
import os
from pathlib import Path
from urllib.parse import urlsplit

from celery import current_task, signals
from tests.broker_recovery_fixture import record


def main():
    from tests.conftest import _require_disposable_test_dsn
    if os.environ.get('BUYEROS_OWNED_MIXED_FIXTURE') != '1':
        raise RuntimeError('owned mixed fixture opt-in required')
    _require_disposable_test_dsn(os.environ['BUYEROS_DATABASE_URL'])
    broker = urlsplit(os.environ['BUYEROS_BROKER_URL'])
    if broker.hostname != '127.0.0.1' or broker.scheme != 'redis':
        raise RuntimeError('owned loopback broker required')
    folder = Path(os.environ['BUYEROS_MIXED_OUTPUT'])
    from buyeros_worker import tasks
    from buyeros_worker.app import celery_app
    from buyeros_worker.config import get_settings
    original = tasks.execute_intent_sync

    class RefuseProvider:
        async def submit(self, *args, **kwargs):
            record(folder, 'forbidden_provider_call', method='submit')
            raise AssertionError('mixed nonpaid workload must not submit')

        async def status(self, *args, **kwargs):
            record(folder, 'forbidden_provider_call', method='status')
            raise AssertionError('retained liabilities are read-only in this workload')

    class Store:
        async def delete_private(self, key):
            record(folder, 'fixture_private_delete', key=key, task_id=current_task.request.id)

    def execute(intent_key, workspace_id, generation):
        assert get_settings().paid_dispatch_enabled is False
        fields = dict(intent=intent_key, workspace=workspace_id, generation=generation,
                      task_id=current_task.request.id)
        record(folder, 'started', **fields)
        outcome = original(intent_key, workspace_id, generation, adapter=RefuseProvider(),
                           private_store=Store(), environment='production')
        record(folder, 'return', outcome=outcome, **fields)
        return outcome

    tasks.execute_intent_sync = execute

    def ready(sender, **kwargs):
        record(folder, 'ready', ordinal=int(os.environ['BUYEROS_MIXED_WORKER']))

    signals.worker_ready.connect(ready, weak=False)
    celery_app.worker_main(['worker', '--pool=solo', '--concurrency=1', '--loglevel=WARNING',
                           '--without-gossip', '--without-mingle', '--without-heartbeat',
                           '--hostname=mixed-'+os.environ['BUYEROS_MIXED_WORKER']+'@%h'])


if __name__ == '__main__':
    main()
