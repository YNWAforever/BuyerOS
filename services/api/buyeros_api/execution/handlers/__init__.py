"""Register shared local handlers without importing any broker transport."""
from . import bulk_mutate, capability_blocked, fetch_evidence  # noqa: F401
