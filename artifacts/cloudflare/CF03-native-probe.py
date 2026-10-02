"""Reviewed local frozen Linux API-only probe; no credential or provider access."""
import importlib.util
import json
import sys

from buyeros_api.execution import document_runner, fetch_runner, pdf_parser, step_runner
from buyeros_api.execution.handlers import draft_generate, retention
import langgraph.checkpoint.postgres

assert importlib.util.find_spec('buyeros_worker') is None
assert importlib.util.find_spec('celery') is None
assert importlib.util.find_spec('pytest') is None
assert not any(name.startswith(('celery', 'buyeros_worker')) for name in sys.modules)
sys.path.insert(0, '/app/services/api/tools')
from probe_worker_runtime import _pdf_probe

records = [{'check': 'frozen_api_only_import', 'state': 'verified',
            'details': {'worker_package': False, 'celery': False, 'development_dependencies': False}}]
_pdf_probe(records)
assert len(records) == 4 and all(row['state'] == 'verified' for row in records)
print(json.dumps({'environment': 'local_linux_api_only', 'deployed': False,
                  'counts': {'verified': 4, 'failed': 0}, 'records': records}))
