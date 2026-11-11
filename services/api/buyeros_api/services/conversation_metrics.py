"""Bounded, tenant-scoped conversation turn metrics for dashboards.

Everything here is derived from persisted rows: turn statuses, per-turn event
timestamps, inline proposals/decisions and notices. No new table, no extra
producer and no provider call. The window is bounded (1..30 days) so a dashboard
read cannot scan unbounded history, and every query is scoped to the current
workspace + project under forced RLS.

User content is used only for aggregate counts: response bodies, thread text and
proposal arguments never leave this module.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select

from ..db.conversation_turn_events import ConversationTurnEvent
from ..db.conversation_turns import (ConversationTurn, ConversationTurnDecision,
    ConversationTurnProposal)
from ..sales.contracts import Scope

DEFAULT_WINDOW_DAYS = 7
MAX_WINDOW_DAYS = 30
# Dashboard labels never invent a model answer; this is the honest gap signal.
MODEL_UNAVAILABLE = 'CONVERSATION_MODEL_UNAVAILABLE'


def validate_window_days(value) -> int:
    if type(value) is not int or not 1 <= value <= MAX_WINDOW_DAYS:
        raise ValueError('window_days must be an integer 1..30')
    return value


def percentile(values, fraction: float) -> int | None:
    """Nearest-rank-free linear interpolation, rounded to whole milliseconds."""
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return int(round(ordered[0]))
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    value = ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
    return int(round(value))


def _latency_ms(started: datetime, finished: datetime) -> float | None:
    if started is None or finished is None or finished < started:
        return None
    return (finished - started).total_seconds() * 1000.0


def _amount(value) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return amount if amount.is_finite() else None


def _budget(proposal_rows) -> dict:
    estimated: dict[str, Decimal] = {}
    priced = unknown_price = no_cost = may_incur = 0
    for _capability, _status, _approval, cost in proposal_rows:
        if not isinstance(cost, dict):
            no_cost += 1
            continue
        known = cost.get('known', True)
        unit = cost.get('unit')
        amount = _amount(cost.get('amount'))
        if cost.get('may_incur_provider_charges') is True:
            may_incur += 1
        if known is False:
            unknown_price += 1
            continue
        priced += 1
        if unit in ('USD', 'credits') and amount is not None:
            estimated[unit] = estimated.get(unit, Decimal('0')) + amount
    return {
        'priced_proposals': priced,
        'unknown_price_proposals': unknown_price,
        'no_cost_proposals': no_cost,
        'may_incur_provider_charges': may_incur,
        'estimated': [{'unit': unit, 'amount': str(estimated[unit])}
                      for unit in ('credits', 'USD') if unit in estimated],
    }


async def turn_metrics(session, scope: Scope, *, window_days: int = DEFAULT_WINDOW_DAYS,
                       now: datetime | None = None) -> dict:
    """Aggregate this project's last ``window_days`` of conversation turns."""
    window_days = validate_window_days(window_days)
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)
    workspace_id, project_id = scope.workspace_id, scope.project_id

    window_turns = (select(ConversationTurnEvent.turn_id)
        .where(ConversationTurnEvent.workspace_id == workspace_id,
               ConversationTurnEvent.project_id == project_id,
               ConversationTurnEvent.created_at >= cutoff)
        .distinct())

    status_rows = (await session.execute(
        select(ConversationTurn.status, func.count())
        .where(ConversationTurn.workspace_id == workspace_id,
               ConversationTurn.project_id == project_id,
               ConversationTurn.id.in_(window_turns))
        .group_by(ConversationTurn.status))).all()
    by_status: dict[str, int] = {}
    for status, count in status_rows:
        by_status[str(status)] = int(count)
    total = sum(by_status.values())

    latency_rows = (await session.execute(
        select(
            ConversationTurnEvent.turn_id,
            func.min(ConversationTurnEvent.created_at).filter(
                ConversationTurnEvent.kind == 'turn.started'),
            func.max(ConversationTurnEvent.created_at).filter(
                ConversationTurnEvent.kind == 'turn.final'),
        )
        .where(ConversationTurnEvent.workspace_id == workspace_id,
               ConversationTurnEvent.project_id == project_id,
               ConversationTurnEvent.created_at >= cutoff)
        .group_by(ConversationTurnEvent.turn_id))).all()
    durations = [duration for started, finished in
                 ((row[1], row[2]) for row in latency_rows)
                 if (duration := _latency_ms(started, finished)) is not None]
    latency = {
        'samples': len(durations),
        'p50': percentile(durations, 0.50),
        'p95': percentile(durations, 0.95),
        'max': int(round(max(durations))) if durations else None,
    }

    proposal_rows = (await session.execute(
        select(ConversationTurnProposal.capability, ConversationTurnProposal.status,
               ConversationTurnProposal.requires_approval, ConversationTurnProposal.cost)
        .where(ConversationTurnProposal.workspace_id == workspace_id,
               ConversationTurnProposal.project_id == project_id,
               ConversationTurnProposal.turn_id.in_(window_turns)))).all()
    by_capability: dict[str, int] = {}
    for capability, _status, _approval, _cost in proposal_rows:
        by_capability[str(capability)] = by_capability.get(str(capability), 0) + 1

    decision_rows = (await session.execute(
        select(ConversationTurnDecision.decision, func.count())
        .where(ConversationTurnDecision.workspace_id == workspace_id,
               ConversationTurnDecision.project_id == project_id,
               ConversationTurnDecision.turn_id.in_(window_turns))
        .group_by(ConversationTurnDecision.decision))).all()
    by_decision = {str(decision): int(count) for decision, count in decision_rows}
    by_decision.setdefault('approve', 0)
    by_decision.setdefault('reject', 0)
    awaiting = len(proposal_rows) - by_decision['approve'] - by_decision['reject']

    tool_rows = (await session.execute(
        select(ConversationTurnEvent.payload['state'].astext, func.count())
        .where(ConversationTurnEvent.workspace_id == workspace_id,
               ConversationTurnEvent.project_id == project_id,
               ConversationTurnEvent.kind == 'tool',
               ConversationTurnEvent.created_at >= cutoff)
        .group_by(ConversationTurnEvent.payload['state'].astext))).all()
    tool_states = {str(state): int(count) for state, count in tool_rows if state is not None}

    notices_rows = (await session.execute(
        select(ConversationTurn.notices)
        .where(ConversationTurn.workspace_id == workspace_id,
               ConversationTurn.project_id == project_id,
               ConversationTurn.id.in_(window_turns)))).scalars().all()
    # Notices are short server-authored `{code, message}` rows; counting them in
    # Python keeps the query dialect-independent and never exposes their text.
    unavailable = sum(1 for notices in notices_rows
                      if isinstance(notices, list) and any(
                          isinstance(notice, dict) and notice.get('code') == MODEL_UNAVAILABLE
                          for notice in notices))

    return {
        'window_days': window_days,
        'generated_at': now.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'turns': {'total': total, 'by_status': by_status},
        'latency_ms': latency,
        'proposals': {
            'total': len(proposal_rows),
            'by_capability': by_capability,
            'by_decision': by_decision,
            'awaiting_decision': max(0, awaiting),
        },
        'tool_activity': {
            'by_state': tool_states,
            'outcome_unknown': tool_states.get('outcome_unknown', 0),
        },
        'model': {'unavailable_turns': int(unavailable)},
        'budget': _budget(proposal_rows),
    }
