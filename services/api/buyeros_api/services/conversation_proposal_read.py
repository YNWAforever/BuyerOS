"""Read-time decision decoration for persisted ``proposal`` parts.

The persisted decision row (``conversation_turn_decisions``) is surfaced on the
proposal part of the *response* only. Nothing here writes to a turn, message,
part or decision row, and no schema/column is added.

Privacy: ``decided_by`` is deliberately a coarse label. The requesting actor is
compared server-side with the persisted decision actor and the response carries
only ``you`` or ``a workspace member`` -- never a user id, email, membership id,
correlation id or any other internal reference.
"""
from datetime import timezone
from uuid import UUID

from sqlalchemy import select

from ..db.conversation_turns import ConversationTurnDecision

DECIDED_BY_SELF = 'you'
DECIDED_BY_OTHER = 'a workspace member'


def coarse_actor_label(decision_actor_id, viewer_actor_id) -> str:
    """Coarse, privacy-preserving decision actor label for one viewer."""
    if decision_actor_id is None or viewer_actor_id is None:
        return DECIDED_BY_OTHER
    try:
        same = UUID(str(decision_actor_id)) == UUID(str(viewer_actor_id))
    except ValueError:
        same = str(decision_actor_id) == str(viewer_actor_id)
    return DECIDED_BY_SELF if same else DECIDED_BY_OTHER


def decision_payload(row, viewer_actor_id) -> dict:
    decided_at = row.created_at
    if decided_at is not None and decided_at.tzinfo is None:
        decided_at = decided_at.replace(tzinfo=timezone.utc)
    return {'choice': row.decision,
        'decided_at': decided_at.isoformat() if decided_at is not None else '',
        'decided_by': coarse_actor_label(row.actor_id, viewer_actor_id)}


async def decisions_for_proposals(session, workspace_id, project_id, proposal_ids):
    ids = []
    for value in proposal_ids:
        try:
            ids.append(UUID(str(value)))
        except (ValueError, TypeError):
            continue
    if not ids:
        return {}
    rows = (await session.execute(select(ConversationTurnDecision).where(
        ConversationTurnDecision.workspace_id == workspace_id,
        ConversationTurnDecision.project_id == project_id,
        ConversationTurnDecision.proposal_id.in_(ids)))).scalars().all()
    return {str(row.proposal_id): row for row in rows}


def _part_dicts(parts):
    return [dict(part) if isinstance(part, dict) else part.model_dump(mode='json')
        for part in parts or ()]


def _proposal_ids(parts):
    return [part.get('proposal_id') for part in parts
        if part.get('kind') == 'proposal' and part.get('proposal_id')]


def decorate_parts(parts, decisions, viewer_actor_id):
    """Return new part dicts with a decision attached where one persists.

    The input part dicts are never mutated; stored parts remain untouched.
    """
    decorated = []
    for part in _part_dicts(parts):
        item = dict(part)
        if item.get('kind') == 'proposal':
            row = decisions.get(str(item.get('proposal_id')))
            if row is not None:
                item['decision'] = decision_payload(row, viewer_actor_id)
        decorated.append(item)
    return decorated


async def decorate_thread_payload(session, workspace_id, project_id, payload,
                                  viewer_actor_id):
    messages = payload.get('messages')
    if not isinstance(messages, list):
        return payload
    all_parts = [part for message in messages for part in (message.get('parts') or ())]
    decisions = await decisions_for_proposals(session, workspace_id, project_id,
        _proposal_ids(all_parts))
    if not decisions:
        return payload
    for message in messages:
        if message.get('parts'):
            message['parts'] = decorate_parts(message['parts'], decisions,
                viewer_actor_id)
    return payload


async def decorate_turn_payload(session, workspace_id, project_id, payload,
                                viewer_actor_id):
    parts = _part_dicts(payload.get('parts') or ())
    decisions = await decisions_for_proposals(session, workspace_id, project_id,
        _proposal_ids(parts))
    if decisions:
        payload['parts'] = decorate_parts(parts, decisions, viewer_actor_id)
    return payload
