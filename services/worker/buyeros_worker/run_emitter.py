"""Run state transitions committed atomically with a run event (BO-016).

A handler calls :func:`emit_run_event` from inside its own transaction on the
tenant-scoped session. The ``search_runs`` status update and the ``run_events``
insert therefore either commit with the work or roll back with it; the sequence
is derived from the current maximum under a row lock so concurrent emitters for
one run cannot collide or reorder.
"""

import uuid

from sqlalchemy import func, select

from buyeros_api.db.runs import RunEvent, SearchRun
from buyeros_api.services.run_events import apply_event, next_sequence

from .run_lifecycle import transition_run


async def emit_run_event(session, run_id, event_type: str, *, transition: str | None = None, payload: dict | None = None) -> int:
    """Advance the run (if ``transition``) and append exactly one event.

    Returns the assigned sequence, or ``0`` when there is nothing to do (no
    session/run, unknown run, or a non-newer sequence). Never performs any
    external call.
    """
    if session is None or run_id is None:
        return 0
    run_key = run_id if isinstance(run_id, uuid.UUID) else uuid.UUID(str(run_id))

    result = await session.execute(select(SearchRun).where(SearchRun.id == run_key).with_for_update())
    run = result.scalar_one_or_none()
    if run is None:
        return 0

    last = (
        await session.execute(select(func.coalesce(func.max(RunEvent.sequence), 0)).where(RunEvent.run_id == run_key))
    ).scalar_one()
    sequence = next_sequence(int(last))
    if not apply_event(int(last), sequence):
        return 0

    if transition is not None:
        new_status = transition_run(run.status, transition)
        if new_status != run.status:
            run.status = new_status

    session.add(
        RunEvent(
            workspace_id=run.workspace_id,
            run_id=run_key,
            sequence=sequence,
            event_type=event_type,
            payload=payload or {},
        )
    )
    return sequence
