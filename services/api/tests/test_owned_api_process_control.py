"""Hard crash must bypass graceful SIGTERM handlers on the original child PID."""
import json

from tests.owned_process_control import hard_stop_signal_handler_child
from tests.owned_api_evidence import record_property


def test_owned_hard_stop_kills_signal_handler_child_without_graceful_timeout(record_property):
    proof = hard_stop_signal_handler_child()
    assert proof['before']['sigterm_handler'] is True
    assert proof['before']['pid'] == proof['exit']['pid']
    assert proof['exit']['alive'] is False and proof['exit']['hard'] is True
    record_property('owned_evidence', json.dumps(proof, sort_keys=True))
