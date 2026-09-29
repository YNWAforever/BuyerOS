"""Outbox dispatcher and recovery sweeper.

**RLS choice:** the dispatcher runs as a least-privilege, ``NOBYPASSRLS`` role,
so it cannot read any tenant's ``outbox_events`` without a workspace context. It
therefore enumerates tenants from ``workspaces`` (the tenant root, which is not
RLS-protected) and opens one transaction-local tenant context per workspace,
claiming within it. No tenant query ever runs without a context, and a claim
made under one workspace can never match another workspace's rows.

**Ordering:** a claim persists its lease and increments ``fencing_generation``
in one transaction *before* the broker publish. If the process dies between the
commit and the publish, the lease expires and the sweeper re-enqueues the row;
a publish that raises puts the row straight back to claimable. Duplicate
publishes are harmless because the worker only executes a non-terminal row whose
generation still matches.
"""

from collections.abc import Callable
from datetime import datetime
from time import monotonic

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from buyeros_api.db.models import Workspace
from buyeros_api.db.outbox import DISPATCHED_STATE, READY_STATE
from buyeros_api.db.session import tenant_session

from .config import get_settings
from .leases import lease_expiry

_CLAIM_COLUMNS = "id, workspace_id, intent_key, event_type, payload, fencing_generation"

# Terminal rows (done/failed) are deliberately absent: the predicate is an
# allow-list, so a terminal row can never be re-claimed or re-run.
_CLAIMABLE_PREDICATE = "state = 'ready' OR (state = 'dispatched' AND lease_expires_at <= :now)"
_EXPIRED_PREDICATE = "state = 'dispatched' AND lease_expires_at <= :now"


def claimable(state: str, lease_expires_at: datetime | None, now: datetime) -> bool:
    if state == READY_STATE:
        return True
    return state == DISPATCHED_STATE and lease_expires_at is not None and lease_expires_at <= now


def select_ready(rows: list[dict], now: datetime, limit: int = 10) -> list[dict]:
    selected = [r for r in rows if claimable(r.get("state", READY_STATE), r.get("lease_expires_at"), now)]
    return selected[:limit]


async def list_workspace_ids(session) -> list:
    from sqlalchemy import select

    return list((await session.execute(select(Workspace.id).order_by(Workspace.id))).scalars().all())


async def claim_outbox_rows(
    session, owner: str, limit: int, now: datetime, lease_seconds: int, *, expired_only: bool = False
) -> list[dict]:
    """Claim ready (or expired in-progress) rows, bumping the fencing generation."""
    predicate = _EXPIRED_PREDICATE if expired_only else _CLAIMABLE_PREDICATE
    result = await session.execute(
        text(
            f"""
            UPDATE outbox_events
               SET lease_owner = :owner,
                   lease_expires_at = :expires,
                   dispatched_at = :now,
                   attempts = attempts + 1,
                   fencing_generation = fencing_generation + 1,
                   state = 'dispatched'
             WHERE id IN (
                   SELECT id FROM outbox_events
                    WHERE ({predicate})
                      AND (:paid_dispatch_enabled OR event_type NOT IN
                           ('provider.external', 'run.discover', 'contact.lookup'))
                      AND (:reconciliation_enabled OR event_type NOT IN
                           ('provider.reconcile', 'research.reconcile', 'contact.reconcile'))
                    ORDER BY created_at
                    LIMIT :limit
                    FOR UPDATE SKIP LOCKED
             )
         RETURNING {_CLAIM_COLUMNS}
            """
        ),
        {"owner": owner, "expires": lease_expiry(now, lease_seconds), "now": now,
         "limit": limit, "paid_dispatch_enabled": get_settings().paid_dispatch_enabled,
         "reconciliation_enabled": get_settings().reconciliation_enabled},
    )
    return [dict(r._mapping) for r in result]


async def release_claim(session, intent_key: str) -> None:
    """Return a claimed row to the claimable pool (publish failure recovery)."""
    await session.execute(
        text(
            "UPDATE outbox_events SET state = 'ready', lease_owner = NULL, lease_expires_at = NULL"
            " WHERE intent_key = :key AND state = 'dispatched'"
        ),
        {"key": intent_key},
    )


async def _workspace_ids(engine) -> list:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        return await list_workspace_ids(session)


async def _dispatch_workspace(
    engine, workspace_id, publish: Callable, owner: str, now: datetime, limit: int, lease_seconds: int, *, expired_only: bool
) -> list[str]:
    async with tenant_session(engine, workspace_id) as session:
        claimed = await claim_outbox_rows(session, owner, limit, now, lease_seconds, expired_only=expired_only)
    # The claim above committed, so dispatch state is durable before the publish.
    published: list[str] = []
    for row in claimed:
        message = {
            "intent_key": row["intent_key"],
            "workspace_id": str(row["workspace_id"]),
            "generation": row["fencing_generation"],
        }
        try:
            publish(message)
        except Exception:
            async with tenant_session(engine, workspace_id) as session:
                await release_claim(session, row["intent_key"])
            raise
        published.append(row["intent_key"])
    return published


async def _fan_out(
    engine, publish: Callable, owner: str, now: datetime, limit: int, lease_seconds: int, *, expired_only: bool
) -> list[str]:
    published: list[str] = []
    for workspace_id in await _workspace_ids(engine):
        published.extend(
            await _dispatch_workspace(
                engine, workspace_id, publish, owner, now, limit, lease_seconds, expired_only=expired_only
            )
        )
    return published


async def dispatch_once(
    engine, publish: Callable, owner: str, now: datetime, limit: int = 10, lease_seconds: int = 120
) -> list[str]:
    """Claim and publish ready intents across all workspaces."""
    return await _fan_out(engine, publish, owner, now, limit, lease_seconds, expired_only=False)


async def sweep_once(
    engine, publish: Callable, owner: str, now: datetime, limit: int = 10, lease_seconds: int = 120
) -> list[str]:
    """Re-enqueue intents whose lease expired without a terminal state."""
    return await _fan_out(engine, publish, owner, now, limit, lease_seconds, expired_only=True)


async def dispatch_cycle(
    engine, publish: Callable, owner: str, now: datetime, *,
    max_total: int, time_budget_seconds: float, cursor: int = 0,
    lease_seconds: int = 120, expired_only: bool = False,
) -> dict:
    """Bound one cycle globally and rotate the first tenant on each invocation.

    The returned cursor is kept by the supervised process. A tenant with an
    empty queue cannot prevent later tenants from being visited.
    """
    if not 1 <= max_total <= 1000 or not 0 < time_budget_seconds <= 60:
        raise ValueError("dispatcher cycle requires bounded count and time")
    workspaces = await _workspace_ids(engine)
    if not workspaces:
        return {"published": [], "next_cursor": 0, "visited": 0}
    position = cursor % len(workspaces)
    published: list[str] = []
    visited = 0
    empty_streak = 0
    started = monotonic()
    while len(published) < max_total and empty_streak < len(workspaces):
        if monotonic() - started >= time_budget_seconds:
            break
        workspace_id = workspaces[position]
        batch = await _dispatch_workspace(
            engine, workspace_id, publish, owner, now, 1, lease_seconds,
            expired_only=expired_only,
        )
        published.extend(batch)
        visited += 1
        empty_streak = 0 if batch else empty_streak + 1
        position = (position + 1) % len(workspaces)
    return {"published": published, "next_cursor": position, "visited": visited}
