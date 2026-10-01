"""Compatibility alias; implementation is owned by buyeros_api.execution.pdf_parser_child."""
import sys
from importlib import import_module

if __name__ == "__main__":
    raise SystemExit(import_module("buyeros_api.execution.pdf_parser_child").main())
sys.modules[__name__] = import_module("buyeros_api.execution.pdf_parser_child")
