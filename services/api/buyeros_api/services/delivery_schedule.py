"""Canonical bounded retained GET batch; every original ledger remains intact.

Server scheduling chooses due targets and independently reviewed status quota.
This service creates no outbox/intent/reservation, performs no submit, and owns
no Celery dependency. Cancellation propagates; blocked rows remain visible.
"""
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from ..api.errors import ApiError
from .delivery_reconciliation import DeliveryReconciliationSelection, _require_selection, reconcile_delivery_status

@dataclass(frozen=True)
class RetainedDeliveryTarget:
    workspace_id: uuid.UUID
    message_id: uuid.UUID
    selection: DeliveryReconciliationSelection = field(repr=False)


@dataclass(frozen=True)
class RetainedDeliverySchedule:
    targets: tuple[RetainedDeliveryTarget, ...]
    valid_until: datetime

    def __post_init__(self):
        try:
            rows=tuple(self.targets)
            if not 1 <= len(rows) <= 100:
                raise ValueError()
            copied=[]
            for row in rows:
                if type(row) is not RetainedDeliveryTarget or type(row.message_id) is not uuid.UUID or not row.message_id.int:
                    raise ValueError()
                _require_selection(row.selection,row.workspace_id)
                copied.append(replace(row,selection=replace(row.selection,authority=replace(row.selection.authority))))
            if len({(row.workspace_id,row.message_id) for row in copied}) != len(copied):
                raise ValueError()
            object.__setattr__(self,'targets',tuple(copied))
            _require_schedule(self)
        except (TypeError, AttributeError):
            raise ValueError('invalid retained delivery schedule') from None


def _require_window(schedule):
    if type(schedule) is not RetainedDeliverySchedule:
        raise ApiError(503,'PROVIDER_UNAVAILABLE','reviewed retained delivery schedule unavailable')
    now=datetime.now(timezone.utc)
    if not isinstance(schedule.valid_until,datetime) or schedule.valid_until.utcoffset() is None or schedule.valid_until <= now:
        raise ApiError(503,'PROVIDER_UNAVAILABLE','reviewed retained delivery schedule unavailable')
    if not 1 <= len(schedule.targets) <= 100 or any(type(row) is not RetainedDeliveryTarget for row in schedule.targets):
        raise ApiError(503,'PROVIDER_UNAVAILABLE','reviewed retained delivery schedule unavailable')
    if len({(r.workspace_id,r.message_id) for r in schedule.targets}) != len(schedule.targets):
        raise ApiError(503,'PROVIDER_UNAVAILABLE','reviewed retained delivery schedule unavailable')


def _require_target(row, valid_until):
    if type(row.message_id) is not uuid.UUID or not row.message_id.int:
        raise ApiError(422,'INVALID_REQUEST','exact original message required')
    _require_selection(row.selection,row.workspace_id)
    if valid_until > row.selection.authority.valid_until:
        raise ApiError(503,'PROVIDER_UNAVAILABLE','reviewed retained delivery schedule unavailable')


def _require_schedule(schedule):
    _require_window(schedule)
    for row in schedule.targets:
        _require_target(row,schedule.valid_until)



async def reconcile_retained_delivery_schedule(engine, schedule: RetainedDeliverySchedule) -> dict:
    _require_schedule(schedule)
    results=[]
    for row in schedule.targets:
        try:
            # Recheck every selected binding at the actual boundary. One
            # slow GET cannot use expired authority for later batch rows.
            _require_window(schedule)
            _require_target(row,schedule.valid_until)
            receipt=await reconcile_delivery_status(engine,workspace_id=row.workspace_id,
                message_id=row.message_id,selection=row.selection)
            results.append({'message_id':str(receipt.message_id),'state':receipt.state,
                'event_id':str(receipt.event_id) if receipt.event_id else None,'replayed':receipt.replayed})
        except ApiError as error:
            results.append({'message_id':str(row.message_id),'code':error.code,'status_code':error.status_code})
        except Exception:
            # No provider exception strings/credentials; cancellation and
            # process exit propagate, with no automatic resubmission.
            results.append({'message_id':str(row.message_id),'code':'INTERNAL_ERROR','status_code':500})
    return {'status':'partial' if any('code' in row for row in results) else 'completed',
            'attempted':len(results),'results':results}
