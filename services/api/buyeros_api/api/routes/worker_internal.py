"""Five internal operations; not part of Auth0 staff role permissions."""
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.routing import APIRoute

from buyeros_api.services import worker_execution as service
from ..errors import ApiError
from ..worker_auth import MAX_BODY_BYTES, verify_worker_request
from ..worker_schemas import (ClaimBatch, ClaimRequest, StepOutcome, StepRequest,
                              PublicationRequest, MaintenanceRequest, MaintenanceResult)


class MachineRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()
        async def handle(request: Request):
            if request.scope.get("query_string"):
                raise ApiError(401, "UNAUTHORIZED", "worker query strings are not allowed")
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > MAX_BODY_BYTES:
                    raise ApiError(413, "INVALID_REQUEST", "worker request too large")
            request._body = bytes(body)
            now = datetime.now(timezone.utc)
            raw_path = request.scope.get("raw_path", request.url.path.encode()).decode("ascii")
            principal = verify_worker_request(request.method, raw_path, request._body, request.headers, now)
            engine = service.create_execution_engine()
            request.state.execution_engine = engine
            try:
                await service.consume_machine_nonce(engine, principal, now)
                response = await original(request)
                response.headers["Cache-Control"] = "private, no-store"
                return response
            finally:
                await engine.dispose()
        return handle


router = APIRouter(prefix="/v1/internal/worker", route_class=MachineRoute, tags=["worker-internal"])


@router.post("/claim", operation_id="workerClaim", response_model=ClaimBatch)
async def claim(body: ClaimRequest, request: Request):
    from buyeros_api.execution.dispatcher import claim_cycle
    return await claim_cycle(request.state.execution_engine, backend="cloudflare", epoch=body.runtime_epoch,
                             max_total=body.max_total, time_budget_seconds=body.time_budget_seconds)


@router.post("/step", operation_id="workerExecuteStep", response_model=StepOutcome)
async def step(body: StepRequest, request: Request):
    return await service.execute_step(request.state.execution_engine, body.envelope, body.step_key)


@router.post("/status", operation_id="workerStepStatus", response_model=StepOutcome)
async def status(body: StepRequest, request: Request):
    return await service.read_step_status(request.state.execution_engine, body.envelope, body.step_key)


@router.post("/publication", operation_id="workerRecordPublication", response_model=StepOutcome)
async def publication(body: PublicationRequest, request: Request):
    return await service.record_publication(request.state.execution_engine, body.envelope, body.state)


@router.post("/maintenance", operation_id="workerMaintenance", response_model=MaintenanceResult)
async def maintenance(body: MaintenanceRequest, request: Request):
    return await service.maintenance(request.state.execution_engine, body.runtime_epoch, probe_id=body.probe_id)
