"""Read-only reconciliation of turns whose execution outcome is unknown.

The probe reads only persisted evidence (the canonical sales task/output state
and content-free receipts). It never creates a stage, quote, receipt, budget
reservation or provider call; resolution is persisted by the turn service in
the same transaction that appends the reconcile continuation events.
"""
import hashlib
import json
from uuid import UUID

from sqlalchemy import select

from ..db.sales_tasks import SalesTask
from ..sales.turn_contracts import ReconcileResult


def evidence_digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


async def probe_outcome(session, scope, turn) -> ReconcileResult:
    """Resolve an unknown turn from what is already durable, never by calling out."""
    from ..db.conversation_turns import ConversationTurnProposal
    from ..db.sales_outputs import SalesOutput
    parts = turn.parts or []
    for part in parts:
        if not isinstance(part, dict) or part.get('kind') != 'tool_activity':
            continue
        call_id = part.get('call_id')
        if not call_id:
            continue
        try:
            proposal_id = UUID(str(call_id))
        except ValueError:
            continue
        proposal = (await session.execute(select(ConversationTurnProposal).where(
            ConversationTurnProposal.workspace_id == scope.workspace_id,
            ConversationTurnProposal.project_id == scope.project_id,
            ConversationTurnProposal.thread_id == turn.thread_id,
            ConversationTurnProposal.id == proposal_id))).scalar_one_or_none()
        result = (proposal.result or {}) if proposal is not None else {}
        task_id = result.get('task_id')
        if not task_id:
            continue
        try:
            task_uuid = UUID(str(task_id))
        except ValueError:
            continue
        task = (await session.execute(select(SalesTask).where(
            SalesTask.workspace_id == scope.workspace_id,
            SalesTask.project_id == scope.project_id,
            SalesTask.thread_id == turn.thread_id,
            SalesTask.id == task_uuid))).scalar_one_or_none()
        if task is None:
            continue
        if task.state == 'completed' and task.output_ids:
            try:
                output_uuid = UUID(str(task.output_ids[0]))
            except ValueError:
                output_uuid = None
            saved = (await session.execute(select(SalesOutput).where(
                SalesOutput.workspace_id == scope.workspace_id,
                SalesOutput.project_id == scope.project_id,
                SalesOutput.id == output_uuid))).scalar_one_or_none() if output_uuid else None
            if saved is not None:
                return ReconcileResult(outcome='completed', code='RECONCILED_COMPLETED',
                    message='The persisted execution completed; review the saved output revision.',
                    evidence_digest=evidence_digest({'task_id': str(task.id),
                        'state': 'completed', 'output_id': str(saved.id),
                        'output_revision': saved.revision}))
        kind = 'failed' if task.state in {'failed', 'cancelled'} else 'unknown'
        return ReconcileResult(outcome=kind,
            code='RECONCILED_FAILED' if kind == 'failed' else 'RECONCILE_NO_EVIDENCE',
            message='The persisted execution failed or was cancelled; no new dispatch was made.'
                if kind == 'failed' else
                'The persisted execution is not in a terminal state; it remains outcome_unknown.',
            evidence_digest=evidence_digest({'task_id': str(task.id), 'state': task.state}))
    return ReconcileResult(outcome='unknown', code='RECONCILE_NO_EVIDENCE',
        message='No authoritative persisted evidence resolves this turn; it remains outcome_unknown.',
        evidence_digest=evidence_digest({'turn_id': str(turn.id), 'evidence': 'none'}))
