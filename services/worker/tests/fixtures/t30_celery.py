"""Test-only Celery consumer for the disposable T30 research fixture."""
from __future__ import annotations

import os
from decimal import Decimal

from celery import Celery

from tests.test_discovery_runner_db import SearchFixture
from buyeros_worker.discovery_runner import DiscoveryBatch

celery_app = Celery("buyeros_t30_fixture", broker=os.environ["BUYEROS_BROKER_URL"])
celery_app.conf.update(task_ignore_result=True, task_acks_late=True,
                       worker_prefetch_multiplier=1, broker_connection_timeout=5)


class BrowserSearchFixture:
    """Clearly fictional, bounded search result for a disposable browser run."""
    test_only = True
    provider = "fixture"
    price_version = "fixture-price-v1"
    quoted_upper_bound = Decimal("0.100000")
    retention_seconds = 86400

    def __init__(self):
        self.accepted = {}

    async def search(self, query, *, market, language, limit, intent_key):
        assert market == "US" and language == "en" and 1 <= limit <= 300
        batch = DiscoveryBatch(
            hits=[{"url": "https://fixture.example.test/t30-industrial-buyer",
                   "legal_name": "T30 Fictional Industrial Buyer",
                   "registry_id": "US-T30-FIXTURE-001",
                   "excerpt": "Fictional distributor lists industrial sensors in a public catalog.",
                   "language": "en", "external_ref": "t30-fixture-buyer"}],
            charge=Decimal("0.050000"), billing_event_id=f"fixture-bill:{intent_key}",
        )
        self.accepted[intent_key] = batch
        return batch

    async def status(self, intent_key):
        return self.accepted.get(intent_key)


@celery_app.task(name="buyeros.execute_intent", acks_late=True)
def execute_fixture_intent(intent_key: str, workspace_id: str, generation: int) -> str:
    from buyeros_worker.tasks import execute_intent_sync

    browser = os.environ.get("BUYEROS_T30_GENERIC_SEARCH") == "1"
    adapter = BrowserSearchFixture() if browser else SearchFixture(os.environ["BUYEROS_TEST_OWNER_DSN"])
    return execute_intent_sync(intent_key, workspace_id, generation,
                               search_adapter=adapter, environment="test",
                               checkpoint_dsn=os.environ["BUYEROS_TEST_OWNER_DSN"] if browser else None)