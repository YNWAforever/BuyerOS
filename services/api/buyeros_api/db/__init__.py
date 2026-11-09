"""Database layer (BO-005).

Importing this package registers every model on ``Base.metadata``. Mapper
configuration and Alembic autogenerate therefore always see the complete schema
(including ``worker_leases``), and a `select()` of one model can resolve its
foreign keys to tables declared in another module.
"""

from . import (  # noqa: F401
    budget,
    buyers,
    buyer_imports,
    contact,
    conversation_threads,
    sales_tasks,
    drafts,
    delivery,
    icp,
    ingestion,
    document_uploads,
    private_objects,
    models,
    lead_workflow,
    outcomes,
    outbox,
    policy,
    rate,
    runs,
    worker,
    worker_execution,
)

__all__ = [
    "budget",
    "buyers",
    "buyer_imports",
    "contact",
    "drafts",
    "delivery",
    "icp",
    "ingestion",
    "document_uploads",
    "private_objects",
    "models",
    "lead_workflow",
    "outcomes",
    "outbox",
    "policy",
    "rate",
    "runs",
    "worker",
    "worker_execution",
]

from . import sales_execution  # noqa: F401
from . import conversation_turns  # noqa: F401
from . import conversation_turn_events  # noqa: F401
from . import sales_accounting  # noqa: F401
from . import xverum  # noqa: F401
from . import xverum_enrichment  # noqa: F401
from .sales_outputs import SalesOutput, SalesOutputVersion, SalesOutputSection, SalesOutputDependency, SalesOutputNativeLink
