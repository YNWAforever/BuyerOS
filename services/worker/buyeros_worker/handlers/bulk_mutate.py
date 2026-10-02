"""Legacy import compatibility; API owns this implementation."""
import sys
from buyeros_api.execution import handlers as _owner
from buyeros_api.execution.handlers import bulk_mutate as _owner
sys.modules[__name__] = _owner
