"""Database layer (BO-005).

Importing this package registers every model on ``Base.metadata``. Mapper
configuration and Alembic autogenerate therefore always see the complete schema
(including ``worker_leases``), and a `select()` of one model can resolve its
foreign keys to tables declared in another module.
"""

from . import (  # noqa: F401
    budget,
    buyers,
    contact,
    drafts,
    icp,
    models,
    outcomes,
    outbox,
    policy,
    runs,
    worker,
)

__all__ = [
    "budget",
    "buyers",
    "contact",
    "drafts",
    "icp",
    "models",
    "outcomes",
    "outbox",
    "policy",
    "runs",
    "worker",
]
