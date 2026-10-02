"""Compatibility alias; sole implementation is buyeros_api.execution.fit_runner."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("buyeros_api.execution.fit_runner")
