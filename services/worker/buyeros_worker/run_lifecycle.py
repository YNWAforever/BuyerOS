"""Legacy import compatibility; API owns this implementation."""
import sys
from buyeros_api.execution import run_lifecycle as _owner
sys.modules[__name__] = _owner
