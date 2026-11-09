"""Read-time decision decoration for persisted ``proposal`` parts.

The persisted decision row (``conversation_turn_decisions``) is surfaced on the
proposal part of the *response* only. Nothing here writes to a turn, message,
part or decision row, and no schema/column is added.

Containment: the lookup joins through ``conversation_turn_proposals`` and filters
the decision's own ``thread_id``/``turn_id`` to the proposal's persisted
thread/turn. Decorating additionally requires the containing message/turn id to
equal the decision's ``turn_id``, so a direct-DB mismatched row cannot decorate a
different thread that happens to hold the same proposal id.

Privacy: ``decided_by`` is deliberately a coarse label. The requesting actor is
compared server-side with the persisted decision actor and the response carries
only ``you`` or ``a workspace member`` -- never a user id, email, membership id,
correlation id or any other internal reference. Malformed/foreign decision data
degrades to "no decoration" rather than an error.
"""
from datetime import timezone
from uuid import UUID

from sqlalchemy import and_, select

from ..db.conversation_turns import (ConversationTurnDecision,
    ConversationTurnProposal)

DECIDED_BY_SELF = 'you'
DECIDED_BY_OTHER = 'a workspace member'
ALLOWED_DECISIONS = frozenset({'approve', 'reject'})


def coarse_actor_label(decision_actor_id, viewer_actor_id) -> str:
    """Coarse, privacy-preserving decision actor label for one viewer."""
    if decision_actor_id is None or viewer_actor_id is None:
        return DECIDED_BY_OTHER
    try:
        same = UUID(str(decision_actor_id)) == UUID(str(viewer_actor_id))
    except (ValueError, TypeError):
        same = str(decision_actor_id) == str(viewer_actor_id)
    return DECIDED_BY_SELF if same else DECIDED_BY_OTHER


def decision_payload(row, viewer_actor_id):
    """Bounded response payload, or None when the persisted row is unusable."""
    choice = getattr(row, 'decision', None)
    if choice not in ALLOWED_DECISIONS:
        # Server-side allowlist: never pass an unexpected stored value through.
        return None
    decided_at = getattr(row, 'created_at', None)
    if decided_at is None:
        return None
    if decided_at.tzinfo is None:
        decided_at = decided_at.replace(tzinfo=timezone.utc)
    return {'choice': choice, 'decided_at': decided_at.isoformat(),
        'decided_by': coarse_actor_label(getattr(row, 'actor_id', None),
            viewer_actor_id)}


async def decisions_for_proposals(session, workspace_id, project_id, thread_id,
                                  proposal_ids):
    """Decision rows for these proposals, contained by thread and proposal turn."""
    ids = []
    for value in proposal_ids:
        try:
            ids.append(UUID(str(value)))
        except (ValueError, TypeError):
            continue
    if not ids:
        return {}
    rows = (await session.execute(select(ConversationTurnDecision).join(
        ConversationTurnProposal,
        and_(ConversationTurnProposal.workspace_id == ConversationTurnDecision.workspace_id,
             ConversationTurnProposal.id == ConversationTurnDecision.proposal_id)).where(
        ConversationTurnDecision.workspace_id == workspace_id,
        ConversationTurnDecision.project_id == project_id,
        ConversationTurnDecision.thread_id == thread_id,
        ConversationTurnProposal.project_id == project_id,
        ConversationTurnProposal.thread_id == thread_id,
        ConversationTurnProposal.turn_id == ConversationTurnDecision.turn_id,
        ConversationTurnDecision.proposal_id.in_(ids)))).scalars().all()
    return {str(row.proposal_id): row for row in rows}


def _part_dicts(parts):
    return [dict(part) if isinstance(part, dict) else part.model_dump(mode='json')
        for part in parts or ()]


def _proposal_ids(parts):
    return [part.get('proposal_id') for part in parts
        if part.get('kind') == 'proposal' and part.get('proposal_id')]


def decorate_parts(parts, decisions, viewer_actor_id, *, turn_id):
    """Return new part dicts with a contained decision attached.

    The input part dicts are never mutated; stored parts remain untouched.
    Without a containing turn id no decoration is possible.
    """
    if turn_id is None:
        return _part_dicts(parts)
    expected_turn = str(turn_id)
    decorated = []
    for part in _part_dicts(parts):
        item = dict(part)
        if item.get('kind') == 'proposal':
            row = decisions.get(str(item.get('proposal_id')))
            if (row is not None
                    and str(getattr(row, 'turn_id', '')) == expected_turn):
                payload = decision_payload(row, viewer_actor_id)
                if payload is not None:
                    item['decision'] = payload
        decorated.append(item)
    return decorated


async def decorate_thread_payload(session, workspace_id, project_id, thread_id,
                                  payload, viewer_actor_id):
    messages = payload.get('messages')
    if not isinstance(messages, list):
        return payload
    all_parts = [part for message in messages for part in (message.get('parts') or ())]
    decisions = await decisions_for_proposals(session, workspace_id, project_id,
        thread_id, _proposal_ids(all_parts))
    if not decisions:
        return payload
    for message in messages:
        if message.get('parts'):
            message['parts'] = decorate_parts(message['parts'], decisions,
                viewer_actor_id, turn_id=message.get('turn_id'))
    return payload


async def decorate_turn_payload(session, workspace_id, project_id, thread_id,
                                turn_id, payload, viewer_actor_id):
    parts = _part_dicts(payload.get('parts') or ())
    decisions = await decisions_for_proposals(session, workspace_id, project_id,
        thread_id, _proposal_ids(parts))
    if decisions:
        payload['parts'] = decorate_parts(parts, decisions, viewer_actor_id,
            turn_id=turn_id)
    return payload
