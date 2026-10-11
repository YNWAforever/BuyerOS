"""Server-selected GET-only periodic delivery boundary; default selection closed."""
from buyeros_api.execution.engine import run_async
from buyeros_api.services import delivery_schedule as core
from buyeros_api.services.delivery_schedule import RetainedDeliverySchedule, RetainedDeliveryTarget, _require_schedule
from .config import get_settings
from .tasks import _with_engine as with_engine

def selected_retained_delivery_schedule() -> RetainedDeliverySchedule | None:
    """Owner-reviewed due targets/GET quota/lifecycle are not installed.

    Repeated GET is safe to reconcile; this does not authorize provider quota,
    free reads or scheduling the same reviewed batch indefinitely. The owner
    must select due work within the independently reviewed retained read scope.
    """
    return None



def run_retained_delivery_schedule_sync() -> dict:
    selected=selected_retained_delivery_schedule()
    if selected is None:
        return {'status':'unavailable','attempted':0,'results':[]}
    _require_schedule(selected)
    if not get_settings().reconciliation_enabled:
        return {'status':'paused','attempted':0,'results':[]}
    schedule=RetainedDeliverySchedule(selected.targets,selected.valid_until)
    async def body(engine):
        return await core.reconcile_retained_delivery_schedule(engine,schedule)
    return run_async(with_engine(body))
