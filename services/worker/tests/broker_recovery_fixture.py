"""Owned-only Celery bootstrap: inject IO faults below the production executor.

No production class/config contains these barriers or this fixture adapter.
The registered production task and ACK path execute unchanged in a real worker.
"""
import asyncio
import json
import os
from pathlib import Path
import time
import uuid
from urllib.parse import urlsplit

from celery import current_task, signals


def record(folder, stage, **fields):
    event = dict(stage=stage, pid=os.getpid(), at_ns=time.monotonic_ns(), **fields)
    path = Path(folder) / 'events' / (uuid.uuid4().hex + '.tmp')
    with path.open('x', encoding='utf-8') as file:
        json.dump(event, file)
    path.rename(path.with_suffix('.json'))


def main():
    from tests.conftest import _require_disposable_test_dsn
    if os.environ.get('BUYEROS_OWNED_BROKER_FIXTURE') != '1':
        raise RuntimeError('owned fixture opt-in required')
    _require_disposable_test_dsn(os.environ['BUYEROS_DATABASE_URL'])
    broker = urlsplit(os.environ['BUYEROS_BROKER_URL'])
    if broker.hostname != '127.0.0.1' or broker.scheme != 'redis':
        raise RuntimeError('owned loopback broker required')
    folder = Path(os.environ['BUYEROS_BROKER_RECOVERY_CASE_DIR'])
    name = os.environ['BUYEROS_BROKER_RECOVERY_CASE']
    ordinal = int(os.environ['BUYEROS_BROKER_RECOVERY_WORKER'])
    if name not in ('redelivery','lease','unknown','accepted') or ordinal not in (1,2):
        raise RuntimeError('unknown owned case/worker')
    from buyeros_api.providers.base import FixtureProviderAdapter, StatusResult
    from tests.test_contact_uncertainty_db import _capability
    from buyeros_worker import tasks
    from buyeros_worker.app import celery_app
    from decimal import Decimal
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    class Store:
        async def delete_private(self, key):
            record(folder, 'delete', key=key)
            if ordinal == 1:
                while not (folder/'release-first').exists():
                    await asyncio.sleep(.1)

    class Adapter(FixtureProviderAdapter):
        async def submit(self, intent):
            result = await super().submit(intent)
            record(folder, 'submit', intent=intent.key, ref=result.provider_ref)
            if name == 'unknown':
                while True:
                    await asyncio.sleep(.1)
            if name == 'accepted' and ordinal == 1:
                while not (folder/'allow-provider-return').exists():
                    await asyncio.sleep(.1)
            return result

        async def status(self, ref):
            settled=(folder/'authoritative-status').exists()
            outcome='not_found' if settled else 'accepted'
            record(folder, 'status', ref=ref, outcome=outcome)
            return StatusResult(outcome, ref, Decimal('0.100000') if settled else None,
                                event_id='fixture-status-once' if settled else None)

    original = tasks.execute_intent_sync

    def execute(intent_key, workspace_id, generation):
        request=current_task.request
        fields=dict(intent=intent_key, generation=generation, task_id=request.id,
                    redelivered=bool(request.delivery_info.get('redelivered')))
        record(folder, 'started', **fields)
        result=original(intent_key, workspace_id, generation,
                        adapter=Adapter(_capability(),environment='test'),
                        private_store=Store(), environment='test')
        if name=='accepted' and ordinal==1:
            record(folder,'committed',outcome=result,**fields)
            while not (folder/'release-first').exists():
                time.sleep(.1)
        record(folder,'return',outcome=result,**fields)
        return result

    tasks.execute_intent_sync=execute
    # Owned time compression only; production broker visibility remains intact.
    celery_app.conf.broker_transport_options={'visibility_timeout':120 if name=='lease' else 2}
    def consumer_ready(sender, **kwargs):
        channel=sender.task_consumer.channel
        def observe():
            record(folder,'broker_scan',visibility_timeout=channel.visibility_timeout,
                   restore_count=channel.qos._vrestore_count)
        observe()
        sender.timer.call_repeatedly(5,observe)
    signals.worker_ready.connect(consumer_ready,weak=False)
    record(folder,'ready',ordinal=ordinal)
    celery_app.worker_main(['worker','--pool=solo','--concurrency=1','--loglevel=WARNING',
                           '--without-gossip','--without-mingle','--without-heartbeat',
                           '--hostname=owned-'+str(ordinal)+'@%h'])


if __name__=='__main__':
    main()
