"""Legacy import compatibility; API owns this implementation."""
import sys
from buyeros_api.execution import config as _owner
sys.modules[__name__] = _owner
