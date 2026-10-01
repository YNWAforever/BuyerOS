"""Compatibility alias; implementation is owned by buyeros_api.execution.pdf_parser."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module("buyeros_api.execution.pdf_parser")
