"""One native delivery attempt across closed tenant transactions.

No production selection or HTTP transport is installed. Server-owned callers
may supply a reviewed selection; the factory only binds the exact prepared
payload locally, and must perform no I/O. POST is never repeated, including
after rejection, cancellation, response loss or a failed receipt commit.
"""
from collections.abc import Callable
from dataclasses import dataclass,field

from ..api.errors import ApiError
from ..db.session import tenant_session
from ..providers.base import Money,SubmissionResult
from ..providers.delivery import DeliveryAdapter,validate_delivery_submission
from ..services.delivery_budget import DeliveryBudgetAuthorization
from ..services.delivery_post import claim_delivery_post
from ..services.delivery_response import DeliverySubmissionReceipt,record_delivery_submission
from ..services.delivery_service import PreparedDelivery
from ..services.delivery_status import DeliveryStatusAuthority,_require_status_authority
from ..services.delivery_submission import claim_delivery_submission,_require_dispatch_flags,_require_submit_authority
from .step_runner import LocalExecution


@dataclass(frozen=True)
class DeliverySelection:
    """Private reviewed binding, never deserialize this from worker/HTTP JSON.

    The factory must bind submit to the passed immutable prepared payload and
    the selected provider/account. It must not resolve client text, submit,
    fetch status, create a hold or perform another external operation.
    """
    authorization:DeliveryBudgetAuthorization
    reconciliation:DeliveryStatusAuthority
    adapter_factory:Callable[[PreparedDelivery],DeliveryAdapter]=field(repr=False)


def _require_selection(selection):
    if type(selection) is not DeliverySelection:
        raise ApiError(503,'PROVIDER_UNAVAILABLE','reviewed delivery selection unavailable')
    _require_submit_authority(selection.authorization)
    _require_status_authority(selection.reconciliation)
    auth,status=selection.authorization,selection.reconciliation
    if (not callable(selection.adapter_factory)
            or any(getattr(auth,key)!=getattr(status,key) for key in
                   ('workspace_id','provider_name','account_reference','scope_hash','reviewed_contract_hash'))):
        raise ApiError(503,'PROVIDER_UNAVAILABLE','original delivery selection binding unavailable')


def _bound_adapter(selection,prepared):
    try:
        adapter=selection.adapter_factory(prepared)
        if any(not callable(getattr(adapter,key,None)) for key in ('estimate','submit','status')):
            raise ValueError()
        # Delivery is independent of the common search/model/contact capability.
        if getattr(adapter,'capability',None) is not None:
            raise ValueError()
        quote=adapter.estimate(prepared.intent)
        if type(quote) is not Money:
            raise ValueError()
        quote.__post_init__()
        if quote.currency!=selection.authorization.currency or not 0<quote.amount<=selection.authorization.upper_bound:
            raise ValueError()
        return adapter
    except Exception:
        # No provider exception, credential, body or recipient enters the log.
        raise ApiError(503,'PROVIDER_UNAVAILABLE','bounded delivery adapter unavailable') from None


async def submit_delivery_claimed(engine,execution:LocalExecution,*,selection:DeliverySelection|None=None)->DeliverySubmissionReceipt:
    _require_selection(selection)
    _require_dispatch_flags()
    if type(execution) is not LocalExecution:
        raise ApiError(422,'INVALID_REQUEST','native delivery execution required')
    auth=selection.authorization
    if execution.envelope.workspace_id!=auth.workspace_id:
        raise ApiError(409,'IDEMPOTENCY_CONFLICT','original delivery workspace differs')

    async with tenant_session(engine,auth.workspace_id) as session:
        claim=await claim_delivery_submission(session,execution=execution,authorization=auth)
    # The first claim is committed and its session closed before factory work.
    # Any slow factory/estimate is followed by a fresh current permission/fence
    # check, never by a cached approval or a lock held over network I/O.
    adapter=_bound_adapter(selection,claim.prepared)
    _require_selection(selection)
    async with tenant_session(engine,auth.workspace_id) as session:
        permit=await claim_delivery_post(session,execution=execution,claim=claim,authorization=auth)
    # Permanent unknown + full original liability is visible before POST.
    # An uncertain or failed commit above never reaches the external await.
    _require_selection(selection)
    _require_dispatch_flags()
    try:
        result=await adapter.submit(permit.prepared.intent)
        validate_delivery_submission(result)
    except Exception:
        result=SubmissionResult('unknown',None)
    # CancelledError/SystemExit are not swallowed. Their committed permanent
    # permit remains unknown; a subsequent execution cannot acquire another.
    # Current admission/role/lease revocation does not erase a received result.
    async with tenant_session(engine,auth.workspace_id) as session:
        return await record_delivery_submission(session,permit=permit,result=result,
                                                authority=selection.reconciliation)


def selected_delivery_runtime(execution:LocalExecution)->DeliverySelection|None:
    """No actual provider/account/sender selection is installed.

    No HTTP/worker field, fixture or common contact capability may activate this
    selector. A separately reviewed production delivery factory is still needed.
    """
    return None


async def execute_delivery_claimed(engine,execution:LocalExecution):
    """Native receipt wrapper; received acceptance remains reconciliation.

    Original response persistence precedes the final native fence. Losing that
    fence changes the worker outcome without deleting a received provider ref.
    """
    from ..services.worker_execution import outcome
    selection=selected_delivery_runtime(execution)
    if selection is None:
        # Preserve the existing closed registered handler/worker outcome. No
        # provider factory is constructed when the actual selection is absent.
        from .domain_executor import run_intent
        async with tenant_session(engine,execution.envelope.workspace_id) as session:
            if not await execution.guard(session):return outcome('stale','STALE_FENCE')
            await run_intent(session,{'workspace_id':str(execution.envelope.workspace_id)},
                             execution.row.intent_key,execution.envelope.generation)
            result=outcome('blocked','CAPABILITY_UNAVAILABLE')
            execution.finish(result)
            return result
    try:
        await submit_delivery_claimed(engine,execution,selection=selection)
        # Accepted is not delivered or settled; unknown/rejected is not proof
        # of no charge. No new key/hold/permit is scheduled from this outcome.
        result=outcome('reconcile','PROVIDER_UNKNOWN')
    except ApiError as error:
        if error.code=='STALE_FENCE':return outcome('stale','STALE_FENCE')
        if error.code=='RETRY_UNSAFE':result=outcome('reconcile','PROVIDER_UNKNOWN')
        else:
            code=('EXECUTION_DISABLED' if error.code=='CAPABILITY_DISABLED' else
                  'CAPABILITY_UNAVAILABLE' if error.code=='PROVIDER_UNAVAILABLE' else
                  'ACTOR_CHANGED' if error.code=='PERMISSION_DENIED' else
                  'POLICY_CHANGED' if error.code in {'POLICY_BLOCKED','STALE_REVISION'} else 'INVALID_INTENT')
            result=outcome('blocked',code)
    async with tenant_session(engine,execution.envelope.workspace_id) as session:
        if not await execution.guard(session):return outcome('stale','STALE_FENCE')
        execution.finish(result)
        return result
