from datetime import datetime
from typing import Callable

from .leases import can_claim, lease_expiry


def select_ready(rows: list[dict], now: datetime, limit: int = 10) -> list[dict]:
    selected = [r for r in rows if can_claim(r.get("state", "free"), r.get("lease_expires_at"), now)]
    return selected[:limit]


async def claim_outbox_rows(session, owner: str, limit: int, now: datetime) -> list[dict]:
    """Claim ready outbox rows atomically, bumping the fencing generation."""
    from sqlalchemy import text

    result = await session.execute(
        text(
            """
            UPDATE outbox_events
               SET lease_owner = :owner,
                   lease_expires_at = :expires,
                   fencing_generation = fencing_generation + 1,
                   state = 'dispatched'
             WHERE id IN (
                   SELECT id FROM outbox_events
                    WHERE state = 'ready'
                       OR (state = 'dispatched' AND lease_expires_at <= :now)
                    ORDER BY created_at
                    LIMIT :limit
                    FOR UPDATE SKIP LOCKED
             )
         RETURNING id, intent_key, event_type, payload, fencing_generation
            """
        ),
        {"owner": owner, "expires": lease_expiry(now, 120), "now": now, "limit": limit},
    )
    return [dict(r._mapping) for r in result]


async def mark_dispatched(session, ids: list[int], now: datetime) -> None:
    from sqlalchemy import text

    if not ids:
        return
    await session.execute(text("UPDATE outbox_events SET dispatched_at = :now WHERE id = ANY(:ids)"), {"now": now, "ids": ids})


async def sweep_expired(session, now: datetime) -> list[int]:
    """Return ids of dispatched rows whose lease expired (re-claimable)."""
    from sqlalchemy import text

    result = await session.execute(
        text("SELECT id FROM outbox_events WHERE state = 'dispatched' AND lease_expires_at <= :now"),
        {"now": now},
    )
    return [r[0] for r in result]


async def dispatch_once(session, publish: Callable, owner: str, now: datetime, limit: int) -> list[str]:
    from buyeros_api.services.outbox_service import build_intent

    claimed = await claim_outbox_rows(session, owner, limit, now)
    published: list[str] = []
    for row in claimed:
        intent = build_intent(row["event_type"], row["payload"], 0)
        publish(intent, row)
        published.append(intent)
    await mark_dispatched(session, [row["id"] for row in claimed], now)
    return published
